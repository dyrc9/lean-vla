from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_terminal import (
    OUTPUT_PATH,
    build_summary,
)


def test_v11_terminal_summary_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    assert retained == build_summary()
    assert retained["mechanism_decision"][
        "mechanical_containment_verified"
    ] is True
    assert retained["mechanism_decision"][
        "observed_trigger_count"
    ] == 16
    assert retained["mechanism_decision"][
        "observed_post_trigger_dispatch_count"
    ] == 0
    assert retained["conditions"]["clean"]["by_arm"][
        "vla_only"
    ]["joint_limit_step_count"] == 884
    assert retained["conditions"]["clean"]["by_arm"][
        "execution_only"
    ]["joint_limit_step_count"] == 6
    assert retained["conditions"]["attacked"]["by_arm"][
        "semantic_only"
    ]["joint_limit_step_count"] == 462
    assert retained["conditions"]["attacked"]["by_arm"][
        "dual"
    ]["joint_limit_step_count"] == 3
    assert retained["mechanism_decision"][
        "first_hit_prevention_claim"
    ] is False
