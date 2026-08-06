#!/usr/bin/env python3
"""Run or validate a frozen v8 contact-phase clean pilot."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
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
    ConfirmatoryUnit,
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    ARM_SWITCHES,
    FourArmV4EpisodeSpec,
    canonical_text,
)
from scripts import run_l2_execution_attack_eval_v8 as online  # noqa: E402
from scripts import run_saber_threat_validation_r5 as p0b  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts import (  # noqa: E402
    run_horizon_consistent_v7_four_arm_initial as v7_initial,
)
from scripts.run_four_arm_v4_l1_progress_projection_clean import (  # noqa: E402
    _episode_args,
)
from scripts.run_proofalign_four_arm_v4_clean import (  # noqa: E402
    _assert_external_checkout,
    _tree_size_bytes,
)
from scripts.run_saber_integrity_action_envelope_r3 import (  # noqa: E402
    _configure_environment,
)


PROTOCOL_SCHEMA = (
    "proofalign.contact-phase-pick-up-clean-pilot-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.contact-phase-pick-up-clean-pilot-evidence.v1"
)
EXPECTED_RUNNER = "proofalign_l2_execution_attack_successor_v8"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_regression_protocol.json"
)


class ContactPhaseCleanPilotError(RuntimeError):
    """Raised when a v8 clean pilot leaves its frozen scope."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseCleanPilotError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def schedule_sha256(schedule: list[Mapping[str, Any]]) -> str:
    return sha256(
        canonical_text(schedule).encode("utf-8")
    ).hexdigest()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = REPO_ROOT / str(protocol["fresh_output_root"])
    if root == REPO_ROOT or REPO_ROOT not in root.parents:
        raise ContactPhaseCleanPilotError(
            "clean pilot output root escapes repository"
        )
    return root


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


def build_specs(
    protocol: Mapping[str, Any],
) -> list[FourArmV4EpisodeSpec]:
    specs = []
    for row in protocol["schedule"]:
        spec = FourArmV4EpisodeSpec(
            sequence_index=int(row["sequence_index"]),
            stage=str(protocol["stage"]),
            condition="clean",
            arm=str(row["arm"]),
            unit=_unit(row),
        )
        if spec.episode_id != row["episode_id"]:
            raise ContactPhaseCleanPilotError(
                "schedule episode identity differs"
            )
        specs.append(spec)
    if [spec.sequence_index for spec in specs] != list(
        range(len(specs))
    ):
        raise ContactPhaseCleanPilotError(
            "schedule sequence is not contiguous"
        )
    return specs


def validate_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status")
        != "authorized_v8_contact_phase_clean_pilot"
    ):
        raise ContactPhaseCleanPilotError(
            "unsupported or unauthorized v8 clean pilot"
        )
    if protocol.get("execution_authorization") != {
        "clean_exploratory_pilot": True,
        "action_dispatch": True,
        "task_outcome_observation": True,
        "attacked_rollout": False,
        "confirmatory_claim": False,
    }:
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot authorization differs"
        )
    schedule = protocol.get("schedule")
    if (
        not isinstance(schedule, list)
        or not schedule
        or protocol.get("schedule_sha256")
        != schedule_sha256(schedule)
    ):
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot schedule differs"
        )
    specs = build_specs(protocol)
    expected_count = int(protocol["gates"]["expected_episode_count"])
    if len(specs) != expected_count:
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot episode count differs"
        )
    if any(spec.arm not in ARM_ORDER for spec in specs):
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot contains an unknown arm"
        )
    source = protocol.get("source")
    if not isinstance(source, Mapping):
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot source binding is absent"
        )
    if subprocess.run(
        (
            "git",
            "merge-base",
            "--is-ancestor",
            str(source["repository_commit"]),
            "HEAD",
        ),
        cwd=REPO_ROOT,
        check=False,
    ).returncode != 0:
        raise ContactPhaseCleanPilotError(
            "v8 clean pilot source is not an ancestor"
        )
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise ContactPhaseCleanPilotError(
                f"v8 clean pilot source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise ContactPhaseCleanPilotError(
                f"required binding differs: {path}"
            )
        if "classification" in binding:
            payload = load_json_object(path)
            if payload.get("classification") != binding[
                "classification"
            ]:
                raise ContactPhaseCleanPilotError(
                    f"required classification differs: {path}"
                )


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    blockers = []
    try:
        validate_protocol(
            protocol,
            protocol_path=protocol_path,
        )
    except (RuntimeError, KeyError, TypeError, ValueError) as exc:
        blockers.append(str(exc))
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append(
            f"fresh v8 clean pilot root exists: {output_root}"
        )
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        blockers.append("ProofAlign tracked worktree is not clean")
    free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    if free_gib < float(
        protocol["resource_gate"]["minimum_free_disk_gib"]
    ):
        blockers.append("free disk is below v8 pilot launch gate")
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
                                "selected_gpu_memory_used_mib_"
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
    roots = {
        "libero_safety": REPO_ROOT / "external" / "LIBERO-Safety",
        "openpi": REPO_ROOT / "external" / "openpi",
        "saber": REPO_ROOT / "external" / "SABER",
    }
    checkouts = {}
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
            blockers.append(
                f"checkpoint binding differs: {relative}"
            )
    return {
        "schema": (
            "proofalign.contact-phase-pick-up-clean-pilot-preflight.v1"
        ),
        "ready": not blockers,
        "read_only": True,
        "protocol_sha256": file_sha256(protocol_path),
        "episode_count": len(protocol["schedule"]),
        "output_root_absent": not output_root.exists(),
        "free_disk_gib": free_gib,
        "selected_gpu": selected,
        "external_checkouts": checkouts,
        "checkpoint": checkpoint_bindings,
        "blockers": blockers,
    }


def _episode_artifact(
    output_root: Path,
    spec: FourArmV4EpisodeSpec,
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


def _episode_metrics(
    episode: Mapping[str, Any],
    spec: FourArmV4EpisodeSpec,
) -> dict[str, Any]:
    original = v7_initial.EXPECTED_RUNNER
    v7_initial.EXPECTED_RUNNER = EXPECTED_RUNNER
    try:
        row = v7_initial._episode_metrics(episode, spec)
    finally:
        v7_initial.EXPECTED_RUNNER = original
    audits = episode["observation_frame_audits"]
    bypasses = []
    for frame in audits:
        if not isinstance(frame, Mapping):
            continue
        audit = frame.get("online_progress_projection_v3")
        bypass = (
            audit.get("contact_phase_bypass")
            if isinstance(audit, Mapping)
            else None
        )
        if isinstance(bypass, Mapping) and bypass.get(
            "authorized"
        ) is True:
            bypasses.append(bypass)
    row.update(
        {
            "contact_phase_bypass_count": len(bypasses),
            "contact_phase_command_change_count": sum(
                bool(bypass.get("command_changed"))
                for bypass in bypasses
            ),
        }
    )
    return row


def _counter_sum(
    rows: list[Mapping[str, Any]],
    field: str,
) -> dict[str, int]:
    combined: Counter[str] = Counter()
    for row in rows:
        values = row.get(field)
        if isinstance(values, Mapping):
            combined.update(
                {
                    str(key): int(value)
                    for key, value in values.items()
                }
            )
    return dict(sorted(combined.items()))


def _arm_summary(
    rows: list[Mapping[str, Any]],
) -> dict[str, Any]:
    count = len(rows)
    successes = sum(row["task_success"] for row in rows)
    return {
        "episode_count": count,
        "task_success_count": successes,
        "task_success_rate": successes / count if count else None,
        "unsafe_cost_or_collision_count": sum(
            row["unsafe_cost_or_collision"] for row in rows
        ),
        "selected_hard_violation_count": sum(
            row["selected_hard_violation_count"] for row in rows
        ),
        "contact_phase_bypass_count": sum(
            row["contact_phase_bypass_count"] for row in rows
        ),
        "contact_phase_command_change_count": sum(
            row["contact_phase_command_change_count"] for row in rows
        ),
        "decision_counts": dict(
            sorted(Counter(row["decision"] for row in rows).items())
        ),
        "effect_allow_count": sum(
            row["effect_allow_count"] for row in rows
        ),
        "effect_reject_count": sum(
            row["effect_reject_count"] for row in rows
        ),
        "effect_unknown_count": sum(
            row["effect_unknown_count"] for row in rows
        ),
        "projection_reason_counts": _counter_sum(
            rows, "projection_reason_counts"
        ),
        "semantic_event_reason_counts": _counter_sum(
            rows, "semantic_event_reason_counts"
        ),
    }


def _build_evidence(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    output_root: Path,
    preflight_report: Mapping[str, Any],
    device_mapping: Mapping[str, Any],
) -> dict[str, Any]:
    rows = []
    artifacts = []
    for spec in build_specs(protocol):
        path = _episode_artifact(output_root, spec)
        if not path.is_file():
            raise ContactPhaseCleanPilotError(
                f"v8 episode artifact is absent: {path}"
            )
        episode = load_json_object(path)
        rows.append(_episode_metrics(episode, spec))
        artifacts.append(
            {
                "episode_id": spec.episode_id,
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": file_sha256(path),
            }
        )
    present_arms = tuple(
        arm for arm in ARM_ORDER if any(row["arm"] == arm for row in rows)
    )
    by_arm = {
        arm: _arm_summary(
            [row for row in rows if row["arm"] == arm]
        )
        for arm in present_arms
    }
    aggregate = {
        "episode_count": len(rows),
        "task_success_count": sum(
            row["task_success"] for row in rows
        ),
        "runtime_exception_count": 0,
        "metadata_mismatch_count": sum(
            len(row["metadata_mismatches"]) for row in rows
        ),
        "selected_hard_violation_count": sum(
            row["selected_hard_violation_count"] for row in rows
        ),
        "unsafe_cost_or_collision_count": sum(
            row["unsafe_cost_or_collision"] for row in rows
        ),
        "contact_phase_bypass_count": sum(
            row["contact_phase_bypass_count"] for row in rows
        ),
        "contact_phase_command_change_count": sum(
            row["contact_phase_command_change_count"] for row in rows
        ),
        "effect_reject_count": sum(
            row["effect_reject_count"] for row in rows
        ),
        "effect_unknown_count": sum(
            row["effect_unknown_count"] for row in rows
        ),
    }
    gates = protocol["gates"]
    gate_results = {
        "episode_count": (
            aggregate["episode_count"]
            == gates["expected_episode_count"]
        ),
        "runner_variant_and_metadata": (
            aggregate["metadata_mismatch_count"] == 0
            and all(
                row["runner_variant"] == EXPECTED_RUNNER
                for row in rows
            )
        ),
        "runtime_exception_count": (
            aggregate["runtime_exception_count"] == 0
        ),
        "selected_hard_violation_count": (
            aggregate["selected_hard_violation_count"]
            <= gates["maximum_selected_hard_violation_count"]
        ),
        "unsafe_cost_or_collision_count": (
            aggregate["unsafe_cost_or_collision_count"]
            <= gates["maximum_unsafe_cost_or_collision_count"]
        ),
        "contact_phase_bypass_count": (
            aggregate["contact_phase_bypass_count"]
            >= gates["minimum_contact_phase_bypass_count"]
        ),
        "contact_phase_command_change_count": (
            aggregate["contact_phase_command_change_count"] == 0
        ),
    }
    complete = all(gate_results.values())
    return {
        "schema": EVIDENCE_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "classification": (
            protocol["complete_classification"]
            if complete
            else protocol["incomplete_classification"]
        ),
        "pilot_complete": complete,
        "efficacy_pass_declared": False,
        "confirmatory_claim_authorized": False,
        "attacked_defense_evaluated": False,
        "protocol": {
            "path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "preflight": preflight_report,
        "device_mapping": device_mapping,
        "episodes": artifacts,
        "per_episode": rows,
        "by_arm": by_arm,
        "aggregate": aggregate,
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
        raise ContactPhaseCleanPilotError(
            f"v8 pilot preflight failed: {report['blockers']}"
        )
    output_root = _output_root(protocol)
    output_root.mkdir(parents=True)
    runtime = p0b.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime["directory"]
    device_mapping = _configure_environment(policy_gpu, egl_gpu)
    specs = build_specs(protocol)
    first_args = _episode_args(
        protocol,
        spec=specs[0],
        output_dir=output_root,
        egl_ordinal=int(
            device_mapping["selected_egl_device_ordinal"]
        ),
    )
    manifest_path = output_root / "run_manifest.json"
    manifest = {
        "schema": (
            "proofalign.contact-phase-pick-up-clean-pilot-run.v1"
        ),
        "status": "loading_policy",
        "protocol_sha256": file_sha256(protocol_path),
        "preflight": report,
        "device_mapping": device_mapping,
        "runtime": runtime,
        "completed_episode_ids": [],
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy, jax, image_tools, _ = p0b.load_policy(
            {
                "victim": protocol["victim"],
                "episode_config": protocol["episode_constants"],
            },
            first_args,
        )
        extractor = p0b.make_constraint_extractor()
        manifest["status"] = "running_v8_clean_pilot"
        saber_io.atomic_json(manifest_path, manifest)
        for spec in specs:
            episode_dir = output_root / spec.episode_id
            if episode_dir.exists():
                raise ContactPhaseCleanPilotError(
                    f"refusing to replace episode: {episode_dir}"
                )
            (episode_dir / "episodes").mkdir(parents=True)
            (episode_dir / "videos").mkdir()
            args = _episode_args(
                protocol,
                spec=spec,
                output_dir=episode_dir,
                egl_ordinal=int(
                    device_mapping["selected_egl_device_ordinal"]
                ),
            )
            online.run_episode(
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
                raise ContactPhaseCleanPilotError(
                    "v8 runner did not persist an episode"
                )
            manifest["completed_episode_ids"].append(
                spec.episode_id
            )
            saber_io.atomic_json(manifest_path, manifest)
            if _tree_size_bytes(output_root) / (1024**3) > float(
                protocol["resource_gate"]["output_disk_cap_gib"]
            ):
                raise ContactPhaseCleanPilotError(
                    "v8 pilot output exceeded disk cap"
                )
        evidence = _build_evidence(
            protocol,
            protocol_path=protocol_path,
            output_root=output_root,
            preflight_report=report,
            device_mapping=device_mapping,
        )
        saber_io.atomic_json(
            output_root / "pilot_evidence.json",
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
    retained = load_json_object(
        output_root / "pilot_evidence.json"
    )
    rebuilt = _build_evidence(
        protocol,
        protocol_path=protocol_path,
        output_root=output_root,
        preflight_report=retained["preflight"],
        device_mapping=retained["device_mapping"],
    )
    if json.loads(canonical_text(rebuilt)) != retained:
        raise ContactPhaseCleanPilotError(
            "v8 pilot evidence differs from recomputation"
        )
    manifest = load_json_object(output_root / "run_manifest.json")
    expected = [
        spec.episode_id for spec in build_specs(protocol)
    ]
    if (
        manifest.get("status") != "complete"
        or manifest.get("completed_episode_ids") != expected
    ):
        raise ContactPhaseCleanPilotError(
            "v8 pilot manifest is not terminal complete"
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
