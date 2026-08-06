#!/usr/bin/env python3
"""Qualify frozen v15.8 observed-force calibration under model mismatch."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
    run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_incremental_adaptive_force_model_mismatch_qualification as predecessor,
)
from scripts import (  # noqa: E402
    run_v15_observed_force_calibrated_model_mismatch_development as development,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.8-observed-force-calibrated-"
    "model-mismatch-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.8-observed-force-calibrated-"
    "model-mismatch-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_8_observed_force_calibrated_model_mismatch_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_observed_force_calibrated_"
    "model_mismatch_qualification_protocol.json"
)
V14_BASELINE = predecessor.V14_BASELINE
V15_BASELINE = "v15_8_observed_force_calibrated_recovery"
BASELINES = ("no_guard", "reactive_stop", V14_BASELINE, V15_BASELINE)
CALIBRATION_GATE_KEYS = (
    "v15_8_calibration_step_coverage",
    "v15_8_calibration_minimum_residual_identity",
    "v15_8_calibration_nominal_residual_dominance",
    "v15_8_calibration_selector_actual_parameter_noninterference",
    "v15_8_calibration_task_outcome_noninterference",
)


class V15ObservedForceCalibratedQualificationError(RuntimeError):
    """Raised when the v15.8 qualification contract differs."""


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15ObservedForceCalibratedQualificationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 output root resolves to repository"
        )
    return root


def _expected_authorization() -> dict[str, bool]:
    return predecessor._expected_authorization()


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    design = protocol.get("design", {})
    selection = protocol.get("selection", {})
    gates = protocol.get("gates", {})
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization") != _expected_authorization()
        or len(protocol.get("environments", ())) != 18
        or design.get("model_mismatch_conditions")
        != [dict(row) for row in predecessor.MODEL_MISMATCH_CONDITIONS]
        or design.get("baselines") != list(BASELINES)
        or design.get("observed_force_shadow_calibration") is not True
        or design.get("observed_force_shadow_calibration_interface")
        != recovery.CALIBRATION_INTERFACE
        or design.get("observed_force_shadow_model_bank")
        != [dict(row) for row in recovery.MODEL_BANK]
        or design.get("registered_force_thresholds_unchanged") is not True
        or design.get("qualification_population") is not True
        or design.get("outcome_disclosed_population_reused") is not False
        or gates.get("expected_v15_8_policy_step_count") != 26460
        or gates.get("calibration_nonminimum_bind_count_max") != 0
        or gates.get("calibration_selected_residual_exceeds_nominal_count_max")
        != 0
        or selection.get("all_prior_exact_task_init_pairs_excluded") is not True
        or selection.get("v15_7_model_mismatch_results_observed_before_freeze")
        is not True
        or selection.get("v15_8_qualification_results_observed_before_freeze")
        is not False
        or selection.get("task_outcomes_used_for_selection") is not False
    ):
        raise V15ObservedForceCalibratedQualificationError(
            "unsupported or unauthorized v15.8 model-mismatch protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15ObservedForceCalibratedQualificationError(
                f"v15.8 model-mismatch source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15ObservedForceCalibratedQualificationError(
                "v15.8 model-mismatch binding differs: "
                + str(binding["path"])
            )


def _compatibility_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    compatible = deepcopy(dict(protocol))
    compatible["schema"] = predecessor.PROTOCOL_SCHEMA
    compatible["status"] = predecessor.AUTHORIZED_STATUS
    compatible["design"]["baselines"] = list(predecessor.BASELINES)
    compatible["design"]["mechanism_parameters_unchanged_from_v15_7"] = True
    compatible["design"][
        "same_model_safety_force_and_latency_thresholds_unchanged"
    ] = True
    compatible["design"][
        "same_model_prediction_identity_replaced_by_mismatch_audit"
    ] = True
    compatible["design"]["incremental_extended_search"] = True
    compatible["design"]["maximum_extended_candidates_per_increment"] = 1
    compatible["selection"]["model_mismatch_results_observed_before_freeze"] = (
        False
    )
    return compatible


def _replace_names(value: Any, *, reverse: bool = False) -> Any:
    old, new = (
        (V15_BASELINE, predecessor.V15_BASELINE)
        if reverse
        else (predecessor.V15_BASELINE, V15_BASELINE)
    )

    def replace(text: str) -> str:
        result = text.replace(old, new)
        return result.replace("v15_8", "v15_7") if reverse else result.replace(
            "v15_7", "v15_8"
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


def _calibration_metrics(analysis: Mapping[str, Any]) -> dict[str, Any]:
    audits = analysis["physics_parameter_audits"]
    return {
        "physics_audit_count": len(audits),
        "evaluation_count": sum(
            int(row["observed_force_calibration_evaluation_count"])
            for row in audits
        ),
        "bind_count": sum(
            int(row["observed_force_calibration_bind_count"]) for row in audits
        ),
        "nonminimum_bind_count": sum(
            int(row["observed_force_calibration_nonminimum_bind_count"])
            for row in audits
        ),
        "selected_residual_exceeds_nominal_count": sum(
            int(
                row[
                    "observed_force_calibration_selected_residual_exceeds_nominal_count"
                ]
            )
            for row in audits
        ),
        "selected_condition_mismatch_count": sum(
            int(
                row[
                    "observed_force_calibration_selected_condition_mismatch_count"
                ]
            )
            for row in audits
        ),
        "maximum_selected_residual": max(
            float(row["observed_force_calibration_maximum_selected_residual"])
            for row in audits
        ),
        "actual_parameter_read_by_selector_count": sum(
            row[
                "observed_force_calibration_actual_parameter_read_by_selector"
            ]
            is not False
            for row in audits
        ),
        "task_outcome_read_count": sum(
            row["observed_force_calibration_task_outcome_read"] is not False
            for row in audits
        ),
    }


def _calibration_gates(
    protocol: Mapping[str, Any], metrics: Mapping[str, Any]
) -> dict[str, bool]:
    expected = int(protocol["gates"]["expected_v15_8_policy_step_count"])
    return {
        "v15_8_calibration_step_coverage": metrics["evaluation_count"]
        == expected
        == metrics["bind_count"],
        "v15_8_calibration_minimum_residual_identity": metrics[
            "nonminimum_bind_count"
        ]
        <= protocol["gates"]["calibration_nonminimum_bind_count_max"],
        "v15_8_calibration_nominal_residual_dominance": metrics[
            "selected_residual_exceeds_nominal_count"
        ]
        <= protocol["gates"][
            "calibration_selected_residual_exceeds_nominal_count_max"
        ],
        "v15_8_calibration_selector_actual_parameter_noninterference": metrics[
            "actual_parameter_read_by_selector_count"
        ]
        == 0,
        "v15_8_calibration_task_outcome_noninterference": metrics[
            "task_outcome_read_count"
        ]
        == 0,
    }


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
        compatible = _compatibility_protocol(protocol)
        predecessor._verify_protocol(compatible)
    except (
        V15ObservedForceCalibratedQualificationError,
        predecessor.V15IncrementalAdaptiveForceModelMismatchQualificationError,
    ) as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh v15.8 model-mismatch output root already exists")
    return {
        "schema": EVIDENCE_SCHEMA.replace("evidence.v1", "preflight.v1"),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "condition_count": len(protocol["design"]["model_mismatch_conditions"]),
        "output_root_absent": not root.exists(),
        "model_mismatch_claim_authorized_on_pass": True,
        "task_outcome_read_authorized": False,
    }


def _persist_evidence(
    evidence: dict[str, Any], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    persisted = _replace_names(evidence)
    persisted["schema"] = EVIDENCE_SCHEMA
    metrics = _calibration_metrics(persisted["analysis"])
    calibration_gates = _calibration_gates(protocol, metrics)
    persisted["analysis"]["observed_force_calibration_metrics"] = metrics
    persisted["gate_results"].update(calibration_gates)
    passed = all(persisted["gate_results"].values())
    persisted["model_mismatch_qualification_pass"] = passed
    persisted["model_mismatch_claim_authorized"] = passed
    persisted["v15_7_model_mismatch_nonpass_reinterpreted"] = False
    root = _output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    evidence_path.write_text(canonical_text(persisted), encoding="utf-8")
    checksums_path = root / "SHA256SUMS"
    checksums_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return persisted


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    compatible = _compatibility_protocol(protocol)
    with development._patched_calibrated_runtime():
        evidence = predecessor.execute(
            compatible, protocol_path=protocol_path, gpu=gpu
        )
    return _persist_evidence(evidence, protocol)


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    _verify_protocol(protocol)
    compatible = _compatibility_protocol(protocol)
    predecessor._verify_protocol(compatible)
    root = _output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 qualification evidence is absent"
        )
    if checksums_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 qualification checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 qualification evidence binding differs"
        )
    metrics = _calibration_metrics(evidence["analysis"])
    calibration_gates = _calibration_gates(protocol, metrics)
    if evidence["analysis"]["observed_force_calibration_metrics"] != metrics:
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 calibration metric recomputation differs"
        )
    for key, value in calibration_gates.items():
        if evidence["gate_results"].get(key) is not value:
            raise V15ObservedForceCalibratedQualificationError(
                "v15.8 calibration gate recomputation differs"
            )

    core = _replace_names(deepcopy(evidence), reverse=True)
    core["analysis"].pop("observed_force_calibration_metrics")
    for key in CALIBRATION_GATE_KEYS:
        core["gate_results"].pop(key.replace("v15_8", "v15_7"), None)
    rows = predecessor.predecessor._raw_lanes(core["lanes"])
    raw = predecessor.predecessor._raw_analysis(core["analysis"])
    with predecessor.predecessor.development._patched_runner_contract():
        with predecessor._patched_mismatch_runtime():
            analysis, gates = predecessor.predecessor.development._analyze(
                compatible,
                rows,
                restore_failures=raw["restore_failure_count_by_condition"],
                contact_reports=raw["contact_reports"],
                physics_audits=raw["physics_parameter_audits"],
            )
    if (
        canonical_text(predecessor.predecessor._persist_names(analysis))
        != canonical_text(core["analysis"])
        or canonical_text(predecessor.predecessor._persist_names(gates))
        != canonical_text(core["gate_results"])
    ):
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 core qualification recomputation differs"
        )
    passed = all(evidence["gate_results"].values())
    if (
        evidence["model_mismatch_qualification_pass"] is not passed
        or evidence["model_mismatch_claim_authorized"] is not passed
    ):
        raise V15ObservedForceCalibratedQualificationError(
            "v15.8 qualification classification differs"
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
    else:
        evidence = execute(protocol, protocol_path=protocol_path, gpu=args.gpu)
    print(
        canonical_text(
            {
                "schema": EVIDENCE_SCHEMA + ".completion",
                "model_mismatch_qualification_pass": evidence[
                    "model_mismatch_qualification_pass"
                ],
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
