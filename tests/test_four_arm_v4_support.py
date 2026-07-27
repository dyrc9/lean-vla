from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from proofalign.benchmark.four_arm_v4 import validate_successor_protocol
from proofalign.benchmark.four_arm_v4_support import (
    SUPPORT_ANALYSIS_SCHEMA,
    build_support_clean_analysis,
    build_support_schedule,
    resolve_pair_bddl_path,
    summarize_supported_m2,
)
from scripts.monitor_and_launch_four_arm_v4_support45_clean import (
    qualified_gpu_indices,
)


ROOT = Path(__file__).resolve().parents[1]


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


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


def test_support_clean_analysis_uses_360_episode_population() -> None:
    confirmatory = load_json_object(
        ROOT / "experiments" / "saber_confirmatory_preregistration_v1.json"
    )
    design = load_json_object(
        ROOT
        / "experiments"
        / "proofalign_four_arm_v4_successor_protocol.json"
    )
    design = deepcopy(design)
    design["analysis"]["bootstrap_resamples"] = 100
    supported = [
        pair["base_pair_id"]
        for pair in confirmatory["frozen_base_pairs"]
        if pair["suite"] != "affordance"
    ]
    rows = []
    for spec in build_support_schedule(
        confirmatory,
        design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported,
    ):
        l1 = spec.arm in {"semantic_only", "dual"}
        l2 = spec.arm in {"execution_only", "dual"}
        rows.append(
            {
                "schema": "proofalign.four-arm-v4-ledger-row.v1",
                "protocol_id": design["protocol_id"],
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
                "l1_semantic_alignment": l1,
                "l2_execution_integrity": l2,
                "attempt_status": "valid",
                "issues": [],
                "episode_artifact_path": (
                    f"episodes/{spec.episode_id}.json"
                ),
                "episode_artifact_sha256": _digest(spec.episode_id),
                "initial_state_sha256": _digest(
                    f"state:{spec.unit.unit_id}"
                ),
                "initial_observation_digest": _digest(
                    f"obs:{spec.unit.unit_id}"
                ),
                "first_policy_action_chunk_sha256": _digest(
                    f"chunk:{spec.unit.unit_id}:l1={l1}"
                ),
                "first_policy_observation_digest": _digest(
                    f"policy-obs:{spec.unit.unit_id}"
                ),
                "exact_policy_prompt_digest": _digest(
                    f"prompt:{spec.unit.unit_id}:l1={l1}"
                ),
                "source_action_block_sha256": None,
                "source_assessment_sha256": None,
                "source_execution_contract_sha256": None,
                "task_success": True,
                "strict_success_no_cost": True,
                "unsafe_cost_or_collision": False,
                "phase_complete": True,
                "deadlock": False,
                "unknown_or_unbound": False,
                "decision": "env_done",
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
    protocol = {
        "protocol_id": (
            "proofalign-four-arm-v4-support45-clean-fresh2-20260727"
        ),
        "supported_base_pair_ids": supported,
    }

    analysis = build_support_clean_analysis(
        protocol,
        design=design,
        confirmatory=confirmatory,
        rows=rows,
        terminal=True,
        episode_artifacts_verified=True,
    )

    assert analysis["schema"] == SUPPORT_ANALYSIS_SCHEMA
    assert analysis["present_episode_count"] == 360
    assert analysis["valid_episode_count"] == 360
    assert analysis["expected_unit_count"] == 90
    assert analysis["classification"] == "support45_clean_gate_pass"
    assert analysis["clean_gate_pass"] is True


def test_support45_launcher_uses_two_least_busy_qualified_gpus() -> None:
    protocol = {
        "resource_budget": {
            "policy_gpu_count": 1,
            "egl_gpu_count": 1,
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive": (
                1024
            ),
        }
    }
    inventory = [
        {"index": 0, "memory_used_mib": 400},
        {"index": 1, "memory_used_mib": 1200},
        {"index": 2, "memory_used_mib": 100},
        {"index": 3, "memory_used_mib": 0},
    ]

    assert qualified_gpu_indices(protocol, inventory) == [3, 2]
