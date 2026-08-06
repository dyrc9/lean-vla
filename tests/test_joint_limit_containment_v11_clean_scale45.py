from __future__ import annotations

from collections import Counter
from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_clean_fresh15 import (
    PRIOR_INIT_STATE_IDS,
)
from scripts.freeze_joint_limit_containment_v11_clean_scale45 import (
    DEVELOPMENT_PROTOCOL_PATH,
    OUTPUT_PATH,
    build_protocol,
    derive_workloads,
)
from scripts.run_joint_limit_containment_v11_clean_scale45 import (
    _patched_inherited,
)


def test_scale45_selection_is_distinct_and_held_out() -> None:
    development = load_json_object(DEVELOPMENT_PROTOCOL_PATH)
    workloads = derive_workloads(development)
    development_ids = {
        (row["suite"], row["task_id"]): row["init_state_id"]
        for row in development["workloads"]
    }
    assert len(workloads) == 45
    assert len(
        {
            (row["suite"], row["task_id"], row["init_state_id"])
            for row in workloads
        }
    ) == 45
    assert Counter(
        (row["suite"], row["task_id"]) for row in workloads
    ) == {
        (suite, task_id): 3
        for suite, task_id in PRIOR_INIT_STATE_IDS
    }
    for workload in workloads:
        key = (workload["suite"], workload["task_id"])
        assert workload["init_state_id"] not in (
            PRIOR_INIT_STATE_IDS[key]
        )
        assert workload["init_state_id"] != development_ids[key]


def test_scale45_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert len(retained["workloads"]) == 45
    assert len(retained["schedule"]) == 180
    assert Counter(row["arm"] for row in retained["schedule"]) == {
        "vla_only": 45,
        "semantic_only": 45,
        "execution_only": 45,
        "dual": 45,
    }
    assert retained["selection"][
        "method_or_threshold_changed_after_fresh15"
    ] is False
    assert retained["v11_gates"][
        "task_success_is_a_completion_gate"
    ] is False


def test_scale45_runner_uses_frozen_v11_online_path() -> None:
    from scripts import run_l2_joint_limit_containment_v11 as online
    from scripts import run_physical_sufficiency_clean_pilot as inherited

    with _patched_inherited(protocol_path=OUTPUT_PATH):
        assert inherited.online is online
        assert inherited._v10_metrics.__name__ == "_v11_metrics"
        assert inherited.DEFAULT_PROTOCOL == OUTPUT_PATH.resolve()
