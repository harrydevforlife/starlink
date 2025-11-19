# PEP-8 Refactoring Plan: camelCase → snake_case

## 📋 Overview

Convert all camelCase variable names, function names, and method parameters to snake_case to comply with PEP-8 style guide.

## 🎯 Scope

### Files to Refactor

1. **logicalplan/**
   - `aggregate.py`: `groupExpr` → `group_expr`, `aggregateExpr` → `aggregate_expr`
   - `expressions.py`: Various camelCase in class attributes
   - `dataframe.py`: Method names and parameters
   - `scan.py`: `dataSource` → `data_source`, `projection` (already OK)
   - `select.py`: `input`, `expr` (already OK)
   - `projection.py`: `input`, `expr` (already OK)

2. **datasources/**
   - `csv.py`: `hasHeaders` → `has_headers`, `batchSize` → `batch_size`
   - `parquet.py`: `batch_size` (already OK)
   - `memory.py`: Check for camelCase
   - `datasource.py`: Interface methods

3. **datatypes/**
   - `arrow_field_vector.py`: `getType()` → `get_type()`, `getValue()` → `get_value()`
   - `arrow_vector_builder.py`: `setValueCount()` → `set_value_count()`
   - `record_batch.py`: `rowCount()` → `row_count()`, `columnCount()` → `column_count()`, `toCSV()` → `to_csv()`
   - `schema.py`: Check for camelCase
   - `literal_value_vector.py`: Check for camelCase

4. **physicalplan/**
   - `hashaggexec.py`: `groupExpr` → `group_expr`, `aggregateExpr` → `aggregate_expr`
   - `selectionexec.py`: Check for camelCase
   - `scanexec.py`: Check for camelCase
   - `projectionexec.py`: Check for camelCase
   - `expressions/`: All expression files

5. **optimizer/**
   - `optimizer.py`: Method names
   - `projection_pushdown.py`: Variable names

6. **queryplanner/**
   - `queryplanner.py`: Method names like `createPhysicalPlan()` → `create_physical_plan()`

7. **execution/**
   - `context.py`: Method names

8. **sql/**
   - `sql_parser.py`: Method names
   - `sql_planner.py`: Method names like `createDataFrame()` → `create_data_frame()`

## 📝 Naming Convention Changes

### Common Patterns

| Current (camelCase) | PEP-8 (snake_case) | Location |
|---------------------|-------------------|----------|
| `groupExpr` | `group_expr` | aggregate.py, hashaggexec.py |
| `aggregateExpr` | `aggregate_expr` | aggregate.py, hashaggexec.py |
| `hasHeaders` | `has_headers` | csv.py |
| `batchSize` | `batch_size` | csv.py, context.py |
| `dataSource` | `data_source` | scan.py |
| `getType()` | `get_type()` | arrow_field_vector.py |
| `getValue()` | `get_value()` | arrow_field_vector.py, record_batch.py |
| `setValueCount()` | `set_value_count()` | arrow_vector_builder.py |
| `rowCount()` | `row_count()` | record_batch.py |
| `columnCount()` | `column_count()` | record_batch.py |
| `toCSV()` | `to_csv()` | record_batch.py |
| `toField()` | `to_field()` | expressions.py |
| `createPhysicalPlan()` | `create_physical_plan()` | queryplanner.py |
| `createDataFrame()` | `create_data_frame()` | sql_planner.py |
| `createLogicalExpr()` | `create_logical_expr()` | sql_planner.py |
| `inputExpression()` | `input_expression()` | expressions/aggexpr.py |
| `createAccumulator()` | `create_accumulator()` | expressions/aggexpr.py |
| `finalValue()` | `final_value()` | expressions/expr.py |
| `_finalSchema()` | `_final_schema()` | csv.py |
| `_inferSchema()` | `_infer_schema()` | csv.py |
| `_detectDelimiter()` | `_detect_delimiter()` | csv.py |
| `_deriveSchema()` | `_derive_schema()` | scan.py |
| `_parseSelect()` | `_parse_select()` | sql_parser.py |
| `_parseExpr()` | `_parse_expr()` | sql_parser.py |
| `_parseExprList()` | `_parse_expr_list()` | sql_parser.py |
| `_parseIdentifier()` | `_parse_identifier()` | sql_parser.py |
| `_parseCast()` | `_parse_cast()` | sql_parser.py |
| `_parseOrder()` | `_parse_order()` | sql_parser.py |
| `planNonAggregateQuery()` | `plan_non_aggregate_query()` | sql_planner.py |
| `planAggregateQuery()` | `plan_aggregate_query()` | sql_planner.py |
| `isAggregateExpr()` | `is_aggregate_expr()` | sql_planner.py |
| `getReferencedColumns()` | `get_referenced_columns()` | sql_planner.py |
| `getColumnsReferencedBySelection()` | `get_columns_referenced_by_selection()` | sql_planner.py |
| `parseDataType()` | `parse_data_type()` | sql_planner.py |
| `registerCsv()` | `register_csv()` | context.py |
| `registerParquet()` | `register_parquet()` | context.py |
| `registerTable()` | `register_table()` | context.py |

## 🔄 Refactoring Strategy

### Phase 1: Analysis
1. ✅ Create comprehensive list of all camelCase names
2. ✅ Identify dependencies and usage patterns
3. ✅ Create mapping table (camelCase → snake_case)

### Phase 2: Core Data Types (Low-level)
1. `datatypes/arrow_field_vector.py`
2. `datatypes/arrow_vector_builder.py`
3. `datatypes/record_batch.py`
4. `datatypes/schema.py`
5. `datatypes/literal_value_vector.py`

### Phase 3: Data Sources
1. `datasources/csv.py`
2. `datasources/parquet.py`
3. `datasources/memory.py`
4. `datasources/datasource.py`

### Phase 4: Logical Plan
1. `logicalplan/expressions.py`
2. `logicalplan/aggregate.py`
3. `logicalplan/scan.py`
4. `logicalplan/dataframe.py`
5. `logicalplan/select.py`
6. `logicalplan/projection.py`

### Phase 5: Physical Plan
1. `physicalplan/expressions/` (all files)
2. `physicalplan/hashaggexec.py`
3. `physicalplan/selectionexec.py`
4. `physicalplan/scanexec.py`
5. `physicalplan/projectionexec.py`

### Phase 6: Query Planning & Optimization
1. `queryplanner/queryplanner.py`
2. `optimizer/optimizer.py`
3. `optimizer/projection_pushdown.py`

### Phase 7: Execution & SQL
1. `execution/context.py`
2. `sql/sql_parser.py`
3. `sql/sql_planner.py`

### Phase 8: Testing
1. Update all test files to use new names
2. Run full test suite
3. Fix any broken references

## ⚠️ Important Considerations

1. **Backward Compatibility**: Consider if we need to maintain old names temporarily
2. **Test Coverage**: Ensure all tests are updated
3. **Documentation**: Update docstrings if they reference old names
4. **Import Statements**: Update all import statements
5. **Type Hints**: Update type hints to use new names

## 🧪 Testing Strategy

1. After each phase, run relevant tests
2. Use grep to find any remaining camelCase references
3. Check for typos in new names
4. Verify all imports are updated

## 📊 Estimated Impact

- **Files to modify**: ~50+ files
- **Method renames**: ~100+ methods
- **Variable renames**: ~200+ variables
- **Test files to update**: ~20+ test files

## ✅ Success Criteria

1. All variable names use snake_case
2. All function/method names use snake_case
3. All tests pass
4. No camelCase remains (except in comments/docstrings referencing external APIs)
5. Code follows PEP-8 naming conventions

