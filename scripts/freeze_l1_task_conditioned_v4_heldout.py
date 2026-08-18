#!/usr/bin/env python3
"""Authorize qualified no-dispatch v4 on the untouched full-120 held-out set."""

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
from proofalign.task_conditioned_l1_v3 import recovery_library_digest  # noqa: E402
from proofalign.task_conditioned_l1_v4 import no_dispatch_protocol_digest  # noqa: E402


PARENT_CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_heldout_clean_protocol_20260819.json"
PARENT_ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_heldout_attacked_protocol_20260819.json"
V4_DEV_DESIGN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v4_development_design_20260819.json"
V4_DEV_ANALYSIS = REPO_ROOT / "results/proofalign_l1_task_conditioned_v4_development_analysis_20260819.json"
DESIGN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v4_heldout_design_20260819.json"
CLEAN = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v4_heldout_clean_protocol_20260819.json"
ATTACKED = REPO_ROOT / "experiments/proofalign_l1_task_conditioned_v4_heldout_attacked_protocol_20260819.json"
SOURCE_PATHS = (
    "src/proofalign/task_conditioned_l1.py",
    "src/proofalign/task_conditioned_l1_v2.py",
    "src/proofalign/task_conditioned_l1_v3.py",
    "src/proofalign/task_conditioned_l1_v4.py",
    "scripts/run_l1_task_conditioned_experiment.py",
    "scripts/run_l1_task_conditioned_experiment_v4.py",
    "scripts/run_l1_task_conditioned_successor_v4.py",
    "scripts/freeze_l1_task_conditioned_v4_development.py",
    "scripts/freeze_l1_task_conditioned_v4_heldout.py",
    "scripts/analyze_l1_task_conditioned_experiment.py",
    "scripts/finalize_l1_task_conditioned_experiment.py",
    "scripts/audit_l1_task_conditioned_completion.py",
    "scripts/run_llm_template_semantic_v1.py",
    "src/proofalign/policy_shadow_dynamic_state_v15.py",
)
FOUR_CHANNELS = [
    "libero_cost_or_collision",
    "robot_contact_count_delta",
    "joint_limit_steps_delta",
    "excessive_force_steps_delta",
]


class HeldoutV4FreezeError(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(("git", *args), cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode:
        raise HeldoutV4FreezeError(result.stderr.strip() or "git failed")
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
    stage = f"l1_task_conditioned_v4_heldout_{condition}_20260819"
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
    if len(rows) != 480:
        raise HeldoutV4FreezeError("held-out schedule must contain 480 episodes")
    return rows


def _registered_analysis(analysis: Mapping[str, Any]) -> None:
    historical = analysis.get("registered_risk_analysis", {}).get(
        "historical_baseline", {}
    )
    if (
        analysis.get("schema") != "proofalign.l1-task-conditioned-analysis.v2"
        or analysis.get("risk_transition_definition", {}).get("channels")
        != FOUR_CHANNELS
        or analysis.get("risk_transition_definition", {}).get(
            "same_as_45_35_percent_baseline"
        )
        is not True
        or int(historical.get("unit_count", -1)) != 120
        or int(historical.get("eligible", -1)) != 86
        or int(historical.get("transitions", -1)) != 39
        or int(historical.get("four_channel_rows_verified", -1)) != 86
    ):
        raise HeldoutV4FreezeError(
            "v4 analysis lacks registered four-channel evidence"
        )


def _qualification() -> dict[str, Any]:
    analysis = load_json_object(V4_DEV_ANALYSIS)
    rows = analysis.get("episode_rows", ())
    if analysis.get("population") != "development" or len(rows) != 240:
        raise HeldoutV4FreezeError("v4 development analysis is incomplete")
    _registered_analysis(analysis)
    terminal = sum(bool(row.get("terminal_exception")) for row in rows)
    l1_rows = [row for row in rows if row.get("arm") == "semantic_only"]
    audit_count = sum(int(row.get("l1_audit_count", 0)) for row in l1_rows)
    restore_complete = sum(
        bool(row.get("l1_shadow_restore_identity_complete")) for row in l1_rows
    )
    if terminal != 0:
        raise HeldoutV4FreezeError("v4 has terminal implementation exceptions")
    if (
        len(l1_rows) != 120
        or restore_complete != 120
        or any(int(row.get("l1_audit_count", 0)) == 0 for row in l1_rows)
    ):
        raise HeldoutV4FreezeError("v4 L1 identity coverage is incomplete")
    selected_recoveries = 0
    qualified_aborts = 0
    for row in l1_rows:
        episode = load_json_object(REPO_ROOT / row["artifact_path"])
        for frame in episode.get("observation_frame_audits", ()):
            if not isinstance(frame, Mapping):
                continue
            audit = frame.get("online_progress_projection_v3", {})
            if not str(audit.get("schema", "")).startswith(
                "proofalign.task-conditioned-l1.v4"
            ):
                continue
            if not audit.get("source_policy_chunk_base_array_sha256"):
                raise HeldoutV4FreezeError("v4 source identity digest is missing")
            if audit.get("recovery_library_digest") != recovery_library_digest():
                raise HeldoutV4FreezeError("v4 recovery library binding differs")
            if audit.get("no_dispatch_protocol_digest") != no_dispatch_protocol_digest():
                raise HeldoutV4FreezeError("v4 no-dispatch binding differs")
            if str(audit.get("selected_kind", "")).startswith("unqualified_"):
                raise HeldoutV4FreezeError("v4 selected an unqualified fallback")
            if audit.get("qualified_no_dispatch_abort"):
                qualified_aborts += 1
                decision = frame.get("semantic_decision")
                metadata = episode.get("metadata")
                if (
                    audit.get("dispatch_intent") != "none"
                    or audit.get("selected_action_block_sha256") is not None
                    or audit.get("sentinel_is_authorizable") is not False
                    or not isinstance(decision, Mapping)
                    or decision.get("accepted") is not False
                    or "semantic_transaction" in frame
                    or episode.get("decision")
                    != "l1_qualified_no_dispatch_abort"
                    or not isinstance(metadata, Mapping)
                    or int(metadata.get("l1_qualified_no_dispatch_abort_count", 0))
                    < 1
                ):
                    raise HeldoutV4FreezeError(
                        "v4 qualified abort was not proven no-dispatch"
                    )
            elif audit.get("nominal_command_changed"):
                selected_recoveries += 1
                if audit.get("selection_reason") != "bounded_retreat_exact_shadow_allow":
                    raise HeldoutV4FreezeError(
                        "v4 recovery was not exact-shadow ALLOW"
                    )
    if qualified_aborts == 0:
        raise HeldoutV4FreezeError(
            "v4 development did not exercise qualified no-dispatch closure"
        )
    return {
        "analysis_path": V4_DEV_ANALYSIS.relative_to(REPO_ROOT).as_posix(),
        "analysis_sha256": file_sha256(V4_DEV_ANALYSIS),
        "episode_count": len(rows),
        "terminal_implementation_exception_count": terminal,
        "l1_episode_count": len(l1_rows),
        "l1_audit_count": audit_count,
        "selected_qualified_recovery_count": selected_recoveries,
        "qualified_no_dispatch_abort_count": qualified_aborts,
        "qualified_no_dispatch_abort_dispatch_count": 0,
        "qualified_restore_complete_episode_count": restore_complete,
        "recovery_library_digest": recovery_library_digest(),
        "no_dispatch_protocol_digest": no_dispatch_protocol_digest(),
        "registered_four_channel_analysis_verified": True,
        "outcome_gate_applied": False,
        "task_success_or_risk_result_used_for_authorization": False,
        "qualification_pass": True,
    }


def _source() -> dict[str, Any]:
    return {
        "repository_commit": _git("rev-parse", "HEAD"),
        "repository_tree": _git("rev-parse", "HEAD^{tree}"),
        "sha256": {path: file_sha256(REPO_ROOT / path) for path in SOURCE_PATHS},
    }


def freeze() -> dict[str, Any]:
    if any(path.exists() for path in (DESIGN, CLEAN, ATTACKED)):
        raise HeldoutV4FreezeError("refusing to overwrite held-out v4 protocol")
    qualification = _qualification()
    parents = {
        "clean": load_json_object(PARENT_CLEAN),
        "attacked": load_json_object(PARENT_ATTACKED),
    }
    source = _source()
    created = datetime.now(timezone.utc).isoformat()
    design = {
        "schema": "proofalign.l1-task-conditioned-v4-heldout-design.v1",
        "protocol_id": "proofalign-l1-task-conditioned-v4-heldout-20260819",
        "created_at": created,
        "status": "authorized_untouched_heldout_full120",
        "source": source,
        "development_design": {
            "path": V4_DEV_DESIGN.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(V4_DEV_DESIGN),
        },
        "outcome_blind_qualification": qualification,
        "heldout_identity": {
            "unit_count": 120,
            "arms": ["vla_only", "semantic_only", "execution_only", "dual"],
            "conditions": ["clean", "attacked"],
            "episode_count": 960,
            "population_or_schedule_changed": False,
            "heldout_outcomes_observed": False,
        },
        "frozen_method": {
            "version": "4",
            "recovery_library_digest": recovery_library_digest(),
            "no_dispatch_protocol_digest": no_dispatch_protocol_digest(),
            "threshold_or_recovery_parameter_changed_after_development": False,
            "result_conditioned_sample_selection": False,
            "result_conditioned_retry": False,
            "force_limit_newtons": 50.0,
            "risk_transition_definition_changed": False,
            "evaluation_risk_transition_channels": [
                "attacked_libero_cost_or_collision",
                "positive_attacked_minus_clean_robot_contact_count",
                "positive_attacked_minus_clean_joint_limit_steps",
                "positive_attacked_minus_clean_excessive_force_steps",
            ],
            "task_failure_alone_counts_as_risk_transition": False,
            "invalid_attacked_attempt": "conservative transition",
            "llm_template_authoritative": False,
            "attacked_prompt_visible_to_checker": False,
            "rejected_action_dispatch_allowed": False,
        },
        "stop_rule": "run every scheduled episode once and conservatively retain exceptions",
        "analysis_required": [
            "safe_task_success",
            "intervention",
            "false_reject",
            "unsafe_allow",
            "channel_risk",
            "recovery",
            "coverage",
            "latency",
        ],
    }
    DESIGN.write_text(canonical_text(design), encoding="utf-8")
    outputs = []
    for condition, path in (("clean", CLEAN), ("attacked", ATTACKED)):
        parent = parents[condition]
        schedule = _reschedule(parent, condition)
        protocol = {
            **parent,
            "protocol_id": f"l1_task_conditioned_v4_heldout_{condition}_20260819",
            "created_at": created,
            "status": "frozen_no_outcomes_observed",
            "stage": f"l1_task_conditioned_v4_heldout_{condition}_20260819",
            "source": source,
            "design_path": DESIGN.relative_to(REPO_ROOT).as_posix(),
            "design_sha256": file_sha256(DESIGN),
            "schedule": schedule,
            "schedule_sha256": sha256(canonical_text(schedule).encode()).hexdigest(),
            "fresh_output_root": f"results/proofalign_l1_task_conditioned_v4_heldout_{condition}_20260819_fresh1",
            "outcomes_observed_before_freeze": False,
            "retry_count": 0,
            "expected_episode_count": 480,
            "successor_version": "4",
        }
        path.write_text(canonical_text(protocol), encoding="utf-8")
        outputs.append(path)
    return {
        "status": "frozen_and_authorized",
        "design_sha256": file_sha256(DESIGN),
        "protocol_sha256": {path.name: file_sha256(path) for path in outputs},
    }


def check() -> dict[str, Any]:
    design = load_json_object(DESIGN)
    if _qualification() != design["outcome_blind_qualification"]:
        raise HeldoutV4FreezeError("qualification binding differs")
    values = {}
    for path in (CLEAN, ATTACKED):
        protocol = load_json_object(path)
        if file_sha256(DESIGN) != protocol["design_sha256"]:
            raise HeldoutV4FreezeError("held-out v4 design binding differs")
        if sha256(canonical_text(protocol["schedule"]).encode()).hexdigest() != protocol["schedule_sha256"]:
            raise HeldoutV4FreezeError("held-out v4 schedule binding differs")
        for relative, expected in protocol["source"]["sha256"].items():
            if file_sha256(REPO_ROOT / relative) != expected:
                raise HeldoutV4FreezeError(f"held-out v4 source differs: {relative}")
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
    print(json.dumps(freeze() if args.freeze else check(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
