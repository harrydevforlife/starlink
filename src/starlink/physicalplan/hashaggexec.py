

from typing import Any, Dict, List, Sequence, Iterator, Tuple
from collections import defaultdict

import pyarrow as pa
import pyarrow.compute as pc

from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.datatypes.arrow_vector_builder import ArrowVectorBuilder
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.physicalplan.expressions.expr import Accumulator, Expression
from starlink.physicalplan.expressions.aggexpr import AggregateExpression
from starlink.physicalplan.physical import PhysicalPlan


class HashAggregateExec(PhysicalPlan):
    """HashAggregateExec is a physical plan that performs a hash aggregate operation.

    Builds a hash map from grouping keys to accumulators.
    Accumulates values for each aggregate input column.
    Builds output columns according to target schema.
    Returns a generator of output batches.
    """
    def __init__(
        self,
        input: PhysicalPlan,
        group_expr: List[Expression],
        aggregate_expr: List[AggregateExpression],
        schema: Schema,
    ):
        self.input = input
        self.group_expr = group_expr
        self.aggregate_expr = aggregate_expr
        self._schema = schema

    def schema(self) -> Schema:
        return self._schema

    def children(self) -> List[PhysicalPlan]:
        return [self.input]

    def __str__(self) -> str:
        group_expr_str = "[" + ", ".join(str(e) for e in self.group_expr) + "]"
        agg_expr_str = "[" + ", ".join(str(e) for e in self.aggregate_expr) + "]"
        return f"HashAggregateExec: groupExpr={group_expr_str}, aggrExpr={agg_expr_str}"

    def execute(self) -> Sequence[RecordBatch]:
        """Execute hash aggregate using batch processing for improved performance.

        This method optimizes aggregation by:
        - Batch extracting values from grouping columns
        - Batch creating grouping keys using zip
        - Grouping rows by key first, then accumulating in batches
        - Reducing Python loop overhead and repeated method calls
        """
        # Map from grouping key tuple -> list of accumulators
        groups: Dict[Tuple[Any, ...], List[Accumulator]] = {}

        # Iterate over input batches
        for batch in self.input.execute():
            # Evaluate grouping expressions and aggregate input expressions
            group_keys_columns = [expr.evaluate(batch) for expr in self.group_expr]
            aggr_input_columns = [ae.input_expression().evaluate(batch) for ae in self.aggregate_expr]

            row_count = batch.row_count()

            # Batch extract values from grouping columns (optimization)
            # This avoids repeated getValue() calls and reduces Python loop overhead
            group_values = []
            for col in group_keys_columns:
                # Extract all values at once from ArrowFieldVector
                if isinstance(col, ArrowFieldVector):
                    arr = col.field
                    # Handle ChunkedArray by combining chunks
                    if isinstance(arr, pa.ChunkedArray):
                        arr = arr.combine_chunks()

                    # Optimization: Check array type to avoid unnecessary conversions
                    # PyArrow string arrays already return strings from as_py()
                    # Only binary arrays need conversion, and we can use PyArrow cast for that
                    if pa.types.is_binary(arr.type) or pa.types.is_large_binary(arr.type):
                        # Convert binary array to string array using PyArrow cast (vectorized)
                        # This is much faster than row-by-row decode
                        arr = pc.cast(arr, pa.string())

                    # Extract all values in one pass
                    # For string arrays, as_py() returns strings directly (no bytes conversion needed)
                    values = [arr[i].as_py() for i in range(len(arr))]
                else:
                    # Fallback to getValue for non-ArrowFieldVector columns
                    values = [col.get_value(i) for i in range(row_count)]
                    # Convert bytes to strings if needed (for non-ArrowFieldVector columns)
                    # This is a fallback for edge cases
                    converted_values = [
                        v.decode('utf-8') if isinstance(v, (bytes, bytearray)) else v
                        for v in values
                    ]
                    group_values.append(converted_values)
                    continue

                # No conversion needed for PyArrow string arrays (already strings)
                # Binary arrays were already converted using PyArrow cast above
                group_values.append(values)

            # Batch create grouping keys using zip (much more efficient than tuple creation in loop)
            # Special case: when there are no grouping columns, all rows belong to the same group
            # Use empty tuple () as the key for all rows
            if len(group_values) == 0:
                # No grouping: all rows go into a single group with empty tuple key
                keys = [()] * row_count
            else:
                keys = list(zip(*group_values))

            # Batch extract values from aggregate input columns
            aggr_values = []
            for col in aggr_input_columns:
                # Extract all values at once
                if isinstance(col, ArrowFieldVector):
                    arr = col.field
                    if isinstance(arr, pa.ChunkedArray):
                        arr = arr.combine_chunks()
                    values = [arr[i].as_py() for i in range(len(arr))]
                else:
                    values = [col.get_value(i) for i in range(row_count)]
                aggr_values.append(values)

            # Group rows by key first (reduces dictionary lookups)
            # This allows us to accumulate values in batches per group
            key_to_indices = defaultdict(list)
            for row_index, key in enumerate(keys):
                key_to_indices[key].append(row_index)

            # Create accumulators for all unique keys upfront
            # This reduces dictionary lookups during accumulation
            for key in key_to_indices:
                if key not in groups:
                    groups[key] = [ae.create_accumulator() for ae in self.aggregate_expr]

            # Accumulate values in batches per group
            # This is more efficient than row-by-row accumulation
            for key, row_indices in key_to_indices.items():
                accs = groups[key]
                for i, acc in enumerate(accs):
                    # Accumulate all values for this group
                    for row_index in row_indices:
                        value = aggr_values[i][row_index]
                        acc.accumulate(value)

        # Build output columns according to target schema
        out_row_count = len(groups)
        # For each field in schema, prepare a builder
        builders = [ArrowVectorBuilder(f.dataType) for f in self._schema.fields]
        for b in builders:
            b.set_value_count(out_row_count)

        # Populate rows
        for out_row_index, (key, accs) in enumerate(groups.items()):
            # First group_expr columns
            for i, kv in enumerate(key):
                builders[i].set(out_row_index, kv)
            # Then aggregate_expr columns
            offset = len(self.group_expr)
            for j, acc in enumerate(accs):
                builders[offset + j].set(out_row_index, acc.final_value())

        # Build ColumnVectors
        columns = [b.build() for b in builders]
        output_batch = RecordBatch(self._schema, columns)

        def generator() -> Iterator[RecordBatch]:
            yield output_batch

        return generator()
