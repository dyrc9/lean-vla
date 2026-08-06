#!/usr/bin/env python3
"""Qualify v15.7 on a fresh globally held-out physics population."""

from __future__ import annotations

import argparse
from pathlib import Path
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
from scripts import (  # noqa: E402
    run_v15_incremental_adaptive_force_physics_development as development,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "physics-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.7-incremental-adaptive-force-"
    "physics-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_7_incremental_adaptive_force_physics_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "physics_qualification_protocol.json"
)
V14_BASELINE = development.V14_BASELINE
V15_BASELINE = development.V15_BASELINE
BASELINES = development.BASELINES
PHYSICS_CONDITIONS = development.PHYSICS_CONDITIONS


class V15IncrementalAdaptiveForcePhysicsQualificationError(RuntimeError):
    """Raised when the frozen v15.7 qualification contract differs."""


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification output root resolves to repository"
        )
    return root


def _expected_authorization() -> dict[str, bool]:
    return {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "physics_domain_robustness_claim": True,
        "model_mismatch_claim": False,
        "task_utility_claim": False,
        "real_time_claim": False,
    }


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    design = protocol.get("design", {})
    selection = protocol.get("selection", {})
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != _expected_authorization()
        or len(protocol.get("environments", ())) != 18
        or design.get("physics_conditions")
        != [dict(row) for row in PHYSICS_CONDITIONS]
        or design.get("baselines") != list(BASELINES)
        or design.get("doses")
        != [
            dict(row)
            for row in development.v156.v155.v154.predecessor.base.calibration.v14.pilot.DOSES
        ]
        or design.get("qualification_population") is not True
        or design.get("outcome_disclosed_population_reused") is not False
        or design.get("dynamic_motion_generator_phase_bound") is not True
        or design.get("gripper_current_action_bound") is not True
        or design.get("incremental_extended_search") is not True
        or design.get("maximum_extended_candidates_per_increment") != 1
        or design.get("extended_recovery_force_attribution_bound") is not True
        or design.get("mechanism_parameters_unchanged_from_v15_7_development")
        is not True
        or selection.get("all_prior_exact_task_init_pairs_excluded") is not True
        or selection.get("physics_qualification_results_observed_before_freeze")
        is not False
        or selection.get("task_outcomes_used_for_selection") is not False
    ):
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "unsupported or unauthorized v15.7 physics qualification protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15IncrementalAdaptiveForcePhysicsQualificationError(
                f"v15.7 qualification source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15IncrementalAdaptiveForcePhysicsQualificationError(
                "v15.7 qualification binding differs: "
                + str(binding["path"])
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15IncrementalAdaptiveForcePhysicsQualificationError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh v15.7 qualification output root already exists")
    return {
        "schema": EVIDENCE_SCHEMA.replace("evidence.v1", "preflight.v1"),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "condition_count": len(protocol["design"]["physics_conditions"]),
        "expected_stress_lane_count": protocol["gates"][
            "expected_total_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_total_baseline_lane_count"
        ],
        "output_root_absent": not root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "physics_domain_robustness_claim_authorized_on_pass": True,
    }


def _persist_names(value: Any) -> Any:
    return development._replace_names(
        development.v156.v155._replace_names(value)
    )


def _persist_lanes(rows: list[Mapping[str, Any]]) -> Any:
    v155 = development.v156.v155
    lanes = v155._replace_names(v155.v154._replace_names(rows))
    return development._replace_names(lanes)


def _raw_lanes(value: Any) -> Any:
    v155 = development.v156.v155
    lanes = development._replace_names(value, reverse=True)
    lanes = v155._replace_names(lanes, reverse=True)
    return v155.v154._replace_names(lanes, reverse=True)


def _raw_analysis(value: Any) -> Any:
    return development.v156.v155._replace_names(
        development._replace_names(value, reverse=True), reverse=True
    )


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    predecessor = development.v156.v155.v154.predecessor
    predecessor.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = predecessor.base.calibration.audit._WarningAudit()
    rows = []
    contact_reports = []
    physics_audits = []
    restore_failures = {
        str(row["condition_id"]): 0 for row in PHYSICS_CONDITIONS
    }
    mujoco.set_mju_user_warning(warnings)
    try:
        with development._patched_runner_contract():
            with development.v156._patched_runtime():
                for condition in PHYSICS_CONDITIONS:
                    condition_id = str(condition["condition_id"])
                    for spec in protocol["environments"]:
                        observed, failures, contacts, physics_audit = (
                            predecessor._run_audited_environment(
                                spec,
                                condition,
                                gpu=gpu,
                                warnings=warnings,
                            )
                        )
                        rows.extend(observed)
                        restore_failures[condition_id] += failures
                        contact_reports.append(contacts)
                        physics_audits.append(physics_audit)
            analysis, gate_results = development._analyze(
                protocol,
                rows,
                restore_failures=restore_failures,
                contact_reports=contact_reports,
                physics_audits=physics_audits,
            )
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    passed = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": passed,
        "physics_domain_robustness_claim_authorized": passed,
        "model_mismatch_claim_authorized": False,
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
        "baseline_execution_identity": {
            V14_BASELINE: (
                "Frozen v14 guard under the v15.4 exact dynamic-state snapshot "
                "harness."
            ),
            V15_BASELINE: (
                "Frozen v15.7 incremental adaptive force recovery selected by "
                "the immutable disclosed-development PASS."
            ),
        },
        "gate_results": _persist_names(gate_results),
        "analysis": _persist_names(analysis),
        "lanes": _persist_lanes(rows),
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "qualification_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksum_path = root / "SHA256SUMS"
    checksum_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return evidence


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksum_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksum_path.is_file():
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification evidence is absent"
        )
    if checksum_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification evidence binding differs"
        )
    rows = _raw_lanes(evidence["lanes"])
    raw = _raw_analysis(evidence["analysis"])
    with development._patched_runner_contract():
        analysis, gates = development._analyze(
            protocol,
            rows,
            restore_failures=raw["restore_failure_count_by_condition"],
            contact_reports=raw["contact_reports"],
            physics_audits=raw["physics_parameter_audits"],
        )
    if (
        canonical_text(_persist_names(analysis))
        != canonical_text(evidence["analysis"])
        or canonical_text(_persist_names(gates))
        != canonical_text(evidence["gate_results"])
        or bool(evidence["qualification_pass"]) != all(gates.values())
        or bool(evidence["physics_domain_robustness_claim_authorized"])
        != all(gates.values())
    ):
        raise V15IncrementalAdaptiveForcePhysicsQualificationError(
            "v15.7 qualification recomputation differs"
        )
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        print(canonical_text(preflight(protocol, gpu=args.gpu)), end="")
        return 0
    if args.validate_results:
        evidence = validate_results(protocol, protocol_path=protocol_path)
        print(
            canonical_text(
                {
                    "schema": EVIDENCE_SCHEMA + ".validation",
                    "valid": True,
                    "qualification_pass": evidence["qualification_pass"],
                    "classification": evidence["classification"],
                }
            ),
            end="",
        )
        return 0
    evidence = execute(protocol, protocol_path=protocol_path, gpu=args.gpu)
    print(
        canonical_text(
            {
                "schema": EVIDENCE_SCHEMA + ".completion",
                "qualification_pass": evidence["qualification_pass"],
                "classification": evidence["classification"],
                "output_root": _output_root(protocol)
                .relative_to(REPO_ROOT)
                .as_posix(),
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
