from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_risk_selective_scale45_replay_qualification import (
    OUTPUT_PATH,
    build_protocol,
)
from scripts.run_risk_selective_scale45_replay_qualification import (
    _partition_atoms,
    build_result,
)


def test_replay_atom_partition_keeps_only_physical_risk() -> None:
    physical, advisory = _partition_atoms(
        [
            "unexpected_contact_neighborhood:human_1",
            "close_outside_target_neighborhood",
            "workspace_exit",
        ]
    )

    assert physical == (
        "unexpected_contact_neighborhood:human_1",
        "workspace_exit",
    )
    assert advisory == ("close_outside_target_neighborhood",)


def test_risk_selective_replay_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    result = build_result(retained, protocol_path=OUTPUT_PATH)
    assert result["qualification_pass"] is True
    assert result["aggregate"][
        "successor_recovered_action_reject_count"
    ] == 43
    assert result["aggregate"][
        "successor_retained_physical_reject_count"
    ] == 6
    assert result["aggregate"][
        "successor_effect_replan_count"
    ] == 9
    assert result["counterfactual_success_rate_computed"] is False
