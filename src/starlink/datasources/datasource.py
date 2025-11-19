
from typing import Sequence, List, Optional

from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.physicalplan.expressions.expr import Expression


class DataSource:
    def schema(self) -> Schema:
        pass

    def scan(self, projection: List[str], filter: Optional[Expression] = None) -> Sequence[RecordBatch]:
        """Scan the data source with optional projection and filter pushdown.
        
        Args:
            projection: List of column names to read (empty list means all columns)
            filter: Optional physical filter expression to apply during scanning
            
        Returns:
            Sequence of RecordBatch objects
        """
        pass
