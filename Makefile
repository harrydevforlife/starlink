
prepare:
	export PYTHONPATH=$$PYTHONPATH:$(shell pwd)/src

benchmark: prepare
	uv run python benchmark/benchmark_comparison_parquet.py --parquet data/tripdata/parquet --iterations 5

run-tests: prepare
	uv run pytest tests/

run-coverage: prepare
	uv run pytest --cov=src/starlink tests/

run-coverage-html: prepare
	uv run pytest --cov=src/starlink tests/ --cov-report=html
