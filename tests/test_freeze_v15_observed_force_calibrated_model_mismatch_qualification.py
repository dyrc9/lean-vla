from __future__ import annotations

from proofalign.benchmark.confirmatory import load_json_object
from scripts import (
    freeze_v15_observed_force_calibrated_model_mismatch_qualification as freezer,
)
from scripts import (
    run_v15_observed_force_calibrated_model_mismatch_qualification as runner,
)


def test_frozen_protocol_is_current_when_present() -> None:
    if not freezer.OUTPUT_PATH.is_file():
        return
    protocol = load_json_object(freezer.OUTPUT_PATH)
    runner._verify_protocol(protocol)
    pairs = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in protocol["environments"]
    }
    old = load_json_object(freezer.OLD_MISMATCH_PROTOCOL)
    old_pairs = {
        (row["suite"], row["task_id"], row["init_state_id"])
        for row in old["environments"]
    }
    assert len(pairs) == 18
    assert pairs.isdisjoint(old_pairs)
    assert protocol["design"]["registered_force_thresholds_unchanged"] is True
