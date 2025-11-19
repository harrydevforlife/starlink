"""Tests for CSV Data Source

Tests reading CSV files with various configurations.
"""

import pytest

from starlink.datasources.csv import CsvDataSource


@pytest.fixture
def employee_csv(tmp_path):
    """Create employee.csv with headers."""
    csv_file = tmp_path / "employee.csv"
    csv_content = """id,first_name,last_name,state,job_title,salary
1,John,Doe,CA,Engineer,50000
2,Jane,Smith,NY,Manager,60000
3,Bob,Einstein,CA,Scientist,70000
4,Alice,Johnson,TX,Engineer,55000
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def employee_no_header_csv(tmp_path):
    """Create employee_no_header.csv without headers."""
    csv_file = tmp_path / "employee_no_header.csv"
    csv_content = """1,John,Doe,CA,Engineer,50000
2,Jane,Smith,NY,Manager,60000
3,Bob,Einstein,CA,Scientist,70000
4,Alice,Johnson,TX,Engineer,55000
"""
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def employee_tsv(tmp_path):
    """Create employee.tsv (tab-separated) with headers."""
    tsv_file = tmp_path / "employee.tsv"
    tsv_content = """id\tfirst_name\tlast_name\tstate\tjob_title\tsalary
1\tJohn\tDoe\tCA\tEngineer\t50000
2\tJane\tSmith\tNY\tManager\t60000
3\tBob\tEinstein\tCA\tScientist\t70000
"""
    tsv_file.write_text(tsv_content)
    return str(tsv_file)


@pytest.fixture
def employee_no_header_tsv(tmp_path):
    """Create employee_no_header.tsv without headers."""
    tsv_file = tmp_path / "employee_no_header.tsv"
    tsv_content = """1\tJohn\tDoe\tCA\tEngineer\t50000
2\tJane\tSmith\tNY\tManager\t60000
3\tBob\tEinstein\tCA\tScientist\t70000
"""
    tsv_file.write_text(tsv_content)
    return str(tsv_file)


class TestCsvDataSource:
    def test_read_csv_with_no_projection(self, employee_csv):
        """Test reading CSV with no projection (all columns)."""
        csv = CsvDataSource(employee_csv, None, True, 1024)
        headers = ["id", "first_name", "last_name", "state", "job_title", "salary"]
        result = list(csv.scan([]))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4  # 4 rows

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_csv_with_projection(self, employee_csv):
        """Test reading CSV with projection (subset of columns)."""
        csv = CsvDataSource(employee_csv, None, True, 1024)
        headers = ["first_name", "last_name", "state", "job_title", "salary"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_csv_with_first_single_projection(self, employee_csv):
        """Test reading CSV with single column projection (first column)."""
        csv = CsvDataSource(employee_csv, None, True, 1024)
        headers = ["id"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_csv_with_middle_single_projection(self, employee_csv):
        """Test reading CSV with single column projection (middle column)."""
        csv = CsvDataSource(employee_csv, None, True, 1024)
        headers = ["state"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_csv_with_small_batch(self, employee_csv):
        """Test reading CSV with small batch size (1 row per batch)."""
        csv = CsvDataSource(employee_csv, None, True, 1)
        result = list(csv.scan([]))

        assert len(result) == 4  # 4 batches (1 row each)

        for batch in result:
            field = batch.field(0)
            assert field.size() == 1  # Each batch has 1 row

    def test_read_csv_with_no_header(self, employee_no_header_csv):
        """Test reading CSV without headers (uses field_1, field_2, etc.)."""
        csv = CsvDataSource(employee_no_header_csv, None, False, 1024)
        result = list(csv.scan([]))
        headers = ["field_1", "field_2", "field_3", "field_4", "field_5", "field_6"]

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4

            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_csv_with_projections_and_no_header(self, employee_no_header_csv):
        """Test reading CSV with projection and no headers."""
        csv = CsvDataSource(employee_no_header_csv, None, False, 1024)
        headers = ["field_1", "field_3", "field_5"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 4

            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_no_projection(self, employee_tsv):
        """Test reading TSV (tab-separated) with no projection."""
        csv = CsvDataSource(employee_tsv, None, True, 1024)
        headers = ["id", "first_name", "last_name", "state", "job_title", "salary"]
        result = list(csv.scan([]))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3  # 3 rows in TSV file

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_projection(self, employee_tsv):
        """Test reading TSV with projection."""
        csv = CsvDataSource(employee_tsv, None, True, 1024)
        headers = ["first_name", "last_name", "state", "job_title", "salary"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_first_single_projection(self, employee_tsv):
        """Test reading TSV with single column projection (first column)."""
        csv = CsvDataSource(employee_tsv, None, True, 1024)
        headers = ["id"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_middle_single_projection(self, employee_tsv):
        """Test reading TSV with single column projection (middle column)."""
        csv = CsvDataSource(employee_tsv, None, True, 1024)
        headers = ["state"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3

            assert len(batch.schema.fields) == len(headers)
            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_small_batch(self, employee_tsv):
        """Test reading TSV with small batch size."""
        csv = CsvDataSource(employee_tsv, None, True, 1)
        result = list(csv.scan([]))

        assert len(result) == 3  # 3 batches (1 row each)

        for batch in result:
            field = batch.field(0)
            assert field.size() == 1

    def test_read_tsv_with_no_header(self, employee_no_header_tsv):
        """Test reading TSV without headers."""
        csv = CsvDataSource(employee_no_header_tsv, None, False, 1024)
        result = list(csv.scan([]))
        headers = ["field_1", "field_2", "field_3", "field_4", "field_5", "field_6"]

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3

            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)

    def test_read_tsv_with_projections_and_no_header(self, employee_no_header_tsv):
        """Test reading TSV with projection and no headers."""
        csv = CsvDataSource(employee_no_header_tsv, None, False, 1024)
        headers = ["field_2", "field_4", "field_6"]
        result = list(csv.scan(headers))

        for batch in result:
            field = batch.field(0)
            assert field.size() == 3

            batch_headers = [f.name for f in batch.schema.fields]
            assert set(batch_headers) == set(headers)
