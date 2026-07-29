from __future__ import annotations

from scripts import (
    run_joint_limit_containment_v11_attacked_scale45 as scale,
)
from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_attacked_scale45 import (
    DEFAULT_PROTOCOL,
    build_protocol,
    build_schedule,
)
from scripts.run_physical_sufficiency_attacked_pilot import (
    M2_ATTACK_RECORDS_PATH,
)


def test_scale45_attack_transplants_cover_every_heldout_init() -> None:
    clean = load_json_object(
        "experiments/"
        "proofalign_joint_limit_containment_v11_clean_"
        "scale45_protocol.json"
    )
    source = load_json_object(M2_ATTACK_RECORDS_PATH)
    records = scale.derive_attack_transplants(clean, source)
    assert len(records) == 45
    assert len(
        {
            (row["suite"], row["task_id"], row["init_state_id"])
            for row in records
        }
    ) == 45
    assert all(
        row["transplant"]["prompt_text_changed"] is False
        for row in records
    )


def test_scale45_attacked_patch_uses_v11_runner_and_metrics() -> None:
    from scripts import run_l2_joint_limit_containment_v11 as online
    from scripts import run_physical_sufficiency_attacked_pilot as inherited

    original = inherited.validate_protocol
    with scale._patched_inherited():
        assert inherited.online is online
        assert inherited.base.online is online
        assert inherited.validate_protocol is scale.validate_protocol
        assert inherited.base._v10_metrics.__name__ == "_v11_metrics"
    assert inherited.validate_protocol is original


def test_attacked_scale45_schedule_is_exact_clean_pair() -> None:
    clean = load_json_object(
        "experiments/"
        "proofalign_joint_limit_containment_v11_clean_"
        "scale45_protocol.json"
    )
    attacked = build_schedule(clean)
    assert len(attacked) == 180
    assert all(
        row["base_pair_id"] == source["base_pair_id"]
        and row["arm"] == source["arm"]
        and row["environment_seed"] == source["environment_seed"]
        and row["policy_seed"] == source["policy_seed"]
        for row, source in zip(attacked, clean["schedule"])
    )


def test_attacked_scale45_protocol_is_current_when_present() -> None:
    if not DEFAULT_PROTOCOL.is_file():
        return
    retained = load_json_object(DEFAULT_PROTOCOL)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )
    assert retained == rebuilt
    assert len(retained["attack_records"]) == 45
    assert len(retained["schedule"]) == 180
    assert retained["selection"][
        "attacked_scale45_outcomes_observed_before_freeze"
    ] is False
