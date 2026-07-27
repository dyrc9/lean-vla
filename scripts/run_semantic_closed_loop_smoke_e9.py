#!/usr/bin/env python3
"""Run or validate the authorized E9 semantic closed-loop engineering smoke."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_closed_loop_smoke_e9_protocol.json"
)
EVIDENCE_NAME = "smoke_evidence.json"
CHECKSUMS_NAME = "SMOKE_SHA256SUMS"


class SmokeError(RuntimeError):
    """Raised when the E9 protocol or evidence fails closed."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SmokeError(f"expected JSON object: {path}")
    return value


def git_output(*args: str, cwd: Path = REPO_ROOT) -> str:
    return subprocess.run(
        ("git", *args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_protocol(
    protocol: dict[str, Any],
    protocol_path: Path,
) -> Path:
    if (
        protocol.get("schema")
        != "proofalign.semantic-closed-loop-smoke-e9.v1"
    ):
        raise SmokeError("unsupported E9 protocol schema")
    if protocol.get("status") != (
        "authorized_benchmark_engineering_smoke"
    ):
        raise SmokeError("E9 protocol is not execution-authorized")
    authorization = protocol["execution_authorization"]
    required_true = (
        "explicit_user_authorization_received",
        "model_load_authorized",
        "gpu_execution_authorized",
        "simulator_creation_authorized",
        "action_dispatch_authorized",
        "outcome_read_authorized",
    )
    if any(authorization.get(name) is not True for name in required_true):
        raise SmokeError("E9 authorization is incomplete")
    if any(
        authorization.get(name) is not False
        for name in (
            "attack_execution_authorized",
            "m2_execution_authorized",
            "four_arm_execution_authorized",
        )
    ):
        raise SmokeError("E9 protocol authorizes work outside its smoke scope")
    source = protocol["source_binding"]
    if git_output("rev-parse", "HEAD") != source["repository_commit"]:
        raise SmokeError("repository HEAD differs from frozen E9 source")
    if git_output("rev-parse", "HEAD^{tree}") != source["repository_tree"]:
        raise SmokeError("repository tree differs from frozen E9 source")
    openpi_root = REPO_ROOT / "external" / "openpi"
    if git_output("rev-parse", "HEAD", cwd=openpi_root) != source[
        "openpi_commit"
    ]:
        raise SmokeError("OpenPI HEAD differs from frozen E9 source")
    if git_output(
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
        cwd=openpi_root,
    ):
        raise SmokeError("OpenPI tracked worktree is not clean")
    for relative, expected in {
        **source["sha256"],
        **protocol["qualified_input_sha256"],
    }.items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise SmokeError(f"E9 source/input binding is stale: {relative}")
    checkpoint = Path(protocol["checkpoint"]["path"])
    if not checkpoint.is_dir():
        raise SmokeError(f"E9 checkpoint is absent: {checkpoint}")
    boundary = protocol["deployment_perception_boundary"]
    if (
        boundary.get("deployment_stack_qualified") is not False
        or boundary.get("e7_remains_open") is not True
        or boundary.get(
            "deployment_perception_required_for_this_benchmark_smoke"
        )
        is not False
    ):
        raise SmokeError("E9 deployment claim boundary changed")
    output_root = REPO_ROOT / protocol["fresh_output_root"]
    if output_root == REPO_ROOT or REPO_ROOT not in output_root.parents:
        raise SmokeError("E9 output root escapes the repository")
    if protocol_path.resolve() != DEFAULT_PROTOCOL.resolve():
        if not protocol_path.is_file():
            raise SmokeError("E9 protocol path is absent")
    return output_root


def gpu_preflight(protocol: dict[str, Any]) -> dict[str, Any]:
    resources = protocol["selected_resources"]
    selected = {
        int(resources["policy_gpu_physical_index"]),
        int(resources["egl_gpu_physical_index"]),
    }
    rows = subprocess.run(
        (
            "nvidia-smi",
            "--query-gpu=index,name,memory.used,uuid",
            "--format=csv,noheader,nounits",
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.splitlines()
    observations = []
    for row in rows:
        index_text, name, memory_text, uuid = (
            value.strip() for value in row.split(",", 3)
        )
        index = int(index_text)
        if index not in selected:
            continue
        observations.append(
            {
                "index": index,
                "name": name,
                "memory_used_mib": int(memory_text),
                "uuid": uuid,
            }
        )
    if {row["index"] for row in observations} != selected:
        raise SmokeError("selected E9 GPUs are not visible")
    limit = int(resources["maximum_prelaunch_memory_used_mib"])
    if any(row["memory_used_mib"] >= limit for row in observations):
        raise SmokeError(f"selected E9 GPU exceeds memory gate: {observations}")
    process_text = subprocess.run(
        (
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name",
            "--format=csv,noheader",
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    ).stdout.strip()
    selected_uuids = {row["uuid"] for row in observations}
    external = [
        row
        for row in process_text.splitlines()
        if row and row.split(",", 1)[0].strip() in selected_uuids
    ]
    if (
        resources["require_no_external_compute_process"]
        and external
    ):
        raise SmokeError(
            f"selected E9 GPU has external compute process: {external}"
        )
    return {
        "gpu_observations": observations,
        "external_compute_processes": external,
        "passed": True,
    }


def build_evidence(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
    preflight: dict[str, Any],
    device_mapping: dict[str, Any],
) -> dict[str, Any]:
    summary = load_object(output_root / "summary.json")
    workload = protocol["workload"]
    episode_path = (
        output_root
        / "episodes"
        / (
            f"{workload['suite']}_task{workload['task_id']}_"
            f"init{workload['init_state_id']}.json"
        )
    )
    episode = load_object(episode_path)
    audits = episode.get("observation_frame_audits", [])
    events = episode.get("semantic_events", [])
    transactions = [
        transaction
        for audit in audits
        if (
            transaction := audit.get("semantic_transaction")
        )
        is not None
    ]
    receipt_count = sum(
        len(transaction.get("step_receipts", []))
        for transaction in transactions
    )
    authorized_count = sum(
        event.get("authorization_status") == "authorized"
        for event in events
    )
    policy_call_count = sum(
        trace.get("phase") == "policy"
        and trace.get("policy_call") is not None
        for trace in episode.get("trace", [])
    )
    observed = {
        "episode_count": int(summary.get("total_episodes", 0)),
        "runner_failure_count": int(summary.get("runner_failures", 0)),
        "policy_call_count": policy_call_count,
        "semantic_event_count": len(events),
        "authorized_event_count": authorized_count,
        "dispatch_receipt_count": receipt_count,
        "effect_allow_count": sum(
            transaction.get("effect_verdict") == "allow"
            for transaction in transactions
        ),
        "effect_reject_count": sum(
            transaction.get("effect_verdict") == "reject"
            for transaction in transactions
        ),
        "effect_unknown_count": sum(
            transaction.get("effect_verdict") == "unknown"
            for transaction in transactions
        ),
        "cost_or_collision_episode_count": int(
            summary.get("episodes_with_cost_or_collision", 0)
        ),
        "decision": episode.get("decision"),
        "task_success": episode.get("task_success"),
        "strict_success_no_cost": episode.get(
            "strict_success_no_cost"
        ),
        "episode_wall_time_seconds": (
            episode.get("runtime") or {}
        ).get("episode_wall_time_seconds"),
    }
    gates = protocol["gates"]
    gate_results = {
        "episode_count": (
            observed["episode_count"]
            == gates["expected_episode_count"]
        ),
        "runner_failure_count": (
            observed["runner_failure_count"]
            <= gates["maximum_runner_failure_count"]
        ),
        "policy_call_count": (
            observed["policy_call_count"]
            >= gates["minimum_policy_call_count"]
        ),
        "semantic_event_count": (
            observed["semantic_event_count"]
            >= gates["minimum_semantic_event_count"]
        ),
        "authorized_event_count": (
            observed["authorized_event_count"]
            >= gates["minimum_authorized_event_count"]
        ),
        "dispatch_receipt_count": (
            observed["dispatch_receipt_count"]
            >= gates["minimum_dispatch_receipt_count"]
        ),
        "cost_or_collision_episode_count": (
            observed["cost_or_collision_episode_count"]
            <= gates["maximum_cost_or_collision_episode_count"]
        ),
    }
    if "minimum_effect_allow_count" in gates:
        gate_results["effect_allow_count"] = (
            observed["effect_allow_count"]
            >= gates["minimum_effect_allow_count"]
        )
    if "maximum_effect_reject_count" in gates:
        gate_results["effect_reject_count"] = (
            observed["effect_reject_count"]
            <= gates["maximum_effect_reject_count"]
        )
    if "maximum_effect_unknown_count" in gates:
        gate_results["effect_unknown_count"] = (
            observed["effect_unknown_count"]
            <= gates["maximum_effect_unknown_count"]
        )
    if "forbidden_episode_decisions" in gates:
        gate_results["episode_decision"] = (
            observed["decision"]
            not in gates["forbidden_episode_decisions"]
        )
    passed = all(gate_results.values())
    return {
        "schema": "proofalign.semantic-closed-loop-smoke-e9-evidence.v1",
        "protocol_id": protocol["protocol_id"],
        "classification": (
            "semantic_closed_loop_engineering_smoke_pass"
            if passed
            else "semantic_closed_loop_engineering_smoke_fail"
        ),
        "smoke_passed": passed,
        "protocol_binding": {
            "path": str(protocol_path.relative_to(REPO_ROOT)),
            "sha256": file_sha256(protocol_path),
        },
        "source_commit": protocol["source_binding"][
            "repository_commit"
        ],
        "preflight": preflight,
        "device_mapping": device_mapping,
        "observed": observed,
        "gate_results": gate_results,
        "episode_binding": {
            "path": str(episode_path.relative_to(REPO_ROOT)),
            "sha256": file_sha256(episode_path),
        },
        "summary_binding": {
            "path": str(
                (output_root / "summary.json").relative_to(REPO_ROOT)
            ),
            "sha256": file_sha256(output_root / "summary.json"),
        },
        "deployment_perception_qualified": False,
        "efficacy_estimated": False,
        "claim_boundary": protocol["claim_boundary"],
    }


def execute(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
) -> int:
    if output_root.exists():
        raise SmokeError(
            f"refusing to replace E9 output root: {output_root}"
        )
    preflight = gpu_preflight(protocol)
    from scripts import run_saber_threat_validation_r5 as p0b
    from scripts.run_saber_integrity_action_envelope_r3 import (
        _configure_environment,
        _egl_cuda_device_mapping,
    )

    resources = protocol["selected_resources"]
    policy_gpu = int(resources["policy_gpu_physical_index"])
    egl_gpu = int(resources["egl_gpu_physical_index"])
    if policy_gpu == egl_gpu:
        # The vendored robosuite import guard compares an EGL ordinal with the
        # textual CUDA list.  Expose one unused shim index, select the EGL
        # ordinal that maps back to the shared physical GPU, and restrict JAX
        # programmatically to local CUDA device zero.
        shim_gpu = 1 if policy_gpu != 1 else 0
        p0b.configure_environment(
            policy_gpu,
            shim_gpu,
            "proofalign-semantic-closed-loop-smoke-e9",
        )
        mapping = _egl_cuda_device_mapping()
        ordinals = [
            int(row["egl_device_ordinal"])
            for row in mapping
            if int(row["cuda_physical_index"]) == egl_gpu
        ]
        if len(ordinals) != 1:
            raise SmokeError(
                "shared policy/EGL GPU has no exact EGL ordinal: "
                f"{mapping}"
            )
        egl_ordinal = ordinals[0]
        os.environ["MUJOCO_EGL_DEVICE_ID"] = str(egl_ordinal)
        import jax

        jax.config.update("jax_cuda_visible_devices", "0")
        device_mapping = {
            "mapping_source": "EGL_NV_device_cuda",
            "mapping": mapping,
            "requested_egl_physical_index": egl_gpu,
            "selected_egl_device_ordinal": egl_ordinal,
            "cuda_visible_devices": os.environ["CUDA_VISIBLE_DEVICES"],
            "jax_cuda_visible_devices": "0",
            "policy_and_egl_share_physical_gpu": True,
            "shim_gpu_has_no_runtime_role": shim_gpu,
        }
    else:
        device_mapping = _configure_environment(policy_gpu, egl_gpu)
    runtime_config = p0b.ensure_libero_runtime_config(output_root)
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    os.environ["MUJOCO_GL"] = "egl"
    workload = protocol["workload"]
    checkpoint = protocol["checkpoint"]
    argv = [
        "run_liberosafety_pi05_openpi_eval.py",
        "--checkpoint-dir",
        checkpoint["path"],
        "--openpi-config",
        checkpoint["openpi_config"],
        "--output-dir",
        str(output_root),
        "--suites",
        workload["suite"],
        "--task-ids",
        str(workload["task_id"]),
        "--init-state-ids",
        str(workload["init_state_id"]),
        "--max-steps",
        str(workload["max_steps"]),
        "--num-steps-wait",
        str(workload["num_steps_wait"]),
        "--replan-steps",
        str(workload["replan_steps"]),
        "--sample-steps",
        str(workload["sample_steps"]),
        "--seed",
        str(workload["environment_seed"]),
        "--policy-seed",
        str(workload["policy_seed"]),
        "--render-gpu-device-id",
        str(device_mapping["selected_egl_device_ordinal"]),
        "--semantic-runtime",
        "--semantic-policy-mode",
        workload["semantic_policy_mode"],
        "--continue-on-error",
    ]
    if workload["save_video"]:
        argv.append("--save-video")
    old_argv = sys.argv
    try:
        sys.argv = argv
        from scripts import run_liberosafety_pi05_openpi_eval as runner

        runner.main()
    finally:
        sys.argv = old_argv
    evidence = build_evidence(
        protocol,
        protocol_path,
        output_root,
        preflight,
        device_mapping,
    )
    evidence_path = output_root / EVIDENCE_NAME
    evidence_path.write_text(
        canonical_text(evidence),
        encoding="utf-8",
    )
    (output_root / CHECKSUMS_NAME).write_text(
        f"{file_sha256(evidence_path)}  {EVIDENCE_NAME}\n",
        encoding="utf-8",
    )
    print(canonical_text(evidence))
    return 0 if evidence["smoke_passed"] else 2


def check_evidence(
    protocol: dict[str, Any],
    protocol_path: Path,
    output_root: Path,
) -> int:
    evidence_path = output_root / EVIDENCE_NAME
    evidence = load_object(evidence_path)
    if evidence["protocol_binding"] != {
        "path": str(protocol_path.relative_to(REPO_ROOT)),
        "sha256": file_sha256(protocol_path),
    }:
        raise SmokeError("E9 evidence protocol binding is stale")
    for key in ("episode_binding", "summary_binding"):
        binding = evidence[key]
        path = REPO_ROOT / binding["path"]
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise SmokeError(f"E9 evidence binding is stale: {path}")
    expected_checksum = f"{file_sha256(evidence_path)}  {EVIDENCE_NAME}\n"
    if (output_root / CHECKSUMS_NAME).read_text(
        encoding="utf-8"
    ) != expected_checksum:
        raise SmokeError("E9 smoke evidence checksum is stale")
    print(
        json.dumps(
            {
                "classification": evidence["classification"],
                "smoke_passed": evidence["smoke_passed"],
                "observed": evidence["observed"],
                "gate_results": evidence["gate_results"],
            },
            indent=2,
        )
    )
    return 0 if evidence["smoke_passed"] else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    try:
        protocol = load_object(protocol_path)
        output_root = validate_protocol(protocol, protocol_path)
        if args.preflight:
            if output_root.exists():
                raise SmokeError(
                    f"E9 output root already exists: {output_root}"
                )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "output_root_absent": True,
                        "source_bound": True,
                        "gpu_preflight": gpu_preflight(protocol),
                    },
                    indent=2,
                )
            )
            return 0
        if args.execute:
            return execute(protocol, protocol_path, output_root)
        return check_evidence(protocol, protocol_path, output_root)
    except (
        KeyError,
        OSError,
        SmokeError,
        subprocess.CalledProcessError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
