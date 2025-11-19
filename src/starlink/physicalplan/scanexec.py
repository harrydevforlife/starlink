from typing import List, Sequence, Optional

from starlink.datasources.datasource import DataSource
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.physicalplan.physical import PhysicalPlan
from starlink.physicalplan.expressions.expr import Expression


class ScanExec(PhysicalPlan):
    """Scan a data source with optional push-down projection and filter."""

    def __init__(self, ds: DataSource, projection: List[str], filter: Optional[Expression] = None):
        self.ds = ds
        self.projection = projection
        self.filter = filter

    def schema(self) -> Schema:
        if not self.projection:
            return self.ds.schema()
        source_schema = self.ds.schema()
        fields = []
        for name in self.projection:
            for field in source_schema.fields:
                if field.name == name:
                    fields.append(field)
                    break
        return Schema(fields)

    def children(self) -> List[PhysicalPlan]:
        return []

    def execute(self) -> Sequence[RecordBatch]:
        # Pass physical filter expression directly to data source
        # Data sources can evaluate physical expressions on batches
        return self.ds.scan(self.projection, self.filter)

    def __str__(self) -> str:
        projection_str = "[" + ", ".join(self.projection) + "]" if self.projection else "None"
        return f"ScanExec: schema={self.schema()}, projection={projection_str}"
