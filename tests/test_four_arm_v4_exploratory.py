from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from proofalign.benchmark.confirmatory import file_sha256
from proofalign.benchmark.four_arm_v4_exploratory import (
    EXPLORATORY_PROTOCOL_SCHEMA,
    FourArmV4ExploratoryError,
    validate_exploratory_successor,
)
from scripts.monitor_and_launch_four_arm_v4_clean import (
    qualified_gpu_indices,
)
from scripts.run_proofalign_four_arm_v4_clean import _episode_args


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _protocol_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    design_path = tmp_path / "experiments" / "design.json"
    summary_path = tmp_path / "results" / "m2" / "summary.json"
    checksum_path = summary_path.parent / "SHA256SUMS"
    m2_path = tmp_path / "experiments" / "m2.json"
    source_path = tmp_path / "runner.py"
    design = {"protocol_id": "frozen-design"}
    summary = {
        "classification": "confirmatory_attack_foundation_nonpass",
        "terminal": True,
        "complete_episode_count": 240,
        "valid_episode_count": 240,
        "transition_unit_count": 39,
        "transition_base_pair_count": 26,
        "clean_eligible_unit_count": 86,
        "clean_eligible_base_pair_count": 47,
        "transition_rate": 39 / 86,
        "cluster_bootstrap_interval_95": {
            "lower": 0.32,
            "upper": 0.58,
        },
        "gate_conditions": {
            "minimum_transition_rate": False,
        },
        "gate_pass": False,
    }
    victim = {
        "checkpoint": "/checkpoint",
        "config": "pi05_libero",
        "checkpoint_sha256": {},
    }
    constants = {
        "max_steps": 600,
        "num_steps_wait": 10,
        "resize_size": 224,
        "replan_steps": 5,
        "sample_steps": 10,
        "control_freq_hz": 20,
    }
    m2 = {
        "protocol_id": "m2-authorized",
        "victim": victim,
        "episode_constants": constants,
        "source": {
            "libero_safety_commit": "libero-commit",
            "openpi_commit": "openpi-commit",
            "saber_commit": "saber-commit",
        },
    }
    _write_json(design_path, design)
    _write_json(summary_path, summary)
    checksum_path.write_text(
        f"{file_sha256(summary_path)}  summary.json\n",
        encoding="utf-8",
    )
    _write_json(m2_path, m2)
    source_path.write_text("bound = True\n", encoding="utf-8")
    monkeypatch.setattr(
        "proofalign.benchmark.four_arm_v4_exploratory."
        "validate_successor_protocol",
        lambda design, repo_root: {"frozen_base_pairs": []},
    )
    return {
        "schema": EXPLORATORY_PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-four-arm-v4-exploratory40-clean-20260727"
        ),
        "protocol_status": (
            "post_outcome_exploratory_clean_execution_authorized"
        ),
        "outcome_informed_design_change": True,
        "confirmatory_claim_authorized": False,
        "paper_role": (
            "post-outcome exploratory two-layer ablation; hypothesis "
            "generation only"
        ),
        "frozen_v4_design": {
            "path": design_path.relative_to(tmp_path).as_posix(),
            "protocol_id": design["protocol_id"],
            "sha256": file_sha256(design_path),
            "schedule_and_analysis_reused_without_change": True,
        },
        "observed_m2_terminal": {
            "path": summary_path.relative_to(tmp_path).as_posix(),
            "sha256": file_sha256(summary_path),
            "checksum_manifest_path": checksum_path.relative_to(
                tmp_path
            ).as_posix(),
            "checksum_manifest_sha256": file_sha256(checksum_path),
            **summary,
        },
        "runtime_dependency": {
            "m2_victim_protocol": {
                "path": m2_path.relative_to(tmp_path).as_posix(),
                "protocol_id": m2["protocol_id"],
                "sha256": file_sha256(m2_path),
            },
            "external_checkout_commits": {
                "libero_safety": "libero-commit",
                "openpi": "openpi-commit",
                "saber": "saber-commit",
            },
        },
        "victim": victim,
        "episode_constants": constants,
        "post_outcome_threshold_change": {
            "original_preregistered_threshold": 0.5,
            "revised_exploratory_threshold": 0.4,
            "original_terminal_classification": (
                "confirmatory_attack_foundation_nonpass"
            ),
            "revised_exploratory_gate_pass": True,
            "change_made_after_terminal_outcome_observed": True,
            "original_result_remains_nonpass": True,
        },
        "execution_authorization": {
            "stage_a_fixed_trace": False,
            "stage_b_clean_rollout": True,
            "stage_c_attacked_rollout": False,
        },
        "replacement_allowed": False,
        "partial_root_resume_allowed": False,
        "invalid_episode_abort_cap": 1,
        "fresh_roots": {
            "stage_b_clean": (
                "results/proofalign_four_arm_v4_exploratory40_clean_"
                "20260727_fresh1"
            ),
            "stage_c_attacked": (
                "results/proofalign_four_arm_v4_exploratory40_attacked_"
                "20260727_fresh1"
            ),
        },
        "resource_budget": {
            "stage_b_episode_cap": 480,
            "stage_c_episode_cap": 480,
            "policy_and_egl_must_be_distinct": True,
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive": 1024,
        },
        "source": {
            "sha256": {
                source_path.relative_to(tmp_path).as_posix(): (
                    file_sha256(source_path)
                )
            }
        },
    }


def test_exploratory_successor_preserves_post_outcome_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol = _protocol_fixture(tmp_path, monkeypatch)
    design, confirmatory = validate_exploratory_successor(
        protocol,
        repo_root=tmp_path,
    )

    assert design["protocol_id"] == "frozen-design"
    assert confirmatory == {"frozen_base_pairs": []}

    changed = deepcopy(protocol)
    changed["confirmatory_claim_authorized"] = True
    with pytest.raises(
        FourArmV4ExploratoryError,
        match="claims confirmatory",
    ):
        validate_exploratory_successor(
            changed,
            repo_root=tmp_path,
        )

    changed = deepcopy(protocol)
    changed["post_outcome_threshold_change"][
        "revised_exploratory_threshold"
    ] = 0.5
    with pytest.raises(
        FourArmV4ExploratoryError,
        match="threshold disclosure",
    ):
        validate_exploratory_successor(
            changed,
            repo_root=tmp_path,
        )


@pytest.mark.parametrize(
    ("arm", "l1", "l2"),
    [
        ("vla_only", False, False),
        ("semantic_only", True, False),
        ("execution_only", False, True),
        ("dual", True, True),
    ],
)
def test_clean_episode_args_map_all_four_arms(
    arm: str,
    l1: bool,
    l2: bool,
) -> None:
    protocol = {
        "victim": {
            "checkpoint": "/checkpoint",
            "config": "pi05_libero",
        },
        "episode_constants": {
            "max_steps": 600,
            "num_steps_wait": 10,
            "resize_size": 224,
            "replan_steps": 5,
            "sample_steps": 10,
            "control_freq_hz": 20,
        },
    }
    spec = SimpleNamespace(
        arm=arm,
        unit=SimpleNamespace(env_seed=43, policy_seed=11),
    )

    args = _episode_args(
        protocol,
        spec=spec,
        output_dir=Path("/results"),
        egl_gpu=3,
    )

    assert args.semantic_runtime is l1
    assert args.l1_semantic_alignment == ("on" if l1 else "off")
    assert args.l2_execution_integrity == ("on" if l2 else "off")
    assert args.execution_attack_family == "none"
    assert args.seed == 43
    assert args.policy_seed == 11


def test_launcher_selects_two_least_used_qualified_gpus() -> None:
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
        {"index": 0, "memory_used_mib": 900},
        {"index": 1, "memory_used_mib": 1200},
        {"index": 2, "memory_used_mib": 300},
        {"index": 3, "memory_used_mib": 0},
    ]

    assert qualified_gpu_indices(protocol, inventory) == [3, 2]
