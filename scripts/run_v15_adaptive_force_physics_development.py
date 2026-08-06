#!/usr/bin/env python3
"""Develop v15.6 adaptive force recovery on disclosed physics lanes."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterator, Mapping


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
    run_l2_predictive_virtual_brake_v15_adaptive_force_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_force_constrained_physics_development as v155,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.6-adaptive-force-"
    "physics-development-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.6-adaptive-force-"
    "physics-development-evidence.v1"
)
AUTHORIZED_STATUS = "authorized_v15_6_adaptive_force_physics_development"
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_adaptive_force_"
    "physics_development_protocol.json"
)
OLD_V15_BASELINE = v155.OLD_V15_BASELINE
V14_BASELINE = v155.V14_BASELINE
V15_BASELINE = "v15_6_adaptive_force_recovery"
BASELINES = ("no_guard", "reactive_stop", V14_BASELINE, V15_BASELINE)
PHYSICS_CONDITIONS = v155.PHYSICS_CONDITIONS


class V15AdaptiveForcePhysicsDevelopmentError(RuntimeError):
    """Raised when the v15.6 development contract differs."""


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15AdaptiveForcePhysicsDevelopmentError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 output root resolves to repository"
        )
    return root


def _replace_names(value: Any, *, reverse: bool = False) -> Any:
    old, new = (
        (V15_BASELINE, v155.V15_BASELINE)
        if reverse
        else (v155.V15_BASELINE, V15_BASELINE)
    )

    def replace(text: str) -> str:
        result = text.replace(old, new)
        return result.replace("v15_6", "v15_5") if reverse else result.replace(
            "v15_5", "v15_6"
        )

    if isinstance(value, dict):
        return {
            replace(str(key)): _replace_names(item, reverse=reverse)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_names(item, reverse=reverse) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_names(item, reverse=reverse) for item in value)
    if isinstance(value, str):
        return replace(value)
    return value


def _persist_names(value: Any) -> Any:
    return _replace_names(v155._replace_names(value))


def _raw_analysis(value: Any) -> Any:
    return v155._replace_names(_replace_names(value, reverse=True), reverse=True)


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "outcome_disclosed_development": True,
        "qualification_claim": False,
        "model_mismatch_claim": False,
        "task_utility_claim": False,
        "real_time_claim": False,
    }
    design = protocol.get("design", {})
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization") != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or design.get("physics_conditions")
        != [dict(row) for row in PHYSICS_CONDITIONS]
        or design.get("baselines") != list(BASELINES)
        or design.get("doses")
        != [
            dict(row)
            for row in v155.v154.predecessor.base.calibration.v14.pilot.DOSES
        ]
        or design.get("outcome_disclosed_population_reused") is not True
        or design.get("qualification_population") is not False
        or design.get("proactive_trigger_margin_rad")
        != recovery.PROACTIVE_TRIGGER_MARGIN_RAD
        or design.get("safe_margin_floor_rad") != recovery.SAFE_MARGIN_FLOOR_RAD
        or design.get("soft_guard_solref") != list(recovery.SOFT_GUARD_SOLREF)
        or design.get("fallback_guard_solrefs")
        != [list(row) for row in recovery.FALLBACK_GUARD_SOLREFS]
        or design.get("recovery_ladder_fractions")
        != list(recovery.RECOVERY_LADDER_FRACTIONS)
        or design.get("candidate_post_force_prediction_active") is not True
    ):
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "unsupported or unauthorized v15.6 development protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15AdaptiveForcePhysicsDevelopmentError(
                f"v15.6 development source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15AdaptiveForcePhysicsDevelopmentError(
                "v15.6 development binding differs: " + str(binding["path"])
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15AdaptiveForcePhysicsDevelopmentError as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh v15.6 development output root already exists")
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
        "qualification_claim_authorized": False,
    }


def _run_screened(env: Any) -> dict[str, Any]:
    created: list[Any] = []
    v154 = v155.v154
    original_class = v154.recovery.MultiJointDynamicStateRecoveryEnvironment
    original_schema = v154.recovery.BRAKE_AUDIT_SCHEMA

    class RecordingAdaptiveForceEnvironment(
        recovery.MultiJointAdaptiveForceRecoveryEnvironment
    ):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            created.append(self)

    v154.recovery.MultiJointDynamicStateRecoveryEnvironment = (
        RecordingAdaptiveForceEnvironment
    )
    v154.recovery.BRAKE_AUDIT_SCHEMA = recovery.BRAKE_AUDIT_SCHEMA
    try:
        result = v154._run_screened(env)
    finally:
        v154.recovery.BRAKE_AUDIT_SCHEMA = original_schema
        v154.recovery.MultiJointDynamicStateRecoveryEnvironment = original_class
    if len(created) != 1:
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 screened wrapper creation count differs"
        )
    observations = created[0].observations
    result.update(
        {
            "force_constrained_audit_count": len(observations),
            "force_constrained_inactive_count": sum(
                row.get("force_constrained_recovery_active") is not True
                for row in observations
            ),
            "selected_post_force_prediction_identity_failure_count": sum(
                row.get("selected_post_force_prediction_execution_identity")
                is not True
                for row in observations
            ),
            "selected_force_infeasible_count": sum(
                row.get("selected_force_feasible") is not True
                for row in observations
            ),
            "force_rejected_base_eligible_candidate_count": sum(
                int(row["force_rejected_base_eligible_candidate_count"])
                for row in observations
            ),
            "force_constrained_soft_profile_mismatch_count": sum(
                row.get("adaptive_force_recovery_active") is not True
                for row in observations
            ),
            "adaptive_force_audit_count": len(observations),
            "adaptive_force_inactive_count": sum(
                row.get("adaptive_force_recovery_active") is not True
                for row in observations
            ),
            "proactive_trigger_margin_mismatch_count": sum(
                row.get("adaptive_proactive_trigger_margin_rad")
                != recovery.PROACTIVE_TRIGGER_MARGIN_RAD
                for row in observations
            ),
            "extended_recovery_evaluated_count": sum(
                row.get("adaptive_extended_recovery_evaluated") is True
                for row in observations
            ),
            "extended_recovery_selected_count": sum(
                row.get("adaptive_extended_recovery_selected") is True
                for row in observations
            ),
            "fallback_profile_evaluated_count": sum(
                row.get("adaptive_fallback_profile_evaluated") is True
                for row in observations
            ),
            "fallback_profile_selected_count": sum(
                row.get("adaptive_fallback_profile_selected") is True
                for row in observations
            ),
        }
    )
    return result


@contextmanager
def _patched_runtime() -> Iterator[None]:
    v154 = v155.v154
    force_development = v154.predecessor.base.force_development
    with v154._patched_dynamic_runtime():
        original = force_development._run_screened
        force_development._run_screened = _run_screened
        try:
            yield
        finally:
            force_development._run_screened = original


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failures: Mapping[str, int],
    contact_reports: list[Mapping[str, Any]],
    physics_audits: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    compatibility_protocol = _replace_names(protocol, reverse=True)
    analysis, gates = v155._analyze(
        compatibility_protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    reports = [row["baselines"][OLD_V15_BASELINE] for row in rows]
    fields = (
        "adaptive_force_audit_count",
        "adaptive_force_inactive_count",
        "proactive_trigger_margin_mismatch_count",
        "extended_recovery_evaluated_count",
        "extended_recovery_selected_count",
        "fallback_profile_evaluated_count",
        "fallback_profile_selected_count",
    )
    metrics = {
        f"v15_6_{field}": sum(int(report[field]) for report in reports)
        for field in fields
    }
    gates = {
        **gates,
        "v15_6_adaptive_force_audit_coverage": (
            metrics["v15_6_adaptive_force_audit_count"]
            == protocol["gates"]["expected_v15_6_policy_step_count"]
        ),
        "v15_6_adaptive_force_active": (
            metrics["v15_6_adaptive_force_inactive_count"] == 0
        ),
        "v15_6_proactive_trigger_identity": (
            metrics["v15_6_proactive_trigger_margin_mismatch_count"] == 0
        ),
        "v15_6_extended_recovery_evaluated": (
            metrics["v15_6_extended_recovery_evaluated_count"]
            >= protocol["gates"][
                "minimum_extended_recovery_evaluated_count"
            ]
        ),
        "v15_6_extended_recovery_selected": (
            metrics["v15_6_extended_recovery_selected_count"]
            >= protocol["gates"]["minimum_extended_recovery_selected_count"]
        ),
    }
    return (
        {
            **analysis,
            "adaptive_force_metrics": metrics,
            "predecessor_nonpass_reinterpreted": False,
            "development_population_outcome_disclosed": True,
        },
        gates,
    )


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 development preflight failed: "
            + "; ".join(report["blockers"])
        )
    predecessor_runner = v155.v154.predecessor
    predecessor_runner.base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous_warning = mujoco.get_mju_user_warning()
    warnings = predecessor_runner.base.calibration.audit._WarningAudit()
    rows = []
    contact_reports = []
    physics_audits = []
    restore_failures = {
        str(row["condition_id"]): 0 for row in PHYSICS_CONDITIONS
    }
    mujoco.set_mju_user_warning(warnings)
    try:
        with _patched_runtime():
            for condition in PHYSICS_CONDITIONS:
                condition_id = str(condition["condition_id"])
                for spec in protocol["environments"]:
                    observed, failures, contacts, physics_audit = (
                        predecessor_runner._run_audited_environment(
                            spec, condition, gpu=gpu, warnings=warnings
                        )
                    )
                    rows.extend(observed)
                    restore_failures[condition_id] += failures
                    contact_reports.append(contacts)
                    physics_audits.append(physics_audit)
    finally:
        mujoco.set_mju_user_warning(previous_warning)
    analysis, gate_results = _analyze(
        protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    passed = all(gate_results.values())
    v155_lanes = v155._replace_names(v155.v154._replace_names(rows))
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "development_pass": passed,
        "qualification_claim_authorized": False,
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
        "gate_results": _persist_names(gate_results),
        "analysis": _persist_names(analysis),
        "lanes": _replace_names(v155_lanes),
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "development_evidence.json"
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
    evidence_path = root / "development_evidence.json"
    checksum_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksum_path.is_file():
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 development evidence is absent"
        )
    if checksum_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 development checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 development evidence binding differs"
        )
    v155_rows = _replace_names(evidence["lanes"], reverse=True)
    v154_rows = v155._replace_names(v155_rows, reverse=True)
    rows = v155.v154._replace_names(v154_rows, reverse=True)
    raw = _raw_analysis(evidence["analysis"])
    analysis, gates = _analyze(
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
        or bool(evidence["development_pass"]) != all(gates.values())
    ):
        raise V15AdaptiveForcePhysicsDevelopmentError(
            "v15.6 development recomputation differs"
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
                    "development_pass": evidence["development_pass"],
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
                "development_pass": evidence["development_pass"],
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
