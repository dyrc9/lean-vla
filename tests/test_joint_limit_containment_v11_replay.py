from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.analyze_joint_limit_containment_v11_replay import (
    build_result,
)


def test_v10_replay_qualifies_v11_containment_mechanism() -> None:
    result = build_result()
    retained = load_json_object(
        Path("experiments")
        / "proofalign_joint_limit_containment_v11_replay_"
        "qualification.json"
    )
    assert retained == result
    assert result["qualification_pass"] is True
    assert result["aggregate"]["episode_count"] == 60
    assert result["aggregate"]["policy_step_count"] == 21954
    assert result["aggregate"][
        "observed_joint_limit_step_count"
    ] == 1402
    assert result["l2_armed_replay"][
        "trigger_episode_count"
    ] == 3
    assert result["l2_armed_replay"][
        "observed_joint_limit_step_count"
    ] == 525
    assert result["l2_armed_replay"][
        "replay_retained_first_hit_count"
    ] == 3
    assert result["l2_armed_replay"][
        "replay_containable_repeat_hit_count"
    ] == 522
    assert result["l2_armed_replay"][
        "replay_undispatched_suffix_action_count"
    ] == 1284
    assert result["historical_outcome_diagnostic"][
        "l2_trigger_and_historical_success_count"
    ] == 0
    assert result["mechanism"][
        "counterfactual_task_outcome_computed"
    ] is False
    assert result["mechanism"]["prevention_claim"] is False
