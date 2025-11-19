from typing import List, Sequence, Optional
from starlink.datasources.datasource import DataSource
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.physicalplan.expressions.expr import Expression


class InMemoryDataSource(DataSource):
    def __init__(self, schema: Schema, data: List[RecordBatch]):
        self._schema = schema
        self.data = data

    def schema(self) -> Schema:
        return self._schema

    def scan(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        # --- Handle filter pushdown ---
        filtered_data = self.data
        
        if not projection:
            # No projection: return whatever (possibly filtered) data
            return filtered_data

        # Find indices of projected columns by name
        projection_indices = []
        for name in projection:
            for idx, field in enumerate(self._schema.fields):
                if field.name == name:
                    projection_indices.append(idx)
                    break
            else:
                raise ValueError(f"Column '{name}' not found in schema")

        # Create projected batches
        result = []
        for batch in filtered_data:
            projected_fields = [batch.field(idx) for idx in projection_indices]
            # Create projected schema
            projected_schema = Schema([self._schema.fields[idx] for idx in projection_indices])
            result.append(RecordBatch(projected_schema, projected_fields))

        return result
