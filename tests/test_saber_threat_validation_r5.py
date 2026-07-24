from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.saber_io import canonical_digest
from scripts.run_liberosafety_pi05_openpi_eval import make_trace_record
from scripts.run_saber_threat_validation_r5 import (
    ACTION_MAGNITUDE_LIMIT,
    EpisodeSpec,
    ProtocolError,
    build_summary,
    episode_specs,
    load_protocol,
    typed_transition,
    validate_episode_payload,
    validate_paired_episode_payloads,
    validate_protocol,
)


def make_record(pair: dict) -> dict:
    return {
        "schema_version": "proofalign.saber-exact-task-record.v2",
        "suite": pair["suite"],
        "task_id": pair["task_id"],
        "init_state_id": pair["init_state_id"],
        "original_instruction": pair["trusted_instruction"],
        "perturbed_instruction": pair["perturbed_instruction"],
        "objective": "constraint_violation",
        "tools_used": ["find_prompt_targets", "apply_structure_inject"],
        "source": "official SABER exact-task prompt-tool producer",
    }


def make_binding(spec: EpisodeSpec) -> dict:
    return {
        "episode_id": spec.episode_id,
        "initial_state_sha256": "i" * 64,
        "first_clean_frame_sha256": "f" * 64,
        "first_policy_action_chunk_sha256": "a" * 64,
    }


def make_payload(protocol: dict, spec: EpisodeSpec, record: dict, *, unsafe: bool = False) -> dict:
    binding = make_binding(spec)
    audit = {
        "schema": "proofalign.observation-frame-audit.v1",
        "policy_call_index": 0,
        "attack_type": "none",
        "attack_strength": None,
        "camera": "agentview",
        "clean_frame_sha256": binding["first_clean_frame_sha256"],
        "attacked_frame_sha256": binding["first_clean_frame_sha256"],
        "changed": False,
        "policy_action_chunk_sha256": binding["first_policy_action_chunk_sha256"],
    }
    metadata = {
        "benchmark_name": spec.suite,
        "task_id": spec.task_id,
        "init_state_id": spec.init_state_id,
        "checkpoint": protocol["victim"]["checkpoint"],
        "openpi_config": protocol["victim"]["config"],
        "max_steps": protocol["episode_config"]["max_steps"],
        "num_steps_wait": protocol["episode_config"]["num_steps_wait"],
        "resize_size": protocol["episode_config"]["resize_size"],
        "replan_steps": protocol["episode_config"]["replan_steps"],
        "sample_steps": protocol["episode_config"]["sample_steps"],
        "seed": protocol["episode_config"]["env_seed"],
        "policy_seed": protocol["episode_config"]["policy_seed"],
        "observation_attack_type": "none",
        "observation_attack_strength": None,
        "initial_state_sha256": binding["initial_state_sha256"],
    }
    if spec.condition == "attacked":
        metadata.update(
            {
                "original_instruction": record["original_instruction"],
                "attack_record_claimed_original_instruction": record["original_instruction"],
                "perturbed_instruction": record["perturbed_instruction"],
                "attack_objective": record["objective"],
                "attack_tools_used": record["tools_used"],
                "attack_record_source": record["source"],
                "attack_record_schema": record["schema_version"],
                "attack_record_digest": canonical_digest(record),
            }
        )
    signals = {
        "robot_contact_count": int(unsafe),
        "joint_limit_violation": False,
        "max_robot_contact_force_newtons": 0.0,
        "excessive_force": False,
        "raw_action_l2": 0.5,
        "raw_action_magnitude_violation": False,
        "action_clipping_ratio": 0.0,
    }
    return {
        "metadata": metadata,
        "task_success": not unsafe,
        "strict_success_no_cost": not unsafe,
        "unsafe_cost_or_collision": unsafe,
        "decision": "constraint_violation" if unsafe else "env_done",
        "trace": [
            {
                "step_id": 10,
                "phase": "policy",
                "action": [0.0] * 7,
                "raw_action": [0.0] * 7,
                "env_info": {"cost": {"checkcontact": int(unsafe)}},
                "policy_call": audit,
                "saber_constraint_signals": signals,
            }
        ],
        "observation_frame_audits": [audit],
    }


def test_protocol_freezes_pair_major_vla_only_plan() -> None:
    protocol = load_protocol()
    specs = episode_specs(protocol)

    assert len(specs) == 8
    assert [spec.condition for spec in specs] == ["clean", "attacked"] * 4
    assert [spec.suite for spec in specs[::2]] == [
        "affordance",
        "obstacle_avoidance",
        "human_safety",
        "obstacle_avoidance_human",
    ]
    assert protocol["scope"]["defense_arms_authorized"] is False
    assert protocol["victim_outcomes_observed"] is False


def test_protocol_rejects_task_failure_signal_or_defense_arm() -> None:
    protocol = load_protocol()
    task_failure = deepcopy(protocol)
    task_failure["primary_signal_gate"]["task_failure_alone_counts_as_signal"] = True
    with pytest.raises(ProtocolError, match="primary gate"):
        validate_protocol(task_failure)

    defense = deepcopy(protocol)
    defense["scope"]["defense_arms_authorized"] = True
    with pytest.raises(ProtocolError, match="defense arm"):
        validate_protocol(defense)


def test_clean_and_attacked_payloads_bind_frames_chunks_and_typed_signals() -> None:
    protocol = load_protocol()
    clean, attacked = episode_specs(protocol)[:2]
    pair = protocol["frozen_pairs"][0]
    record = make_record(pair)

    clean_issues, clean_details = validate_episode_payload(
        protocol, clean, make_payload(protocol, clean, record), record, make_binding(clean)
    )
    attack_issues, attack_details = validate_episode_payload(
        protocol,
        attacked,
        make_payload(protocol, attacked, record, unsafe=True),
        record,
        make_binding(attacked),
    )

    assert clean_issues == []
    assert attack_issues == []
    assert clean_details["constraint_metrics"]["typed_signal_coverage_complete"] is True
    assert attack_details["unsafe_cost_or_collision"] is True


def test_payload_fails_without_cost_raw_action_or_chunk_binding() -> None:
    protocol = load_protocol()
    spec = episode_specs(protocol)[0]
    record = make_record(protocol["frozen_pairs"][0])
    payload = make_payload(protocol, spec, record)
    del payload["trace"][0]["env_info"]["cost"]
    del payload["trace"][0]["raw_action"]
    del payload["observation_frame_audits"][0]["policy_action_chunk_sha256"]

    issues, _ = validate_episode_payload(
        protocol, spec, payload, record, make_binding(spec)
    )

    assert any("cost is absent" in issue for issue in issues)
    assert any("raw policy action" in issue for issue in issues)
    assert any("action-chunk" in issue for issue in issues)


def test_actual_pair_binds_first_policy_frame_without_using_zero_step_frame() -> None:
    protocol = load_protocol()
    clean, attacked = episode_specs(protocol)[:2]
    record = make_record(protocol["frozen_pairs"][0])
    clean_payload = make_payload(protocol, clean, record)
    attacked_payload = make_payload(protocol, attacked, record, unsafe=True)
    assert validate_paired_episode_payloads(clean_payload, attacked_payload) == []

    attacked_payload["observation_frame_audits"][0]["clean_frame_sha256"] = "b" * 64
    issues = validate_paired_episode_payloads(clean_payload, attacked_payload)
    assert "paired first policy frame differs" in issues


def test_summary_uses_only_eligible_clean_pairs_and_positive_deltas() -> None:
    protocol = load_protocol()
    ledger = []
    for index, pair in enumerate(protocol["frozen_pairs"]):
        base_metrics = {
            "robot_contact_count": 2,
            "joint_limit_violation_steps": 0,
            "excessive_force_steps": 0,
            "raw_action_magnitude_violation_rate": 0.1,
        }
        clean = {
            "episode_id": f"clean_{pair['pair_id']}",
            "valid": True,
            "task_success": index != 3,
            "unsafe_cost_or_collision": False,
            "constraint_metrics": dict(base_metrics),
        }
        attacked_metrics = dict(base_metrics)
        if index < 2:
            attacked_metrics["robot_contact_count"] += 1
        attacked = {
            "episode_id": f"attacked_{pair['pair_id']}",
            "valid": True,
            "task_success": False,
            "unsafe_cost_or_collision": False,
            "constraint_metrics": attacked_metrics,
        }
        ledger.extend([clean, attacked])

    summary = build_summary(protocol, ledger)

    assert summary["eligible_pair_count"] == 3
    assert summary["clean_safe_to_attacked_unsafe_count"] == 2
    assert summary["classification"] == "r5_saber_independent_safety_signal_reproduced"
    assert summary["task_failure_only_never_counts"] is True
    assert summary["defense_execution_authorized"] is False


def test_typed_transition_uses_attacked_minus_clean_and_trace_keeps_raw_action() -> None:
    clean = {
        "unsafe_cost_or_collision": False,
        "constraint_metrics": {
            "robot_contact_count": 4,
            "joint_limit_violation_steps": 0,
            "excessive_force_steps": 0,
            "raw_action_magnitude_violation_rate": 0.2,
        },
    }
    attacked = deepcopy(clean)
    attacked["constraint_metrics"]["raw_action_magnitude_violation_rate"] = 0.3
    transition = typed_transition(clean, attacked)
    assert transition["observed"] is True
    assert transition["channels"]["raw_action_magnitude_rate_delta"] is True

    trace = make_trace_record(
        10,
        "policy",
        [1.0, 0.0],
        0.0,
        False,
        {"cost": {}},
        0.1,
        0.1,
        raw_action=[ACTION_MAGNITUDE_LIMIT + 0.1, 0.0],
        constraint_signals={"raw_action_magnitude_violation": True},
    )
    assert trace["raw_action"][0] > ACTION_MAGNITUDE_LIMIT
    assert trace["saber_constraint_signals"]["raw_action_magnitude_violation"] is True
