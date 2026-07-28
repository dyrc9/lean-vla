#!/usr/bin/env python3
"""Run or validate the authorized progress-projection clean screening stage."""

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
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_SWITCHES,
    canonical_text,
    ledger_row_from_episode_payload,
    read_ledger,
    verify_episode_artifacts,
)
from proofalign.benchmark.four_arm_v4_progress_clean import (  # noqa: E402
    STAGE_SCREEN,
    ProgressProjectionCleanError,
    build_analysis,
    build_schedule,
    validate_protocol,
    validate_rows,
)
from scripts import run_l2_execution_attack_eval_v3 as online  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_proofalign_four_arm_v4_clean import (  # noqa: E402
    _assert_external_checkout,
    _tree_size_bytes,
)
from scripts.run_saber_integrity_action_envelope_r3 import (  # noqa: E402
    _configure_environment,
)


DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "clean_screening_protocol.json"
)
QUALIFICATION_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_progress_projection_"
    "qualification_protocol.json"
)


class ProgressProjectionCleanRunnerError(RuntimeError):
    """Raised when clean screening must stop fail-closed."""


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_roots"]["screening_clean"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise ProgressProjectionCleanRunnerError(
            "clean screening root escapes repository"
        )
    return root


def _episode_args(
    protocol: Mapping[str, Any],
    *,
    spec: Any,
    output_dir: Path,
    egl_ordinal: int,
) -> SimpleNamespace:
    constants = protocol["episode_constants"]
    victim = protocol["victim"]
    l1_enabled, l2_enabled = ARM_SWITCHES[spec.arm]
    return SimpleNamespace(
        checkpoint_dir=Path(victim["checkpoint"]),
        openpi_config=victim["config"],
        output_dir=output_dir,
        max_steps=int(constants["max_steps"]),
        num_steps_wait=int(constants["num_steps_wait"]),
        env_img_res=256,
        resize_size=int(constants["resize_size"]),
        replan_steps=int(constants["replan_steps"]),
        sample_steps=int(constants["sample_steps"]),
        seed=int(spec.unit.env_seed),
        policy_seed=int(spec.unit.policy_seed),
        policy_seeds=None,
        render_gpu_device_id=egl_ordinal,
        camera_names="agentview,robot0_eye_in_hand",
        control_freq=int(constants["control_freq_hz"]),
        horizon=1000,
        save_video=False,
        continue_on_error=False,
        attack_record=None,
        observation_attack_type="none",
        observation_attack_strength=None,
        semantic_runtime=l1_enabled,
        semantic_policy_mode="deployment",
        semantic_max_projection_l2=0.5,
        semantic_min_progress_m=None,
        semantic_candidate_count=1,
        semantic_authorization_ttl_ns=60_000_000_000,
        execution_attack_family="none",
        execution_attack_placement="pre_boundary",
        l1_semantic_alignment="on" if l1_enabled else "off",
        l2_execution_integrity="on" if l2_enabled else "off",
        _multiple_policy_seeds=False,
    )


def _episode_artifact(
    output_root: Path,
    spec: Any,
) -> Path:
    return (
        output_root
        / spec.episode_id
        / "episodes"
        / (
            f"{spec.unit.suite}_task{spec.unit.task_id}_"
            f"init{spec.unit.init_state_id}.json"
        )
    )


def _online_metrics(
    payload: Mapping[str, Any],
    *,
    l1_enabled: bool,
) -> dict[str, Any]:
    audits = payload.get("observation_frame_audits")
    if not isinstance(audits, list):
        raise ProgressProjectionCleanRunnerError(
            "episode lacks observation frame audits"
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
    if not l1_enabled:
        if online_audits:
            raise ProgressProjectionCleanRunnerError(
                "non-L1 arm unexpectedly contains online projection audits"
            )
        return {
            "online_audit_count": 0,
            "online_eligible_audit_count": 0,
            "online_selected_hard_violation_count": 0,
            "online_projection_reason_counts": {},
            "online_release_bypass_count": 0,
        }
    reason_counts: Counter[str] = Counter()
    selected_hard = 0
    eligible = 0
    release_bypass = 0
    for audit in online_audits:
        candidates = audit.get("candidates")
        if (
            not isinstance(candidates, list)
            or len(candidates) != 1
            or not isinstance(candidates[0], Mapping)
        ):
            raise ProgressProjectionCleanRunnerError(
                "online audit does not contain exactly one candidate"
            )
        candidate = candidates[0]
        projection = candidate.get("progress_projection")
        checked = candidate.get("checked")
        if (
            not isinstance(projection, Mapping)
            or not isinstance(checked, Mapping)
        ):
            raise ProgressProjectionCleanRunnerError(
                "online projection or checked audit is absent"
            )
        reason = str(projection.get("reason", ""))
        if not reason:
            raise ProgressProjectionCleanRunnerError(
                "online projection reason is absent"
            )
        reason_counts[reason] += 1
        selected = (
            audit.get("eligible_selected_source_candidate_index") == 0
        )
        eligible += int(selected)
        if selected:
            violations = checked.get("hard_violation_atoms")
            if not isinstance(violations, (list, tuple)):
                raise ProgressProjectionCleanRunnerError(
                    "selected hard-violation audit is malformed"
                )
            selected_hard += len(violations)
        release_bypass += int(
            reason
            == "nominal_checker_eligible_without_projection:release"
        )
    return {
        "online_audit_count": len(online_audits),
        "online_eligible_audit_count": eligible,
        "online_selected_hard_violation_count": selected_hard,
        "online_projection_reason_counts": dict(
            sorted(reason_counts.items())
        ),
        "online_release_bypass_count": release_bypass,
    }


def _validate_source_and_smoke(protocol: Mapping[str, Any]) -> None:
    source = protocol.get("source")
    bindings = (
        source.get("sha256")
        if isinstance(source, Mapping)
        else None
    )
    if not isinstance(bindings, Mapping) or not bindings:
        raise ProgressProjectionCleanRunnerError(
            "clean screening source bindings are absent"
        )
    ancestor = _git(
        "merge-base",
        "--is-ancestor",
        str(source["repository_commit"]),
        "HEAD",
    )
    if ancestor.returncode != 0:
        raise ProgressProjectionCleanRunnerError(
            "clean screening source commit is not an ancestor"
        )
    for relative, expected in bindings.items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ProgressProjectionCleanRunnerError(
                f"clean screening source binding differs: {relative}"
            )
    smoke = protocol.get("required_smoke_successor")
    if not isinstance(smoke, Mapping):
        raise ProgressProjectionCleanRunnerError(
            "required smoke binding is absent"
        )
    evidence_path = REPO_ROOT / str(smoke.get("evidence_path", ""))
    if (
        not evidence_path.is_file()
        or file_sha256(evidence_path) != smoke.get("evidence_sha256")
    ):
        raise ProgressProjectionCleanRunnerError(
            "closed-loop smoke evidence binding differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("classification")
        != "l1_progress_projection_closed_loop_smoke_pass"
        or evidence.get("smoke_pass") is not True
    ):
        raise ProgressProjectionCleanRunnerError(
            "closed-loop smoke did not pass"
        )


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    blockers = []
    try:
        validate_protocol(
            protocol,
            qualification_protocol=qualification,
            allow_execution=True,
        )
        _validate_source_and_smoke(protocol)
    except (ProgressProjectionCleanError, RuntimeError, KeyError) as exc:
        blockers.append(str(exc))
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append(f"fresh clean screening root exists: {output_root}")
    status = _git(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    if status.returncode != 0 or status.stdout.strip():
        blockers.append("ProofAlign tracked worktree is not clean")
    selected = None
    if policy_gpu is None or egl_gpu is None:
        blockers.append("policy and EGL GPUs are not selected")
    else:
        try:
            selected = p0b.validate_gpu_selection(
                {
                    "execution_gate": {
                        "selected_gpu_memory_used_mib_max_exclusive": (
                            protocol["resource_budget"][
                                "selected_gpu_prelaunch_memory_used_mib_"
                                "max_exclusive"
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
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < float(
        protocol["resource_budget"]["minimum_free_disk_gib_at_launch"]
    ):
        blockers.append("free disk is below clean screening launch gate")
    checkouts = {}
    roots = {
        "libero_safety": REPO_ROOT / "external" / "LIBERO-Safety",
        "openpi": REPO_ROOT / "external" / "openpi",
        "saber": REPO_ROOT / "external" / "SABER",
    }
    for label, commit in protocol["runtime_dependency"][
        "external_checkout_commits"
    ].items():
        try:
            checkouts[label] = _assert_external_checkout(
                roots[label],
                expected_commit=commit,
                label=label,
            )
        except (RuntimeError, KeyError) as exc:
            blockers.append(str(exc))
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
            "proofalign.four-arm-v4-progress-projection-clean-"
            "screening-preflight.v1"
        ),
        "ready": not blockers,
        "read_only": True,
        "protocol_path": protocol_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "protocol_sha256": file_sha256(protocol_path),
        "episode_count": 60,
        "output_root": output_root.relative_to(REPO_ROOT).as_posix(),
        "output_root_absent": not output_root.exists(),
        "selected_gpu": selected,
        "free_disk_gib": free_gib,
        "external_checkouts": checkouts,
        "checkpoint": checkpoint_bindings,
        "blockers": blockers,
    }


def _run_episode(
    protocol: dict[str, Any],
    *,
    spec: Any,
    output_root: Path,
    ledger_path: Path,
    policy: Any,
    jax: Any,
    image_tools: Any,
    egl_ordinal: int,
    extractor: Any,
) -> dict[str, Any]:
    episode_dir = output_root / spec.episode_id
    if episode_dir.exists():
        raise ProgressProjectionCleanRunnerError(
            f"refusing to replace clean episode: {episode_dir}"
        )
    (episode_dir / "episodes").mkdir(parents=True)
    (episode_dir / "videos").mkdir()
    args = _episode_args(
        protocol,
        spec=spec,
        output_dir=episode_dir,
        egl_ordinal=egl_ordinal,
    )
    payload = online.run_episode(
        args=args,
        policy=policy,
        jax=jax,
        policy_seed=spec.unit.policy_seed,
        image_tools=image_tools,
        suite=spec.unit.suite,
        task_id=spec.unit.task_id,
        init_state_id=spec.unit.init_state_id,
        attack_records={},
        output_dir=episode_dir,
        observation_transform=None,
        wrist_observation_transform=None,
        constraint_signal_extractor=extractor,
    )
    artifact = _episode_artifact(output_root, spec)
    if not artifact.is_file():
        raise ProgressProjectionCleanRunnerError(
            f"episode artifact is absent: {artifact}"
        )
    row = ledger_row_from_episode_payload(
        protocol,
        spec,
        payload,
        episode_artifact_path=artifact.relative_to(
            output_root
        ).as_posix(),
        episode_artifact_sha256=file_sha256(artifact),
    )
    l1_enabled, _l2_enabled = ARM_SWITCHES[spec.arm]
    row.update(
        _online_metrics(payload, l1_enabled=l1_enabled)
    )
    saber_io.append_ledger(ledger_path, row)
    if row["attempt_status"] != "valid":
        raise ProgressProjectionCleanRunnerError(
            f"clean episode is invalid: {spec.episode_id}: {row['issues']}"
        )
    return row


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
        raise ProgressProjectionCleanRunnerError(
            f"clean screening preflight failed: {report['blockers']}"
        )
    output_root = _output_root(protocol)
    output_root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device_mapping = _configure_environment(policy_gpu, egl_gpu)
    specs = build_schedule(protocol, stage=STAGE_SCREEN)
    first_args = _episode_args(
        protocol,
        spec=specs[0],
        output_dir=output_root,
        egl_ordinal=int(
            device_mapping["selected_egl_device_ordinal"]
        ),
    )
    manifest_path = output_root / "run_manifest.json"
    ledger_path = output_root / "episodes_ledger.jsonl"
    manifest = {
        "schema": (
            "proofalign.four-arm-v4-progress-projection-clean-"
            "screening-run.v1"
        ),
        "status": "loading_policy",
        "protocol_sha256": file_sha256(protocol_path),
        "preflight": report,
        "device_mapping": device_mapping,
        "runtime": runtime,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy_protocol = {
            "victim": protocol["victim"],
            "episode_config": protocol["episode_constants"],
        }
        policy, jax, image_tools, _ = p0b.load_policy(
            policy_protocol,
            first_args,
        )
        extractor = p0b.make_constraint_extractor()
        manifest["status"] = "running_clean_screening"
        saber_io.atomic_json(manifest_path, manifest)
        for spec in specs:
            _run_episode(
                protocol,
                spec=spec,
                output_root=output_root,
                ledger_path=ledger_path,
                policy=policy,
                jax=jax,
                image_tools=image_tools,
                egl_ordinal=int(
                    device_mapping["selected_egl_device_ordinal"]
                ),
                extractor=extractor,
            )
            output_gib = _tree_size_bytes(output_root) / (1024**3)
            if output_gib > 2.0:
                raise ProgressProjectionCleanRunnerError(
                    "clean screening output exceeded 2 GiB"
                )
        rows = read_ledger(ledger_path)
        validate_rows(protocol, rows, stages=(STAGE_SCREEN,))
        verify_episode_artifacts(rows, artifact_root=output_root)
        analysis = build_analysis(protocol, rows, full=False)
        saber_io.atomic_json(output_root / "analysis.json", analysis)
        manifest["status"] = "complete"
        manifest["classification"] = analysis["classification"]
        saber_io.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        return analysis
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        saber_io.atomic_json(manifest_path, manifest)
        p0b.write_checksums(output_root)
        raise


def validate_results(
    protocol: dict[str, Any],
) -> dict[str, Any]:
    qualification = load_json_object(QUALIFICATION_PROTOCOL_PATH)
    validate_protocol(
        protocol,
        qualification_protocol=qualification,
        allow_execution=True,
    )
    _validate_source_and_smoke(protocol)
    output_root = _output_root(protocol)
    p0b.read_checksums(output_root)
    manifest = load_json_object(output_root / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise ProgressProjectionCleanRunnerError(
            "clean screening manifest is not terminal complete"
        )
    rows = read_ledger(output_root / "episodes_ledger.jsonl")
    validate_rows(protocol, rows, stages=(STAGE_SCREEN,))
    verify_episode_artifacts(rows, artifact_root=output_root)
    recomputed = build_analysis(protocol, rows, full=False)
    retained = load_json_object(output_root / "analysis.json")
    if retained != recomputed:
        raise ProgressProjectionCleanRunnerError(
            "clean screening analysis differs from recomputation"
        )
    return recomputed


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
        payload = validate_results(protocol)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
