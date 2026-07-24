.PHONY: sync test lean paper-artifacts paper-artifacts-check action-block-check m1-readiness-check check

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

check: test lean paper-artifacts-check action-block-check m1-readiness-check
