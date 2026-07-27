#!/usr/bin/env python3
"""Freeze and preflight the no-simulator semantic resource smoke."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from probe_pi05_semantic_subtasks import (  # noqa: E402
    checkpoint_identity,
)


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_resource_smoke_e6_v2_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_semantic_resource_smoke_e6_v2_20260727_fresh1"
)
CHECKPOINT = Path("/data0/ldx/libero_safety_models/pi05_libero_safety")
SELECTED_GPU = {
    "physical_index": 0,
    "uuid": "GPU-7ad5c3eb-adf0-f70a-e670-8438701a553e",
    "name": "NVIDIA RTX 6000 Ada Generation",
}
SOURCE_PATHS = (
    "scripts/prepare_semantic_resource_smoke_e6.py",
    "scripts/run_pi05_action_conditioning_e2.py",
    "scripts/run_liberosafety_pi05_openpi_eval.py",
    "src/proofalign/semantic_policy_wrapper.py",
    "src/proofalign/semantic_local_checker.py",
    "src/proofalign/semantic_effect_observer.py",
    "src/proofalign/integrity_v4_models.py",
    "src/proofalign/integrity_v4_runtime.py",
)
INPUT_PATHS = (
    "experiments/proofalign_pi05_action_conditioning_e2_protocol.json",
    (
        "results/proofalign_action_conditioning_e2_20260725_fresh1/"
        "qualification.json"
    ),
    "experiments/proofalign_deterministic_selector_e1f.json",
    (
        "results/proofalign_local_checker_e3_v2_20260727_fresh1/"
        "qualification.json"
    ),
    (
        "results/proofalign_semantic_effect_observer_e5_v2_20260727_fresh1/"
        "qualification.json"
    ),
)


class ResourceSmokePreflightError(RuntimeError):
    """Raised when the frozen E6 preregistration is stale."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def build_protocol() -> dict[str, Any]:
    return {
        "schema": "proofalign.semantic-resource-smoke-e6.v1",
        "protocol_id": "proofalign-semantic-resource-smoke-e6-v2-20260727",
        "status": "frozen_waiting_explicit_model_load_authorization",
        "created_at": "2026-07-27T00:00:00+08:00",
        "predecessor": {
            "path": (
                "experiments/"
                "proofalign_semantic_resource_smoke_e6_protocol.json"
            ),
            "scope": (
                "Preserves the E6 workload and gates while rebinding the "
                "qualified v2 checker/effect-observer stack and a fresh GPU."
            ),
        },
        "checkpoint": checkpoint_identity(CHECKPOINT),
        "selected_gpu": SELECTED_GPU,
        "workload": {
            "source": (
                "the 100 frozen E2 fixed-observation snapshots, using the "
                "exact prompt template, fixed flow-noise construction, "
                "deterministic FSM, analytic local checker, v4 artifact "
                "construction, and analytic effect-observer microfixtures"
            ),
            "snapshot_count": 100,
            "measured_policy_passes": 3,
            "warmup_policy_calls": 1,
            "expected_measured_policy_calls": 300,
            "simulator_required": False,
            "action_sink_required": False,
            "reward_or_success_required": False,
            "gpu_monitor_interval_ms": 100,
        },
        "gates": {
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive": 4096,
            "selected_gpu_external_compute_process_count": 0,
            "maximum_checkpoint_load_seconds": 60.0,
            "maximum_warm_policy_p99_seconds": 0.150,
            "maximum_semantic_pipeline_p99_seconds": 0.250,
            "maximum_component_cpu_p99_ns": 1_000_000,
            "maximum_peak_process_gpu_memory_mib": 24_576,
            "maximum_peak_process_rss_mib": 24_576,
            "maximum_output_bytes": 1_073_741_824,
            "minimum_repeat_exact_rate": 1.0,
        },
        "measurement_requirements": {
            "checkpoint_load_wall_time": True,
            "warm_policy_latency_p50_p95_p99": True,
            "semantic_pipeline_latency_p50_p95_p99": True,
            "selector_checker_observer_cpu_latency": True,
            "process_gpu_memory_peak": True,
            "process_rss_peak": True,
            "output_bytes": True,
            "exact_action_digest_repeatability": True,
        },
        "source_sha256": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in SOURCE_PATHS
        },
        "input_artifact_sha256": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in INPUT_PATHS
        },
        "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "explicit_user_authorization_received": False,
            "model_load_authorized": False,
            "gpu_execution_authorized": False,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
        },
        "successor_rule": (
            "Execution requires a fresh successor protocol that preserves "
            "this workload and gates, records the user's explicit "
            "authorization, rechecks source/input bindings, and uses a new "
            "absent output root. This preregistration itself cannot execute."
        ),
        "claim_boundary": (
            "Engineering latency/resource measurement only. Even a passing "
            "successor smoke would not measure task outcome, defense "
            "efficacy, deployment perception, or physical safety."
        ),
    }


def validate_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.semantic-resource-smoke-e6.v1"
    ):
        raise ResourceSmokePreflightError(
            "unsupported E6 protocol schema"
        )
    if protocol["status"] != (
        "frozen_waiting_explicit_model_load_authorization"
    ):
        raise ResourceSmokePreflightError("E6 status changed")
    if protocol["selected_gpu"] != SELECTED_GPU:
        raise ResourceSmokePreflightError("E6 selected GPU changed")
    if protocol["fresh_output_root"] != str(
        OUTPUT_ROOT.relative_to(REPO_ROOT)
    ):
        raise ResourceSmokePreflightError(
            "E6 fresh output root changed"
        )
    if any(protocol["execution_authorization"].values()):
        raise ResourceSmokePreflightError(
            "E6 preregistration unexpectedly authorizes execution"
        )
    if protocol["workload"]["simulator_required"] is not False:
        raise ResourceSmokePreflightError(
            "E6 workload unexpectedly requires a simulator"
        )
    for relative, expected in protocol["source_sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ResourceSmokePreflightError(
                f"E6 source binding is stale: {relative}"
            )
    for relative, expected in protocol[
        "input_artifact_sha256"
    ].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ResourceSmokePreflightError(
                f"E6 input binding is stale: {relative}"
            )
    if protocol["checkpoint"] != checkpoint_identity(CHECKPOINT):
        raise ResourceSmokePreflightError(
            "E6 checkpoint binding is stale"
        )


def _gpu_inventory() -> list[dict[str, Any]]:
    completed = subprocess.run(
        (
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.used,memory.total,"
            "utilization.gpu",
            "--format=csv,noheader,nounits",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    rows = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 6:
            raise ResourceSmokePreflightError(
                f"unexpected nvidia-smi GPU row: {line}"
            )
        rows.append(
            {
                "physical_index": int(parts[0]),
                "uuid": parts[1],
                "name": parts[2],
                "memory_used_mib": int(parts[3]),
                "memory_total_mib": int(parts[4]),
                "utilization_percent": int(parts[5]),
            }
        )
    return rows


def _compute_processes() -> list[dict[str, Any]]:
    completed = subprocess.run(
        (
            "nvidia-smi",
            "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    rows = []
    for line in completed.stdout.splitlines():
        if not line.strip():
            continue
        parts = [part.strip() for part in line.split(",", 3)]
        if len(parts) != 4:
            raise ResourceSmokePreflightError(
                f"unexpected nvidia-smi process row: {line}"
            )
        rows.append(
            {
                "gpu_uuid": parts[0],
                "pid": int(parts[1]),
                "process_name": parts[2],
                "used_memory_mib": int(parts[3]),
            }
        )
    return rows


def build_preflight(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_protocol(protocol)
    inventory = _gpu_inventory()
    selected = [
        row
        for row in inventory
        if row["physical_index"]
        == protocol["selected_gpu"]["physical_index"]
    ]
    if len(selected) != 1:
        raise ResourceSmokePreflightError(
            "selected E6 GPU is absent or ambiguous"
        )
    gpu = selected[0]
    if (
        gpu["uuid"] != protocol["selected_gpu"]["uuid"]
        or gpu["name"] != protocol["selected_gpu"]["name"]
    ):
        raise ResourceSmokePreflightError(
            "selected E6 GPU identity changed"
        )
    processes = [
        row
        for row in _compute_processes()
        if row["gpu_uuid"] == gpu["uuid"]
    ]
    resource_gate_now = (
        gpu["memory_used_mib"]
        < protocol["gates"][
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
        ]
        and len(processes)
        == protocol["gates"][
            "selected_gpu_external_compute_process_count"
        ]
    )
    output_absent = not OUTPUT_ROOT.exists()
    return {
        "schema": "proofalign.semantic-resource-smoke-e6-preflight.v1",
        "protocol_path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
        "protocol_sha256": file_sha256(PROTOCOL_PATH),
        "checkpoint_present": CHECKPOINT.is_dir(),
        "fresh_output_root_absent": output_absent,
        "selected_gpu_snapshot": gpu,
        "selected_gpu_compute_processes": processes,
        "resource_gate_passes_at_query_time": resource_gate_now,
        "source_and_input_bindings_current": True,
        "model_loaded": False,
        "gpu_kernel_launched": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "outcomes_read": False,
        "execution_authorized": False,
        "may_execute": False,
        "ready_for_authorization_request": (
            output_absent
            and resource_gate_now
            and CHECKPOINT.is_dir()
        ),
        "blocking_reasons": (
            "explicit model-load/GPU authorization is absent",
            "this frozen preregistration requires an authorized successor",
        ),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-protocol", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_protocol:
            if PROTOCOL_PATH.exists():
                raise ResourceSmokePreflightError(
                    f"refusing to replace frozen protocol: {PROTOCOL_PATH}"
                )
            PROTOCOL_PATH.parent.mkdir(parents=True, exist_ok=True)
            PROTOCOL_PATH.write_text(
                canonical_text(build_protocol()),
                encoding="utf-8",
            )
            print(PROTOCOL_PATH)
            return 0
        protocol = json.loads(
            PROTOCOL_PATH.read_text(encoding="utf-8")
        )
        validate_protocol(protocol)
        if args.check:
            expected = canonical_text(build_protocol())
            if PROTOCOL_PATH.read_text(encoding="utf-8") != expected:
                raise ResourceSmokePreflightError(
                    "E6 protocol is not canonical or current"
                )
            print(f"E6 protocol is current: {PROTOCOL_PATH}")
            return 0
        print(
            json.dumps(
                build_preflight(protocol),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except (
        FileNotFoundError,
        KeyError,
        OSError,
        ResourceSmokePreflightError,
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
