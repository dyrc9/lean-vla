from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_attacked_fresh15 import (
    DEFAULT_PROTOCOL,
    build_protocol,
)
from scripts.run_joint_limit_containment_v11_attacked_pilot import (
    _patched_inherited,
)


def test_v11_attacked_protocol_is_current_when_present() -> None:
    if not Path(DEFAULT_PROTOCOL).is_file():
        return
    retained = load_json_object(DEFAULT_PROTOCOL)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert len(retained["schedule"]) == 60
    assert len(retained["attack_records"]) == 15
    assert retained["selection"][
        "v11_attacked_outcomes_observed_before_freeze"
    ] is False
    assert retained["design"][
        "first_joint_limit_hit_counted"
    ] is True


def test_v11_attacked_patch_uses_v11_runner_and_metrics() -> None:
    from scripts import run_joint_limit_containment_v11_clean_pilot as clean
    from scripts import run_l2_joint_limit_containment_v11 as online
    from scripts import run_physical_sufficiency_attacked_pilot as inherited

    with _patched_inherited():
        assert inherited.online is online
        assert inherited.base.online is online
        assert inherited.base._v10_metrics is clean._v11_metrics
