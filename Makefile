
prepare:
	export PYTHONPATH=$$PYTHONPATH:$(shell pwd)/src

benchmark: prepare
	uv run python benchmark/benchmark_comparison_parquet.py --parquet data/tripdata/parquet --iterations 5

run-tests: prepare
	uv run pytest tests/

run-lint: prepare
	uv run ruff check src/starlink

sure-no-wrong: run-tests run-lint
	echo "No wrong"

