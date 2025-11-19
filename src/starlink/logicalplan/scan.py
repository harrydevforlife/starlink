from typing import List, Optional

from starlink.datasources.datasource import DataSource
from starlink.datatypes.schema import Schema
from starlink.logicalplan.logical import LogicalPlan
from starlink.logicalplan.expr import LogicalExpr


class Scan(LogicalPlan):
    """Represents a scan of a data source.
    
    Supports both projection pushdown and filter pushdown (predicate pushdown).
    """

    def __init__(self, path: str, data_source: DataSource, projection: List[str], filter: Optional[LogicalExpr] = None):
        self.path = path
        self.data_source = data_source
        self.projection = projection
        self.filter = filter
        self._schema = self._derive_schema()

    def schema(self) -> Schema:
        return self._schema

    def _derive_schema(self) -> Schema:
        schema = self.data_source.schema()
        if not self.projection:
            return schema
        else:
            # Select fields in the order specified by projection
            # (not original schema order)
            # schema order
            fields = []
            for name in self.projection:
                for field in schema.fields:
                    if field.name == name:
                        fields.append(field)
                        break
            return Schema(fields)

    def children(self) -> List[LogicalPlan]:
        return []

    def __str__(self) -> str:
        parts = []
        if not self.projection:
            parts.append("projection=None")
        else:
            projection_str = "[" + ", ".join(self.projection) + "]"
            parts.append(f"projection={projection_str}")
        
        if self.filter is not None:
            parts.append(f"filter={self.filter}")
        
        filter_str = ", ".join(parts)
        return f"Scan: {self.path}; {filter_str}"
