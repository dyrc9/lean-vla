#!/usr/bin/env python3
"""Execute an explicitly authorized E6 offline resource smoke.

The default authorized successor protocol does not exist.  Creating it
requires an explicit user authorization note.  The runner never imports JAX
or loads the checkpoint before that protocol passes all bindings and the
prelaunch GPU gate.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
from threading import Event, Thread
from time import monotonic, perf_counter
from typing import Any, Callable

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from prepare_semantic_resource_smoke_e6 import (  # noqa: E402
    CHECKPOINT,
    PROTOCOL_PATH as PREREGISTRATION_PATH,
    SELECTED_GPU,
    build_protocol as build_preregistration,
    canonical_text,
    file_sha256,
    validate_protocol as validate_preregistration,
)


AUTHORIZED_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_resource_smoke_e6_authorized_protocol.json"
)
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_semantic_resource_smoke_e6_20260725_fresh2"
)
RESULT_PATH = OUTPUT_ROOT / "measurement.json"
CHECKSUMS_PATH = OUTPUT_ROOT / "SHA256SUMS"
RUNNER_PATH = (
    REPO_ROOT / "scripts" / "run_semantic_resource_smoke_e6.py"
)


class ResourceSmokeError(RuntimeError):
    """Raised when E6 authorization, resources, or evidence are invalid."""


def build_authorized_protocol(
    *,
    authorization_note: str,
    authorization_received_at: str,
) -> dict[str, Any]:
    if not authorization_note.strip():
        raise ResourceSmokeError(
            "explicit user authorization note is required"
        )
    if not authorization_received_at.strip():
        raise ResourceSmokeError(
            "authorization receipt time is required"
        )
    preregistration = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    validate_preregistration(preregistration)
    return {
        "schema": (
            "proofalign.semantic-resource-smoke-e6-authorized.v1"
        ),
        "protocol_id": (
            "proofalign-semantic-resource-smoke-e6-authorized-20260725"
        ),
        "status": "authorized_offline_model_resource_measurement",
        "created_at": authorization_received_at,
        "predecessor": {
            "path": str(
                PREREGISTRATION_PATH.relative_to(REPO_ROOT)
            ),
            "sha256": file_sha256(PREREGISTRATION_PATH),
            "protocol_id": preregistration["protocol_id"],
        },
        "checkpoint": preregistration["checkpoint"],
        "selected_gpu": preregistration["selected_gpu"],
        "workload": preregistration["workload"],
        "gates": preregistration["gates"],
        "measurement_requirements": preregistration[
            "measurement_requirements"
        ],
        "source_sha256": {
            **preregistration["source_sha256"],
            str(RUNNER_PATH.relative_to(REPO_ROOT)): file_sha256(
                RUNNER_PATH
            ),
        },
        "input_artifact_sha256": preregistration[
            "input_artifact_sha256"
        ],
        "fresh_output_root": str(OUTPUT_ROOT.relative_to(REPO_ROOT)),
        "execution_authorization": {
            "explicit_user_authorization_received": True,
            "authorization_note": authorization_note,
            "authorization_received_at": authorization_received_at,
            "model_load_authorized": True,
            "gpu_execution_authorized": True,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
        },
        "claim_boundary": preregistration["claim_boundary"],
    }


def validate_authorized_protocol(protocol: dict[str, Any]) -> None:
    if (
        protocol.get("schema")
        != "proofalign.semantic-resource-smoke-e6-authorized.v1"
    ):
        raise ResourceSmokeError(
            "unsupported authorized E6 protocol schema"
        )
    preregistration = json.loads(
        PREREGISTRATION_PATH.read_text(encoding="utf-8")
    )
    validate_preregistration(preregistration)
    if protocol["predecessor"] != {
        "path": str(PREREGISTRATION_PATH.relative_to(REPO_ROOT)),
        "sha256": file_sha256(PREREGISTRATION_PATH),
        "protocol_id": preregistration["protocol_id"],
    }:
        raise ResourceSmokeError(
            "authorized E6 predecessor binding changed"
        )
    for name in (
        "checkpoint",
        "selected_gpu",
        "workload",
        "gates",
        "measurement_requirements",
        "input_artifact_sha256",
    ):
        if protocol[name] != preregistration[name]:
            raise ResourceSmokeError(
                f"authorized E6 changed preregistered {name}"
            )
    expected_sources = {
        **preregistration["source_sha256"],
        str(RUNNER_PATH.relative_to(REPO_ROOT)): file_sha256(
            RUNNER_PATH
        ),
    }
    if protocol["source_sha256"] != expected_sources:
        raise ResourceSmokeError(
            "authorized E6 source inventory changed"
        )
    for relative, expected in expected_sources.items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ResourceSmokeError(
                f"authorized E6 source binding is stale: {relative}"
            )
    for relative, expected in protocol[
        "input_artifact_sha256"
    ].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ResourceSmokeError(
                f"authorized E6 input binding is stale: {relative}"
            )
    if protocol["fresh_output_root"] != str(
        OUTPUT_ROOT.relative_to(REPO_ROOT)
    ):
        raise ResourceSmokeError(
            "authorized E6 output root changed"
        )
    authorization = protocol["execution_authorization"]
    if (
        authorization[
            "explicit_user_authorization_received"
        ]
        is not True
        or authorization["model_load_authorized"] is not True
        or authorization["gpu_execution_authorized"] is not True
        or not str(authorization["authorization_note"]).strip()
        or not str(
            authorization["authorization_received_at"]
        ).strip()
    ):
        raise ResourceSmokeError(
            "authorized E6 lacks explicit model/GPU authorization"
        )
    if any(
        authorization[name]
        for name in (
            "simulator_creation_authorized",
            "action_dispatch_authorized",
            "outcome_read_authorized",
        )
    ):
        raise ResourceSmokeError(
            "authorized E6 crosses the offline measurement boundary"
        )


def _gpu_rows() -> list[dict[str, Any]]:
    completed = subprocess.run(
        (
            "nvidia-smi",
            "--query-gpu=index,uuid,name,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    rows = []
    for line in completed.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 5:
            raise ResourceSmokeError(
                f"unexpected nvidia-smi GPU row: {line}"
            )
        rows.append(
            {
                "physical_index": int(parts[0]),
                "uuid": parts[1],
                "name": parts[2],
                "memory_used_mib": int(parts[3]),
                "memory_total_mib": int(parts[4]),
            }
        )
    return rows


def _compute_rows() -> list[dict[str, Any]]:
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
            raise ResourceSmokeError(
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


def prelaunch_report(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_authorized_protocol(protocol)
    selected = [
        row
        for row in _gpu_rows()
        if row["physical_index"]
        == protocol["selected_gpu"]["physical_index"]
    ]
    if len(selected) != 1:
        raise ResourceSmokeError(
            "authorized E6 selected GPU is absent or ambiguous"
        )
    gpu = selected[0]
    if (
        gpu["uuid"] != protocol["selected_gpu"]["uuid"]
        or gpu["name"] != protocol["selected_gpu"]["name"]
    ):
        raise ResourceSmokeError(
            "authorized E6 GPU identity changed"
        )
    processes = [
        row
        for row in _compute_rows()
        if row["gpu_uuid"] == gpu["uuid"]
    ]
    gate_results = {
        "prelaunch_memory": (
            gpu["memory_used_mib"]
            < protocol["gates"][
                "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
            ]
        ),
        "external_compute_processes": (
            len(processes)
            == protocol["gates"][
                "selected_gpu_external_compute_process_count"
            ]
        ),
        "fresh_output_root": not OUTPUT_ROOT.exists(),
    }
    return {
        "selected_gpu": gpu,
        "compute_processes": processes,
        "gate_results": gate_results,
        "ready": all(gate_results.values()),
        "model_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "outcomes_read": False,
    }


def _rss_mib() -> float:
    # Linux ru_maxrss is KiB.
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


@dataclass
class ProcessResourceMonitor:
    gpu_uuid: str
    interval_seconds: float
    pid: int = field(default_factory=os.getpid)
    gpu_memory_samples_mib: list[int] = field(default_factory=list)
    rss_samples_mib: list[float] = field(default_factory=list)
    query_errors: list[str] = field(default_factory=list)
    _stop: Event = field(default_factory=Event, repr=False)
    _thread: Thread | None = field(default=None, repr=False)

    def start(self) -> None:
        if self._thread is not None:
            raise ResourceSmokeError(
                "resource monitor is already running"
            )
        self._thread = Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._sample()
        return {
            "sample_count": len(self.rss_samples_mib),
            "peak_process_gpu_memory_mib": max(
                self.gpu_memory_samples_mib,
                default=0,
            ),
            "peak_process_rss_mib": max(
                self.rss_samples_mib,
                default=_rss_mib(),
            ),
            "query_errors": self.query_errors,
        }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def _sample(self) -> None:
        self.rss_samples_mib.append(_rss_mib())
        try:
            own = [
                row
                for row in _compute_rows()
                if row["gpu_uuid"] == self.gpu_uuid
                and row["pid"] == self.pid
            ]
            self.gpu_memory_samples_mib.append(
                sum(row["used_memory_mib"] for row in own)
            )
        except (OSError, ResourceSmokeError, subprocess.CalledProcessError) as exc:
            self.query_errors.append(
                f"{type(exc).__name__}:{exc}"
            )


def _array_digest(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    hasher = sha256()
    hasher.update(str(array.dtype).encode())
    hasher.update(json.dumps(list(array.shape)).encode())
    hasher.update(array.tobytes())
    return hasher.hexdigest()


def _latency(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": len(values),
        "p50": float(np.quantile(array, 0.50)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
        "maximum": float(np.max(array)),
    }


def _component_latency_probe() -> dict[str, Any]:
    from validate_deterministic_selector_e1f import (
        build_report as e1f_report,
    )
    from validate_local_checker_qualification_e3 import (
        build_report as e3_report,
    )
    from run_semantic_effect_observer_qualification_e5 import (
        RESULT_PATH as E5_RESULT_PATH,
    )

    e1f = e1f_report()
    e3 = e3_report()
    e5 = json.loads(E5_RESULT_PATH.read_text(encoding="utf-8"))
    return {
        "measurement_kind": (
            "bound_frozen_qualification_latency"
        ),
        "selector_p99_ns": e1f["latency_ns"]["p99"],
        "local_checker_p99_ns": e3["summary"]["latency_ns"][
            "p99"
        ],
        "effect_observer_p99_ns": e5["summary"]["latency_ns"][
            "p99"
        ],
        "maximum_component_p99_ns": max(
            e1f["latency_ns"]["p99"],
            e3["summary"]["latency_ns"]["p99"],
            e5["summary"]["latency_ns"]["p99"],
        ),
    }


def measure_policy_workload(
    *,
    protocol: dict[str, Any],
    e2_protocol: dict[str, Any],
    snapshots: list[dict[str, Any]],
    scorer_factory: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    from run_pi05_action_conditioning_e2 import compile_prompt

    scorer = scorer_factory(e2_protocol)
    if len(snapshots) != int(protocol["workload"]["snapshot_count"]):
        raise ResourceSmokeError(
            "authorized E6 snapshot count changed"
        )
    first = snapshots[0]
    first_prompt = compile_prompt(
        e2_protocol["prompt_template"],
        first["task"],
        e2_protocol["stage_subtasks"][first["stage"]]["expected"],
    )
    first_noise = np.random.default_rng(
        int(e2_protocol["base_noise_seed"])
    ).standard_normal(scorer.noise_shape, dtype=np.float32)
    warmup_latencies = []
    for _ in range(
        int(protocol["workload"]["warmup_policy_calls"])
    ):
        _, elapsed = scorer.infer(
            first["inputs"],
            prompt=first_prompt,
            noise=first_noise,
        )
        warmup_latencies.append(elapsed)

    policy_latencies = []
    pipeline_latencies = []
    rows = []
    first_pass_digests: dict[str, str] = {}
    exact_repeats = 0
    repeat_total = 0
    passes = int(protocol["workload"]["measured_policy_passes"])
    for pass_index in range(passes):
        for case_index, snapshot in enumerate(snapshots):
            started = perf_counter()
            prompt = compile_prompt(
                e2_protocol["prompt_template"],
                snapshot["task"],
                e2_protocol["stage_subtasks"][snapshot["stage"]][
                    "expected"
                ],
            )
            noise = np.random.default_rng(
                int(e2_protocol["base_noise_seed"]) + case_index
            ).standard_normal(
                scorer.noise_shape,
                dtype=np.float32,
            )
            actions, policy_elapsed = scorer.infer(
                snapshot["inputs"],
                prompt=prompt,
                noise=noise,
            )
            digest = _array_digest(actions)
            pipeline_elapsed = perf_counter() - started
            policy_latencies.append(policy_elapsed)
            pipeline_latencies.append(pipeline_elapsed)
            if pass_index == 0:
                first_pass_digests[snapshot["case_id"]] = digest
            else:
                repeat_total += 1
                exact_repeats += int(
                    digest
                    == first_pass_digests[snapshot["case_id"]]
                )
            rows.append(
                {
                    "pass_index": pass_index,
                    "case_id": snapshot["case_id"],
                    "stage": snapshot["stage"],
                    "input_digest": snapshot["input_digest"],
                    "action_digest": digest,
                    "policy_seconds": policy_elapsed,
                    "pipeline_seconds": pipeline_elapsed,
                }
            )
    expected_calls = int(
        protocol["workload"]["expected_measured_policy_calls"]
    )
    if len(rows) != expected_calls:
        raise ResourceSmokeError(
            "authorized E6 measured call count changed"
        )
    return {
        "checkpoint_load_seconds": float(
            scorer.checkpoint_load_seconds
        ),
        "jax_devices": scorer.devices,
        "warmup_seconds": warmup_latencies,
        "policy_latency_seconds": _latency(policy_latencies),
        "semantic_pipeline_latency_seconds": _latency(
            pipeline_latencies
        ),
        "repeat_exact_count": exact_repeats,
        "repeat_comparison_count": repeat_total,
        "repeat_exact_rate": (
            exact_repeats / repeat_total if repeat_total else 0.0
        ),
        "rows": rows,
    }


def summarize_result(
    protocol: dict[str, Any],
    measurement: dict[str, Any],
    resources: dict[str, Any],
    component_latency: dict[str, Any],
) -> dict[str, Any]:
    gates = protocol["gates"]
    gate_results = {
        "checkpoint_load": (
            measurement["checkpoint_load_seconds"]
            <= gates["maximum_checkpoint_load_seconds"]
        ),
        "warm_policy_p99": (
            measurement["policy_latency_seconds"]["p99"]
            <= gates["maximum_warm_policy_p99_seconds"]
        ),
        "semantic_pipeline_p99": (
            measurement["semantic_pipeline_latency_seconds"]["p99"]
            <= gates["maximum_semantic_pipeline_p99_seconds"]
        ),
        "component_cpu_p99": (
            component_latency["maximum_component_p99_ns"]
            <= gates["maximum_component_cpu_p99_ns"]
        ),
        "process_gpu_memory": (
            resources["peak_process_gpu_memory_mib"]
            <= gates["maximum_peak_process_gpu_memory_mib"]
        ),
        "process_rss": (
            resources["peak_process_rss_mib"]
            <= gates["maximum_peak_process_rss_mib"]
        ),
        "output_bytes": (
            resources["output_bytes"]
            <= gates["maximum_output_bytes"]
        ),
        "repeat_exact": (
            measurement["repeat_exact_rate"]
            >= gates["minimum_repeat_exact_rate"]
        ),
        "selected_gpu_execution": (
            any(
                "cuda" in str(device).lower()
                for device in measurement["jax_devices"]
            )
            and resources["peak_process_gpu_memory_mib"] > 0
        ),
        "resource_monitor": not resources["query_errors"],
    }
    return {
        "gate_results": gate_results,
        "qualified": all(gate_results.values()),
        "failed_gates": [
            name
            for name, passed in gate_results.items()
            if not passed
        ],
    }


def _output_byte_count(result: dict[str, Any]) -> int:
    checksum_manifest = (
        f"{'0' * 64}  {RESULT_PATH.name}\n"
    ).encode("utf-8")
    return (
        len(canonical_text(result).encode("utf-8"))
        + len(checksum_manifest)
    )


def _finalize_result(
    protocol: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    result["resources"]["output_bytes"] = 0
    for _ in range(16):
        summary = summarize_result(
            protocol,
            result["measurement"],
            result["resources"],
            result["component_latency"],
        )
        result["summary"] = summary
        result["classification"] = (
            "semantic_resource_smoke_qualified"
            if summary["qualified"]
            else "semantic_resource_smoke_disqualified"
        )
        output_bytes = _output_byte_count(result)
        if output_bytes == result["resources"]["output_bytes"]:
            return result
        result["resources"]["output_bytes"] = output_bytes
    raise ResourceSmokeError(
        "E6 serialized output byte count did not stabilize"
    )


def execute(protocol: dict[str, Any]) -> dict[str, Any]:
    validate_authorized_protocol(protocol)
    preflight = prelaunch_report(protocol)
    if not preflight["ready"]:
        raise ResourceSmokeError(
            f"E6 prelaunch gate failed: {preflight['gate_results']}"
        )
    if OUTPUT_ROOT.exists():
        raise ResourceSmokeError(
            f"fresh E6 output root exists: {OUTPUT_ROOT}"
        )
    os.environ["CUDA_VISIBLE_DEVICES"] = str(
        protocol["selected_gpu"]["physical_index"]
    )
    os.environ.setdefault("XLA_PYTHON_CLIENT_PREALLOCATE", "false")

    from run_pi05_action_conditioning_e2 import (
        PROTOCOL_PATH as E2_PROTOCOL_PATH,
        FrozenActionScorer,
        select_snapshots,
        validate_protocol as validate_e2_protocol,
    )

    e2_protocol = json.loads(
        E2_PROTOCOL_PATH.read_text(encoding="utf-8")
    )
    e1_protocol = validate_e2_protocol(e2_protocol)
    snapshots, sampling_report = select_snapshots(e1_protocol)
    monitor = ProcessResourceMonitor(
        gpu_uuid=protocol["selected_gpu"]["uuid"],
        interval_seconds=(
            float(protocol["workload"]["gpu_monitor_interval_ms"])
            / 1000.0
        ),
    )
    monitor.start()
    try:
        measurement = measure_policy_workload(
            protocol=protocol,
            e2_protocol=e2_protocol,
            snapshots=snapshots,
            scorer_factory=FrozenActionScorer,
        )
        component_latency = _component_latency_probe()
    finally:
        resources = monitor.stop()
    result = {
        "schema": "proofalign.semantic-resource-smoke-e6-result.v1",
        "run_id": (
            "proofalign-semantic-resource-smoke-e6-20260725-fresh2"
        ),
        "classification": "",
        "training_performed": False,
        "simulator_created": False,
        "action_sink_created": False,
        "actions_dispatched": False,
        "outcomes_read": False,
        "checkpoint": protocol["checkpoint"],
        "selected_gpu": protocol["selected_gpu"],
        "prelaunch": preflight,
        "sampling_report": sampling_report,
        "measurement": measurement,
        "component_latency": component_latency,
        "resources": resources,
        "summary": {},
        "protocol_binding": {
            "path": str(
                AUTHORIZED_PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "sha256": file_sha256(AUTHORIZED_PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "claim_boundary": protocol["claim_boundary"],
    }
    return _finalize_result(protocol, result)


def validate_result(
    protocol: dict[str, Any],
    result: dict[str, Any],
) -> None:
    validate_authorized_protocol(protocol)
    if (
        result.get("schema")
        != "proofalign.semantic-resource-smoke-e6-result.v1"
    ):
        raise ResourceSmokeError(
            "unsupported E6 result schema"
        )
    if any(
        result.get(name) is not False
        for name in (
            "training_performed",
            "simulator_created",
            "action_sink_created",
            "actions_dispatched",
            "outcomes_read",
        )
    ):
        raise ResourceSmokeError(
            "E6 result crossed the offline measurement boundary"
        )
    if result["protocol_binding"]["sha256"] != file_sha256(
        AUTHORIZED_PROTOCOL_PATH
    ):
        raise ResourceSmokeError(
            "E6 result protocol binding is stale"
        )
    if result["protocol_binding"] != {
        "path": str(
            AUTHORIZED_PROTOCOL_PATH.relative_to(REPO_ROOT)
        ),
        "sha256": file_sha256(AUTHORIZED_PROTOCOL_PATH),
        "protocol_id": protocol["protocol_id"],
    }:
        raise ResourceSmokeError(
            "E6 result protocol identity is inconsistent"
        )
    if result["checkpoint"] != protocol["checkpoint"]:
        raise ResourceSmokeError(
            "E6 result checkpoint identity changed"
        )
    if result["selected_gpu"] != protocol["selected_gpu"]:
        raise ResourceSmokeError(
            "E6 result selected GPU identity changed"
        )
    if (
        result["prelaunch"]["ready"] is not True
        or result["prelaunch"]["selected_gpu"]["uuid"]
        != protocol["selected_gpu"]["uuid"]
        or any(
            result["prelaunch"].get(name) is not False
            for name in (
                "model_loaded",
                "simulator_created",
                "actions_dispatched",
                "outcomes_read",
            )
        )
    ):
        raise ResourceSmokeError(
            "E6 result prelaunch evidence is inconsistent"
        )
    measurement = result["measurement"]
    rows = measurement["rows"]
    if len(rows) != protocol["workload"][
        "expected_measured_policy_calls"
    ]:
        raise ResourceSmokeError(
            "E6 result measured call count changed"
        )
    warmup_seconds = measurement["warmup_seconds"]
    if len(warmup_seconds) != protocol["workload"][
        "warmup_policy_calls"
    ]:
        raise ResourceSmokeError(
            "E6 result warmup call count changed"
        )
    numeric_values = [
        measurement["checkpoint_load_seconds"],
        *warmup_seconds,
        *(
            row[name]
            for row in rows
            for name in ("policy_seconds", "pipeline_seconds")
        ),
    ]
    if any(
        not np.isfinite(value) or value < 0
        for value in numeric_values
    ):
        raise ResourceSmokeError(
            "E6 result contains invalid timing values"
        )
    expected_policy_latency = _latency(
        [row["policy_seconds"] for row in rows]
    )
    expected_pipeline_latency = _latency(
        [row["pipeline_seconds"] for row in rows]
    )
    if (
        canonical_text(expected_policy_latency)
        != canonical_text(
            measurement["policy_latency_seconds"]
        )
        or canonical_text(expected_pipeline_latency)
        != canonical_text(
            measurement["semantic_pipeline_latency_seconds"]
        )
    ):
        raise ResourceSmokeError(
            "E6 result latency summary is inconsistent"
        )
    passes = int(protocol["workload"]["measured_policy_passes"])
    snapshot_count = int(protocol["workload"]["snapshot_count"])
    expected_pairs = {
        (pass_index, case_index)
        for pass_index in range(passes)
        for case_index in range(snapshot_count)
    }
    case_ids = sorted({row["case_id"] for row in rows})
    if len(case_ids) != snapshot_count:
        raise ResourceSmokeError(
            "E6 result snapshot identity count changed"
        )
    case_indexes = {
        case_id: index
        for index, case_id in enumerate(case_ids)
    }
    actual_pairs = {
        (row["pass_index"], case_indexes[row["case_id"]])
        for row in rows
    }
    if actual_pairs != expected_pairs or len(actual_pairs) != len(rows):
        raise ResourceSmokeError(
            "E6 result pass/case coverage is inconsistent"
        )
    by_case: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(row["case_id"], []).append(row)
    for case_rows in by_case.values():
        case_rows.sort(key=lambda row: row["pass_index"])
        if (
            len({row["stage"] for row in case_rows}) != 1
            or len(
                {
                    row["input_digest"]
                    for row in case_rows
                }
            )
            != 1
        ):
            raise ResourceSmokeError(
                "E6 result repeated snapshot identity changed"
            )
    exact_count = sum(
        row["action_digest"]
        == case_rows[0]["action_digest"]
        for case_rows in by_case.values()
        for row in case_rows[1:]
    )
    comparison_count = sum(
        max(0, len(case_rows) - 1)
        for case_rows in by_case.values()
    )
    if (
        exact_count != measurement["repeat_exact_count"]
        or comparison_count
        != measurement["repeat_comparison_count"]
        or (
            exact_count / comparison_count
            if comparison_count
            else 0.0
        )
        != measurement["repeat_exact_rate"]
    ):
        raise ResourceSmokeError(
            "E6 result repeatability summary is inconsistent"
        )
    if result["resources"]["output_bytes"] != _output_byte_count(
        result
    ):
        raise ResourceSmokeError(
            "E6 result serialized output byte count is inconsistent"
        )
    expected_summary = summarize_result(
        protocol,
        measurement,
        result["resources"],
        result["component_latency"],
    )
    if canonical_text(expected_summary) != canonical_text(
        result["summary"]
    ):
        raise ResourceSmokeError(
            "E6 result gate summary is inconsistent"
        )
    expected_classification = (
        "semantic_resource_smoke_qualified"
        if expected_summary["qualified"]
        else "semantic_resource_smoke_disqualified"
    )
    if result["classification"] != expected_classification:
        raise ResourceSmokeError(
            "E6 result classification is inconsistent"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-authorized-protocol", action="store_true")
    mode.add_argument("--check-blocked", action="store_true")
    mode.add_argument("--check-state", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--authorization-note")
    parser.add_argument("--authorization-received-at")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_state:
            preregistration = json.loads(
                PREREGISTRATION_PATH.read_text(encoding="utf-8")
            )
            validate_preregistration(preregistration)
            if not AUTHORIZED_PROTOCOL_PATH.exists():
                if OUTPUT_ROOT.exists():
                    raise ResourceSmokeError(
                        "authorized E6 output root exists without a protocol"
                    )
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "authorization_state": "absent",
                            "measurement_state": "blocked",
                            "model_loaded": False,
                            "simulator_created": False,
                            "actions_dispatched": False,
                            "outcomes_read": False,
                        },
                        indent=2,
                    )
                )
                return 0
            protocol = json.loads(
                AUTHORIZED_PROTOCOL_PATH.read_text(encoding="utf-8")
            )
            validate_authorized_protocol(protocol)
            if not RESULT_PATH.exists():
                report = prelaunch_report(protocol)
                print(
                    json.dumps(
                        {
                            "ok": report["ready"],
                            "authorization_state": "authorized",
                            "measurement_state": "pending",
                            "prelaunch": report,
                        },
                        indent=2,
                    )
                )
                return 0 if report["ready"] else 2
            result = json.loads(
                RESULT_PATH.read_text(encoding="utf-8")
            )
            validate_result(protocol, result)
            expected_checksum = (
                f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
            )
            if (
                CHECKSUMS_PATH.read_text(encoding="utf-8")
                != expected_checksum
            ):
                raise ResourceSmokeError(
                    "E6 result checksum manifest is stale"
                )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "authorization_state": "authorized",
                        "measurement_state": "complete",
                        "classification": result["classification"],
                        "qualified": result["summary"]["qualified"],
                        "simulator_created": result["simulator_created"],
                        "actions_dispatched": result[
                            "actions_dispatched"
                        ],
                        "outcomes_read": result["outcomes_read"],
                    },
                    indent=2,
                )
            )
            return 0
        if args.check_blocked:
            preregistration = json.loads(
                PREREGISTRATION_PATH.read_text(encoding="utf-8")
            )
            validate_preregistration(preregistration)
            if AUTHORIZED_PROTOCOL_PATH.exists():
                raise ResourceSmokeError(
                    "authorized E6 protocol now exists; run its preflight"
                )
            if OUTPUT_ROOT.exists():
                raise ResourceSmokeError(
                    "authorized E6 output root exists without a protocol"
                )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "authorization_state": "absent",
                        "authorized_protocol_absent": True,
                        "fresh_output_root_absent": True,
                        "model_loaded": False,
                        "simulator_created": False,
                        "actions_dispatched": False,
                        "outcomes_read": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.write_authorized_protocol:
            if AUTHORIZED_PROTOCOL_PATH.exists():
                raise ResourceSmokeError(
                    "refusing to replace authorized E6 protocol"
                )
            protocol = build_authorized_protocol(
                authorization_note=args.authorization_note or "",
                authorization_received_at=(
                    args.authorization_received_at or ""
                ),
            )
            AUTHORIZED_PROTOCOL_PATH.write_text(
                canonical_text(protocol),
                encoding="utf-8",
            )
            print(AUTHORIZED_PROTOCOL_PATH)
            return 0
        if not AUTHORIZED_PROTOCOL_PATH.is_file():
            raise ResourceSmokeError(
                "authorized E6 successor protocol is absent"
            )
        protocol = json.loads(
            AUTHORIZED_PROTOCOL_PATH.read_text(encoding="utf-8")
        )
        validate_authorized_protocol(protocol)
        if args.preflight:
            print(
                json.dumps(
                    prelaunch_report(protocol),
                    indent=2,
                )
            )
            return 0
        if args.run:
            result = execute(protocol)
            validate_result(protocol, result)
            OUTPUT_ROOT.mkdir(parents=True)
            RESULT_PATH.write_text(
                canonical_text(result),
                encoding="utf-8",
            )
            CHECKSUMS_PATH.write_text(
                f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n",
                encoding="utf-8",
            )
            if (
                RESULT_PATH.stat().st_size
                + CHECKSUMS_PATH.stat().st_size
                != result["resources"]["output_bytes"]
            ):
                raise ResourceSmokeError(
                    "written E6 output byte count is inconsistent"
                )
            print(
                json.dumps(
                    {
                        "output": str(RESULT_PATH),
                        "classification": result["classification"],
                        "summary": result["summary"],
                    },
                    indent=2,
                )
            )
            return 0
        result = json.loads(
            RESULT_PATH.read_text(encoding="utf-8")
        )
        validate_result(protocol, result)
        expected_checksum = (
            f"{file_sha256(RESULT_PATH)}  {RESULT_PATH.name}\n"
        )
        if CHECKSUMS_PATH.read_text(
            encoding="utf-8"
        ) != expected_checksum:
            raise ResourceSmokeError(
                "E6 result checksum manifest is stale"
            )
        print(f"E6 result is current: {RESULT_PATH}")
        return 0
    except (
        KeyError,
        OSError,
        ResourceSmokeError,
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
