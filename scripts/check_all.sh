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
"$PYTHON_BIN" scripts/freeze_recoverable_alignment_v12_contract_qualification.py --check
if [[ -f results/proofalign_recoverable_alignment_v12_contract_qualification_20260729_fresh1/qualification.json ]]; then
    "$PYTHON_BIN" scripts/run_recoverable_alignment_v12_contract_qualification.py --check
    "$PYTHON_BIN" scripts/freeze_recoverable_alignment_v12_contract_terminal.py --check
else
    echo "Skipping v12 contract result check: local-only qualification evidence is absent"
fi
"$PYTHON_BIN" scripts/freeze_escape_recovery_v12_simulator_preflight.py --check
if [[ -f results/proofalign_escape_recovery_v12_simulator_preflight_20260729_fresh1/summary.json ]]; then
    "$PYTHON_BIN" scripts/freeze_escape_recovery_v12_simulator_preflight_terminal.py --check
else
    echo "Skipping v12 simulator-preflight result check: local-only evidence is absent"
fi
"$PYTHON_BIN" scripts/freeze_recovery_runtime_v12_fixed_trace.py --check
"$PYTHON_BIN" scripts/run_recovery_runtime_v12_fixed_trace.py --check
"$PYTHON_BIN" scripts/freeze_recovery_runtime_v12_fixed_trace_terminal.py --check
"$PYTHON_BIN" scripts/freeze_prefix_recovery_v12_multijoint_qualification.py --check
"$PYTHON_BIN" scripts/freeze_prefix_recovery_v12_multijoint_terminal.py --check
"$PYTHON_BIN" scripts/freeze_recovery_snapshot_v12_qualification.py --check
"$PYTHON_BIN" scripts/freeze_recovery_snapshot_v12_terminal.py --check
"$PYTHON_BIN" scripts/generate_fixed_policy_prefix_v12_corpus.py --check
"$PYTHON_BIN" scripts/freeze_policy_prefix_shadow_v12_resource_failure.py --check
"$PYTHON_BIN" scripts/freeze_fixed_policy_prefix_shadow_v12_qualification.py --check
"$PYTHON_BIN" scripts/run_fixed_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/freeze_fixed_policy_prefix_shadow_v12_terminal.py --check
"$PYTHON_BIN" scripts/freeze_warmstart_policy_prefix_shadow_v12_qualification.py --check
"$PYTHON_BIN" scripts/run_warmstart_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/freeze_warmstart_policy_prefix_shadow_v12_terminal.py --check
"$PYTHON_BIN" scripts/freeze_policy_prefix_shadow_v12_qualification.py --check
"$PYTHON_BIN" scripts/run_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/freeze_policy_prefix_shadow_v12_terminal.py --check
"$PYTHON_BIN" scripts/freeze_integrated_predictive_recovery_v12_fixed_trace.py --check
"$PYTHON_BIN" scripts/run_integrated_predictive_recovery_v12_fixed_trace.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/freeze_integrated_predictive_recovery_v12_terminal.py --check
"$PYTHON_BIN" scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/run_h3_hard_virtual_joint_guard_beam_heldout_v12.py --validate-results >/dev/null
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_clean_fresh3.py --check
if [[ -f results/proofalign_predictive_virtual_brake_v13_clean_20260731_fresh3/pilot_evidence.json ]]; then
    "$PYTHON_BIN" scripts/run_predictive_virtual_brake_v13_clean_fresh3.py --validate-results >/dev/null
    "$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_clean_terminal.py --check
else
    echo "Skipping v13 clean outcome result check: frozen rollout evidence is absent"
fi
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_shadow_only.py --check
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_attacked.py --check
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_attacked_shadow_only.py --check
if [[ -f results/proofalign_predictive_virtual_brake_v13_shadow_only_20260731_fresh1/pilot_evidence.json ]]; then
    "$PYTHON_BIN" scripts/run_predictive_virtual_brake_v13_shadow_only.py --validate-results >/dev/null
else
    echo "Skipping v13 shadow-only result check: frozen rollout evidence is absent"
fi
if [[ -f results/proofalign_predictive_virtual_brake_v13_attacked_20260731_fresh1/pilot_evidence.json ]]; then
    "$PYTHON_BIN" scripts/run_predictive_virtual_brake_v13_attacked.py --validate-results >/dev/null
    "$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_attacked_terminal.py --check
else
    echo "Skipping v13 attacked result check: frozen rollout evidence is absent"
fi
if [[ -f results/proofalign_predictive_virtual_brake_v13_attacked_shadow_only_20260731_fresh1/pilot_evidence.json ]]; then
    "$PYTHON_BIN" scripts/run_predictive_virtual_brake_v13_attacked_shadow_only.py --validate-results >/dev/null
    "$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v13_attacked_shadow_terminal.py --check
else
    echo "Skipping v13 attacked shadow-only result check: frozen rollout evidence is absent"
fi
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v14_multijoint_clean.py --check
"$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v14_multijoint_clean_fresh2.py --check
if [[ -f results/proofalign_predictive_virtual_brake_v14_multijoint_clean_20260731_development1/run_manifest.json ]]; then
    "$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v14_multijoint_development1_failure.py --check
else
    echo "Skipping v14 development1 failure check: local-only failed root is absent"
fi
if [[ -f results/proofalign_predictive_virtual_brake_v14_multijoint_clean_20260731_development2/pilot_evidence.json ]]; then
    "$PYTHON_BIN" scripts/run_predictive_virtual_brake_v14_multijoint_clean_fresh2.py --validate-results >/dev/null
    "$PYTHON_BIN" scripts/freeze_predictive_virtual_brake_v14_multijoint_clean_terminal.py --check
else
    echo "Skipping v14 multijoint clean result check: local-only rollout evidence is absent"
fi
"$PYTHON_BIN" scripts/generate_saber_confirmatory_records.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/run_saber_confirmatory_victim.py --dry-run >/dev/null
"$PYTHON_BIN" scripts/export_proofalign_fixed_trace.py --dry-run >/dev/null
(cd lean && PATH="$LEAN_BIN:$PATH" lake build ProofAlign)
