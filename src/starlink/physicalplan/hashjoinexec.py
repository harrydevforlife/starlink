from __future__ import annotations

from typing import Dict, Iterator, List, Sequence, Tuple

import pyarrow as pa

from starlink.datatypes.arrow_field_vector import ArrowFieldVector
from starlink.datatypes.record_batch import RecordBatch
from starlink.datatypes.schema import Schema
from starlink.physicalplan.physical import PhysicalPlan


class HashJoinExec(PhysicalPlan):
    """Physical hash join (inner join) using PyArrow arrays for column storage.
    
    Build a hash table from the left relation and probe the right relation using the hash table.
    If there are no matches, return an empty batch.
    """

    def __init__(
        self,
        left: PhysicalPlan,
        right: PhysicalPlan,
        left_on: List[str],
        right_on: List[str],
        schema: Schema,
        join_type: str = "inner",
    ):
        if len(left_on) != len(right_on):
            raise ValueError("left_on and right_on must have the same number of columns")
        if join_type.lower() != "inner":
            raise ValueError("Only INNER JOIN is currently supported")

        self.left = left
        self.right = right
        self.left_on = left_on
        self.right_on = right_on
        self._schema = schema

        self.left_schema = self.left.schema()
        self.right_schema = self.right.schema()
        self.join_type = join_type.lower()

        self.left_name_to_index = {field.name: idx for idx, field in enumerate(self.left_schema.fields)}
        self.right_name_to_index = {field.name: idx for idx, field in enumerate(self.right_schema.fields)}

        try:
            self.left_key_indices = [self.left_name_to_index[name] for name in self.left_on]
        except KeyError as exc:
            raise ValueError(f"Join column '{exc.args[0]}' not found in left relation") from exc

        try:
            self.right_key_indices = [self.right_name_to_index[name] for name in self.right_on]
        except KeyError as exc:
            raise ValueError(f"Join column '{exc.args[0]}' not found in right relation") from exc

        self.left_field_count = len(self.left_schema.fields)

    def schema(self) -> Schema:
        return self._schema

    def children(self) -> List[PhysicalPlan]:
        return [self.left, self.right]

    def execute(self) -> Sequence[RecordBatch]:
        def generator() -> Iterator[RecordBatch]:
            build_batches = list(self.left.execute())
            hash_table = self._build_hash_table(build_batches)
            emitted = False

            for probe_batch in self.right.execute():
                batch = self._probe(hash_table, build_batches, probe_batch)
                if batch is not None:
                    yield batch
                    emitted = True

            if not emitted:
                empty_columns = [
                    ArrowFieldVector(pa.array([], type=field.dataType))
                    for field in self._schema.fields
                ]
                yield RecordBatch(self._schema, empty_columns)

        return generator()

    def _build_hash_table(
        self, batches: List[RecordBatch]
    ) -> Dict[Tuple[object, ...], List[Tuple[int, int]]]:
        hash_table: Dict[Tuple[object, ...], List[Tuple[int, int]]] = {}

        for batch_idx, batch in enumerate(batches):
            key_arrays = [self._get_arrow_array(batch.field(i)) for i in self.left_key_indices]
            row_count = batch.row_count()
            for row_idx in range(row_count):
                key = self._build_key(key_arrays, row_idx)
                if key is None:
                    continue
                hash_table.setdefault(key, []).append((batch_idx, row_idx))
        return hash_table

    def _probe(
        self,
        hash_table: Dict[Tuple[object, ...], List[Tuple[int, int]]],
        build_batches: List[RecordBatch],
        probe_batch: RecordBatch,
    ) -> RecordBatch | None:
        key_arrays = [self._get_arrow_array(probe_batch.field(i)) for i in self.right_key_indices]
        probe_row_count = probe_batch.row_count()

        buffers: List[List[object]] = [[] for _ in self._schema.fields]

        for row_idx in range(probe_row_count):
            key = self._build_key(key_arrays, row_idx)
            if key is None:
                continue
            matches = hash_table.get(key)
            if not matches:
                continue
            for batch_idx, build_row_idx in matches:
                build_batch = build_batches[batch_idx]
                self._append_row(buffers, build_batch, build_row_idx, is_left=True)
                self._append_row(buffers, probe_batch, row_idx, is_left=False)

        if not buffers[0]:
            return None

        columns = []
        for values, field in zip(buffers, self._schema.fields):
            arr = pa.array(values, type=field.dataType)
            columns.append(ArrowFieldVector(arr))

        return RecordBatch(self._schema, columns)

    def _append_row(self, buffers: List[List[object]], batch: RecordBatch, row_idx: int, is_left: bool) -> None:
        offset = 0 if is_left else self.left_field_count
        schema = self.left_schema if is_left else self.right_schema
        for col_idx, _field in enumerate(schema.fields):
            value = batch.field(col_idx).get_value(row_idx)
            buffers[offset + col_idx].append(value)

    def _build_key(self, arrays: List[pa.Array], row_idx: int) -> Tuple[object, ...] | None:
        key_values = []
        for array in arrays:
            value = array[row_idx].as_py()
            if value is None:
                return None
            key_values.append(value)
        return tuple(key_values)

    def _get_arrow_array(self, column_vector):
        if not isinstance(column_vector, ArrowFieldVector):
            raise ValueError("HashJoinExec requires ArrowFieldVector columns")
        array = column_vector.field
        if isinstance(array, pa.ChunkedArray):
            array = array.combine_chunks()
        return array

    def __str__(self) -> str:
        return f"HashJoinExec: type={self.join_type}, left_on={self.left_on}, right_on={self.right_on}"

