"""Tests for Parquet Data Source

Tests reading Parquet files with various configurations.
"""

import pytest
import pyarrow as pa
import pyarrow.parquet as pq

from starlink.datasources.parquet import ParquetDataSource


@pytest.fixture
def simple_parquet(tmp_path):
    """Create a simple parquet file with id column."""
    parquet_file = tmp_path / "simple.parquet"
    
    # Create a simple table with id column
    table = pa.table({
        "id": [4, 5, 6, 7, 2, 3, 0, 1, None]
    })
    
    pq.write_table(table, parquet_file)
    return str(parquet_file)


@pytest.fixture
def alltypes_parquet(tmp_path):
    """Create a parquet file with multiple data types (similar to alltypes_plain.parquet)."""
    parquet_file = tmp_path / "alltypes_plain.parquet"
    
    # Create a table with various data types
    table = pa.table({
        "id": pa.array([0, 1, 2, 3, 4, 5, 6, 7], type=pa.int32()),
        "bool_col": pa.array([True, False, True, False, True, False, True, False], type=pa.bool_()),
        "tinyint_col": pa.array([0, 1, 2, 3, 4, 5, 6, 7], type=pa.int32()),
        "smallint_col": pa.array([0, 1, 2, 3, 4, 5, 6, 7], type=pa.int32()),
        "int_col": pa.array([0, 1, 2, 3, 4, 5, 6, 7], type=pa.int32()),
        "bigint_col": pa.array([0, 1, 2, 3, 4, 5, 6, 7], type=pa.int64()),
        "float_col": pa.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], type=pa.float32()),
        "double_col": pa.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], type=pa.float64()),
        "date_string_col": pa.array(["01/01/09", "01/01/09", "01/01/09", "01/01/09", 
                                     "01/01/09", "01/01/09", "01/01/09", "01/01/09"], type=pa.binary()),
        "string_col": pa.array(["0", "1", "2", "3", "4", "5", "6", "7"], type=pa.binary()),
        "timestamp_col": pa.array(["01/01/09 00:00:00", "01/01/09 00:00:00", "01/01/09 00:00:00", 
                                   "01/01/09 00:00:00", "01/01/09 00:00:00", "01/01/09 00:00:00", 
                                   "01/01/09 00:00:00", "01/01/09 00:00:00"], type=pa.binary()),
    })
    
    pq.write_table(table, parquet_file)
    return str(parquet_file)


class TestParquetDataSource:
    def test_read_parquet_schema(self, alltypes_parquet):
        """Test reading parquet schema."""
        parquet = ParquetDataSource(alltypes_parquet)
        schema = parquet.schema()
        
        # Check that schema has all expected fields
        field_names = [f.name for f in schema.fields]
        expected_fields = [
            "id", "bool_col", "tinyint_col", "smallint_col", "int_col",
            "bigint_col", "float_col", "double_col", "date_string_col",
            "string_col", "timestamp_col"
        ]
        
        assert len(schema.fields) == len(expected_fields)
        assert set(field_names) == set(expected_fields)
        
        # Check some field types
        id_field = next(f for f in schema.fields if f.name == "id")
        assert id_field.dataType == pa.int32()
        
        bool_field = next(f for f in schema.fields if f.name == "bool_col")
        assert bool_field.dataType == pa.bool_()
        
        bigint_field = next(f for f in schema.fields if f.name == "bigint_col")
        assert bigint_field.dataType == pa.int64()

    def test_read_parquet_file_with_projection(self, simple_parquet):
        """Test reading parquet file with column projection."""
        parquet = ParquetDataSource(simple_parquet)
        result = list(parquet.scan(["id"]))
        
        # Should have at least one batch
        assert len(result) > 0
        
        # Get the first batch
        batch = result[0]
        
        # Check schema has only projected column
        assert len(batch.schema.fields) == 1
        assert batch.schema.fields[0].name == "id"
        
        # Check batch size
        id_field = batch.field(0)
        assert id_field.size() == 9  # 9 rows including null
        
        # Check values match expected: 4,5,6,7,2,3,0,1,null
        expected_values = [4, 5, 6, 7, 2, 3, 0, 1, None]
        actual_values = [id_field.get_value(i) for i in range(id_field.size())]
        
        assert actual_values == expected_values

    def test_read_parquet_file_no_projection(self, alltypes_parquet):
        """Test reading parquet file without projection (all columns)."""
        parquet = ParquetDataSource(alltypes_parquet)
        result = list(parquet.scan([]))
        
        # Should have at least one batch
        assert len(result) > 0
        
        # Get the first batch
        batch = result[0]
        
        # Check schema has all columns
        assert len(batch.schema.fields) == 11
        
        # Check batch size
        assert batch.row_count() == 8

    def test_read_parquet_file_multiple_columns_projection(self, alltypes_parquet):
        """Test reading parquet file with multiple column projection."""
        parquet = ParquetDataSource(alltypes_parquet)
        result = list(parquet.scan(["id", "bool_col", "int_col"]))
        
        # Should have at least one batch
        assert len(result) > 0
        
        # Get the first batch
        batch = result[0]
        
        # Check schema has only projected columns
        assert len(batch.schema.fields) == 3
        field_names = [f.name for f in batch.schema.fields]
        assert set(field_names) == {"id", "bool_col", "int_col"}
        
        # Check batch size
        assert batch.row_count() == 8

    def test_read_parquet_file_with_batch_size(self, alltypes_parquet):
        """Test reading parquet file with custom batch size."""
        parquet = ParquetDataSource(alltypes_parquet, batch_size=2)
        result = list(parquet.scan([]))
        
        # Should have multiple batches (8 rows / 2 per batch = 4 batches)
        assert len(result) == 4
        
        # Each batch should have 2 rows (except possibly the last)
        for i, batch in enumerate(result):
            if i < len(result) - 1:
                assert batch.row_count() == 2
            else:
                # Last batch might have fewer rows
                assert batch.row_count() <= 2
