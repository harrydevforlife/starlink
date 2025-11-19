from typing import List, Sequence, Iterator

import pyarrow as pa

from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.physicalplan.expressions.expr import Expression
from starlink.physicalplan.physical import PhysicalPlan


class SelectionExec(PhysicalPlan):
    """Execute a selection (filter) over the input physical plan."""

    def __init__(self, input: PhysicalPlan, expr: Expression):
        self.input = input
        self.expr = expr

    def schema(self) -> Schema:
        return self.input.schema()

    def children(self) -> List[PhysicalPlan]:
        return [self.input]

    def execute(self) -> Sequence[RecordBatch]:
        """Execute selection (filter) using vectorized PyArrow operations.

        This method uses PyArrow's optimized filter operations to efficiently
        filter all columns at once, eliminating Python loop overhead.
        """
        def generator() -> Iterator[RecordBatch]:
            for batch in self.input.execute():
                # Evaluate filter expression to get boolean ColumnVector
                sel_vec = self.expr.evaluate(batch)

                # Extract boolean array from ArrowFieldVector
                # Expression evaluation already returns ArrowFieldVector with boolean array
                if not isinstance(sel_vec, ArrowFieldVector):
                    raise ValueError(
                        f"SelectionExec requires ArrowFieldVector from expression, got {type(sel_vec)}"
                    )

                bool_array = sel_vec.field

                # Handle ChunkedArray by combining chunks into a single Array
                if isinstance(bool_array, pa.ChunkedArray):
                    bool_array = bool_array.combine_chunks()

                # Verify it's a boolean array
                if bool_array.type != pa.bool_():
                    raise ValueError(
                        f"SelectionExec requires boolean expression result, got {bool_array.type}"
                    )

                # Convert our RecordBatch to PyArrow RecordBatch for vectorized filtering
                # Extract arrays from our RecordBatch fields
                arrays = [vec.field for vec in batch.fields]

                # Create PyArrow schema from our schema
                pa_schema = pa.schema([
                    pa.field(f.name, f.dataType)
                    for f in batch.schema.fields
                ])

                # Create PyArrow RecordBatch
                pa_batch = pa.RecordBatch.from_arrays(arrays, schema=pa_schema)

                # Apply vectorized filter - PyArrow filters all columns at once efficiently
                filtered_pa_batch = pa_batch.filter(bool_array)

                # Convert filtered PyArrow RecordBatch back to our RecordBatch
                # Extract columns from filtered batch
                filtered_columns = filtered_pa_batch.columns

                # Wrap each column in ArrowFieldVector
                vectors = [ArrowFieldVector(col) for col in filtered_columns]

                # Create our RecordBatch with filtered vectors
                yield RecordBatch(batch.schema, vectors)

        return generator()

    def __str__(self) -> str:
        return f"SelectionExec: {self.expr}"
