.PHONY: sync test lean demo experiments check export-libero

sync:
	uv sync --dev

test:
	uv run pytest

lean:
	cd lean && lake build ProofAlign

demo:
	uv run python -m proofalign.executor

experiments:
	uv run python -m proofalign.experiments --input examples/tasks --output results/toy

check: test lean demo experiments

export-libero:
	uv run python scripts/export_libero_safety.py --output examples/libero_safety_export
