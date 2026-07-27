from __future__ import annotations

import json
from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import validate_successor_protocol
from proofalign.benchmark.four_arm_v4_support import (
    build_support_schedule,
    resolve_pair_bddl_path,
    summarize_supported_m2,
)


ROOT = Path(__file__).resolve().parents[1]


def test_bddl_resolver_normalizes_hyphens(tmp_path: Path) -> None:
    path = (
        tmp_path
        / "external"
        / "LIBERO-Safety"
        / "libero"
        / "libero"
        / "bddl_files"
        / "human_safety"
        / "L2"
        / "place_on_hand-held_plate.bddl"
    )
    path.parent.mkdir(parents=True)
    path.write_text("(:goal (And (On object plate)))\n")
    pair = {
        "base_pair_id": "pair",
        "suite": "human_safety",
        "level": 2,
        "trusted_instruction": "place on hand held plate",
    }

    assert resolve_pair_bddl_path(
        pair,
        repo_root=tmp_path,
    ) == path


def test_support_schedule_is_frozen_subset() -> None:
    confirmatory = load_json_object(
        ROOT / "experiments" / "saber_confirmatory_preregistration_v1.json"
    )
    design = load_json_object(
        ROOT
        / "experiments"
        / "proofalign_four_arm_v4_successor_protocol.json"
    )
    validate_successor_protocol(design, repo_root=ROOT)
    supported = [
        pair["base_pair_id"]
        for pair in confirmatory["frozen_base_pairs"]
        if pair["suite"] != "affordance"
    ]

    schedule = build_support_schedule(
        confirmatory,
        design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported,
    )

    assert len(schedule) == 360
    assert len({spec.unit.unit_id for spec in schedule}) == 90
    assert {spec.unit.base_pair_id for spec in schedule} == set(supported)
    assert [spec.sequence_index for spec in schedule] == list(
        range(1, 361)
    )


def test_supported_m2_summary_uses_only_eligible_pairs() -> None:
    summary = {
        "units": [
            {
                "base_pair_id": "a",
                "clean_eligible": True,
                "transition_observed": True,
            },
            {
                "base_pair_id": "a",
                "clean_eligible": True,
                "transition_observed": False,
            },
            {
                "base_pair_id": "b",
                "clean_eligible": False,
                "transition_observed": False,
            },
            {
                "base_pair_id": "b",
                "clean_eligible": True,
                "transition_observed": True,
            },
            {
                "base_pair_id": "excluded",
                "clean_eligible": True,
                "transition_observed": False,
            },
        ]
    }

    result = summarize_supported_m2(
        summary,
        supported_base_pair_ids=["a", "b"],
        resamples=100,
        seed=7,
    )

    assert result["unit_count"] == 4
    assert result["clean_eligible_unit_count"] == 3
    assert result["transition_unit_count"] == 2
    assert result["transition_rate"] == 2 / 3
    assert result["cluster_bootstrap_interval_95"]["resamples"] == 100
