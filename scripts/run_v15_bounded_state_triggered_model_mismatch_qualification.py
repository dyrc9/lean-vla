#!/usr/bin/env python3
"""Qualify frozen v15.11 bounded state-triggered model-mismatch recovery."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
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
    run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_bounded_state_triggered_model_mismatch_development as development,
)
from scripts import (  # noqa: E402
    run_v15_observed_force_calibrated_model_mismatch_qualification as predecessor,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.11-bounded-state-triggered-"
    "model-mismatch-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.11-bounded-state-triggered-"
    "model-mismatch-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_11_bounded_state_triggered_model_mismatch_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_protocol_fresh4.json"
)
V15_BASELINE = "v15_11_bounded_state_triggered_recovery"
BASELINES = (
    "no_guard",
    "reactive_stop",
    predecessor.V14_BASELINE,
    V15_BASELINE,
)


class V15BoundedStateTriggeredQualificationError(RuntimeError):
    """Raised when the v15.11 qualification contract differs."""


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15BoundedStateTriggeredQualificationError(
            completed.stderr.strip() or "git status failed"
        )
    return completed.stdout.strip()


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 output root resolves to repository"
        )
    return root


def _replace_names(value: Any, *, reverse: bool = False) -> Any:
    old_baseline, new_baseline = (
        (V15_BASELINE, predecessor.V15_BASELINE)
        if reverse
        else (predecessor.V15_BASELINE, V15_BASELINE)
    )
    old_version, new_version = (
        ("v15_11", "v15_8") if reverse else ("v15_8", "v15_11")
    )
    old_dotted, new_dotted = (
        ("v15.11", "v15.8") if reverse else ("v15.8", "v15.11")
    )

    def replace(text: str) -> str:
        return (
            text.replace(old_baseline, new_baseline)
            .replace(old_version, new_version)
            .replace(old_dotted, new_dotted)
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


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    design = protocol.get("design", {})
    selection = protocol.get("selection", {})
    gates = protocol.get("gates", {})
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or len(protocol.get("environments", ())) != 18
        or design.get("baselines") != list(BASELINES)
        or design.get("bounded_state_triggered_recovery") is not True
        or design.get("state_trigger_margin_rad")
        != recovery.STATE_TRIGGER_MARGIN_RAD
        or design.get("state_target_offset_rad")
        != recovery.STATE_TARGET_OFFSET_RAD
        or design.get("maximum_guarded_candidate_rollouts_per_action")
        != recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS
        or design.get("unguarded_shadow_rollout_active") is not False
        or design.get("registered_force_thresholds_unchanged") is not True
        or design.get("qualification_population") is not True
        or design.get("outcome_disclosed_population_reused") is not False
        or gates.get("expected_v15_11_policy_step_count") != 26460
        or gates.get("expected_v15_11_calibration_evaluation_count")
        != 31752
        or gates.get(
            "minimum_v15_11_dynamic_motion_generator_step_count"
        )
        != 1
        or gates.get("minimum_extended_recovery_evaluated_count") != 0
        or gates.get("minimum_extended_recovery_selected_count") != 0
        or gates.get(
            "minimum_force_rejected_base_eligible_candidate_count"
        )
        != 0
        or design.get("conditional_extended_recovery_activation_required")
        is not False
        or design.get("force_rejection_activation_required") is not False
        or selection.get("all_prior_exact_task_init_pairs_excluded") is not True
        or selection.get("v15_8_qualification_results_observed_before_freeze")
        is not True
        or selection.get("v15_11_qualification_results_observed_before_freeze")
        is not False
        or selection.get("task_outcomes_used_for_selection") is not False
    ):
        raise V15BoundedStateTriggeredQualificationError(
            "unsupported or unauthorized v15.11 model-mismatch protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15BoundedStateTriggeredQualificationError(
                f"v15.11 model-mismatch source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15BoundedStateTriggeredQualificationError(
                "v15.11 model-mismatch binding differs: "
                + str(binding["path"])
            )


def _compatibility_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    compatible = deepcopy(dict(protocol))
    compatible["schema"] = predecessor.PROTOCOL_SCHEMA
    compatible["status"] = predecessor.AUTHORIZED_STATUS
    compatible["design"]["baselines"] = list(predecessor.BASELINES)
    compatible["design"]["proactive_trigger_margin_rad"] = 0.16
    compatible["design"][
        "proactive_trigger_and_force_thresholds_unchanged_from_v15_6"
    ] = True
    compatible["design"][
        "guard_candidates_order_thresholds_actions_unchanged"
    ] = True
    compatible["selection"][
        "v15_8_qualification_results_observed_before_freeze"
    ] = False
    compatible["selection"].pop(
        "v15_11_qualification_results_observed_before_freeze", None
    )
    compatible["gates"]["expected_v15_8_policy_step_count"] = 26460
    compatible["gates"]["minimum_extended_recovery_evaluated_count"] = 1
    compatible["gates"]["minimum_extended_recovery_selected_count"] = 1
    compatible["gates"][
        "minimum_force_rejected_base_eligible_candidate_count"
    ] = 1
    return compatible


@contextmanager
def _patched_qualification_runtime() -> Iterator[None]:
    original = predecessor.development._patched_calibrated_runtime
    predecessor.development._patched_calibrated_runtime = (
        development._patched_bounded_runtime
    )
    try:
        yield
    finally:
        predecessor.development._patched_calibrated_runtime = original


def _bounded_metrics(evidence: Mapping[str, Any]) -> dict[str, Any]:
    reports = [
        lane["baselines"][V15_BASELINE] for lane in evidence["lanes"]
    ]
    calibration = evidence["analysis"]["observed_force_calibration_metrics"]
    return {
        "audit_count": sum(
            int(report["bounded_state_triggered_audit_count"])
            for report in reports
        ),
        "inactive_count": sum(
            int(report["bounded_state_triggered_inactive_count"])
            for report in reports
        ),
        "state_trigger_margin_mismatch_count": sum(
            int(report["bounded_state_trigger_margin_mismatch_count"])
            for report in reports
        ),
        "unguarded_shadow_rollout_count": sum(
            int(report["bounded_unguarded_rollout_count"])
            for report in reports
        ),
        "rollout_budget_violation_count": sum(
            int(report["bounded_rollout_budget_violation_count"])
            for report in reports
        ),
        "guarded_candidate_rollout_count": sum(
            int(report["bounded_guarded_candidate_rollout_count"])
            for report in reports
        ),
        "guarded_candidate_rollout_max": max(
            int(report["bounded_guarded_candidate_rollout_max"])
            for report in reports
        ),
        "calibration_evaluation_count": int(calibration["evaluation_count"]),
        "calibration_bind_count": int(calibration["bind_count"]),
        "dynamic_motion_generator_step_count": int(
            evidence["analysis"]["dynamic_state_metrics"][
                "v15_5_dynamic_motion_generator_step_count"
            ]
        ),
        "extended_recovery_evaluated_count": int(
            evidence["analysis"]["adaptive_force_metrics"][
                "v15_11_extended_recovery_evaluated_count"
            ]
        ),
        "extended_recovery_selected_count": int(
            evidence["analysis"]["adaptive_force_metrics"][
                "v15_11_extended_recovery_selected_count"
            ]
        ),
        "force_rejected_candidate_count": int(
            evidence["analysis"]["force_constrained_metrics"][
                "v15_5_force_rejected_base_eligible_candidate_count"
            ]
        ),
    }


def _bounded_gates(
    protocol: Mapping[str, Any], metrics: Mapping[str, Any]
) -> dict[str, bool]:
    expected_steps = int(protocol["gates"]["expected_v15_11_policy_step_count"])
    expected_calibration = int(
        protocol["gates"]["expected_v15_11_calibration_evaluation_count"]
    )
    return {
        "v15_11_bounded_audit_coverage": metrics["audit_count"]
        == expected_steps,
        "v15_11_bounded_state_trigger_active": metrics["inactive_count"] == 0,
        "v15_11_bounded_state_trigger_identity": metrics[
            "state_trigger_margin_mismatch_count"
        ]
        == 0,
        "v15_11_zero_unguarded_shadow_rollout": metrics[
            "unguarded_shadow_rollout_count"
        ]
        == 0,
        "v15_11_guarded_candidate_rollout_budget": metrics[
            "rollout_budget_violation_count"
        ]
        == 0
        and metrics["guarded_candidate_rollout_max"]
        <= recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS,
        "v15_11_rolling_calibration_coverage": metrics[
            "calibration_evaluation_count"
        ]
        == expected_calibration
        == metrics["calibration_bind_count"],
        "v15_11_dynamic_motion_generator_activated": metrics[
            "dynamic_motion_generator_step_count"
        ]
        >= protocol["gates"][
            "minimum_v15_11_dynamic_motion_generator_step_count"
        ],
        "v15_11_extended_recovery_evaluated": metrics[
            "extended_recovery_evaluated_count"
        ]
        >= protocol["gates"]["minimum_extended_recovery_evaluated_count"],
        "v15_11_extended_recovery_selected": metrics[
            "extended_recovery_selected_count"
        ]
        >= protocol["gates"]["minimum_extended_recovery_selected_count"],
        "v15_5_force_rejection_activated": metrics[
            "force_rejected_candidate_count"
        ]
        >= protocol["gates"][
            "minimum_force_rejected_base_eligible_candidate_count"
        ],
    }


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
        predecessor._verify_protocol(_compatibility_protocol(protocol))
    except (
        V15BoundedStateTriggeredQualificationError,
        predecessor.V15ObservedForceCalibratedQualificationError,
    ) as exc:
        blockers.append(str(exc))
    if _git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh v15.11 model-mismatch output root already exists")
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
    evidence: Mapping[str, Any], protocol: Mapping[str, Any]
) -> dict[str, Any]:
    persisted = _replace_names(deepcopy(dict(evidence)))
    persisted["schema"] = EVIDENCE_SCHEMA
    metrics = _bounded_metrics(persisted)
    gates = _bounded_gates(protocol, metrics)
    persisted["analysis"]["bounded_state_triggered_metrics"] = metrics
    # These v15.8 compatibility gates describe mechanisms intentionally
    # superseded by v15.11.  Their replacements are registered above.
    persisted["gate_results"].pop(
        "v15_11_calibration_step_coverage", None
    )
    persisted["gate_results"].pop(
        "v15_11_proactive_trigger_identity", None
    )
    persisted["gate_results"].pop(
        "v15_5_selected_post_force_prediction_identity", None
    )
    persisted["gate_results"].pop(
        "v15_5_dynamic_motion_generator_activated", None
    )
    persisted["gate_results"].pop(
        "v15_11_extended_recovery_evaluated", None
    )
    persisted["gate_results"].pop(
        "v15_11_extended_recovery_selected", None
    )
    persisted["gate_results"].pop(
        "v15_5_force_rejection_activated", None
    )
    persisted["gate_results"].update(gates)
    passed = all(persisted["gate_results"].values())
    persisted["model_mismatch_qualification_pass"] = passed
    persisted["model_mismatch_claim_authorized"] = passed
    persisted["v15_8_qualification_nonpass_reinterpreted"] = False
    persisted["classification"] = protocol[
        "pass_classification" if passed else "nonpass_classification"
    ]
    root = _output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    evidence_path.write_text(canonical_text(persisted), encoding="utf-8")
    (root / "SHA256SUMS").write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return persisted


def execute(
    protocol: Mapping[str, Any], *, protocol_path: Path, gpu: int
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 qualification preflight failed: "
            + "; ".join(report["blockers"])
        )
    compatible = _compatibility_protocol(protocol)
    with _patched_qualification_runtime():
        evidence = predecessor.execute(
            compatible, protocol_path=protocol_path, gpu=gpu
        )
    return _persist_evidence(evidence, protocol)


def validate_results(
    protocol: Mapping[str, Any], *, protocol_path: Path
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "model_mismatch_qualification_evidence.json"
    checksums_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksums_path.is_file():
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 qualification evidence is absent"
        )
    expected_checksum = f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    if checksums_path.read_text(encoding="utf-8") != expected_checksum:
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 qualification checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence.get("protocol", {}).get("sha256")
        != file_sha256(protocol_path)
    ):
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 qualification evidence binding differs"
        )
    metrics = _bounded_metrics(evidence)
    gates = _bounded_gates(protocol, metrics)
    if evidence["analysis"]["bounded_state_triggered_metrics"] != metrics:
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 bounded metric recomputation differs"
        )
    if any(evidence["gate_results"].get(key) is not value for key, value in gates.items()):
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 bounded gate recomputation differs"
        )
    passed = all(evidence["gate_results"].values())
    if (
        evidence["model_mismatch_qualification_pass"] is not passed
        or evidence["model_mismatch_claim_authorized"] is not passed
    ):
        raise V15BoundedStateTriggeredQualificationError(
            "v15.11 qualification classification differs"
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
