from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

from proofalign.benchmark.execution_attack_relay import (
    AttackPlacement,
    PublishedAffineFamily,
)
from scripts import run_l2_execution_attack_eval as l2_runner


ROOT = Path(__file__).resolve().parents[1]
FEASIBILITY_PATH = (
    ROOT / "experiments" / "proofalign_l2_interface_feasibility_v1.json"
)
M2_VICTIM_PROTOCOL_PATH = (
    ROOT
    / "experiments"
    / "saber_confirmatory_victim_m2_authorized_protocol.json"
)


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_l2_feasibility_artifact_matches_implemented_enums_and_paths() -> None:
    artifact = _read_json(FEASIBILITY_PATH)

    assert artifact["status"] == "engineering_only_no_outcome"
    assert artifact["frozen_before_l2_rollout_outcomes"] is True
    assert artifact["current_mainline_unchanged"] == {
        "m2_episode_count": 240,
        "m2_population_changed": False,
        "m2_attack_records_changed": False,
        "m2_thresholds_changed": False,
    }
    assert set(artifact["attack_families"]) == {
        family.value
        for family in PublishedAffineFamily
        if family is not PublishedAffineFamily.NONE
    }
    assert set(artifact["placements"]) == {
        placement.value for placement in AttackPlacement
    }
    implementation = artifact["implementation"]
    for key in (
        "attack_module",
        "successor_runner",
        "frozen_base_runner",
    ):
        assert (ROOT / implementation[key]).is_file()
    for relative in implementation["tests"]:
        assert (ROOT / relative).is_file()


def test_l2_successor_keeps_the_m2_base_runner_byte_identical() -> None:
    artifact = _read_json(FEASIBILITY_PATH)
    protocol = _read_json(M2_VICTIM_PROTOCOL_PATH)
    relative = artifact["implementation"]["frozen_base_runner"]

    assert artifact["implementation"]["frozen_base_runner_modified"] is False
    assert _sha256(ROOT / relative) == protocol["source"]["sha256"][relative]


def test_l2_successor_cli_dry_parse_exposes_all_attack_switches(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_l2_execution_attack_eval.py",
            "--execution-attack-family",
            "ueda_blevins_shear",
            "--execution-attack-placement",
            "post_boundary_forged",
            "--semantic-runtime",
            "--task-ids",
            "3",
            "--init-state-ids",
            "4",
            "--policy-seed",
            "5",
        ],
    )

    args = l2_runner.parse_args()

    assert args.execution_attack_family == "ueda_blevins_shear"
    assert args.execution_attack_placement == "post_boundary_forged"
    assert args.semantic_runtime is True
    assert args.task_ids == "3"
    assert args.init_state_ids == "4"
    assert args.policy_seed == 5
