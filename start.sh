#!/bin/bash

export PYTHONPATH=$(pwd)/src:$PYTHONPATH

PYTHONPATH=$(pwd)/src uv run python examples/query_sql.py

