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
"$PYTHON_BIN" scripts/run_semantic_v4_fixed_trace_gate.py --check
"$PYTHON_BIN" scripts/generate_semantic_v4_equivalence_evidence.py --check
"$PYTHON_BIN" scripts/validate_semantic_v4_c5_readiness.py --check
"$PYTHON_BIN" scripts/validate_pi05_selector_qualification_e1.py >/dev/null
"$PYTHON_BIN" scripts/validate_deterministic_selector_e1f.py >/dev/null
"$PYTHON_BIN" scripts/run_pi05_action_conditioning_e2.py --check >/dev/null
"$PYTHON_BIN" scripts/validate_local_checker_qualification_e3.py >/dev/null
"$PYTHON_BIN" scripts/run_semantic_no_dispatch_four_arm_e4.py --check >/dev/null
"$PYTHON_BIN" scripts/run_semantic_effect_observer_qualification_e5.py --check >/dev/null
"$PYTHON_BIN" scripts/prepare_semantic_resource_smoke_e6.py --check
"$PYTHON_BIN" scripts/run_semantic_resource_smoke_e6.py --check-state >/dev/null
"$PYTHON_BIN" scripts/run_deployment_perception_preflight_e7.py --check
"$PYTHON_BIN" scripts/prepare_deployment_perception_dataset_e7.py --check-schema
"$PYTHON_BIN" scripts/run_deployment_perception_dataset_qualification_e7.py --check-contract
"$PYTHON_BIN" scripts/generate_semantic_source_binding_e8.py --check
"$PYTHON_BIN" scripts/validate_semantic_post_e5_readiness.py --check
"$PYTHON_BIN" scripts/generate_saber_confirmatory_records.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/run_saber_confirmatory_victim.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/export_proofalign_fixed_trace.py --dry-run >/dev/null
(cd lean && PATH="$LEAN_BIN:$PATH" lake build ProofAlign)
