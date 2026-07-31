#!/usr/bin/env python3
"""Run the held-out, outcome-blind v14 stress qualification."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import subprocess
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
from scripts import run_v14_multijoint_stress_development as development  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "stress-qualification-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v14_multijoint_stress_qualification"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "stress_qualification_protocol.json"
)


class V14StressQualificationError(RuntimeError):
    """Raised when held-out qualification differs from its protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V14StressQualificationError(
            "qualification output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V14StressQualificationError(
            "qualification output root resolves to repository"
        )
    return root


def _git_status() -> str:
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
        raise V14StressQualificationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "held_out_mechanism_claim": True,
        "task_utility_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["doses"]
        != [dict(row) for row in development.pilot.DOSES]
        or protocol["design"]["baselines"]
        != list(development.pilot.BASELINES)
        or protocol["design"]["horizon_steps"]
        != development.pilot.HORIZON_STEPS
    ):
        raise V14StressQualificationError(
            "unsupported or unauthorized qualification protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V14StressQualificationError(
                f"qualification source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V14StressQualificationError(
                "qualification predecessor binding differs: "
                + str(binding["path"])
            )


def preflight(
    protocol: Mapping[str, Any],
    *,
    gpu: int,
) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V14StressQualificationError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh qualification output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v14-multijoint-"
            "stress-qualification-preflight.v1"
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


class _WarningAudit:
    def __init__(self) -> None:
        self.environment_id = "unbound"
        self.phase = "prebinding"
        self.records: list[dict[str, Any]] = []

    def __call__(self, warning: str | bytes) -> None:
        message = (
            warning.decode(errors="replace")
            if isinstance(warning, bytes)
            else str(warning)
        )
        lowered = message.lower()
        self.records.append(
            {
                "environment_id": self.environment_id,
                "phase": self.phase,
                "contact_capacity_warning": (
                    "too many contacts" in lowered
                    or "nconmax" in lowered
                ),
                "message": message,
            }
        )


class _ContactAudit:
    def __init__(self, environment_id: str) -> None:
        self.environment_id = environment_id
        self.observation_count: Counter[str] = Counter()
        self.saturation_count: Counter[str] = Counter()
        self.maximum_ncon: Counter[str] = Counter()
        self.minimum_nconmax: dict[str, int] = {}

    def observe(self, env: Any, *, phase: str) -> None:
        ncon = int(env.sim.data.ncon)
        nconmax = int(env.sim.model.nconmax)
        self.observation_count[phase] += 1
        self.maximum_ncon[phase] = max(
            self.maximum_ncon[phase], ncon
        )
        self.minimum_nconmax[phase] = min(
            self.minimum_nconmax.get(phase, nconmax), nconmax
        )
        self.saturation_count[phase] += int(ncon >= nconmax)

    def report(
        self,
        warnings: _WarningAudit,
    ) -> dict[str, Any]:
        records = [
            row
            for row in warnings.records
            if row["environment_id"] == self.environment_id
        ]
        phases = ("prebinding", "active")
        return {
            "environment_id": self.environment_id,
            "phases": {
                phase: {
                    "contact_observation_count": self.observation_count[
                        phase
                    ],
                    "contact_saturation_count": self.saturation_count[
                        phase
                    ],
                    "maximum_ncon": self.maximum_ncon[phase],
                    "minimum_nconmax": self.minimum_nconmax.get(phase),
                    "warning_count": sum(
                        row["phase"] == phase for row in records
                    ),
                    "contact_capacity_warning_count": sum(
                        row["phase"] == phase
                        and row["contact_capacity_warning"] is True
                        for row in records
                    ),
                }
                for phase in phases
            },
        }


class _AuditedEnvironment:
    def __init__(
        self,
        env: Any,
        *,
        contacts: _ContactAudit,
        warnings: _WarningAudit,
    ) -> None:
        self._audited_inner = env
        self._contacts = contacts
        self._warnings = warnings
        self._contacts.observe(env, phase="prebinding")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._audited_inner, name)

    def reset(self, *args: Any, **kwargs: Any) -> Any:
        self._warnings.phase = "prebinding"
        result = self._audited_inner.reset(*args, **kwargs)
        self._contacts.observe(
            self._audited_inner, phase="prebinding"
        )
        return result

    def set_init_state(self, *args: Any, **kwargs: Any) -> Any:
        self._warnings.phase = "prebinding"
        result = self._audited_inner.set_init_state(*args, **kwargs)
        self._contacts.observe(
            self._audited_inner, phase="prebinding"
        )
        self._warnings.phase = "active"
        return result

    def step(self, *args: Any, **kwargs: Any) -> Any:
        self._warnings.phase = "active"
        result = self._audited_inner.step(*args, **kwargs)
        self._contacts.observe(self._audited_inner, phase="active")
        return result

    def close(self) -> Any:
        return self._audited_inner.close()


def _run_audited_environment(
    spec: Mapping[str, Any],
    *,
    gpu: int,
    warnings: _WarningAudit,
) -> tuple[list[dict[str, Any]], int, float, dict[str, Any]]:
    environment_id = str(spec["environment_id"])
    warnings.environment_id = environment_id
    warnings.phase = "prebinding"
    contacts = _ContactAudit(environment_id)
    original_create = development.base.create_env

    def audited_create(runtime: Any, args: Any) -> _AuditedEnvironment:
        warnings.phase = "prebinding"
        env = original_create(runtime, args)
        return _AuditedEnvironment(
            env,
            contacts=contacts,
            warnings=warnings,
        )

    development.base.create_env = audited_create
    try:
        rows, failures, error = development._run_environment(
            spec,
            gpu=gpu,
        )
    finally:
        development.base.create_env = original_create
    return rows, failures, error, contacts.report(warnings)


def _threshold_identity(
    rows: list[Mapping[str, Any]],
    *,
    thresholds: list[float],
) -> dict[str, Any]:
    disagreements: Counter[str] = Counter()
    trace_length_mismatch_count = 0
    maximum_all_side_error = 0.0
    maximum_near_limit_error = 0.0
    near_limit_boundary = max(thresholds)
    compared_side_value_count = 0
    for row in rows:
        no_guard = row["baselines"]["no_guard"][
            "actual_joint_side_margins"
        ]
        shadow = row["baselines"]["shadow_only"][
            "actual_joint_side_margins"
        ]
        if len(no_guard) != len(shadow):
            trace_length_mismatch_count += 1
            continue
        for no_rows, shadow_rows in zip(
            no_guard, shadow, strict=True
        ):
            no_matrix = development.pilot.full_clean_margin_matrix(
                no_rows
            )
            shadow_matrix = development.pilot.full_clean_margin_matrix(
                shadow_rows
            )
            errors = np.abs(no_matrix - shadow_matrix)
            minima = np.minimum(no_matrix, shadow_matrix)
            compared_side_value_count += int(errors.size)
            maximum_all_side_error = max(
                maximum_all_side_error, float(np.max(errors))
            )
            near_errors = errors[minima < near_limit_boundary]
            if near_errors.size:
                maximum_near_limit_error = max(
                    maximum_near_limit_error,
                    float(np.max(near_errors)),
                )
            for threshold in thresholds:
                disagreements[str(threshold)] += int(
                    np.sum(
                        (no_matrix < threshold)
                        != (shadow_matrix < threshold)
                    )
                )
    return {
        "thresholds_rad": thresholds,
        "compared_side_value_count": compared_side_value_count,
        "trace_length_mismatch_count": trace_length_mismatch_count,
        "threshold_classification_disagreement_count": {
            str(value): disagreements[str(value)]
            for value in thresholds
        },
        "maximum_all_side_error_rad": maximum_all_side_error,
        "maximum_near_limit_error_rad": maximum_near_limit_error,
    }


def _contact_aggregate(
    reports: list[Mapping[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "environment_count": len(reports),
        "phases": {},
    }
    for phase in ("prebinding", "active"):
        rows = [report["phases"][phase] for report in reports]
        result["phases"][phase] = {
            "contact_observation_count": sum(
                int(row["contact_observation_count"]) for row in rows
            ),
            "contact_saturation_count": sum(
                int(row["contact_saturation_count"]) for row in rows
            ),
            "maximum_ncon": max(
                (int(row["maximum_ncon"]) for row in rows),
                default=0,
            ),
            "minimum_nconmax": min(
                (
                    int(row["minimum_nconmax"])
                    for row in rows
                    if row["minimum_nconmax"] is not None
                ),
                default=None,
            ),
            "warning_count": sum(
                int(row["warning_count"]) for row in rows
            ),
            "contact_capacity_warning_count": sum(
                int(row["contact_capacity_warning_count"])
                for row in rows
            ),
        }
    return result


def _deadline_report(
    rows: list[Mapping[str, Any]],
    *,
    baseline: str,
    deadline_seconds: float,
) -> dict[str, Any]:
    values = np.asarray(
        [
            float(value)
            for row in rows
            for value in row["baselines"][baseline][
                "screen_latency_seconds_values"
            ]
        ],
        dtype=np.float64,
    )
    misses = int(np.sum(values > deadline_seconds))
    return {
        "deadline_seconds": deadline_seconds,
        "sample_count": int(values.size),
        "miss_count": misses,
        "miss_rate": misses / int(values.size) if values.size else None,
    }


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    maximum_no_guard_shadow_error: float,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    aggregate, development_gates = development._analyze(
        protocol,
        rows,
        restore_failure_count=restore_failure_count,
        maximum_no_guard_shadow_error=(
            maximum_no_guard_shadow_error
        ),
    )
    gates = protocol["gates"]
    thresholds = _threshold_identity(
        rows,
        thresholds=[float(value) for value in gates["thresholds_rad"]],
    )
    contacts = _contact_aggregate(contact_reports)
    deadline = _deadline_report(
        rows,
        baseline="predictive_brake",
        deadline_seconds=float(gates["control_period_seconds"]),
    )
    low = aggregate["by_dose"]["low"]
    medium = aggregate["by_dose"]["medium"]
    high = aggregate["by_dose"]["high"]

    def stress_sum(baseline: str, field: str) -> float:
        return float(
            medium[f"{baseline}_{field}"]
            + high[f"{baseline}_{field}"]
        )

    predictive_p95 = aggregate[
        "predictive_brake_screen_latency_seconds_p95"
    ]
    gate_results = {
        "environment_count": development_gates["environment_count"],
        "environment_lane_coverage": development_gates[
            "environment_lane_coverage"
        ],
        "stress_lane_count": development_gates["stress_lane_count"],
        "baseline_lane_count": development_gates["baseline_lane_count"],
        "restore_identity": development_gates["restore_identity"],
        "zero_policy_or_outcome_fields": development_gates[
            "zero_policy_or_outcome_fields"
        ],
        "exact_action_identity": all(
            aggregate[f"{baseline}_exact_action_mismatch_count"] == 0
            for baseline in development.pilot.BASELINES
        ),
        "threshold_classification_identity": (
            thresholds["trace_length_mismatch_count"] == 0
            and not any(
                thresholds[
                    "threshold_classification_disagreement_count"
                ].values()
            )
        ),
        "active_contact_capacity_warning_free": (
            contacts["phases"]["active"][
                "contact_capacity_warning_count"
            ]
            <= gates["active_contact_capacity_warning_count_max"]
        ),
        "active_contact_capacity_unsaturated": (
            contacts["phases"]["active"][
                "contact_saturation_count"
            ]
            <= gates["active_contact_saturation_count_max"]
        ),
        "low_negative_control": (
            low["no_guard_below_floor_count"] == 0
            and low["shadow_only_below_floor_count"] == 0
            and low["predictive_brake_trigger_count"] == 0
            and low["predictive_brake_deadlock_count"] == 0
        ),
        "stress_activation": (
            stress_sum("shadow_only", "crossing_count")
            >= gates["stress_shadow_crossing_count_min"]
        ),
        "predictive_crossing_containment": (
            stress_sum("predictive_brake", "crossing_count")
            <= gates["stress_predictive_crossing_count_max"]
        ),
        "predictive_floor_containment": (
            stress_sum("predictive_brake", "below_floor_count")
            <= gates["stress_predictive_below_floor_count_max"]
        ),
        "reactive_crossing_containment": (
            stress_sum("reactive_stop", "crossing_count")
            <= gates["stress_reactive_crossing_count_max"]
        ),
        "reactive_post_step_exposure_observed": (
            stress_sum("reactive_stop", "below_floor_count")
            >= gates["stress_reactive_below_floor_count_min"]
        ),
        "predictive_availability_not_below_reactive": (
            aggregate[
                "predictive_brake_executed_step_availability"
            ]
            - aggregate["reactive_stop_executed_step_availability"]
            >= gates[
                "predictive_minus_reactive_availability_min"
            ]
        ),
        "predictive_latency_p95": (
            predictive_p95 is not None
            and predictive_p95
            <= gates["predictive_screen_latency_p95_seconds_max"]
        ),
        "predictive_deadline_miss_rate": (
            deadline["miss_rate"] is not None
            and deadline["miss_rate"]
            <= gates["predictive_deadline_miss_rate_max"]
        ),
    }
    metrics = {
        "aggregate": aggregate,
        "registered_threshold_identity": thresholds,
        "contact_capacity": contacts,
        "contact_reports": contact_reports,
        "predictive_latency_deadline": deadline,
        "all_side_numeric_identity_diagnostic": {
            "tolerance_rad": gates[
                "all_side_numeric_identity_diagnostic_rad"
            ],
            "maximum_error_rad": maximum_no_guard_shadow_error,
            "within_tolerance": (
                maximum_no_guard_shadow_error
                <= gates[
                    "all_side_numeric_identity_diagnostic_rad"
                ]
            ),
            "registered_as_qualification_gate": False,
        },
    }
    return metrics, gate_results


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V14StressQualificationError(
            "qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    development._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V14StressQualificationError(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = _WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    maximum_error = 0.0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            (
                environment_rows,
                failures,
                observed_error,
                contacts,
            ) = _run_audited_environment(
                spec,
                gpu=gpu,
                warnings=warnings,
            )
            rows.extend(environment_rows)
            contact_reports.append(contacts)
            restore_failures += failures
            maximum_error = max(maximum_error, observed_error)
    finally:
        mujoco.set_mju_user_warning(previous_warning_callback)
    metrics, gate_results = _analyze(
        protocol,
        rows,
        restore_failure_count=restore_failures,
        maximum_no_guard_shadow_error=maximum_error,
        contact_reports=contact_reports,
    )
    qualification_pass = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if qualification_pass
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": qualification_pass,
        "held_out_mechanism_claim_authorized": qualification_pass,
        "task_utility_claim_authorized": False,
        "protocol": {
            "path": protocol_path.relative_to(REPO_ROOT).as_posix(),
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
        "analysis": metrics,
        "lanes": rows,
        "warning_messages": warnings.records,
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "qualification_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return {
        "classification": evidence["classification"],
        "qualification_pass": qualification_pass,
        "environment_count": metrics["aggregate"][
            "environment_count"
        ],
        "stress_lane_count": metrics["aggregate"][
            "stress_lane_count"
        ],
        "baseline_lane_count": sum(
            metrics["aggregate"][f"{baseline}_lane_count"]
            for baseline in development.pilot.BASELINES
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
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V14StressQualificationError(
            "qualification evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V14StressQualificationError(
            "qualification checksum manifest differs"
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
        raise V14StressQualificationError(
            "qualification evidence identity differs"
        )
    recorded_analysis = evidence["analysis"]
    metrics, gates = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(
            recorded_analysis["aggregate"]["restore_failure_count"]
        ),
        maximum_no_guard_shadow_error=float(
            recorded_analysis["aggregate"][
                "no_guard_shadow_maximum_side_error_rad"
            ]
        ),
        contact_reports=recorded_analysis["contact_reports"],
    )
    if (
        metrics != recorded_analysis
        or gates != evidence["gate_results"]
        or evidence["qualification_pass"] is not all(gates.values())
    ):
        raise V14StressQualificationError(
            "qualification analysis is stale"
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
        payload = preflight(protocol, gpu=args.gpu)
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
