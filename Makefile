.PHONY: sync test lean paper-artifacts paper-artifacts-check check

PYTHON ?= .venv/bin/python
UV ?= uv

sync:
	$(UV) sync --dev

test:
	$(PYTHON) -m pytest

lean:
	cd lean && lake build ProofAlign

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

check: test lean paper-artifacts-check
