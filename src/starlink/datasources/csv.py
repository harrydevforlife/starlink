from typing import Iterator, List, Optional, Sequence

import csv as stdlib_csv

import pyarrow as pa
import pyarrow.csv as pacsv

from starlink.datasources.datasource import DataSource
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Field, Schema
from starlink.physicalplan.expressions.expr import Expression


class CsvDataSource(DataSource):
    def __init__(self, filename: str, schema: Optional[Schema], has_headers: bool, batch_size: int):
        self.filename = filename
        self._provided_schema = schema
        self.has_headers = has_headers
        self.batch_size = batch_size
        self._final_schema: Optional[Schema] = None
        self._cached_delimiter: Optional[str] = None  # Cache delimiter detection result

    def _get_final_schema(self) -> Schema:
        if self._final_schema is None:
            self._final_schema = self._provided_schema or self._infer_schema()
        return self._final_schema

    def schema(self) -> Schema:
        return self._get_final_schema()

    def scan(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        """Scan CSV file using PyArrow CSV reader.

        Uses PyArrow's efficient CSV reading with support for:
        - Projection (column selection)
        - Filter pushdown (predicate pushdown) - filters rows during reading
        - Batching (controlled batch size)
        - Headers/no headers
        - Automatic delimiter detection
        """
        # Get full schema (we need to read all columns, then project)
        full_schema = self._get_final_schema()

        # Determine output schema (projected schema)
        if not projection:
            output_schema = full_schema
        else:
            # Select fields in the order specified by projection (not original schema order)
            # This matches the behavior in Scan._deriveSchema() and ScanExec.schema()
            fields = []
            for name in projection:
                for field in full_schema.fields:
                    if field.name == name:
                        fields.append(field)
                        break
            output_schema = Schema(fields)

        def generator() -> Iterator[RecordBatch]:
            # Configure PyArrow CSV read options
            # Always use full schema for reading (PyArrow needs all columns)
            read_options = None
            if not self.has_headers:
                # If no headers, provide column names from full schema
                # This ensures PyArrow uses our field_N naming convention
                read_options = pacsv.ReadOptions(
                    column_names=[f.name for f in full_schema.fields]
                )

            # Parse options: detect delimiter (PyArrow auto-detect doesn't work well for TSV)
            delimiter = self._detect_delimiter()
            parse_options = pacsv.ParseOptions(
                delimiter=delimiter,
                escape_char=None,
                quote_char='"',
                double_quote=True,
                newlines_in_values=False,
                ignore_empty_lines=True,
            )

        # Convert options: treat all columns as strings
            # Optimization: If projection is specified, use include_columns to only read needed columns
            # This reduces I/O and memory by avoiding reading unnecessary columns from disk
            if projection:
                # Only specify column types for projected columns (reduces overhead)
                column_types = {name: pa.string() for name in projection}
                convert_options = pacsv.ConvertOptions(
                    include_columns=projection,  # Only read projected columns (early projection)
                    column_types=column_types,
                    strings_can_be_null=True,
                    null_values=[""],  # Empty strings become null
                    include_missing_columns=False,  # Don't include columns not in projection
                )
            else:
                # No projection: read all columns
                column_types = {f.name: pa.string() for f in full_schema.fields}
                convert_options = pacsv.ConvertOptions(
                    column_types=column_types,
                    strings_can_be_null=True,
                    null_values=[""],  # Empty strings become null
                )

            # Open CSV file for streaming
            reader = pacsv.open_csv(
                self.filename,
                read_options=read_options,
                parse_options=parse_options,
                convert_options=convert_options,
            )

            # Accumulate arrays per column to reach desired batch size
            # This avoids Table conversion overhead by working directly with arrays
            num_cols = len(output_schema.fields)
            accumulated_arrays = [[] for _ in range(num_cols)]
            accumulated_row_count = 0

            # Create PyArrow schema for RecordBatch creation
            pa_schema = pa.schema([
                pa.field(f.name, f.dataType)
                for f in output_schema.fields
            ])

            for pyarrow_batch in reader:
                # Projection is already applied at reader level via include_columns
                # No need to call batch.select() - PyArrow already returned only projected columns
                # This reduces I/O and memory overhead

                # Accumulate arrays per column (more efficient than accumulating batches)
                for col_idx in range(num_cols):
                    accumulated_arrays[col_idx].append(pyarrow_batch.columns[col_idx])

                accumulated_row_count += len(pyarrow_batch)

                # Yield batches when we reach desired size
                if accumulated_row_count >= self.batch_size:
                    # Concatenate arrays for each column (avoids Table conversion)
                    concat_arrays = [
                        pa.concat_arrays(accumulated_arrays[col_idx])
                        for col_idx in range(num_cols)
                    ]

                    # Split into batches of batch_size by slicing arrays directly
                    for i in range(0, accumulated_row_count, self.batch_size):
                        end_idx = min(i + self.batch_size, accumulated_row_count)
                        length = end_idx - i

                        # Slice arrays directly (more efficient than slicing Table)
                        sliced_arrays = [
                            concat_arrays[col_idx].slice(i, length)
                            for col_idx in range(num_cols)
                        ]

                        # Create RecordBatch directly from sliced arrays
                        # This avoids Table → batch conversion overhead
                        batch = pa.RecordBatch.from_arrays(sliced_arrays, schema=pa_schema)

                        # Convert PyArrow RecordBatch to our RecordBatch
                        # Use output_schema to ensure correct field order
                        vectors = [ArrowFieldVector(col) for col in batch.columns]
                        record_batch = RecordBatch(output_schema, vectors)
                        
                        # Apply filter pushdown if filter is provided
                        if filter is not None:
                            record_batch = self._apply_filter(record_batch, filter, full_schema)
                            # Skip empty batches after filtering
                            if record_batch.row_count() == 0:
                                continue
                        
                        yield record_batch

                    # Reset accumulation
                    accumulated_arrays = [[] for _ in range(num_cols)]
                    accumulated_row_count = 0

            # Yield remaining rows using array concatenation
            if accumulated_arrays[0]:  # Check if any arrays were accumulated
                # Concatenate remaining arrays for each column
                concat_arrays = [
                    pa.concat_arrays(accumulated_arrays[col_idx])
                    for col_idx in range(num_cols)
                ]

                # Create RecordBatch directly from concatenated arrays
                # No slicing needed for remaining rows
                batch = pa.RecordBatch.from_arrays(concat_arrays, schema=pa_schema)
                vectors = [ArrowFieldVector(col) for col in batch.columns]
                record_batch = RecordBatch(output_schema, vectors)
                
                # Apply filter pushdown if filter is provided
                if filter is not None:
                    record_batch = self._apply_filter(record_batch, filter, full_schema)
                    # Skip empty batches after filtering
                    if record_batch.row_count() > 0:
                        yield record_batch
                else:
                    yield record_batch

        # Return a sequence-like object (generator)
        return generator()

    def _apply_filter(self, batch: RecordBatch, filter_expr: Expression, full_schema: Schema) -> RecordBatch:
        """Apply filter expression to a record batch.
        
        This implements filter pushdown by evaluating the filter expression
        on the batch and filtering out rows that don't match.
        
        Args:
            batch: RecordBatch to filter
            filter_expr: Physical filter expression to evaluate
            full_schema: Full schema of the data source (needed for filter evaluation)
            
        Returns:
            Filtered RecordBatch
        """
        # Evaluate filter expression to get boolean mask
        filter_result = filter_expr.evaluate(batch)
        
        # Extract boolean array from ColumnVector
        if not isinstance(filter_result, ArrowFieldVector):
            raise ValueError(f"Filter expression must return ArrowFieldVector, got {type(filter_result)}")
        
        bool_array = filter_result.field
        
        # Handle ChunkedArray by combining chunks
        if isinstance(bool_array, pa.ChunkedArray):
            bool_array = bool_array.combine_chunks()
        
        # Verify it's a boolean array
        if bool_array.type != pa.bool_():
            raise ValueError(f"Filter expression must return boolean, got {bool_array.type}")
        
        # Convert our RecordBatch to PyArrow RecordBatch for vectorized filtering
        arrays = [vec.field for vec in batch.fields]
        pa_schema = pa.schema([
            pa.field(f.name, f.dataType)
            for f in batch.schema.fields
        ])
        pa_batch = pa.RecordBatch.from_arrays(arrays, schema=pa_schema)
        
        # Apply vectorized filter - PyArrow filters all columns at once efficiently
        filtered_pa_batch = pa_batch.filter(bool_array)
        
        # Convert filtered PyArrow RecordBatch back to our RecordBatch
        filtered_columns = filtered_pa_batch.columns
        vectors = [ArrowFieldVector(col) for col in filtered_columns]
        
        return RecordBatch(batch.schema, vectors)

    def _detect_delimiter(self) -> str:
        """Detect CSV delimiter using Python's csv.Sniffer."""
        if self._cached_delimiter is None:
            with open(self.filename, 'r', encoding='utf-8') as f:
                sample = f.read(4096)
                f.seek(0)
                try:
                    dialect = stdlib_csv.Sniffer().sniff(sample)
                    self._cached_delimiter = dialect.delimiter
                except Exception:
                    # Default to comma if detection fails
                    self._cached_delimiter = ','
        return self._cached_delimiter

    def _infer_schema(self) -> Schema:
        """Infer schema from CSV file using PyArrow."""
        # Detect delimiter first (PyArrow auto-detect doesn't work well for TSV)
        delimiter = self._detect_delimiter()

        parse_options = pacsv.ParseOptions(
            delimiter=delimiter,
            escape_char=None,
            quote_char='"',
            double_quote=True,
            newlines_in_values=False,
            ignore_empty_lines=True,
        )

        # Read just enough to infer schema (first row)
        # PyArrow will read the file and infer schema
        try:
            if self.has_headers:
                # With headers, PyArrow will read column names from first line
                table = pacsv.read_csv(
                    self.filename,
                    parse_options=parse_options,
                )
                # Use column names from table
                fields = [Field(col_name, pa.string()) for col_name in table.column_names]
            else:
                # For no headers, we need to count columns from first row
                # Read first line to count columns, then use field_N naming
                with open(self.filename, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if not first_line:
                        raise ValueError(f"Cannot infer schema from empty CSV file: {self.filename}")

                    # Parse first row with detected delimiter
                    reader = stdlib_csv.reader([first_line], delimiter=delimiter)
                    first_row = next(reader, [])
                    num_cols = len(first_row)

                # Use field_N naming convention
                fields = [Field(f"field_{i+1}", pa.string()) for i in range(num_cols)]

            return Schema(fields)
        except Exception as e:
            # Fallback: try reading first line manually
            # This handles edge cases where PyArrow might fail
            with open(self.filename, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if not first_line:
                    raise ValueError(f"Cannot infer schema from empty CSV file: {self.filename}")

                # Parse with detected delimiter
                reader = stdlib_csv.reader([first_line], delimiter=delimiter)
                header = next(reader, [])

                if self.has_headers:
                    header = [h.strip() for h in header if h]
                    fields = [Field(col_name, pa.string()) for col_name in header]
                else:
                    num_cols = len(header)
                    fields = [Field(f"field_{i+1}", pa.string()) for i in range(num_cols)]

                return Schema(fields)

