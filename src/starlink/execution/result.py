"""Query Result

Provides a user-friendly interface for query results with convenient display methods.
"""

from typing import Any, List, Optional, Sequence

from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema


class QueryResult:
    """Wrapper around query execution results providing convenient display methods.
    
    This class wraps a sequence of RecordBatch objects and provides methods like:
    - show(): Display results in a formatted table
    - to_markdown(): Convert results to markdown table
    - collect(): Collect all batches into a list of dictionaries
    - to_pandas(): Convert to pandas DataFrame (if pandas is available)
    """
    
    def __init__(self, batches: Sequence[RecordBatch]):
        """Initialize QueryResult with a sequence of RecordBatch objects.
        
        Args:
            batches: Sequence of RecordBatch objects from query execution
        """
        self._batches = batches
        self._batches_list: Optional[List[RecordBatch]] = None  # Cached list version
        self._schema: Optional[Schema] = None
        self._collected: Optional[List[dict]] = None
    
    def _get_batches_list(self) -> List[RecordBatch]:
        """Get batches as a list, caching the result."""
        if self._batches_list is None:
            # Convert to list to handle generators (only once)
            self._batches_list = list(self._batches) if not isinstance(self._batches, list) else list(self._batches)
        return self._batches_list
    
    def _get_schema(self) -> Schema:
        """Get schema from first batch."""
        if self._schema is None:
            # Get schema from first batch (even if empty)
            batches_list = self._get_batches_list()
            if len(batches_list) > 0:
                self._schema = batches_list[0].schema
            else:
                raise ValueError("No batches available to determine schema")
        return self._schema

    def to_batches(self) -> List[RecordBatch]:
        """Get the batches from the query result."""
        return self._get_batches_list()

    def scalar(self) -> Any:
        """Get the scalar result of the query."""
        if len(self._get_batches_list()) > 0:
            return self._get_batches_list()[0].scalar()
        else:
            raise ValueError("No batches available to determine scalar result")
    
    def collect(self, limit: Optional[int] = None) -> List[dict]:
        """Collect all results into a list of dictionaries.
        
        Each dictionary represents a row with column names as keys.
        
        Returns:
            List of dictionaries, each representing a row
        """
        if self._collected is not None:
            return self._collected
        
        rows = []
        batches_list = self._get_batches_list()
        
        if len(batches_list) > 0:
            schema = batches_list[0].schema
            column_names = [field.name for field in schema.fields]
            
            for batch in batches_list:
                row_count = batch.row_count()
                for i in range(row_count):
                    row = {}
                    for j, col_name in enumerate(column_names):
                        value = batch.field(j).get_value(i)
                        row[col_name] = value
                    rows.append(row)
                    if limit is not None and len(rows) >= limit:
                        break
                if limit is not None and len(rows) >= limit:
                    break
        else:
            # Empty result - try to get schema from _get_schema which will raise if no batches
            schema = self._get_schema()
            column_names = [field.name for field in schema.fields]
        
        self._collected = rows
        return rows
    
    def show(self, limit: Optional[int] = 20, truncate: bool = True) -> None:
        """Display results in a formatted table.
        
        Args:
            limit: Maximum number of rows to display (None for all)
            truncate: Whether to truncate long values
        """
        import tabulate
        rows = self.collect(limit)
        if truncate:
            for row in rows:
                for key, value in row.items():
                    if len(str(value)) > 30:
                        row[key] = str(value)[:27] + "..."
            print(tabulate.tabulate(rows, headers='keys', tablefmt='github'))
        else:
            print(tabulate.tabulate(rows, headers='keys', tablefmt='github'))
        if limit is not None:
            if len(self) > limit:
                print(f"\n({limit} of {len(self)} row(s) shown)")
            else:
                print(f"\n({len(self)} row(s) shown)")
        else:
            print(f"\n({len(self)} row(s))")

    def to_markdown(self, limit: Optional[int] = None) -> str:
        """Convert results to markdown table.
        
        Returns:
            Markdown table
        """
        import tabulate
        return tabulate.tabulate(
            self.collect(limit), headers='keys', tablefmt='github'
        )
    
    def to_pandas(self):
        """Convert results to pandas DataFrame.
        
        Returns:
            pandas DataFrame
            
        Raises:
            ImportError: If pandas is not installed
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_pandas(). Install it with: pip install pandas")
        
        rows = self.collect()
        if not rows:
            schema = self._get_schema()
            column_names = [field.name for field in schema.fields]
            return pd.DataFrame(columns=column_names)
        
        return pd.DataFrame(rows)
    
    def to_csv(self) -> str:
        """Convert results to CSV format.
        
        Returns:
            CSV-formatted string
        """
        rows = self.collect()
        schema = self._get_schema()
        column_names = [field.name for field in schema.fields]
        
        if not rows:
            return ",".join(column_names)
        
        lines = []
        lines.append(",".join(column_names))
        
        for row in rows:
            values = [self._format_value(row.get(col_name), truncate=False) for col_name in column_names]
            # Escape values that contain commas or quotes
            escaped_values = []
            for val in values:
                val_str = str(val) if val is not None else ""
                if "," in val_str or '"' in val_str or "\n" in val_str:
                    val_str = '"' + val_str.replace('"', '""') + '"'
                escaped_values.append(val_str)
            lines.append(",".join(escaped_values))
        
        return "\n".join(lines)
    
    def _format_value(self, value, truncate: bool = True) -> str:
        """Format a value for display.
        
        Args:
            value: Value to format
            truncate: Whether to truncate long values
            
        Returns:
            Formatted string
        """
        if value is None:
            return "null"
        
        value_str = str(value)
        
        if truncate and len(value_str) > 30:
            return value_str[:27] + "..."
        
        return value_str
    
    def __iter__(self):
        """Allow iteration over batches."""
        # Always use cached list to avoid consuming generator multiple times
        batches_list = self._get_batches_list()
        return iter(batches_list)
    
    def __len__(self) -> int:
        """Return total number of rows."""
        if self._collected is not None:
            return len(self._collected)
        # If not collected yet, use cached batches list
        batches_list = self._get_batches_list()
        return sum(batch.row_count() for batch in batches_list)
    
    def __repr__(self) -> str:
        """String representation."""
        try:
            schema = self._get_schema()
            column_names = [field.name for field in schema.fields]
        except (ValueError, AttributeError):
            column_names = []
        
        if self._collected is not None:
            total_rows = len(self._collected)
        else:
            # Try to get count without consuming generator
            try:
                total_rows = sum(batch.row_count() for batch in self._batches)
            except:
                total_rows = "?"
        
        return f"QueryResult(rows={total_rows}, columns={column_names})"

