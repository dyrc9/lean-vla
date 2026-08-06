#!/usr/bin/env python3
"""Retry v15.2 stress qualification with analysis aliases only."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
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
from scripts import run_v15_current_edge_priority_recovery_stress_qualification as predecessor  # noqa: E402


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-qualification-fresh2-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.2-current-edge-priority-"
    "recovery-stress-qualification-fresh2-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_2_recovery_stress_qualification_fresh2"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh2_protocol.json"
)


class V15RecoveryStressQualificationFresh2Error(RuntimeError):
    """Raised when the compatibility-only retry differs from protocol."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 output root resolves to repository"
        )
    return root


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "held_out_mechanism_claim": True,
        "task_utility_claim": False,
        "real_time_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["doses"]
        != [
            dict(row)
            for row in predecessor.calibration.v14.pilot.DOSES
        ]
        or protocol["design"]["baselines"]
        != list(predecessor.calibration.BASELINES)
        or protocol["design"]["horizon_steps"]
        != predecessor.calibration.v14.pilot.HORIZON_STEPS
        or protocol.get("fresh1_abort", {}).get(
            "analysis_compatibility_aliases_only"
        )
        is not True
    ):
        raise V15RecoveryStressQualificationFresh2Error(
            "unsupported or unauthorized fresh2 protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise V15RecoveryStressQualificationFresh2Error(
                f"fresh2 source binding differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if (
            not path.is_file()
            or file_sha256(path) != binding["sha256"]
        ):
            raise V15RecoveryStressQualificationFresh2Error(
                "fresh2 predecessor binding differs: "
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
    except V15RecoveryStressQualificationFresh2Error as exc:
        blockers.append(str(exc))
    if predecessor.calibration._git_status():
        blockers.append("worktree is not clean")
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append("fresh2 output root already exists")
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.2-current-edge-"
            "priority-recovery-stress-qualification-fresh2-preflight.v1"
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
        "analysis_compatibility_aliases_only": True,
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "real_time_claim_authorized": False,
    }


def _compatibility_protocol(
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    compatible = deepcopy(dict(protocol))
    gates = dict(compatible["gates"])
    gates["selected_floor_violation_count_max"] = gates[
        "v15_2_selected_floor_violation_count_max"
    ]
    gates["control_period_seconds"] = 0.05
    compatible["gates"] = gates
    return compatible


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failure_count: int,
    maximum_no_guard_shadow_error: float,
    contact_reports: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    return predecessor._analyze(
        _compatibility_protocol(protocol),
        rows,
        restore_failure_count=restore_failure_count,
        maximum_no_guard_shadow_error=maximum_no_guard_shadow_error,
        contact_reports=contact_reports,
    )


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 preflight failed: "
            + "; ".join(report["blockers"])
        )
    predecessor.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15RecoveryStressQualificationFresh2Error(
            "mujoco warning callback is unavailable"
        ) from exc
    previous_warning_callback = mujoco.get_mju_user_warning()
    warnings = predecessor.calibration.audit._WarningAudit()
    rows: list[dict[str, Any]] = []
    contact_reports = []
    restore_failures = 0
    maximum_error = 0.0
    mujoco.set_mju_user_warning(warnings)
    try:
        for spec in protocol["environments"]:
            environment_rows, failures, error, contacts = (
                predecessor.calibration._run_audited_environment(
                    spec,
                    gpu=gpu,
                    warnings=warnings,
                )
            )
            rows.extend(environment_rows)
            contact_reports.append(contacts)
            restore_failures += failures
            maximum_error = max(maximum_error, error)
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
        "real_time_claim_authorized": False,
        "fresh1_abort_acknowledged": True,
        "analysis_compatibility_aliases_only": True,
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
        "environment_count": metrics["aggregate"]["environment_count"],
        "stress_lane_count": metrics["aggregate"]["stress_lane_count"],
        "baseline_lane_count": sum(
            metrics["aggregate"][f"{baseline}_lane_count"]
            for baseline in predecessor.calibration.BASELINES
        ),
        "evidence_path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "checksums_path": checksums_path.relative_to(REPO_ROOT).as_posix(),
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
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 evidence or checksums are absent"
        )
    expected = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected:
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 checksum manifest differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
        or evidence.get("fresh1_abort_acknowledged") is not True
        or evidence.get("analysis_compatibility_aliases_only") is not True
        or evidence["integrity"]
        != {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        }
    ):
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 evidence identity differs"
        )
    recorded = evidence["analysis"]
    metrics, gates = _analyze(
        protocol,
        evidence["lanes"],
        restore_failure_count=int(
            recorded["aggregate"]["restore_failure_count"]
        ),
        maximum_no_guard_shadow_error=float(
            recorded["aggregate"][
                "no_guard_shadow_maximum_side_error_rad"
            ]
        ),
        contact_reports=recorded["contact_reports"],
    )
    if (
        metrics != recorded
        or gates != evidence["gate_results"]
        or evidence["qualification_pass"] is not all(gates.values())
    ):
        raise V15RecoveryStressQualificationFresh2Error(
            "fresh2 analysis is stale"
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
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
