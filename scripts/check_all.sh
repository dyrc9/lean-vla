#!/usr/bin/env bash
set -euo pipefail

uv run pytest
(cd lean && lake build ProofAlign)
uv run python -m proofalign.executor
uv run python -m proofalign.experiments --input examples/tasks --output results/toy
