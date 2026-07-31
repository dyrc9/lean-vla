from __future__ import annotations

from scripts import freeze_predictive_virtual_brake_v13_clean_terminal as terminal


def test_v13_clean_terminal_recomputes_and_bounds_claim() -> None:
    payload = terminal.build_terminal()

    assert payload["terminal"] is True
    assert payload["episode_count"] == 180
    assert payload["clean_utility_gate_passed"] is True
    assert payload["attacked_stage_authorized"] is True
    assert payload["confirmatory_claim_authorized"] is False
    assert payload["failed_gates"] == []
    assert payload["by_arm"]["vla_only"]["task_success_count"] == 36
    assert payload["by_arm"]["execution_only"][
        "task_success_count"
    ] == 36
    assert payload["by_arm"]["semantic_only"][
        "task_success_count"
    ] == 32
    assert payload["by_arm"]["dual"]["task_success_count"] == 31
    assert payload["mechanism"]["trigger_count"] == 1
    assert payload["mechanism"]["intervention_count"] == 0
    assert payload["mechanism"]["deadlock_count"] == 1
    assert payload["next_experiments"][
        "shadow_only_ablation_required"
    ] is True
    assert payload["next_experiments"][
        "targeted_trigger_population_required"
    ] is True
