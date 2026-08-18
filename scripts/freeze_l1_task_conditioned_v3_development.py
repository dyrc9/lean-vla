#!/usr/bin/env python3
"""Freeze bounded-retreat v3 on development after complete v2 diagnostics."""

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

from proofalign.benchmark.confirmatory import ConfirmatoryUnit, file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import FourArmV4EpisodeSpec, canonical_text  # noqa: E402
from proofalign.task_conditioned_l1_v3 import recovery_library_digest  # noqa: E402


PARENT_CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v2_dev_clean_protocol_20260819.json"
PARENT_ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v2_dev_attacked_protocol_20260819.json"
PARENT_ANALYSIS = REPO_ROOT / "results/proofalign_l1_task_conditioned_v2_development_analysis_20260819.json"
DESIGN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v3_development_design_20260819.json"
CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v3_dev_clean_protocol_20260819.json"
ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v3_dev_attacked_protocol_20260819.json"
SOURCE_PATHS = (
    "src/proofalign/task_conditioned_l1.py",
    "src/proofalign/task_conditioned_l1_v2.py",
    "src/proofalign/task_conditioned_l1_v3.py",
    "scripts/run_l1_task_conditioned_experiment.py",
    "scripts/run_l1_task_conditioned_experiment_v3.py",
    "scripts/run_l1_task_conditioned_successor_v3.py",
    "scripts/freeze_l1_task_conditioned_v3_development.py",
    "scripts/run_llm_template_semantic_v1.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
)
ARMS = ("vla_only", "semantic_only")


class FreezeV3Error(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise FreezeV3Error(result.stderr.strip() or "git failed")
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
    stage = f"l1_task_conditioned_v3_development_{condition}_20260819"
    rows = []
    for source in parent["schedule"]:
        spec = FourArmV4EpisodeSpec(
            sequence_index=len(rows),
            stage=stage,
            condition="clean",
            arm=str(source["arm"]),
            unit=_unit(source),
        )
        row = dict(source)
        row["sequence_index"] = spec.sequence_index
        row["episode_id"] = spec.episode_id
        rows.append(row)
    if len(rows) != 120 or {row["arm"] for row in rows} != set(ARMS):
        raise FreezeV3Error("v3 development schedule differs")
    return rows


def _v2_diagnostic() -> dict[str, Any]:
    if not PARENT_ANALYSIS.is_file():
        raise FreezeV3Error("complete v2 development analysis is absent")
    analysis = load_json_object(PARENT_ANALYSIS)
    rows = analysis.get("episode_rows", ())
    if analysis.get("population") != "development" or len(rows) != 240:
        raise FreezeV3Error("v2 development analysis is incomplete")
    terminal = [row for row in rows if row.get("terminal_exception")]
    if not terminal:
        raise FreezeV3Error("v2 has no bounded-recovery coverage failure to repair")
    if any(
        row.get("terminal_exception_type") != "TaskConditionedL1Error"
        or not str(row.get("terminal_exception_message", "")).startswith(
            "no qualified fresh recovery ActionBlock:"
        )
        for row in terminal
    ):
        raise FreezeV3Error("v2 contains an implementation failure outside the v3 repair scope")
    return {
        "analysis_path": PARENT_ANALYSIS.relative_to(REPO_ROOT).as_posix(),
        "analysis_sha256": file_sha256(PARENT_ANALYSIS),
        "complete_episode_count": len(rows),
        "terminal_recovery_coverage_failure_count": len(terminal),
        "repair_scope": "fixed bounded retreat coverage only",
        "task_success_or_risk_result_used": False,
    }


def _source() -> dict[str, Any]:
    return {
        "repository_commit": _git("rev-parse", "HEAD"),
        "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        "sha256": {path: file_sha256(REPO_ROOT / path) for path in SOURCE_PATHS},
    }


def freeze() -> dict[str, Any]:
    if any(path.exists() for path in (DESIGN, CLEAN, ATTACKED)):
        raise FreezeV3Error("refusing to overwrite v3 development protocol")
    diagnostic = _v2_diagnostic()
    parents = {
        "clean": load_json_object(PARENT_CLEAN),
        "attacked": load_json_object(PARENT_ATTACKED),
    }
    source = _source()
    created = datetime.now(timezone.utc).isoformat()
    design = {
        "schema": "proofalign.l1-task-conditioned-v3-development-design.v1",
        "protocol_id": "proofalign-l1-task-conditioned-v3-development-20260819",
        "created_at": created,
        "status": "frozen_before_v3_development_outcomes",
        "source": source,
        "v2_diagnostic": diagnostic,
        "versioned_change_only": {
            "bounded_retreat_library_digest": recovery_library_digest(),
            "motion_step_options": [2, 4],
            "cartesian_action_scale": 0.25,
            "selection": "first exact-shadow ALLOW in frozen order",
            "no_allow": "fail closed without dispatch",
        },
        "unchanged": {
            "population": True,
            "episode_schedule": True,
            "source_policy_action": True,
            "risk_channels_and_thresholds": True,
            "contact_contract": True,
            "force_limit_newtons": 50.0,
            "task_or_sample_filter_active": False,
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
    for condition, path in (("clean", CLEAN), ("attacked", ATTACKED)):
        parent = parents[condition]
        schedule = _reschedule(parent, condition)
        protocol = {
            **parent,
            "protocol_id": f"l1_task_conditioned_v3_development_{condition}_20260819",
            "created_at": created,
            "status": "frozen_no_outcomes_observed",
            "stage": f"l1_task_conditioned_v3_development_{condition}_20260819",
            "source": source,
            "design_path": DESIGN.relative_to(REPO_ROOT).as_posix(),
            "design_sha256": file_sha256(DESIGN),
            "schedule": schedule,
            "schedule_sha256": sha256(canonical_text(schedule).encode()).hexdigest(),
            "fresh_output_root": f"results/proofalign_l1_task_conditioned_v3_development_{condition}_20260819_fresh1",
            "outcomes_observed_before_freeze": False,
            "retry_count": 0,
            "successor_version": "3",
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
    if _v2_diagnostic() != design["v2_diagnostic"]:
        raise FreezeV3Error("v2 diagnostic binding differs")
    values = {}
    for path in (CLEAN, ATTACKED):
        protocol = load_json_object(path)
        if file_sha256(DESIGN) != protocol["design_sha256"]:
            raise FreezeV3Error("v3 design binding differs")
        if sha256(canonical_text(protocol["schedule"]).encode()).hexdigest() != protocol["schedule_sha256"]:
            raise FreezeV3Error("v3 schedule binding differs")
        for relative, expected in protocol["source"]["sha256"].items():
            if file_sha256(REPO_ROOT / relative) != expected:
                raise FreezeV3Error(f"v3 source differs: {relative}")
        values[path.name] = file_sha256(path)
    return {"status": "valid", "design_sha256": file_sha256(DESIGN), "protocol_sha256": values}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(freeze() if args.freeze else check(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
