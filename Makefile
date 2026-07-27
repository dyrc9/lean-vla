.PHONY: sync test lean paper-artifacts paper-artifacts-check action-block-check m1-readiness-check semantic-v4-c5-check e1-selector-check e1-fallback-check e2-conditioning-check e3-checker-check e4-no-dispatch-check e5-effect-observer-check e6-resource-smoke-preflight-check e7-perception-preflight-check semantic-post-e5-readiness-check l2-interface-check check

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

check: test lean paper-artifacts-check action-block-check m1-readiness-check semantic-v4-c5-check e1-selector-check e1-fallback-check e2-conditioning-check e3-checker-check e4-no-dispatch-check e5-effect-observer-check e6-resource-smoke-preflight-check e7-perception-preflight-check e8-source-binding-check semantic-post-e5-readiness-check
