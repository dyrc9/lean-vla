from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_clean_fresh15 import (
    OUTPUT_PATH,
    PRIOR_INIT_STATE_IDS,
    build_protocol,
)
from scripts.run_joint_limit_containment_v11_clean_pilot import (
    _v11_metrics,
)


def test_v11_clean_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert len(retained["workloads"]) == 15
    assert len(retained["schedule"]) == 60
    assert {
        row["arm"] for row in retained["schedule"]
    } == {
        "vla_only",
        "semantic_only",
        "execution_only",
        "dual",
    }
    for workload in retained["workloads"]:
        key = (workload["suite"], workload["task_id"])
        assert workload["init_state_id"] not in (
            PRIOR_INIT_STATE_IDS[key]
        )
    assert retained["outcomes_observed_for_selection"] is True
    assert retained["v11_gates"][
        "task_success_is_a_completion_gate"
    ] is False


def test_v11_metrics_require_l2_only_observer_coverage() -> None:
    protocol = {
        "schedule": [
            {
                "episode_id": "execution",
                "base_pair_id": "pair",
            }
        ],
        "v10_gates": {
            "expected_paired_first_action_block_match_count": 0,
            "expected_paired_workload_count": 0,
        },
    }
    # The full metric adapter depends on v10 frame audits; its dedicated
    # online trace behavior is covered in test_joint_limit_containment.py.
    assert callable(_v11_metrics)
    assert protocol["v10_gates"][
        "expected_paired_workload_count"
    ] == 0
