from __future__ import annotations

from scripts.run_deterministic_selector_qualification_e1f import (
    CASE_FAMILIES,
)
from scripts.validate_deterministic_selector_e1f import build_report


def test_deterministic_fallback_evidence_is_current_and_exact() -> None:
    evidence = build_report()

    assert evidence["valid"] is True
    assert evidence["classification"] == (
        "deterministic_fsm_fallback_gate_pass"
    )
    assert evidence["case_count"] == 10 * len(CASE_FAMILIES) == 160
    assert evidence["exact_match_rate"] == 1.0
    assert evidence["unknown_fail_closed_rate"] == 1.0
    assert evidence["qualified"] is True
    assert evidence["no_outcome_boundary"] == {
        "training_performed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_executed": False,
        "outcomes_read": False,
    }
