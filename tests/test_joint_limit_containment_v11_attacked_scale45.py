from __future__ import annotations

from scripts import (
    run_joint_limit_containment_v11_attacked_scale45 as scale,
)
from proofalign.benchmark.confirmatory import load_json_object
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
