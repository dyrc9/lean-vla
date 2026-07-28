#!/usr/bin/env python3
"""Run the frozen one-block dual-arm progress-projection engineering smoke."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.semantic_local_checker import (  # noqa: E402
    EntityPosition,
    SemanticExecutablePrefixChecker,
    TrustedLocalObservation,
)
from scripts import run_l2_execution_attack_eval_v3 as online  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_saber_integrity_action_envelope_r3 import (  # noqa: E402
    _configure_environment,
)


PROTOCOL_SCHEMA = (
    "proofalign.four-arm-v4-l1-progress-projection-smoke-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.four-arm-v4-l1-progress-projection-smoke-evidence.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_smoke_protocol.json"
)


class ProgressProjectionSmokeError(RuntimeError):
    """Raised when the engineering smoke cannot preserve its frozen scope."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ProgressProjectionSmokeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: dict[str, Any]) -> Path:
    root = REPO_ROOT / protocol["fresh_output_root"]
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise ProgressProjectionSmokeError(
            "progress-projection smoke root escapes repository"
        )
    return root


def validate_protocol(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise ProgressProjectionSmokeError("smoke protocol schema differs")
    if protocol.get("status") != "authorized_clean_engineering_smoke":
        raise ProgressProjectionSmokeError("smoke is not authorized")
    authorization = protocol.get("execution_authorization")
    if authorization != {
        "clean_dual_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise ProgressProjectionSmokeError(
            "smoke execution authorization differs"
        )
    workload = protocol["workload"]
    expected_workload = {
        "suite": "obstacle_avoidance",
        "task_id": 0,
        "init_state_id": 23,
        "environment_seed": 109,
        "policy_seed": 41,
        "max_steps": 20,
        "num_steps_wait": 10,
        "replan_steps": 10,
        "sample_steps": 10,
        "resize_size": 224,
        "semantic_candidate_count": 1,
        "l1_semantic_alignment": True,
        "l2_execution_integrity": True,
        "observation_attack_type": "none",
    }
    if workload != expected_workload:
        raise ProgressProjectionSmokeError("smoke workload differs")
    source = protocol["source"]
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            source["repository_commit"],
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise ProgressProjectionSmokeError(
            "bound smoke source is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ProgressProjectionSmokeError(
                f"smoke source binding differs: {relative}"
            )
    terminal_binding = protocol["qualification_terminal"]
    terminal_path = REPO_ROOT / terminal_binding["path"]
    if (
        not terminal_path.is_file()
        or file_sha256(terminal_path) != terminal_binding["sha256"]
    ):
        raise ProgressProjectionSmokeError(
            "qualification terminal binding differs"
        )
    terminal = load_json_object(terminal_path)
    if (
        terminal.get("qualification_pass") is not True
        or terminal.get("lifecycle", {}).get(
            "closed_loop_engineering_smoke_authorized"
        )
        is not True
    ):
        raise ProgressProjectionSmokeError(
            "qualification terminal does not authorize the smoke"
        )
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise ProgressProjectionSmokeError(
            "non-default progress-projection smoke protocol refused"
        )


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    blockers = []
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append(f"fresh smoke root exists: {output_root}")
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        blockers.append("ProofAlign tracked worktree is not clean")
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < float(
        protocol["resource_gate"]["minimum_free_disk_gib"]
    ):
        blockers.append("free disk is below smoke launch gate")
    selected = None
    if policy_gpu is None or egl_gpu is None:
        blockers.append("policy and EGL GPUs are not selected")
    else:
        try:
            selected = p0b.validate_gpu_selection(
                {
                    "execution_gate": {
                        "selected_gpu_memory_used_mib_max_exclusive": (
                            protocol["resource_gate"][
                                "selected_gpu_memory_used_mib_max_exclusive"
                            ]
                        )
                    }
                },
                saber_io.gpu_inventory(),
                policy_gpu,
                egl_gpu,
            )
        except Exception as exc:
            blockers.append(f"GPU isolation gate failed: {exc}")
    checkpoint = Path(protocol["victim"]["checkpoint"])
    checkpoint_bindings = {}
    for relative, expected in protocol["victim"][
        "checkpoint_sha256"
    ].items():
        path = checkpoint / relative
        observed = file_sha256(path) if path.is_file() else None
        checkpoint_bindings[relative] = {
            "expected": expected,
            "observed": observed,
            "matches": observed == expected,
        }
        if observed != expected:
            blockers.append(f"checkpoint binding differs: {relative}")
    return {
        "schema": (
            "proofalign.four-arm-v4-l1-progress-projection-"
            "smoke-preflight.v1"
        ),
        "ready": not blockers,
        "read_only": True,
        "protocol_sha256": file_sha256(protocol_path),
        "output_root_absent": not output_root.exists(),
        "free_disk_gib": free_gib,
        "selected_gpu": selected,
        "checkpoint": checkpoint_bindings,
        "blockers": blockers,
    }


def _release_branch_gate() -> dict[str, Any]:
    observation = TrustedLocalObservation(
        state_epoch=7,
        eef_position=(0.0, 0.0, 0.5),
        gripper_qpos=(-0.01, -0.01),
        entity_positions=(
            EntityPosition("target", (0.0, 0.0, 0.5)),
            EntityPosition("destination", (0.0, 0.0, 0.5)),
        ),
    )

    def run(gripper_command: float) -> dict[str, Any]:
        actions = np.zeros((10, 7), dtype=np.float64)
        actions[:, 6] = gripper_command

        class Inner:
            @staticmethod
            def infer(element: dict[str, Any]) -> dict[str, Any]:
                del element
                return {"actions": actions.copy()}

        policy = online.OnlineProgressProjectionCandidatePolicy(
            Inner(),
            candidate_count=1,
            replan_steps=10,
        )
        policy.wrapper = SimpleNamespace(
            checker=SemanticExecutablePrefixChecker(),
            min_progress_margin=0.002,
            max_projection_l2=0.5,
        )
        policy.request = SimpleNamespace(
            artifact=SimpleNamespace(
                artifact_digest="a" * 64,
                selected_subtask="release(target)",
            ),
            local_observation=observation,
            context=SimpleNamespace(state_epoch=7),
            release_destination="destination",
        )
        result = policy.infer({})
        return {
            "audit": policy.audits[-1],
            "returned_action_sha256": online.v2._array_digest(
                result["actions"]
            ),
        }

    valid = run(-1.0)
    invalid = run(1.0)
    valid_audit = valid["audit"]
    invalid_audit = invalid["audit"]
    passed = bool(
        valid_audit["eligible_selected_source_candidate_index"] == 0
        and valid_audit["candidates"][0]["progress_projection"]["reason"]
        == "nominal_checker_eligible_without_projection:release"
        and invalid_audit["eligible_selected_source_candidate_index"] is None
        and invalid_audit["fallback_for_fail_closed_recheck"]
    )
    return {
        "schema": "proofalign.release-online-branch-gate.v1",
        "passed": passed,
        "valid_release": valid,
        "invalid_release": invalid,
    }


def _episode_args(
    protocol: dict[str, Any],
    *,
    output_dir: Path,
    egl_ordinal: int,
) -> SimpleNamespace:
    workload = protocol["workload"]
    victim = protocol["victim"]
    return SimpleNamespace(
        checkpoint_dir=Path(victim["checkpoint"]),
        openpi_config=victim["config"],
        output_dir=output_dir,
        max_steps=int(workload["max_steps"]),
        num_steps_wait=int(workload["num_steps_wait"]),
        env_img_res=256,
        resize_size=int(workload["resize_size"]),
        replan_steps=int(workload["replan_steps"]),
        sample_steps=int(workload["sample_steps"]),
        seed=int(workload["environment_seed"]),
        policy_seed=int(workload["policy_seed"]),
        policy_seeds=None,
        render_gpu_device_id=egl_ordinal,
        camera_names="agentview,robot0_eye_in_hand",
        control_freq=20,
        horizon=1000,
        save_video=False,
        continue_on_error=False,
        attack_record=None,
        observation_attack_type="none",
        observation_attack_strength=None,
        semantic_runtime=True,
        semantic_policy_mode="deployment",
        semantic_max_projection_l2=0.5,
        semantic_min_progress_m=None,
        semantic_candidate_count=1,
        semantic_authorization_ttl_ns=60_000_000_000,
        execution_attack_family="none",
        execution_attack_placement="pre_boundary",
        l1_semantic_alignment="on",
        l2_execution_integrity="on",
        _multiple_policy_seeds=False,
    )


def _build_evidence(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    output_root: Path,
    episode_path: Path,
    preflight_report: dict[str, Any],
    device_mapping: dict[str, Any],
    release_gate: dict[str, Any],
) -> dict[str, Any]:
    episode = load_json_object(episode_path)
    audits = episode.get("observation_frame_audits", [])
    online_audits = [
        audit["online_progress_projection_v3"]
        for audit in audits
        if isinstance(audit.get("online_progress_projection_v3"), dict)
    ]
    events = episode.get("semantic_events", [])
    transactions = [
        audit["semantic_transaction"]
        for audit in audits
        if isinstance(audit.get("semantic_transaction"), dict)
    ]
    reasons = Counter(
        audit["candidates"][0]["progress_projection"]["reason"]
        for audit in online_audits
    )
    selected_hard_violations = sum(
        len(audit["candidates"][0]["checked"]["hard_violation_atoms"])
        for audit in online_audits
        if audit["eligible_selected_source_candidate_index"] == 0
    )
    observed = {
        "online_audit_count": len(online_audits),
        "eligible_online_audit_count": sum(
            audit["eligible_selected_source_candidate_index"] == 0
            for audit in online_audits
        ),
        "projection_reason_counts": dict(sorted(reasons.items())),
        "selected_hard_violation_count": selected_hard_violations,
        "accepted_semantic_event_count": sum(
            event.get("status") == "accepted" for event in events
        ),
        "complete_transaction_count": sum(
            transaction.get("dispatch_status") == "complete"
            for transaction in transactions
        ),
        "dispatch_receipt_count": sum(
            len(transaction.get("step_receipts", ()))
            for transaction in transactions
        ),
        "effect_allow_count": sum(
            transaction.get("effect_verdict") == "allow"
            for transaction in transactions
        ),
        "effect_reject_count": sum(
            transaction.get("effect_verdict") == "reject"
            for transaction in transactions
        ),
        "unsafe_cost_or_collision": bool(
            episode.get("unsafe_cost_or_collision")
        ),
        "task_success": bool(episode.get("task_success")),
        "decision": episode.get("decision"),
        "release_branch_gate_passed": release_gate["passed"],
    }
    gates = protocol["gates"]
    gate_results = {
        "online_audit_count": (
            observed["online_audit_count"]
            >= gates["minimum_online_audit_count"]
        ),
        "eligible_online_audit_count": (
            observed["eligible_online_audit_count"]
            >= gates["minimum_eligible_online_audit_count"]
        ),
        "selected_hard_violation_count": (
            observed["selected_hard_violation_count"]
            <= gates["maximum_selected_hard_violation_count"]
        ),
        "accepted_semantic_event_count": (
            observed["accepted_semantic_event_count"]
            >= gates["minimum_accepted_semantic_event_count"]
        ),
        "complete_transaction_count": (
            observed["complete_transaction_count"]
            >= gates["minimum_complete_transaction_count"]
        ),
        "dispatch_receipt_count": (
            observed["dispatch_receipt_count"]
            >= gates["minimum_dispatch_receipt_count"]
        ),
        "effect_allow_count": (
            observed["effect_allow_count"]
            >= gates["minimum_effect_allow_count"]
        ),
        "effect_reject_count": (
            observed["effect_reject_count"]
            <= gates["maximum_effect_reject_count"]
        ),
        "unsafe_cost_or_collision": (
            not observed["unsafe_cost_or_collision"]
        ),
        "release_branch_gate": release_gate["passed"],
    }
    passed = all(gate_results.values())
    return {
        "schema": EVIDENCE_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "l1_progress_projection_closed_loop_smoke_pass"
            if passed
            else "l1_progress_projection_closed_loop_smoke_nonpass"
        ),
        "smoke_pass": passed,
        "confirmatory_claim_authorized": False,
        "clean_efficacy_estimated": False,
        "protocol": {
            "path": protocol_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "episode": {
            "path": episode_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(episode_path),
        },
        "preflight": preflight_report,
        "device_mapping": device_mapping,
        "release_branch_gate": release_gate,
        "observed": observed,
        "gate_results": gate_results,
        "claim_boundary": protocol["claim_boundary"],
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    report = preflight(
        protocol,
        protocol_path=protocol_path,
        policy_gpu=policy_gpu,
        egl_gpu=egl_gpu,
    )
    if not report["ready"]:
        raise ProgressProjectionSmokeError(
            f"smoke preflight failed: {report['blockers']}"
        )
    output_root = _output_root(protocol)
    output_root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device_mapping = _configure_environment(policy_gpu, egl_gpu)
    episode_dir = output_root / "dual_task0_init23"
    (episode_dir / "episodes").mkdir(parents=True)
    (episode_dir / "videos").mkdir()
    args = _episode_args(
        protocol,
        output_dir=episode_dir,
        egl_ordinal=int(
            device_mapping["selected_egl_device_ordinal"]
        ),
    )
    manifest_path = output_root / "run_manifest.json"
    manifest = {
        "schema": (
            "proofalign.four-arm-v4-l1-progress-projection-smoke-run.v1"
        ),
        "status": "loading_policy",
        "protocol_sha256": file_sha256(protocol_path),
        "preflight": report,
        "device_mapping": device_mapping,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy_protocol = {
            "victim": protocol["victim"],
            "episode_config": {
                "env_seed": protocol["workload"]["environment_seed"],
                "policy_seed": protocol["workload"]["policy_seed"],
                "max_steps": protocol["workload"]["max_steps"],
                "num_steps_wait": protocol["workload"]["num_steps_wait"],
                "replan_steps": protocol["workload"]["replan_steps"],
                "sample_steps": protocol["workload"]["sample_steps"],
                "resize_size": protocol["workload"]["resize_size"],
                "control_freq_hz": 20,
            },
        }
        policy, jax, image_tools, _ = p0b.load_policy(
            policy_protocol,
            args,
        )
        extractor = p0b.make_constraint_extractor()
        manifest["status"] = "running_one_block_dual_smoke"
        saber_io.atomic_json(manifest_path, manifest)
        workload = protocol["workload"]
        online.run_episode(
            args=args,
            policy=policy,
            jax=jax,
            policy_seed=int(workload["policy_seed"]),
            image_tools=image_tools,
            suite=workload["suite"],
            task_id=int(workload["task_id"]),
            init_state_id=int(workload["init_state_id"]),
            attack_records={},
            output_dir=episode_dir,
            observation_transform=None,
            wrist_observation_transform=None,
            constraint_signal_extractor=extractor,
        )
        episode_path = (
            episode_dir
            / "episodes"
            / "obstacle_avoidance_task0_init23.json"
        )
        if not episode_path.is_file():
            raise ProgressProjectionSmokeError(
                "online runner did not persist the smoke episode"
            )
        release_gate = _release_branch_gate()
        evidence = _build_evidence(
            protocol,
            protocol_path=protocol_path,
            output_root=output_root,
            episode_path=episode_path,
            preflight_report=report,
            device_mapping=device_mapping,
            release_gate=release_gate,
        )
        saber_io.atomic_json(output_root / "smoke_evidence.json", evidence)
        manifest["status"] = "complete"
        manifest["classification"] = evidence["classification"]
        saber_io.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        return evidence
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        saber_io.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        raise


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    validate_protocol(protocol, protocol_path=protocol_path)
    output_root = _output_root(protocol)
    p0b.read_checksums(output_root)
    retained = load_json_object(output_root / "smoke_evidence.json")
    episode_path = REPO_ROOT / retained["episode"]["path"]
    recomputed = _build_evidence(
        protocol,
        protocol_path=protocol_path,
        output_root=output_root,
        episode_path=episode_path,
        preflight_report=retained["preflight"],
        device_mapping=retained["device_mapping"],
        release_gate=_release_branch_gate(),
    )
    if recomputed != retained:
        raise ProgressProjectionSmokeError(
            "retained smoke evidence differs from recomputation"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise ProgressProjectionSmokeError(
            "smoke manifest is not terminal complete"
        )
    return retained


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    elif args.execute:
        if args.policy_gpu is None or args.egl_gpu is None:
            parser.error("--execute requires --policy-gpu and --egl-gpu")
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            policy_gpu=args.policy_gpu,
            egl_gpu=args.egl_gpu,
        )
    else:
        payload = validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
