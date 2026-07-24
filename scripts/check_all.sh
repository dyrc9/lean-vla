#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROOFALIGN_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"

cd "$PROJECT_ROOT"
"$PYTHON_BIN" -m pytest
if [[ -f results/saber_integrity_action_envelope_r9_20260723_fresh1/episodes_ledger.jsonl ]]; then
    "$PYTHON_BIN" scripts/generate_action_envelope_paper_artifacts.py --check
else
    echo "Skipping action-envelope raw-artifact check: local-only R9 evidence is absent"
fi
if [[ -f external/LIBERO-Safety/libero/libero/benchmark/vla_safety_task_map.py ]]; then
    "$PYTHON_BIN" scripts/freeze_confirmatory_preregistration.py --check
else
    echo "Skipping confirmatory source check: local-only LIBERO-Safety checkout is absent"
fi
(cd lean && lake build ProofAlign)
