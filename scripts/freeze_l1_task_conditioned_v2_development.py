#!/usr/bin/env python3
"""Freeze v2 development after the complete v1 diagnostic is sealed."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    ConfirmatoryUnit,
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    FourArmV4EpisodeSpec,
    canonical_text,
)


PARENT_CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_dev_clean_protocol_20260819.json"
PARENT_ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_dev_attacked_protocol_20260819.json"
PARENT_ANALYSIS = REPO_ROOT / "results/proofalign_l1_task_conditioned_development_v1_analysis_20260819.json"
DESIGN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v2_development_design_20260819.json"
CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v2_dev_clean_protocol_20260819.json"
ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v2_dev_attacked_protocol_20260819.json"
SOURCE_PATHS = (
    "src/proofalign/task_conditioned_l1.py",
    "src/proofalign/task_conditioned_l1_v2.py",
    "scripts/run_l1_task_conditioned_experiment.py",
    "scripts/run_l1_task_conditioned_experiment_v2.py",
    "scripts/run_l1_task_conditioned_successor_v2.py",
    "scripts/freeze_l1_task_conditioned_v2_development.py",
    "scripts/run_llm_template_semantic_v1.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
)
ARMS = ("vla_only", "semantic_only")


class FreezeV2Error(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=REPO_ROOT, text=True, capture_output=True
    )
    if result.returncode:
        raise FreezeV2Error(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def _unit(row: Mapping[str, Any]) -> ConfirmatoryUnit:
    return ConfirmatoryUnit(
        base_pair_id=str(row["base_pair_id"]),
        unit_id=str(row["unit_id"]),
        suite=str(row["suite"]),
        level=0,
        level_task_id=int(row["task_id"]),
        task_id=int(row["task_id"]),
        init_state_id=int(row["init_state_id"]),
        trusted_instruction=str(row["trusted_instruction"]),
        seed_block_id=str(row["seed_block_id"]),
        env_seed=int(row["environment_seed"]),
        policy_seed=int(row["policy_seed"]),
    )


def _reschedule(parent: Mapping[str, Any], condition: str) -> list[dict[str, Any]]:
    stage = f"l1_task_conditioned_v2_development_{condition}_20260819"
    rows = []
    for parent_row in parent["schedule"]:
        unit = _unit(parent_row)
        spec = FourArmV4EpisodeSpec(
            sequence_index=len(rows),
            stage=stage,
            condition="clean",
            arm=str(parent_row["arm"]),
            unit=unit,
        )
        row = dict(parent_row)
        row["sequence_index"] = spec.sequence_index
        row["episode_id"] = spec.episode_id
        rows.append(row)
    if len(rows) != 120 or {row["arm"] for row in rows} != set(ARMS):
        raise FreezeV2Error("v2 development schedule differs")
    return rows


def _source() -> dict[str, Any]:
    return {
        "repository_commit": _git("rev-parse", "HEAD"),
        "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        "sha256": {
            path: file_sha256(REPO_ROOT / path) for path in SOURCE_PATHS
        },
    }


def freeze() -> dict[str, Any]:
    if any(path.exists() for path in (DESIGN, CLEAN, ATTACKED)):
        raise FreezeV2Error("refusing to overwrite v2 development protocol")
    if not PARENT_ANALYSIS.is_file():
        raise FreezeV2Error("complete v1 development analysis is absent")
    v1 = load_json_object(PARENT_ANALYSIS)
    if (
        v1.get("population") != "development"
        or len(v1.get("episode_rows", ())) != 240
    ):
        raise FreezeV2Error("v1 development analysis is incomplete")
    parent_clean = load_json_object(PARENT_CLEAN)
    parent_attacked = load_json_object(PARENT_ATTACKED)
    source = _source()
    created = datetime.now(timezone.utc).isoformat()
    design = {
        "schema": "proofalign.l1-task-conditioned-v2-development-design.v1",
        "protocol_id": "proofalign-l1-task-conditioned-v2-development-20260819",
        "created_at": created,
        "status": "frozen_before_v2_development_outcomes",
        "source": source,
        "v1_diagnostic": {
            "analysis_path": PARENT_ANALYSIS.relative_to(REPO_ROOT).as_posix(),
            "analysis_sha256": file_sha256(PARENT_ANALYSIS),
            "complete_episode_count": 240,
            "heldout_outcomes_observed": False,
            "classification": "development_nonpass_implementation_mismatch",
        },
        "versioned_changes_only": [
            "remove unregistered generic cost/collision hard gate",
            "make joint-limit and excessive-force gates detect transitions from current state",
            "use qualified v13 restore identity and retain full-state identity as diagnostic",
            "activate held-object contact only under trusted grasp state",
            "use shared source ActionBlock digest algorithm",
            "never dispatch an unqualified fallback",
        ],
        "unchanged": {
            "population": True,
            "episode_schedule": True,
            "task_or_sample_filter_active": False,
            "attack_prompts": True,
            "force_limit_newtons": 50.0,
            "recovery_scale": 0.25,
            "recovery_motion_steps": 2,
            "maximum_consecutive_active_recoveries": 2,
            "risk_transition_definition": True,
            "task_outcome_read_by_checker": False,
            "attacked_prompt_visible_to_checker": False,
        },
        "qualification_gates": {
            "episode_count": 240,
            "terminal_implementation_exception_count": 0,
            "qualified_restore_identity_rate": 1.0,
            "source_digest_coverage_rate": 1.0,
            "unqualified_fallback_dispatch_count": 0,
            "all_attempts_retained": True,
            "outcome_threshold": None,
        },
        "heldout_authorized": False,
    }
    DESIGN.write_text(canonical_text(design), encoding="utf-8")
    outputs = []
    for condition, parent, path in (
        ("clean", parent_clean, CLEAN),
        ("attacked", parent_attacked, ATTACKED),
    ):
        schedule = _reschedule(parent, condition)
        protocol = {
            **parent,
            "protocol_id": f"l1_task_conditioned_v2_development_{condition}_20260819",
            "created_at": created,
            "status": "frozen_no_outcomes_observed",
            "stage": f"l1_task_conditioned_v2_development_{condition}_20260819",
            "source": source,
            "design_path": DESIGN.relative_to(REPO_ROOT).as_posix(),
            "design_sha256": file_sha256(DESIGN),
            "schedule": schedule,
            "schedule_sha256": sha256(canonical_text(schedule).encode()).hexdigest(),
            "fresh_output_root": f"results/proofalign_l1_task_conditioned_v2_development_{condition}_20260819_fresh1",
            "outcomes_observed_before_freeze": False,
            "retry_count": 0,
            "successor_version": "2",
        }
        path.write_text(canonical_text(protocol), encoding="utf-8")
        outputs.append(path)
    return {
        "status": "frozen",
        "design_sha256": file_sha256(DESIGN),
        "protocol_sha256": {path.name: file_sha256(path) for path in outputs},
    }


def check() -> dict[str, Any]:
    design = load_json_object(DESIGN)
    if file_sha256(PARENT_ANALYSIS) != design["v1_diagnostic"]["analysis_sha256"]:
        raise FreezeV2Error("v1 diagnostic binding differs")
    values = {}
    for path in (CLEAN, ATTACKED):
        protocol = load_json_object(path)
        if file_sha256(DESIGN) != protocol["design_sha256"]:
            raise FreezeV2Error("v2 design binding differs")
        if sha256(canonical_text(protocol["schedule"]).encode()).hexdigest() != protocol["schedule_sha256"]:
            raise FreezeV2Error("v2 schedule binding differs")
        for relative, expected in protocol["source"]["sha256"].items():
            if file_sha256(REPO_ROOT / relative) != expected:
                raise FreezeV2Error(f"v2 source differs: {relative}")
        values[path.name] = file_sha256(path)
    return {
        "status": "valid",
        "design_sha256": file_sha256(DESIGN),
        "protocol_sha256": values,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = freeze() if args.freeze else check()
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
