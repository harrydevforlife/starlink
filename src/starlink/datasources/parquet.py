from pathlib import Path
from typing import List, Sequence, Iterator, Optional, Union

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from starlink.datasources.datasource import DataSource
from starlink.datatypes.schema import Schema, Field
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.expressions.colexpr import ColumnExpression
from starlink.physicalplan.expressions.expr import (
    LiteralLongExpression,
    LiteralDoubleExpression,
    LiteralStringExpression,
)
from starlink.physicalplan.expressions.booleanexpr import (
    GtExpression,
    LtExpression,
    GtEqExpression,
    LtEqExpression,
    EqExpression,
    NeqExpression,
    AndExpression,
    OrExpression,
)
from starlink.physicalplan.expressions.castexpr import CastExpression


class ParquetDataSource(DataSource):
    """Parquet data source.

    Using PyArrow Dataset API for folders (supports true predicate pushdown)
    Using native PyArrow ParquetFile API for single files (educational, shows how it works).
    """
    def __init__(self, filename: str, batch_size: Optional[int] = None):
        self.path = Path(filename)
        self.batch_size = batch_size
        # Auto-detect if path is file or folder
        self.is_directory = self.path.is_dir()
        self._dataset = None  # Lazy initialization for Dataset API

    def schema(self) -> Schema:
        if self.is_directory:
            # Use Dataset API for folders
            dataset = self._get_dataset()
            arrow_schema = dataset.schema
        else:
            # Use native API for single files
            pf = pq.ParquetFile(str(self.path))
            arrow_schema = pf.schema_arrow
        
        fields = [Field(f.name, f.type) for f in arrow_schema]
        return Schema(fields)
    
    def _get_dataset(self) -> ds.Dataset:
        """Get or create PyArrow Dataset for directory paths."""
        if self._dataset is None:
            self._dataset = ds.dataset(str(self.path), format="parquet")
        return self._dataset

    def scan(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        if self.is_directory:
            # Use PyArrow Dataset API for folders (supports true predicate pushdown)
            return self._scan_with_dataset(projection, filter)
        else:
            # Use native API for single files (educational, shows how it works)
            return self._scan_native(projection, filter)
    
    def _scan_with_dataset(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        """Scan using PyArrow Dataset API - supports true predicate pushdown with row group statistics."""
        dataset = self._get_dataset()
        
        # Build column name mapping: index in projected schema -> column name in full schema
        # This is needed because ColumnExpression uses indices from projected schema
        # but we need to map them to column names in the full dataset schema
        full_schema = dataset.schema
        column_name_map = {}
        if projection:
            # Map projected column indices to their names in full schema
            for idx, col_name in enumerate(projection):
                column_name_map[idx] = col_name
        else:
            # No projection: map indices directly to full schema field names
            for idx, field in enumerate(full_schema):
                column_name_map[idx] = field.name
        
        # Convert our filter expression to PyArrow Dataset filter
        pa_filter = None
        if filter is not None:
            try:
                pa_filter = self._convert_expression_to_dataset_filter(filter, full_schema, column_name_map)
                # Note: We don't validate the filter here to avoid overhead
                # If the filter is invalid, PyArrow will throw an error when we create the scanner
                # We'll catch it then and fall back to post-read filtering
            except Exception as e:
                # If conversion fails, fall back to post-read filtering
                # This can happen for unsupported expression types (e.g., complex casts)
                pa_filter = None
        
        def generator() -> Iterator[RecordBatch]:
            # Use Dataset API to scan with projection
            # Dataset API automatically uses row group statistics for predicate pushdown
            current_filter = pa_filter
            use_post_read_filter = False
            try:
                scanner = dataset.scanner(
                    columns=projection if projection else None,
                    filter=current_filter,  # PyArrow Dataset filter (uses row group statistics)
                    batch_size=self.batch_size,
                )
            except (pa.lib.ArrowNotImplementedError, pa.lib.ArrowInvalid) as e:
                # Filter contains unsupported operations, fall back to post-read filtering
                # Create scanner without filter
                scanner = dataset.scanner(
                    columns=projection if projection else None,
                    filter=None,
                    batch_size=self.batch_size,
                )
                current_filter = None  # Mark that we need post-read filtering
                use_post_read_filter = True
            
            for batch in scanner.to_batches():
                # batch is a pyarrow.RecordBatch
                arrow_schema: pa.Schema = batch.schema
                schema = Schema([Field(f.name, f.type) for f in arrow_schema])
                vectors = [ArrowFieldVector(col) for col in batch.columns]
                record_batch = RecordBatch(schema, vectors)
                
                # If we couldn't convert filter to Dataset filter, apply it post-read
                if filter is not None and (current_filter is None or use_post_read_filter):
                    record_batch = self._apply_filter(record_batch, filter, schema)
                    if record_batch.row_count() == 0:
                        continue
                
                yield record_batch
        
        return generator()
    
    def _convert_expression_to_dataset_filter(
        self, expr: Expression, schema: pa.Schema, column_name_map: dict
    ) -> Optional[ds.Expression]:
        """Convert our Expression to PyArrow Dataset filter expression.
        
        This enables true predicate pushdown using row group statistics.
        
        Args:
            expr: Our physical Expression
            schema: PyArrow full dataset schema
            column_name_map: Mapping from column index (in projected schema) to column name (in full schema)
            
        Returns:
            PyArrow Dataset filter expression, or None if conversion not supported
        """
        # Handle ColumnExpression -> ds.field(name)
        if isinstance(expr, ColumnExpression):
            # Get column name from mapping (index in projected schema -> name in full schema)
            if expr.i in column_name_map:
                column_name = column_name_map[expr.i]
                return ds.field(column_name)
            else:
                raise ValueError(f"Column index {expr.i} not found in column_name_map. Available indices: {list(column_name_map.keys())}")
        
        # Handle Literal expressions -> scalar values
        if isinstance(expr, LiteralLongExpression):
            return expr.value
        if isinstance(expr, LiteralDoubleExpression):
            return expr.value
        if isinstance(expr, LiteralStringExpression):
            return expr.value
        
        # Handle CastExpression - try to apply cast in Dataset filter
        # Note: Dataset API supports some casts in filters (e.g., numeric casts)
        # Some casts are not supported (e.g., timestamp to double) - fall back to post-read filtering
        if isinstance(expr, CastExpression):
            inner_expr = self._convert_expression_to_dataset_filter(expr.expr, schema, column_name_map)
            if inner_expr is None:
                return None
            
            # If inner expression is a field reference, check if cast is needed
            if hasattr(inner_expr, 'cast'):
                # Check if cast is actually needed (skip unnecessary casts)
                # Get the source field type from schema
                if isinstance(inner_expr, ds.Expression):
                    # Try to get field name from expression (if it's a field reference)
                    # For now, we'll try the cast and let PyArrow handle it
                    # PyArrow might optimize away unnecessary casts
                    try:
                        # Try to cast the field expression
                        # This works for numeric casts (e.g., string -> int64, double -> int64)
                        # But fails for unsupported casts (e.g., timestamp -> double)
                        cast_result = inner_expr.cast(expr.dataType)
                        return cast_result
                    except (pa.lib.ArrowNotImplementedError, pa.lib.ArrowInvalid) as e:
                        # PyArrow Dataset API doesn't support this cast in filters
                        # Fall back to post-read filtering
                        return None
                    except Exception as e:
                        # Other errors - also fall back
                        return None
                else:
                    # Not a field expression, can't cast
                    return None
            else:
                # If inner expression is not a field (e.g., literal), cast might not be needed
                # or might not be supported in Dataset filters
                return None
        
        # Handle boolean expressions
        if isinstance(expr, (GtExpression, LtExpression, GtEqExpression, LtEqExpression, EqExpression, NeqExpression)):
            left = self._convert_expression_to_dataset_filter(expr.l, schema, column_name_map)
            right = self._convert_expression_to_dataset_filter(expr.r, schema, column_name_map)
            
            if left is None or right is None:
                return None
            
            # Apply the comparison operator
            if isinstance(expr, GtExpression):
                return left > right
            elif isinstance(expr, LtExpression):
                return left < right
            elif isinstance(expr, GtEqExpression):
                return left >= right
            elif isinstance(expr, LtEqExpression):
                return left <= right
            elif isinstance(expr, EqExpression):
                return left == right
            elif isinstance(expr, NeqExpression):
                return left != right
        
        # Handle logical expressions (AND, OR)
        if isinstance(expr, AndExpression):
            left = self._convert_expression_to_dataset_filter(expr.l, schema, column_name_map)
            right = self._convert_expression_to_dataset_filter(expr.r, schema, column_name_map)
            if left is None or right is None:
                return None
            return left & right
        
        if isinstance(expr, OrExpression):
            left = self._convert_expression_to_dataset_filter(expr.l, schema)
            right = self._convert_expression_to_dataset_filter(expr.r, schema)
            if left is None or right is None:
                return None
            return left | right
        
        # Unsupported expression type
        return None
    
    def _scan_native(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        """Scan using native PyArrow ParquetFile API (educational, shows how it works)."""
        columns = projection if projection else None
        pf = pq.ParquetFile(str(self.path))

        def generator() -> Iterator[RecordBatch]:
            # Only pass batch_size if it's not None (PyArrow uses default if not provided)
            kwargs = {}
            if self.batch_size is not None:
                kwargs["batch_size"] = self.batch_size

            for batch in pf.iter_batches(columns=columns, **kwargs):
                # batch is a pyarrow.RecordBatch
                arrow_schema: pa.Schema = batch.schema
                schema = Schema([Field(f.name, f.type) for f in arrow_schema])
                vectors = [ArrowFieldVector(col) for col in batch.columns]
                record_batch = RecordBatch(schema, vectors)
                
                # Apply filter pushdown if filter is provided
                # Note: For Parquet, we could also use row group statistics to skip entire row groups
                # This is a future optimization
                if filter is not None:
                    record_batch = self._apply_filter(record_batch, filter, schema)
                    # Skip empty batches after filtering
                    if record_batch.row_count() == 0:
                        continue
                
                yield record_batch

        return generator()
    
    def _apply_filter(self, batch: RecordBatch, filter_expr: Expression, schema: Schema) -> RecordBatch:
        """Apply filter expression to a record batch (same as CSV implementation).
        
        Future: For Parquet, we could use row group statistics to skip entire row groups
        before reading them, which would be much more efficient.
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
