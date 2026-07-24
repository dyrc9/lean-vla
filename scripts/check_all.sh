#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PROOFALIGN_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
LEAN_BIN="${PROOFALIGN_LEAN_BIN:-$PROJECT_ROOT/.tools/lean-4.24.0-linux/bin}"

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
"$PYTHON_BIN" scripts/generate_checker_equivalence_evidence.py --check
"$PYTHON_BIN" scripts/run_action_block_fixed_trace_gate.py --check
"$PYTHON_BIN" scripts/validate_m1_readiness.py --check
"$PYTHON_BIN" scripts/generate_saber_confirmatory_records.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/run_saber_confirmatory_victim.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/export_proofalign_fixed_trace.py --dry-run >/dev/null
(cd lean && PATH="$LEAN_BIN:$PATH" lake build ProofAlign)
