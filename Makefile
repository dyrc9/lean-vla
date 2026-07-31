.PHONY: sync test lean paper-artifacts paper-artifacts-check action-block-check m1-readiness-check semantic-v4-c5-check e1-selector-check e1-fallback-check e2-conditioning-check e3-checker-check e4-no-dispatch-check e5-effect-observer-check e6-resource-smoke-preflight-check e7-perception-preflight-check semantic-post-e5-readiness-check l2-interface-check four-arm-v4-check four-arm-v4-exploratory-check v12-contract-check v12-simulator-preflight-check v12-recovery-successor-check v12-policy-shadow-check v12-integrated-recovery-check v12-hard-guard-check v13-clean-outcome-check v13-followup-check check

PYTHON ?= .venv/bin/python
UV ?= uv
LEAN_BIN ?= $(CURDIR)/.tools/lean-4.24.0-linux/bin

sync:
	$(UV) sync --dev

test:
	$(PYTHON) -m pytest

lean:
	cd lean && PATH="$(LEAN_BIN):$$PATH" lake build ProofAlign

paper-artifacts:
	@if [ -f results/saber_integrity_action_envelope_r9_20260723_fresh1/episodes_ledger.jsonl ]; then \
		$(PYTHON) scripts/generate_action_envelope_paper_artifacts.py; \
	else \
		echo "Cannot regenerate action-envelope artifacts: local-only R9 evidence is absent"; \
		exit 1; \
	fi
	@if [ -f external/LIBERO-Safety/libero/libero/benchmark/vla_safety_task_map.py ]; then \
		$(PYTHON) scripts/freeze_confirmatory_preregistration.py; \
	else \
		echo "Cannot regenerate preregistration: local-only LIBERO-Safety checkout is absent"; \
		exit 1; \
	fi

paper-artifacts-check:
	@if [ -f results/saber_integrity_action_envelope_r9_20260723_fresh1/episodes_ledger.jsonl ]; then \
		$(PYTHON) scripts/generate_action_envelope_paper_artifacts.py --check; \
	else \
		echo "Skipping action-envelope raw-artifact check: local-only R9 evidence is absent"; \
	fi
	@if [ -f external/LIBERO-Safety/libero/libero/benchmark/vla_safety_task_map.py ]; then \
		$(PYTHON) scripts/freeze_confirmatory_preregistration.py --check; \
	else \
		echo "Skipping confirmatory source check: local-only LIBERO-Safety checkout is absent"; \
	fi

action-block-check:
	$(PYTHON) scripts/run_action_block_fixed_trace_gate.py --check

m1-readiness-check:
	$(PYTHON) scripts/generate_checker_equivalence_evidence.py --check
	$(PYTHON) scripts/validate_m1_readiness.py --check
	$(PYTHON) scripts/generate_saber_confirmatory_records.py --dry-run >/dev/null
	$(PYTHON) scripts/run_saber_confirmatory_victim.py --dry-run >/dev/null
	$(PYTHON) scripts/export_proofalign_fixed_trace.py --dry-run >/dev/null

semantic-v4-c5-check:
	$(PYTHON) scripts/run_semantic_v4_fixed_trace_gate.py --check
	$(PYTHON) scripts/generate_semantic_v4_equivalence_evidence.py --check
	$(PYTHON) scripts/validate_semantic_v4_c5_readiness.py --check

e1-selector-check:
	$(PYTHON) scripts/validate_pi05_selector_qualification_e1.py >/dev/null

e1-fallback-check:
	$(PYTHON) scripts/validate_deterministic_selector_e1f.py >/dev/null

e2-conditioning-check:
	$(PYTHON) scripts/run_pi05_action_conditioning_e2.py --check >/dev/null

e3-checker-check:
	$(PYTHON) scripts/validate_local_checker_qualification_e3.py >/dev/null

e4-no-dispatch-check:
	$(PYTHON) scripts/run_semantic_no_dispatch_four_arm_e4.py --check >/dev/null

e5-effect-observer-check:
	$(PYTHON) scripts/run_semantic_effect_observer_qualification_e5.py --check >/dev/null

e6-resource-smoke-preflight-check:
	$(PYTHON) scripts/prepare_semantic_resource_smoke_e6.py --check
	$(PYTHON) scripts/run_semantic_resource_smoke_e6.py --check-state >/dev/null

e7-perception-preflight-check:
	$(PYTHON) scripts/run_deployment_perception_preflight_e7.py --check
	$(PYTHON) scripts/prepare_deployment_perception_dataset_e7.py --check-schema
	$(PYTHON) scripts/run_deployment_perception_dataset_qualification_e7.py --check-contract

e8-source-binding-check:
	$(PYTHON) scripts/generate_semantic_source_binding_e8.py --check

semantic-post-e5-readiness-check:
	$(PYTHON) scripts/validate_semantic_post_e5_readiness.py --check

l2-interface-check:
	$(PYTHON) -m pytest tests/test_execution_attack_relay.py tests/test_l2_interface_feasibility.py tests/test_l2_online_arm_runtime.py tests/test_semantic_online_runner.py
	$(PYTHON) scripts/run_l2_four_arm_identity_gate.py --check >/dev/null
	$(PYTHON) scripts/run_l2_execution_attack_eval.py --help >/dev/null

four-arm-v4-check:
	$(PYTHON) -m pytest tests/test_four_arm_v4.py
	$(PYTHON) scripts/freeze_four_arm_v4_successor_protocol.py --check
	$(PYTHON) scripts/run_proofalign_four_arm_v4.py --check
	$(PYTHON) scripts/analyze_proofalign_four_arm_v4.py --check-contract

four-arm-v4-exploratory-check:
	$(PYTHON) -m pytest tests/test_four_arm_v4_exploratory.py tests/test_four_arm_v4_support.py
	@if [ -f results/saber_confirmatory_victim_m2_20260727_fresh1/summary.json ]; then \
		$(PYTHON) scripts/freeze_four_arm_v4_exploratory40_successor.py --check; \
	else \
		echo "Skipping exploratory successor evidence check: local-only M2 terminal evidence is absent"; \
	fi
	$(PYTHON) scripts/run_proofalign_four_arm_v4_clean.py --help >/dev/null
	$(PYTHON) scripts/monitor_and_launch_four_arm_v4_clean.py --help >/dev/null
	$(PYTHON) scripts/run_proofalign_four_arm_v4_support45_clean.py --help >/dev/null
	$(PYTHON) scripts/monitor_and_launch_four_arm_v4_support45_clean.py --help >/dev/null
	$(PYTHON) scripts/freeze_four_arm_v4_support45_terminal.py --help >/dev/null
	@if [ -f results/proofalign_four_arm_v4_exploratory40_clean_20260727_fresh1/run_manifest.json ]; then \
		$(PYTHON) scripts/audit_four_arm_v4_semantic_support.py --check; \
	else \
		echo "Skipping semantic-support failure audit: local-only fresh1 failure is absent"; \
	fi
	@if [ -f experiments/proofalign_four_arm_v4_support45_successor.json ] && \
	    [ -f results/proofalign_four_arm_v4_exploratory40_clean_20260727_fresh1/run_manifest.json ]; then \
		$(PYTHON) scripts/freeze_four_arm_v4_support45_successor.py --check; \
	else \
		echo "Skipping support45 successor check: protocol or local-only failure evidence is absent"; \
	fi
	@if [ -f experiments/proofalign_four_arm_v4_support45_clean_terminal_summary.json ] && \
	    [ -f results/proofalign_four_arm_v4_support45_clean_20260727_fresh2/analysis.json ] && \
	    [ -f results/proofalign_four_arm_v4_support45_clean_launcher_20260727/clean_execution.log ]; then \
		$(PYTHON) scripts/freeze_four_arm_v4_support45_terminal.py --check; \
	else \
		echo "Skipping support45 terminal check: tracked summary or local-only evidence is absent"; \
	fi

v12-contract-check:
	$(PYTHON) scripts/freeze_recoverable_alignment_v12_contract_qualification.py --check
	@if [ -f results/proofalign_recoverable_alignment_v12_contract_qualification_20260729_fresh1/qualification.json ]; then \
		$(PYTHON) scripts/run_recoverable_alignment_v12_contract_qualification.py --check; \
		$(PYTHON) scripts/freeze_recoverable_alignment_v12_contract_terminal.py --check; \
	else \
		echo "Skipping v12 contract result check: local-only qualification evidence is absent"; \
	fi

v12-simulator-preflight-check:
	$(PYTHON) scripts/freeze_escape_recovery_v12_simulator_preflight.py --check
	@if [ -f results/proofalign_escape_recovery_v12_simulator_preflight_20260729_fresh1/summary.json ]; then \
		$(PYTHON) scripts/freeze_escape_recovery_v12_simulator_preflight_terminal.py --check; \
	else \
		echo "Skipping v12 simulator-preflight result check: local-only evidence is absent"; \
	fi

v12-recovery-successor-check:
	$(PYTHON) scripts/freeze_recovery_runtime_v12_fixed_trace.py --check
	$(PYTHON) scripts/run_recovery_runtime_v12_fixed_trace.py --check
	$(PYTHON) scripts/freeze_recovery_runtime_v12_fixed_trace_terminal.py --check
	$(PYTHON) scripts/freeze_prefix_recovery_v12_multijoint_qualification.py --check
	$(PYTHON) scripts/freeze_prefix_recovery_v12_multijoint_terminal.py --check
	$(PYTHON) scripts/freeze_recovery_snapshot_v12_qualification.py --check
	$(PYTHON) scripts/freeze_recovery_snapshot_v12_terminal.py --check

v12-policy-shadow-check:
	$(PYTHON) scripts/generate_fixed_policy_prefix_v12_corpus.py --check
	$(PYTHON) scripts/freeze_policy_prefix_shadow_v12_resource_failure.py --check
	$(PYTHON) scripts/freeze_fixed_policy_prefix_shadow_v12_qualification.py --check
	$(PYTHON) scripts/run_fixed_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
	$(PYTHON) scripts/freeze_fixed_policy_prefix_shadow_v12_terminal.py --check
	$(PYTHON) scripts/freeze_warmstart_policy_prefix_shadow_v12_qualification.py --check
	$(PYTHON) scripts/run_warmstart_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
	$(PYTHON) scripts/freeze_warmstart_policy_prefix_shadow_v12_terminal.py --check
	$(PYTHON) scripts/freeze_policy_prefix_shadow_v12_qualification.py --check
	$(PYTHON) scripts/run_policy_prefix_shadow_v12_qualification.py --validate-results >/dev/null
	$(PYTHON) scripts/freeze_policy_prefix_shadow_v12_terminal.py --check

v12-integrated-recovery-check:
	$(PYTHON) scripts/freeze_integrated_predictive_recovery_v12_fixed_trace.py --check
	$(PYTHON) scripts/run_integrated_predictive_recovery_v12_fixed_trace.py --validate-results >/dev/null
	$(PYTHON) scripts/freeze_integrated_predictive_recovery_v12_terminal.py --check

v12-hard-guard-check:
	$(PYTHON) scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py --validate-results >/dev/null
	$(PYTHON) scripts/run_h3_hard_virtual_joint_guard_beam_heldout_v12.py --validate-results >/dev/null

v13-clean-outcome-check:
	$(PYTHON) scripts/freeze_predictive_virtual_brake_v13_clean_fresh3.py --check
	@if [ -f results/proofalign_predictive_virtual_brake_v13_clean_20260731_fresh3/pilot_evidence.json ]; then \
		$(PYTHON) scripts/run_predictive_virtual_brake_v13_clean_fresh3.py --validate-results >/dev/null; \
		$(PYTHON) scripts/freeze_predictive_virtual_brake_v13_clean_terminal.py --check; \
	else \
		echo "Skipping v13 clean outcome result check: frozen rollout evidence is absent"; \
	fi

v13-followup-check:
	$(PYTHON) scripts/freeze_predictive_virtual_brake_v13_shadow_only.py --check
	$(PYTHON) scripts/freeze_predictive_virtual_brake_v13_attacked.py --check
	@if [ -f results/proofalign_predictive_virtual_brake_v13_shadow_only_20260731_fresh1/pilot_evidence.json ]; then \
		$(PYTHON) scripts/run_predictive_virtual_brake_v13_shadow_only.py --validate-results >/dev/null; \
	else \
		echo "Skipping v13 shadow-only result check: frozen rollout evidence is absent"; \
	fi
	@if [ -f results/proofalign_predictive_virtual_brake_v13_attacked_20260731_fresh1/pilot_evidence.json ]; then \
		$(PYTHON) scripts/run_predictive_virtual_brake_v13_attacked.py --validate-results >/dev/null; \
	else \
		echo "Skipping v13 attacked result check: frozen rollout evidence is absent"; \
	fi

check: test lean paper-artifacts-check action-block-check m1-readiness-check semantic-v4-c5-check e1-selector-check e1-fallback-check e2-conditioning-check e3-checker-check e4-no-dispatch-check e5-effect-observer-check e6-resource-smoke-preflight-check e7-perception-preflight-check e8-source-binding-check semantic-post-e5-readiness-check four-arm-v4-check four-arm-v4-exploratory-check v12-contract-check v12-simulator-preflight-check v12-recovery-successor-check v12-policy-shadow-check v12-integrated-recovery-check v12-hard-guard-check v13-clean-outcome-check v13-followup-check
