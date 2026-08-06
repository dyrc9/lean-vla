from __future__ import annotations

from scripts.run_four_arm_v4_l1_progress_projection_smoke import (
    _release_branch_gate,
)


def test_release_branch_gate_allows_valid_and_rejects_invalid() -> None:
    gate = _release_branch_gate()

    assert gate["passed"]
    valid = gate["valid_release"]["audit"]
    invalid = gate["invalid_release"]["audit"]
    assert valid["eligible_selected_source_candidate_index"] == 0
    assert invalid["eligible_selected_source_candidate_index"] is None
    assert invalid["fallback_for_fail_closed_recheck"]
