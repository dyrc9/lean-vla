#!/usr/bin/env python3
"""Run the frozen Dual regression smoke for the v3 pick-up contract."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from proofalign.horizon_consistent_pick_up import (  # noqa: E402
    PICK_UP_PREFIX_PROGRESS_EFFECT,
)
from scripts import run_l2_execution_attack_eval_v4 as online  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_four_arm_v4_l1_progress_projection_smoke import (  # noqa: E402
    _episode_args,
)
from scripts.run_saber_integrity_action_envelope_r3 import (  # noqa: E402
    _configure_environment,
)


PROTOCOL_SCHEMA = (
    "proofalign.horizon-consistent-pick-up-regression-smoke-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.horizon-consistent-pick-up-regression-smoke-evidence.v1"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_regression_smoke_protocol.json"
)


class HorizonPickUpSmokeError(RuntimeError):
    """Raised when the regression smoke cannot preserve its frozen scope."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise HorizonPickUpSmokeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise HorizonPickUpSmokeError(
            "regression smoke root escapes repository"
        )
    return root


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_post_outcome_dual_regression_smoke"
    ):
        raise HorizonPickUpSmokeError(
            "unsupported or unauthorized regression smoke"
        )
    if protocol.get("execution_authorization") != {
        "clean_dual_regression_smoke": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "clean_efficacy_rollout": False,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise HorizonPickUpSmokeError(
            "regression smoke authorization differs"
        )
    if protocol.get("workload") != {
        "suite": "obstacle_avoidance_human",
        "task_id": 0,
        "init_state_id": 9,
        "environment_seed": 127,
        "policy_seed": 47,
        "max_steps": 80,
        "num_steps_wait": 10,
        "replan_steps": 10,
        "sample_steps": 10,
        "resize_size": 224,
        "semantic_candidate_count": 1,
        "l1_semantic_alignment": True,
        "l2_execution_integrity": True,
        "observation_attack_type": "none",
    }:
        raise HorizonPickUpSmokeError(
            "regression smoke workload differs"
        )
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        raise HorizonPickUpSmokeError(
            "non-default regression smoke protocol refused"
        )
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
        raise HorizonPickUpSmokeError(
            "bound regression source is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise HorizonPickUpSmokeError(
                f"regression source binding differs: {relative}"
            )
    for binding_name in (
        "parent_screening_nonpass",
        "offline_replay_qualification",
    ):
        binding = protocol[binding_name]
        path = REPO_ROOT / binding["path"]
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise HorizonPickUpSmokeError(
                f"{binding_name} binding differs"
            )
    replay = load_json_object(
        REPO_ROOT / protocol["offline_replay_qualification"]["path"]
    )
    if (
        replay.get("classification")
        != "pick_up_prefix_progress_replay_qualified"
        or replay.get("qualified") is not True
    ):
        raise HorizonPickUpSmokeError(
            "offline replay did not qualify"
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
        blockers.append(f"fresh regression root exists: {output_root}")
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        blockers.append("ProofAlign tracked worktree is not clean")
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < float(
        protocol["resource_gate"]["minimum_free_disk_gib"]
    ):
        blockers.append("free disk is below regression launch gate")
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
            "proofalign.horizon-consistent-pick-up-regression-"
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


def _build_evidence(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    episode_path: Path,
    preflight_report: Mapping[str, Any],
    device_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    episode = load_json_object(episode_path)
    audits = episode.get("observation_frame_audits", [])
    if not isinstance(audits, list):
        raise HorizonPickUpSmokeError(
            "regression episode lacks frame audits"
        )
    online_audits = [
        frame["online_progress_projection_v3"]
        for frame in audits
        if isinstance(frame, Mapping)
        and isinstance(
            frame.get("online_progress_projection_v3"),
            Mapping,
        )
    ]
    transactions = [
        frame["semantic_transaction"]
        for frame in audits
        if isinstance(frame, Mapping)
        and isinstance(frame.get("semantic_transaction"), Mapping)
    ]
    contracts = []
    for frame in audits:
        decision = (
            frame.get("semantic_decision")
            if isinstance(frame, Mapping)
            else None
        )
        contract = (
            decision.get("execution_contract")
            if isinstance(decision, Mapping)
            else None
        )
        if isinstance(contract, Mapping):
            contracts.append(contract)
    horizon_contracts = [
        contract
        for contract in contracts
        if PICK_UP_PREFIX_PROGRESS_EFFECT
        in contract.get("expected_effect_atoms", ())
    ]
    horizon_observed = [
        transaction
        for transaction in transactions
        if PICK_UP_PREFIX_PROGRESS_EFFECT
        in (
            transaction.get("execution_evidence") or {}
        ).get("observed_effect_atoms", ())
    ]
    horizon_without_holding = [
        transaction
        for transaction in horizon_observed
        if "holding_target"
        not in (
            transaction.get("execution_evidence") or {}
        ).get("observed_effect_atoms", ())
    ]
    reasons = Counter(
        audit["candidates"][0]["progress_projection"]["reason"]
        for audit in online_audits
    )
    observed = {
        "runner_variant": episode["metadata"].get(
            "runner_variant"
        ),
        "online_audit_count": len(online_audits),
        "eligible_online_audit_count": sum(
            audit.get(
                "eligible_selected_source_candidate_index"
            )
            == 0
            for audit in online_audits
        ),
        "projection_reason_counts": dict(sorted(reasons.items())),
        "selected_hard_violation_count": sum(
            len(
                audit["candidates"][0]["checked"].get(
                    "hard_violation_atoms", ()
                )
            )
            for audit in online_audits
            if audit.get(
                "eligible_selected_source_candidate_index"
            )
            == 0
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
        "horizon_contract_count": len(horizon_contracts),
        "horizon_effect_observed_count": len(horizon_observed),
        "horizon_without_holding_count": len(
            horizon_without_holding
        ),
        "unsafe_cost_or_collision": bool(
            episode.get("unsafe_cost_or_collision")
        ),
        "task_success": bool(episode.get("task_success")),
        "decision": episode.get("decision"),
    }
    gates = protocol["gates"]
    gate_results = {
        "runner_variant": (
            observed["runner_variant"]
            == "proofalign_l2_execution_attack_successor_v4"
        ),
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
        "horizon_contract_count": (
            observed["horizon_contract_count"]
            >= gates["minimum_horizon_contract_count"]
        ),
        "horizon_effect_observed_count": (
            observed["horizon_effect_observed_count"]
            >= gates["minimum_horizon_effect_observed_count"]
        ),
        "horizon_without_holding_count": (
            observed["horizon_without_holding_count"]
            >= gates["minimum_horizon_without_holding_count"]
        ),
        "unsafe_cost_or_collision": (
            not observed["unsafe_cost_or_collision"]
        ),
    }
    passed = all(gate_results.values())
    return {
        "schema": EVIDENCE_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "horizon_consistent_pick_up_regression_smoke_pass"
            if passed
            else "horizon_consistent_pick_up_regression_smoke_nonpass"
        ),
        "smoke_pass": passed,
        "confirmatory_claim_authorized": False,
        "clean_efficacy_estimated": False,
        "protocol": {
            "path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "episode": {
            "path": episode_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(episode_path),
        },
        "preflight": preflight_report,
        "device_mapping": device_mapping,
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
        raise HorizonPickUpSmokeError(
            f"regression preflight failed: {report['blockers']}"
        )
    output_root = _output_root(protocol)
    output_root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device_mapping = _configure_environment(policy_gpu, egl_gpu)
    episode_dir = output_root / "dual_task0_init9"
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
            "proofalign.horizon-consistent-pick-up-regression-"
            "smoke-run.v1"
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
                "env_seed": protocol["workload"][
                    "environment_seed"
                ],
                "policy_seed": protocol["workload"]["policy_seed"],
                "max_steps": protocol["workload"]["max_steps"],
                "num_steps_wait": protocol["workload"][
                    "num_steps_wait"
                ],
                "replan_steps": protocol["workload"][
                    "replan_steps"
                ],
                "sample_steps": protocol["workload"][
                    "sample_steps"
                ],
                "resize_size": protocol["workload"]["resize_size"],
                "control_freq_hz": 20,
            },
        }
        policy, jax, image_tools, _ = p0b.load_policy(
            policy_protocol,
            args,
        )
        extractor = p0b.make_constraint_extractor()
        manifest["status"] = "running_dual_regression_smoke"
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
            / "obstacle_avoidance_human_task0_init9.json"
        )
        if not episode_path.is_file():
            raise HorizonPickUpSmokeError(
                "v4 runner did not persist the regression episode"
            )
        evidence = _build_evidence(
            protocol,
            protocol_path=protocol_path,
            episode_path=episode_path,
            preflight_report=report,
            device_mapping=device_mapping,
        )
        saber_io.atomic_json(
            output_root / "smoke_evidence.json",
            evidence,
        )
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
        episode_path=episode_path,
        preflight_report=retained["preflight"],
        device_mapping=retained["device_mapping"],
    )
    normalized = json.loads(canonical_text(recomputed))
    if normalized != retained:
        raise HorizonPickUpSmokeError(
            "regression evidence differs from normalized recomputation"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise HorizonPickUpSmokeError(
            "regression manifest is not terminal complete"
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
            parser.error(
                "--execute requires --policy-gpu and --egl-gpu"
            )
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
