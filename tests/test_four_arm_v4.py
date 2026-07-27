from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import (
    ARM_ORDER,
    ARM_SWITCHES,
    LEDGER_ROW_SCHEMA,
    FourArmV4Error,
    build_schedule,
    build_terminal_analysis,
    canonical_text,
    exact_mcnemar,
    holm_adjust,
    ledger_row_from_episode_payload,
    schedule_digest,
    validate_ledger_rows,
    validate_successor_protocol,
    verify_episode_artifacts,
)
from scripts.analyze_proofalign_four_arm_v4 import (
    DEFAULT_CONTRACT,
    build_contract_evidence,
)
from scripts.run_proofalign_four_arm_v4 import (
    DEFAULT_EVIDENCE,
    DEFAULT_PROTOCOL,
    FourArmV4OrchestrationError,
    build_dry_run_evidence,
    main as orchestration_main,
)


ROOT = Path(__file__).resolve().parents[1]


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def designs() -> tuple[dict, dict]:
    protocol = load_json_object(DEFAULT_PROTOCOL)
    confirmatory = validate_successor_protocol(
        protocol,
        repo_root=ROOT,
    )
    protocol = deepcopy(protocol)
    protocol["analysis"]["bootstrap_resamples"] = 2000
    return protocol, confirmatory


def _ledger(
    protocol: dict,
    confirmatory: dict,
    *,
    stage: str,
) -> list[dict]:
    rows = []
    for spec in build_schedule(
        confirmatory,
        protocol,
        stage=stage,
    ):
        l1_enabled, l2_enabled = ARM_SWITCHES[spec.arm]
        if stage == "B_clean_closed_loop":
            desirable = True
        else:
            desirable = spec.arm == "dual"
        rows.append(
            {
                "schema": LEDGER_ROW_SCHEMA,
                "protocol_id": protocol["protocol_id"],
                "episode_id": spec.episode_id,
                "sequence_index": spec.sequence_index,
                "stage": spec.stage,
                "condition": spec.condition,
                "arm": spec.arm,
                "unit_id": spec.unit.unit_id,
                "base_pair_id": spec.unit.base_pair_id,
                "seed_block_id": spec.unit.seed_block_id,
                "suite": spec.unit.suite,
                "task_id": spec.unit.task_id,
                "init_state_id": spec.unit.init_state_id,
                "env_seed": spec.unit.env_seed,
                "policy_seed": spec.unit.policy_seed,
                "l1_semantic_alignment": l1_enabled,
                "l2_execution_integrity": l2_enabled,
                "attempt_status": "valid",
                "issues": [],
                "episode_artifact_path": (
                    f"episodes/{spec.episode_id}.json"
                ),
                "episode_artifact_sha256": _digest(
                    f"artifact:{spec.episode_id}"
                ),
                "initial_state_sha256": _digest(
                    f"state:{spec.unit.unit_id}"
                ),
                "initial_observation_digest": _digest(
                    f"observation:{spec.unit.unit_id}"
                ),
                "first_policy_action_chunk_sha256": _digest(
                    f"chunk:{spec.unit.unit_id}:l1={l1_enabled}"
                ),
                "first_policy_observation_digest": _digest(
                    f"policy-observation:{spec.unit.unit_id}"
                ),
                "exact_policy_prompt_digest": _digest(
                    f"prompt:{spec.unit.unit_id}:l1={l1_enabled}"
                ),
                "source_action_block_sha256": (
                    _digest(f"fixed-block:{spec.unit.unit_id}")
                    if stage == "A_fixed_trace_shadow"
                    else None
                ),
                "source_assessment_sha256": (
                    _digest(f"fixed-assessment:{spec.unit.unit_id}")
                    if stage == "A_fixed_trace_shadow"
                    else None
                ),
                "source_execution_contract_sha256": (
                    _digest(f"fixed-contract:{spec.unit.unit_id}")
                    if stage == "A_fixed_trace_shadow"
                    else None
                ),
                "task_success": desirable,
                "strict_success_no_cost": desirable,
                "unsafe_cost_or_collision": False,
                "phase_complete": True,
                "deadlock": False,
                "unknown_or_unbound": False,
                "decision": "env_done" if desirable else "max_steps",
                "first_rejection_layer": None,
                "risk_metrics": {
                    "robot_contact_count": 0,
                    "joint_limit_violation_steps": 0,
                    "excessive_force_steps": 0,
                },
                "latency_metrics": {
                    "episode_wall_time_seconds": 1.0,
                    "policy_time_seconds": 0.4,
                    "env_step_time_seconds": 0.2,
                },
            }
        )
    return rows


def test_successor_protocol_is_current_and_does_not_overwrite_legacy() -> None:
    protocol = load_json_object(DEFAULT_PROTOCOL)
    confirmatory = validate_successor_protocol(
        protocol,
        repo_root=ROOT,
    )

    assert len(confirmatory["frozen_base_pairs"]) == 60
    assert protocol["outcomes_observed"] is False
    assert not any(protocol["execution_authorization"].values())
    assert protocol["identity_contract"][
        "counterfactual_action_chunk_replay_allowed"
    ] is False
    assert (
        ROOT
        / "experiments"
        / "proofalign_four_arm_preregistration_v1.json"
    ).is_file()


def test_schedule_is_balanced_and_frozen(designs) -> None:
    protocol, confirmatory = designs
    schedules = {
        stage: build_schedule(
            confirmatory,
            protocol,
            stage=stage,
        )
        for stage in (
            "A_fixed_trace_shadow",
            "B_clean_closed_loop",
            "C_attacked_closed_loop",
        )
    }

    for rows in schedules.values():
        assert len(rows) == 480
        assert len({row.unit.unit_id for row in rows}) == 120
        assert {
            arm: sum(row.arm == arm for row in rows)
            for arm in ARM_ORDER
        } == {arm: 120 for arm in ARM_ORDER}
        assert len(schedule_digest(rows)) == 64


def test_closed_loop_identity_is_within_l1_stratum_not_cross_l1(
    designs,
) -> None:
    protocol, confirmatory = designs
    rows = _ledger(
        protocol,
        confirmatory,
        stage="B_clean_closed_loop",
    )

    validate_ledger_rows(
        rows,
        confirmatory=confirmatory,
        protocol=protocol,
        stage="B_clean_closed_loop",
    )
    unit_rows = rows[:4]
    assert {
        row["first_policy_action_chunk_sha256"]
        for row in unit_rows
    } == {
        _digest(
            f"chunk:{unit_rows[0]['unit_id']}:l1=False"
        ),
        _digest(
            f"chunk:{unit_rows[0]['unit_id']}:l1=True"
        ),
    }

    broken = deepcopy(rows)
    row = next(
        row
        for row in broken
        if row["arm"] == "execution_only"
    )
    row["first_policy_action_chunk_sha256"] = _digest("substituted")
    with pytest.raises(FourArmV4Error, match="L2-paired"):
        validate_ledger_rows(
            broken,
            confirmatory=confirmatory,
            protocol=protocol,
            stage="B_clean_closed_loop",
        )


def test_fixed_trace_requires_exact_source_identity_across_arms(
    designs,
) -> None:
    protocol, confirmatory = designs
    rows = _ledger(
        protocol,
        confirmatory,
        stage="A_fixed_trace_shadow",
    )

    validate_ledger_rows(
        rows,
        confirmatory=confirmatory,
        protocol=protocol,
        stage="A_fixed_trace_shadow",
    )
    broken = deepcopy(rows)
    broken[0]["source_assessment_sha256"] = _digest(
        "different-assessment"
    )
    with pytest.raises(FourArmV4Error, match="fixed-trace"):
        validate_ledger_rows(
            broken,
            confirmatory=confirmatory,
            protocol=protocol,
            stage="A_fixed_trace_shadow",
        )


def test_clean_terminal_gate_passes_complete_synthetic_ledger(
    designs,
) -> None:
    protocol, confirmatory = designs
    rows = _ledger(
        protocol,
        confirmatory,
        stage="B_clean_closed_loop",
    )

    result = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage="B_clean_closed_loop",
        rows=rows,
        terminal=True,
        episode_artifacts_verified=True,
    )

    assert result["classification"] == "four_arm_clean_gate_pass"
    assert result["valid_episode_count"] == 480
    assert result["analysis"]["clean_gate_pass"] is True
    assert (
        result["analysis"]["dual_strict_success_retention"] == 1.0
    )
    assert (
        result["analysis"]["dual_minus_vla_strict_success"][
            "estimate"
        ]
        == 0.0
    )
    assert result["analysis"]["arm_descriptives"]["dual"][
        "task_success_rate_conservative"
    ] == 1.0
    assert result["analysis"]["arm_descriptives"]["dual"][
        "latency_metrics_valid_only_secondary"
    ]["episode_wall_time_seconds"]["valid_only_median"] == 1.0


def test_missing_or_invalid_rows_are_terminal_conservative(
    designs,
) -> None:
    protocol, confirmatory = designs
    rows = _ledger(
        protocol,
        confirmatory,
        stage="B_clean_closed_loop",
    )
    missing = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage="B_clean_closed_loop",
        rows=rows[:-1],
        terminal=True,
        episode_artifacts_verified=True,
    )
    assert (
        missing["classification"]
        == "four_arm_terminal_invalid_conservative"
    )
    assert missing["missing_episode_count"] == 1
    assert missing["analysis"]["clean_gate_pass"] is False

    invalid_rows = deepcopy(rows)
    invalid_rows[0]["attempt_status"] = "invalid"
    invalid_rows[0]["issues"] = ["runner_failure"]
    invalid = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage="B_clean_closed_loop",
        rows=invalid_rows,
        terminal=True,
        episode_artifacts_verified=True,
    )
    assert invalid["invalid_episode_count"] == 1
    assert invalid["analysis"]["clean_gate_pass"] is False


def test_ledger_adapter_binds_derivations_and_episode_artifact(
    designs,
) -> None:
    protocol, confirmatory = designs
    spec = build_schedule(
        confirmatory,
        protocol,
        stage="B_clean_closed_loop",
    )[0]
    l1_enabled, l2_enabled = ARM_SWITCHES[spec.arm]
    payload = {
        "metadata": {
            "benchmark_name": spec.unit.suite,
            "task_id": spec.unit.task_id,
            "init_state_id": spec.unit.init_state_id,
            "seed": spec.unit.env_seed,
            "policy_seed": spec.unit.policy_seed,
            "l1_semantic_alignment": l1_enabled,
            "l2_execution_integrity": l2_enabled,
            "four_arm_label": spec.arm,
            "initial_state_sha256": _digest("state"),
            "initial_execution_observation_digest": _digest(
                "initial-observation"
            ),
        },
        "task_success": True,
        "strict_success_no_cost": True,
        "unsafe_cost_or_collision": False,
        "decision": "env_done",
        "observation_frame_audits": [
            {
                "policy_action_chunk_sha256": _digest("chunk"),
                "policy_observation_digest": _digest(
                    "policy-observation"
                ),
                "exact_policy_prompt_digest": _digest("prompt"),
            }
        ],
        "trace": [
            {
                "phase": "policy",
                "runtime_seconds": {
                    "policy": 0.4,
                    "env_step": 0.2,
                },
                "saber_constraint_signals": {
                    "robot_contact_count": 2,
                    "joint_limit_violation": True,
                    "excessive_force": False,
                },
            }
        ],
        "runtime": {
            "episode_wall_time_seconds": 1.0,
        },
    }

    row = ledger_row_from_episode_payload(
        protocol,
        spec,
        payload,
        episode_artifact_path="episodes/example.json",
        episode_artifact_sha256=_digest("episode-artifact"),
    )

    assert row["attempt_status"] == "valid"
    assert row["phase_complete"] is True
    assert row["deadlock"] is False
    assert row["risk_metrics"] == {
        "robot_contact_count": 2,
        "joint_limit_violation_steps": 1,
        "excessive_force_steps": 0,
    }
    assert row["episode_artifact_sha256"] == _digest(
        "episode-artifact"
    )
    assert row["latency_metrics"] == {
        "episode_wall_time_seconds": 1.0,
        "policy_time_seconds": 0.4,
        "env_step_time_seconds": 0.2,
    }


def test_attacked_terminal_analysis_locks_composition_statistics(
    designs,
) -> None:
    protocol, confirmatory = designs
    clean = _ledger(
        protocol,
        confirmatory,
        stage="B_clean_closed_loop",
    )
    attacked = _ledger(
        protocol,
        confirmatory,
        stage="C_attacked_closed_loop",
    )

    result = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage="C_attacked_closed_loop",
        rows=attacked,
        clean_rows=clean,
        terminal=True,
        episode_artifacts_verified=True,
        clean_episode_artifacts_verified=True,
    )

    analysis = result["analysis"]
    assert (
        result["classification"]
        == "four_arm_attacked_terminal_analyzed"
    )
    assert analysis["desirable_outcome_rates"] == {
        "vla_only": 0.0,
        "semantic_only": 0.0,
        "execution_only": 0.0,
        "dual": 1.0,
    }
    assert analysis["composition_claim_pass"] is True
    assert all(
        row["holm_reject"]
        for row in analysis["composition_holm_family"]
    )
    assert analysis["arm_descriptives"]["vla_only"][
        "task_success_rate_conservative"
    ] == 0.0
    assert analysis["arm_descriptives"]["dual"][
        "task_success_rate_conservative"
    ] == 1.0


def test_attacked_analysis_is_blocked_by_nonpassing_clean_gate(
    designs,
) -> None:
    protocol, confirmatory = designs
    clean = _ledger(
        protocol,
        confirmatory,
        stage="B_clean_closed_loop",
    )
    for row in clean:
        if row["arm"] == "dual":
            row["task_success"] = False
            row["strict_success_no_cost"] = False
            row["phase_complete"] = False
            row["deadlock"] = True
            row["decision"] = "max_steps"
    attacked = _ledger(
        protocol,
        confirmatory,
        stage="C_attacked_closed_loop",
    )

    result = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage="C_attacked_closed_loop",
        rows=attacked,
        clean_rows=clean,
        terminal=True,
        episode_artifacts_verified=True,
        clean_episode_artifacts_verified=True,
    )

    assert result["classification"] == (
        "four_arm_attacked_blocked_clean_gate_nonpass"
    )
    assert result["clean_dependency_gate_pass"] is False
    assert (
        result["analysis"]["claims_enabled_by_clean_dependency"]
        is False
    )
    assert result["analysis"]["composition_claim_pass"] is False


def test_episode_artifact_verification_is_fail_closed(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "episodes" / "episode.json"
    artifact.parent.mkdir()
    artifact.write_text('{"ok": true}\\n', encoding="utf-8")
    row = {
        "episode_id": "episode",
        "episode_artifact_path": "episodes/episode.json",
        "episode_artifact_sha256": sha256(
            artifact.read_bytes()
        ).hexdigest(),
    }

    assert verify_episode_artifacts(
        [row],
        artifact_root=tmp_path,
    ) == 1
    broken = deepcopy(row)
    broken["episode_artifact_sha256"] = _digest("wrong")
    with pytest.raises(FourArmV4Error, match="digest differs"):
        verify_episode_artifacts(
            [broken],
            artifact_root=tmp_path,
        )


def test_exact_mcnemar_and_holm_are_deterministic() -> None:
    units = [
        {
            "outcomes": {
                "dual": index < 9,
                "semantic_only": False,
                "execution_only": index == 9,
            }
        }
        for index in range(10)
    ]
    comparison = exact_mcnemar(
        units,
        treatment="dual",
        control="semantic_only",
    )
    family = holm_adjust(
        [
            {"name": "a", "p_value": 0.01},
            {"name": "b", "p_value": 0.04},
        ],
        alpha=0.05,
    )

    assert comparison["treatment_only"] == 9
    assert comparison["control_only"] == 0
    assert comparison["p_value"] < 0.01
    assert family[0]["holm_adjusted_p_value"] == 0.02
    assert family[1]["holm_adjusted_p_value"] == 0.04
    assert all(row["holm_reject"] for row in family)


def test_committed_dry_run_and_analysis_contract_are_current() -> None:
    dry_run = build_dry_run_evidence()
    contract = build_contract_evidence()

    assert dry_run["complete"] is True
    assert dry_run["outcomes_observed"] is False
    assert all(
        row["execution_ready"] is False
        for row in dry_run["stages"]
    )
    assert DEFAULT_EVIDENCE.read_text(
        encoding="utf-8"
    ) == canonical_text(dry_run)
    assert contract["outcomes_observed"] is False
    assert DEFAULT_CONTRACT.read_text(
        encoding="utf-8"
    ) == canonical_text(contract)


def test_orchestrator_refuses_execution_without_successor_authority() -> None:
    with pytest.raises(
        FourArmV4OrchestrationError,
        match="authorizes no execution",
    ):
        orchestration_main([])
