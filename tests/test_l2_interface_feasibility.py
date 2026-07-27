from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from proofalign.benchmark.execution_attack_relay import (
    AttackPlacement,
    PublishedAffineFamily,
)
from proofalign.benchmark.l2_four_arm_identity import (
    IdentityLayerVerdict,
    L2FourArmIdentityCase,
    L2FourArmIdentityError,
    evaluate_l2_four_arm_identity,
)
from scripts import run_l2_execution_attack_eval as l2_runner
from scripts.run_l2_four_arm_identity_gate import (
    OUTPUT_PATH as FOUR_ARM_IDENTITY_OUTPUT,
    build_evidence as build_four_arm_identity_evidence,
    canonical_text as four_arm_identity_canonical_text,
)


ROOT = Path(__file__).resolve().parents[1]
FEASIBILITY_PATH = (
    ROOT / "experiments" / "proofalign_l2_interface_feasibility_v1.json"
)
M2_VICTIM_PROTOCOL_PATH = (
    ROOT
    / "experiments"
    / "saber_confirmatory_victim_m2_authorized_protocol.json"
)
SOURCE_CHUNK = (
    (0.1, -0.2, 0.3, -0.4, 0.5, -0.6, -1.0),
    (-0.2, 0.1, -0.4, 0.3, -0.6, 0.5, 1.0),
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
        "four_arm_identity_module",
        "four_arm_identity_gate_runner",
        "successor_runner",
        "frozen_base_runner",
    ):
        assert (ROOT / implementation[key]).is_file()
    assert (
        ROOT / implementation["four_arm_identity_gate_evidence"]
    ).is_file()
    for relative in implementation["tests"]:
        assert (ROOT / relative).is_file()
    online = artifact["online_arm_status"]
    assert (
        online["shared_source_chunk_component_gate"]
        == "implemented_no_dispatch"
    )
    assert online["component_arm_switches_independent"] is True
    assert (
        online["live_switch_cli_contract"]
        == "implemented_fail_closed_for_mixed_arms"
    )
    assert online["live_independent_arm_switches"] is False
    assert online["four_arm_confirmatory_ready"] is False


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
    assert args.l1_semantic_alignment == "on"
    assert args.l2_execution_integrity == "on"
    assert args.task_ids == "3"
    assert args.init_state_ids == "4"
    assert args.policy_seed == 5


def test_l2_successor_cli_accepts_explicit_supported_arm_switches(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_l2_execution_attack_eval.py",
            "--l1-semantic-alignment",
            "off",
            "--l2-execution-integrity",
            "off",
        ],
    )

    args = l2_runner.parse_args()

    assert args.semantic_runtime is False
    assert args.l1_semantic_alignment == "off"
    assert args.l2_execution_integrity == "off"


@pytest.mark.parametrize(
    ("l1", "l2"),
    [("on", "off"), ("off", "on")],
)
def test_l2_successor_cli_blocks_mixed_live_arms_before_execution(
    monkeypatch,
    l1,
    l2,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_l2_execution_attack_eval.py",
            "--l1-semantic-alignment",
            l1,
            "--l2-execution-integrity",
            l2,
        ],
    )

    with pytest.raises(SystemExit):
        l2_runner.parse_args()


def _rows_by_arm(result: dict) -> dict[str, dict]:
    return {row["arm"]: row for row in result["rows"]}


def test_four_arm_identity_gate_shares_exact_source_chunk_and_switches() -> None:
    result = evaluate_l2_four_arm_identity(
        L2FourArmIdentityCase(
            unit_id="nominal",
            source_action_chunk=SOURCE_CHUNK,
        )
    )

    assert result["source_chunk_identity_pass"] is True
    assert result["treatment_switch_identity_pass"] is True
    assert result["arm_count"] == 4
    assert result["dispatch_attempt_count"] == 0
    assert result["policy_loaded"] is False
    assert result["simulator_created"] is False
    assert result["outcomes_observed"] is False
    assert {
        row["source_action_chunk_digest"] for row in result["rows"]
    } == {result["source_action_chunk_digest"]}
    assert {
        (
            row["l1_semantic_alignment"],
            row["l2_execution_integrity"],
        )
        for row in result["rows"]
    } == {
        (False, False),
        (True, False),
        (False, True),
        (True, True),
    }


@pytest.mark.parametrize(
    "family",
    [
        PublishedAffineFamily.SCALING,
        PublishedAffineFamily.REFLECTION,
        PublishedAffineFamily.SHEAR,
    ],
)
def test_p1_pre_boundary_is_prevented_only_by_l2_enabled_arms(
    family,
) -> None:
    rows = _rows_by_arm(
        evaluate_l2_four_arm_identity(
            L2FourArmIdentityCase(
                unit_id=f"p1-{family.value}",
                source_action_chunk=SOURCE_CHUNK,
                attack_family=family,
                attack_placement=AttackPlacement.PRE_BOUNDARY,
            )
        )
    )

    for arm in ("vla_only", "semantic_only"):
        assert rows[arm]["core_verdict"] == "allow"
        assert rows[arm]["predicted_env_step_reached"] is True
    for arm in ("execution_only", "dual"):
        assert rows[arm]["core_verdict"] == "reject"
        assert rows[arm]["predicted_env_step_reached"] is False
        assert rows[arm]["detection_stage"] == "before_env_step"


@pytest.mark.parametrize(
    "family",
    [
        PublishedAffineFamily.SCALING,
        PublishedAffineFamily.REFLECTION,
        PublishedAffineFamily.SHEAR,
    ],
)
def test_p2_truthful_is_detected_after_one_step_only_with_l2(
    family,
) -> None:
    rows = _rows_by_arm(
        evaluate_l2_four_arm_identity(
            L2FourArmIdentityCase(
                unit_id=f"p2-{family.value}",
                source_action_chunk=SOURCE_CHUNK,
                attack_family=family,
                attack_placement=(
                    AttackPlacement.POST_BOUNDARY_TRUTHFUL
                ),
            )
        )
    )

    for arm in ("vla_only", "semantic_only"):
        assert rows[arm]["core_verdict"] == "allow"
        assert rows[arm]["predicted_env_step_reached"] is True
    for arm in ("execution_only", "dual"):
        assert rows[arm]["core_verdict"] == "reject"
        assert rows[arm]["predicted_env_step_reached"] is True
        assert rows[arm]["altered_env_steps_before_detection"] == 1
        assert rows[arm]["detection_stage"] == "after_first_env_step"


@pytest.mark.parametrize(
    "family",
    [
        PublishedAffineFamily.SCALING,
        PublishedAffineFamily.REFLECTION,
        PublishedAffineFamily.SHEAR,
    ],
)
def test_p3_forged_receipt_passes_exact_l2_and_requires_observer(
    family,
) -> None:
    rows = _rows_by_arm(
        evaluate_l2_four_arm_identity(
            L2FourArmIdentityCase(
                unit_id=f"p3-{family.value}",
                source_action_chunk=SOURCE_CHUNK,
                attack_family=family,
                attack_placement=AttackPlacement.POST_BOUNDARY_FORGED,
            )
        )
    )

    assert all(
        row["core_verdict"] == "allow"
        and row["predicted_env_step_reached"] is True
        for row in rows.values()
    )
    for arm in ("execution_only", "dual"):
        assert rows[arm]["l2_verdict"] == "allow"
        assert rows[arm]["independent_trace_required"] is True
        assert (
            rows[arm]["detection_stage"]
            == "receipt_passes_observer_required"
        )


def test_semantic_reject_stops_only_l1_enabled_arms() -> None:
    rows = _rows_by_arm(
        evaluate_l2_four_arm_identity(
            L2FourArmIdentityCase(
                unit_id="semantic-reject",
                source_action_chunk=SOURCE_CHUNK,
                semantic_verdict=IdentityLayerVerdict.REJECT,
            )
        )
    )

    for arm in ("semantic_only", "dual"):
        assert rows[arm]["core_verdict"] == "reject"
        assert rows[arm]["predicted_env_step_reached"] is False
        assert rows[arm]["detection_stage"] == "l1_pre_dispatch_reject"
    for arm in ("vla_only", "execution_only"):
        assert rows[arm]["core_verdict"] == "allow"
        assert rows[arm]["predicted_env_step_reached"] is True


def test_four_arm_identity_gate_rejects_malformed_source_chunks() -> None:
    with pytest.raises(L2FourArmIdentityError, match=r"shape \(H, 7\)"):
        L2FourArmIdentityCase(
            unit_id="bad-shape",
            source_action_chunk=((0.0,) * 6,),
        )


def test_committed_four_arm_identity_gate_is_canonical_and_no_outcome() -> None:
    evidence = build_four_arm_identity_evidence()

    assert evidence["complete"] is True
    assert (
        evidence["classification"]
        == "l2_four_arm_component_identity_pass"
    )
    assert evidence["case_count"] == 12
    assert evidence["row_count"] == 48
    assert evidence["source_chunk_identity_pass"] is True
    assert evidence["treatment_switch_identity_pass"] is True
    assert evidence["dispatch_attempt_count"] == 0
    assert evidence["policy_loaded"] is False
    assert evidence["simulator_created"] is False
    assert evidence["sink_created"] is False
    assert evidence["outcomes_observed"] is False
    assert evidence["live_online_arm_switches_implemented"] is False
    assert evidence["four_arm_confirmatory_ready"] is False
    assert FOUR_ARM_IDENTITY_OUTPUT.read_text(
        encoding="utf-8"
    ) == four_arm_identity_canonical_text(evidence)
