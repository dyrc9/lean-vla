#!/usr/bin/env python3
"""Run or validate the frozen v14 trigger-rich stress development matrix."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any, Mapping

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
from scripts import run_liberosafety_pi05_openpi_eval as base  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint as full  # noqa: E402
from scripts import run_l2_predictive_virtual_brake_v14_multijoint_shadow_only as shadow  # noqa: E402
from scripts import run_v14_multijoint_stress_design_pilot as pilot  # noqa: E402
from scripts.run_escape_recovery_v12_simulator_preflight import (  # noqa: E402
    _configure_environment,
    _robot_arrays,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-development-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v14_multijoint_stress_development"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_development_protocol.json"
)


class V14StressDevelopmentError(RuntimeError):
    """Raised when stress development differs from its frozen protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V14StressDevelopmentError(
            "stress output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V14StressDevelopmentError(
            "stress output root resolves to repository"
        )
    return root


def _verify_protocol(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> None:
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != {
            "simulator_action_dispatch": True,
            "policy_load": False,
            "task_outcome_read": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        }
        or len(protocol.get("environments", ())) != 12
        or protocol["design"]["doses"]
        != [dict(row) for row in pilot.DOSES]
        or protocol["design"]["baselines"]
        != list(pilot.BASELINES)
        or protocol["design"]["horizon_steps"]
        != pilot.HORIZON_STEPS
    ):
        raise V14StressDevelopmentError(
            "unsupported or unauthorized stress protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V14StressDevelopmentError(
                f"stress source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V14StressDevelopmentError(
                f"stress predecessor binding differs: {binding['path']}"
            )


def preflight(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol, protocol_path=protocol_path)
    except V14StressDevelopmentError as exc:
        blockers.append(str(exc))
    if (
        subprocess_status()
    ):
        blockers.append("tracked worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh stress output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "stress-development-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "expected_stress_lane_count": protocol["gates"][
            "expected_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_baseline_lane_count"
        ],
        "output_root_absent": not output_root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
    }


def subprocess_status() -> str:
    import subprocess

    completed = subprocess.run(
        (
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=normal",
        ),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V14StressDevelopmentError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _run_screened(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    *,
    baseline: str,
) -> dict[str, Any]:
    """Run a screened lane while retaining system-overhead observations."""

    wrapper_class = (
        shadow.MultiJointPredictiveVirtualBrakeShadowOnlyEnvironment
        if baseline == "shadow_only"
        else full.MultiJointPredictiveVirtualBrakeEnvironment
    )
    wrapper = wrapper_class(
        env,
        wait_steps=0,
        enabled=True,
        config=None,
    )
    matrices = []
    latencies = []
    maximum_constraint_force = 0.0
    for _ in range(pilot.HORIZON_STEPS):
        # Deliberately discard reward, done, and info returned by the wrapper.
        wrapper.step(pilot.HOLD_ACTION)
        audit = wrapper.observations[-1]
        latencies.append(float(audit["screen_latency_seconds"]))
        maximum_constraint_force = max(
            maximum_constraint_force,
            float(
                audit["maximum_abs_guarded_constraint_force"]
            ),
        )
        if audit["deadlock"] is not True:
            matrices.append(
                pilot.full_clean_margin_matrix(
                    audit["actual_joint_side_margins"]
                )
            )
        if audit["deadlock"] is True:
            break
    audits = wrapper.observations
    return {
        "executed_step_count": sum(
            audit["deadlock"] is not True for audit in audits
        ),
        "policy_decision_count": len(audits),
        "trigger_count": sum(
            audit["triggered"] is True for audit in audits
        ),
        "intervention_count": sum(
            audit["intervened"] is True for audit in audits
        ),
        "deadlock_count": sum(
            audit["deadlock"] is True for audit in audits
        ),
        "reactive_stop_count": 0,
        "stop_reason": (
            str(audits[-1]["deadlock_reason"])
            if audits and audits[-1]["deadlock"]
            else None
        ),
        "shadow_env_step_count": sum(
            int(audit["shadow_env_step_count"])
            for audit in audits
        ),
        "restore_failure_count": sum(
            audit["shadow_restore_identity"] is not True
            for audit in audits
        ),
        "exact_action_mismatch_count": sum(
            audit["deadlock"] is not True
            and audit["exact_action_identity"] is not True
            for audit in audits
        ),
        "screen_latency_seconds_values": latencies,
        "screen_latency_seconds_sum": float(sum(latencies)),
        "screen_latency_seconds_max": (
            max(latencies) if latencies else 0.0
        ),
        "maximum_abs_constraint_force": maximum_constraint_force,
        "actual_joint_side_margins": [
            pilot._margin_rows(matrix) for matrix in matrices
        ],
        **pilot._exposure(matrices),
    }


def _direct_result(
    env: Any,
    qidx: np.ndarray,
    limits: np.ndarray,
    *,
    reactive: bool,
) -> dict[str, Any]:
    result = dict(
        pilot._run_direct(
            env,
            qidx,
            limits,
            reactive=reactive,
        )
    )
    result.update(
        {
            "screen_latency_seconds_values": [],
            "screen_latency_seconds_sum": 0.0,
            "screen_latency_seconds_max": 0.0,
        }
    )
    return result


def _run_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
) -> tuple[list[dict[str, Any]], int, float]:
    runtime = base.load_libero_task_runtime(
        benchmark_name=str(spec["suite"]),
        task_id=int(spec["task_id"]),
        init_state_id=int(spec["init_state_id"]),
        bddl_file=str(REPO_ROOT / spec["bddl_path"]),
    )
    args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=gpu,
        control_freq=20,
        horizon=1000,
        seed=int(spec["environment_seed"]),
    )
    env = base.create_env(runtime, args)
    rows = []
    restore_failures = 0
    maximum_no_guard_shadow_error = 0.0
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = _robot_arrays(env)
        canonical = (
            full.core.capture_warmstart_policy_shadow_snapshot(
                env,
                robot,
                source_id=(
                    "v14-stress-development:"
                    f"{spec['environment_id']}:canonical"
                ),
            )
        )
        for joint_index in range(full.JOINT_COUNT):
            for side in full.JOINT_SIDES:
                for dose in pilot.DOSES:
                    canonical_restore = (
                        full.core.restore_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            canonical,
                        )
                    )
                    canonical_identity = full.core._restore_identity(
                        canonical_restore
                    )
                    restore_failures += int(not canonical_identity)
                    if not canonical_identity:
                        raise V14StressDevelopmentError(
                            "canonical environment restore lost identity"
                        )
                    pilot._inject(
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=joint_index,
                        side=side,
                        dose=dose,
                    )
                    injected = (
                        full.core.capture_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            source_id=(
                                "v14-stress-development:"
                                f"{spec['environment_id']}:"
                                f"joint{joint_index}:{side}:"
                                f"{dose['dose']}"
                            ),
                        )
                    )
                    initial = pilot._margin_matrix(
                        env, qidx, limits
                    )
                    baselines = {}
                    for baseline in pilot.BASELINES:
                        restored = (
                            full.core.restore_warmstart_policy_shadow_snapshot(
                                env,
                                robot,
                                injected,
                            )
                        )
                        identity = full.core._restore_identity(restored)
                        restore_failures += int(not identity)
                        if not identity:
                            raise V14StressDevelopmentError(
                                "baseline environment restore lost identity"
                            )
                        if baseline == "no_guard":
                            result = _direct_result(
                                env,
                                qidx,
                                limits,
                                reactive=False,
                            )
                        elif baseline == "reactive_stop":
                            result = _direct_result(
                                env,
                                qidx,
                                limits,
                                reactive=True,
                            )
                        else:
                            result = _run_screened(
                                env,
                                qidx,
                                limits,
                                baseline=baseline,
                            )
                        baselines[baseline] = result
                    no_guard = baselines["no_guard"][
                        "actual_joint_side_margins"
                    ]
                    shadow_only = baselines["shadow_only"][
                        "actual_joint_side_margins"
                    ]
                    if len(no_guard) != len(shadow_only):
                        raise V14StressDevelopmentError(
                            "no-guard/shadow trace lengths differ"
                        )
                    for no_guard_rows, shadow_rows in zip(
                        no_guard,
                        shadow_only,
                        strict=True,
                    ):
                        maximum_no_guard_shadow_error = max(
                            maximum_no_guard_shadow_error,
                            float(
                                np.max(
                                    np.abs(
                                        pilot.full_clean_margin_matrix(
                                            no_guard_rows
                                        )
                                        - pilot.full_clean_margin_matrix(
                                            shadow_rows
                                        )
                                    )
                                )
                            ),
                        )
                    rows.append(
                        {
                            "environment_id": str(
                                spec["environment_id"]
                            ),
                            "suite": str(spec["suite"]),
                            "task_id": int(spec["task_id"]),
                            "init_state_id": int(
                                spec["init_state_id"]
                            ),
                            "lane_id": (
                                f"{spec['environment_id']}:"
                                f"joint{joint_index}:{side}:"
                                f"{dose['dose']}"
                            ),
                            "joint_index": joint_index,
                            "side": side,
                            "dose": dict(dose),
                            "initial_joint_side_margins": (
                                pilot._margin_rows(initial)
                            ),
                            "baselines": baselines,
                        }
                    )
    finally:
        if hasattr(env, "close"):
            env.close()
    return rows, restore_failures, maximum_no_guard_shadow_error


_INTEGER_REPORT_FIELDS = (
    "trigger_count",
    "intervention_count",
    "deadlock_count",
    "reactive_stop_count",
    "below_floor_count",
    "crossing_count",
    "executed_step_count",
    "policy_decision_count",
    "shadow_env_step_count",
    "observed_state_count",
    "observed_side_value_count",
    "restore_failure_count",
    "exact_action_mismatch_count",
)


def _accumulate_report(
    values: dict[str, float],
    latency_values: dict[str, list[float]],
    *,
    baseline: str,
    report: Mapping[str, Any],
) -> None:
    values[f"{baseline}_lane_count"] += 1
    for field in _INTEGER_REPORT_FIELDS:
        values[f"{baseline}_{field}"] += int(report[field])
    for event in (
        "trigger",
        "intervention",
        "deadlock",
        "reactive_stop",
    ):
        values[f"{baseline}_{event}_lane_count"] += int(
            int(report[f"{event}_count"]) > 0
        )
    minimum = report["minimum_margin_rad"]
    minimum_key = f"{baseline}_minimum_margin_rad"
    if minimum is not None:
        values[minimum_key] = min(
            values.get(minimum_key, float("inf")),
            float(minimum),
        )
    force_key = f"{baseline}_maximum_abs_constraint_force"
    values[force_key] = max(
        values.get(force_key, 0.0),
        float(report["maximum_abs_constraint_force"]),
    )
    latency_values[baseline].extend(
        float(value)
        for value in report["screen_latency_seconds_values"]
    )


def _finalize_metrics(
    values: Mapping[str, float],
    latency_values: Mapping[str, list[float]],
) -> dict[str, Any]:
    result: dict[str, Any] = dict(values)
    for baseline in pilot.BASELINES:
        lane_count = int(result[f"{baseline}_lane_count"])
        side_count = int(
            result[f"{baseline}_observed_side_value_count"]
        )
        decision_count = int(
            result[f"{baseline}_policy_decision_count"]
        )
        expected_steps = lane_count * pilot.HORIZON_STEPS
        result[f"{baseline}_below_floor_side_rate"] = (
            result[f"{baseline}_below_floor_count"] / side_count
            if side_count
            else None
        )
        result[f"{baseline}_crossing_side_rate"] = (
            result[f"{baseline}_crossing_count"] / side_count
            if side_count
            else None
        )
        result[f"{baseline}_executed_step_availability"] = (
            result[f"{baseline}_executed_step_count"]
            / expected_steps
            if expected_steps
            else None
        )
        for event in (
            "trigger",
            "intervention",
            "deadlock",
            "reactive_stop",
        ):
            result[f"{baseline}_{event}_lane_rate"] = (
                result[f"{baseline}_{event}_lane_count"]
                / lane_count
                if lane_count
                else None
            )
        result[f"{baseline}_intervention_decision_rate"] = (
            result[f"{baseline}_intervention_count"]
            / decision_count
            if decision_count
            else None
        )
        samples = np.asarray(
            latency_values.get(baseline, ()),
            dtype=np.float64,
        )
        result[f"{baseline}_screen_latency_sample_count"] = int(
            samples.size
        )
        result[f"{baseline}_screen_latency_seconds_sum"] = float(
            np.sum(samples)
        )
        result[f"{baseline}_screen_latency_seconds_mean"] = (
            float(np.mean(samples)) if samples.size else None
        )
        for label, quantile in (
            ("p50", 0.50),
            ("p95", 0.95),
            ("p99", 0.99),
            ("max", 1.00),
        ):
            result[
                f"{baseline}_screen_latency_seconds_{label}"
            ] = (
                float(np.quantile(samples, quantile))
                if samples.size
                else None
            )
    return dict(sorted(result.items()))


def _contains_forbidden_outcome_field(value: Any) -> bool:
    forbidden = {
        "reward",
        "done",
        "task_success",
        "cost",
        "collision",
        "unsafe",
        "environment_done",
    }
    if isinstance(value, Mapping):
        return any(
            str(key) in forbidden
            or _contains_forbidden_outcome_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_outcome_field(item) for item in value)
    return False


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    maximum_no_guard_shadow_error: float,
) -> tuple[dict[str, Any], dict[str, bool]]:
    counters: dict[str, float] = defaultdict(float)
    latencies: dict[str, list[float]] = defaultdict(list)
    by_dose: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    by_dose_latencies: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    by_joint_side: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    by_joint_side_latencies: dict[
        str, dict[str, list[float]]
    ] = defaultdict(lambda: defaultdict(list))
    environment_lanes: Counter[str] = Counter()
    for row in rows:
        environment_id = str(row["environment_id"])
        environment_lanes[environment_id] += 1
        dose = str(row["dose"]["dose"])
        side_id = f"joint{row['joint_index']}_{row['side']}"
        for baseline in pilot.BASELINES:
            report = row["baselines"][baseline]
            _accumulate_report(
                counters,
                latencies,
                baseline=baseline,
                report=report,
            )
            _accumulate_report(
                by_dose[dose],
                by_dose_latencies[dose],
                baseline=baseline,
                report=report,
            )
            _accumulate_report(
                by_joint_side[side_id],
                by_joint_side_latencies[side_id],
                baseline=baseline,
                report=report,
            )
    gates = protocol["gates"]
    gate_results = {
        "environment_count": (
            len(environment_lanes)
            == gates["expected_environment_count"]
        ),
        "environment_lane_coverage": all(
            count == gates["expected_stress_lanes_per_environment"]
            for count in environment_lanes.values()
        ),
        "stress_lane_count": (
            len(rows) == gates["expected_stress_lane_count"]
        ),
        "baseline_lane_count": all(
            counters[f"{baseline}_lane_count"]
            == gates["expected_stress_lane_count"]
            for baseline in pilot.BASELINES
        ),
        "restore_identity": restore_failure_count == 0,
        "no_guard_shadow_trace_identity": (
            maximum_no_guard_shadow_error
            <= gates[
                "no_guard_shadow_maximum_side_error_rad"
            ]
        ),
        "zero_policy_or_outcome_fields": (
            not _contains_forbidden_outcome_field(rows)
        ),
    }
    aggregate = _finalize_metrics(counters, latencies)
    metrics = {
        **aggregate,
        "environment_count": len(environment_lanes),
        "stress_lane_count": len(rows),
        "restore_failure_count": restore_failure_count,
        "no_guard_shadow_maximum_side_error_rad": (
            maximum_no_guard_shadow_error
        ),
        "by_dose": {
            dose: _finalize_metrics(
                values,
                by_dose_latencies[dose],
            )
            for dose, values in sorted(by_dose.items())
        },
        "by_joint_side": {
            side: _finalize_metrics(
                values,
                by_joint_side_latencies[side],
            )
            for side, values in sorted(by_joint_side.items())
        },
    }
    return metrics, gate_results


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(
        protocol,
        protocol_path=protocol_path,
        gpu=gpu,
    )
    if report["ready"] is not True:
        raise V14StressDevelopmentError(
            "stress preflight failed: "
            + "; ".join(report["blockers"])
        )
    _configure_environment(gpu)
    rows = []
    restore_failures = 0
    maximum_error = 0.0
    for spec in protocol["environments"]:
        environment_rows, failures, observed_error = (
            _run_environment(spec, gpu=gpu)
        )
        rows.extend(environment_rows)
        restore_failures += failures
        maximum_error = max(maximum_error, observed_error)
    metrics, gate_results = _analyze(
        protocol,
        rows,
        restore_failure_count=restore_failures,
        maximum_no_guard_shadow_error=maximum_error,
    )
    data_complete = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["complete_classification"]
            if data_complete
            else protocol["incomplete_classification"]
        ),
        "development_data_complete": data_complete,
        "confirmatory_claim_authorized": False,
        "attacked_stage_authorized": False,
        "protocol": {
            "path": protocol_path.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(protocol_path),
        },
        "protocol_id": protocol["protocol_id"],
        "integrity": {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        },
        "gate_results": gate_results,
        "aggregate": metrics,
        "lanes": rows,
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "pilot_evidence.json"
    evidence_path.write_text(
        canonical_text(evidence),
        encoding="utf-8",
    )
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return {
        "classification": evidence["classification"],
        "development_data_complete": data_complete,
        "stress_lane_count": metrics["stress_lane_count"],
        "baseline_lane_count": sum(
            metrics[f"{baseline}_lane_count"]
            for baseline in pilot.BASELINES
        ),
        "evidence_path": evidence_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "checksums_path": checksums_path.relative_to(
            REPO_ROOT
        ).as_posix(),
    }


def validate_results(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    _verify_protocol(protocol, protocol_path=protocol_path)
    root = _output_root(protocol)
    evidence_path = root / "pilot_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V14StressDevelopmentError(
            "stress evidence or checksum manifest is absent"
        )
    expected_checksums = (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    )
    if checksums_path.read_text(
        encoding="utf-8"
    ) != expected_checksums:
        raise V14StressDevelopmentError(
            "stress checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"]
        != file_sha256(protocol_path)
        or evidence["integrity"]
        != {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        }
    ):
        raise V14StressDevelopmentError(
            "stress evidence identity differs"
        )
    metrics, gate_results = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(
            evidence["aggregate"]["restore_failure_count"]
        ),
        maximum_no_guard_shadow_error=float(
            evidence["aggregate"][
                "no_guard_shadow_maximum_side_error_rad"
            ]
        ),
    )
    if (
        metrics != evidence["aggregate"]
        or gate_results != evidence["gate_results"]
        or evidence["development_data_complete"]
        is not all(gate_results.values())
    ):
        raise V14StressDevelopmentError(
            "stress evidence analysis is stale"
        )
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=2)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    elif args.execute:
        payload = execute(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
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
