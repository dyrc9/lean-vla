#!/usr/bin/env python3
"""Freeze the post-outcome diagnostic split for the v14 shadow control.

The registered shadow-only study remains a prediction-calibration nonpass.
This diagnostic does not change that classification.  It reports, on a
separate axis, whether the already frozen Full/Shadow comparison established
the pre-divergence and disabled-arm identities needed to interpret the
observed intervention-authority contrast.
"""

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


PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_development_protocol.json"
)
REGISTERED_TERMINAL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_terminal_summary.json"
)
SHADOW_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_predictive_virtual_brake_v14_"
    "multijoint_shadow_only_20260731_causal1"
)
SHADOW_EVIDENCE_PATH = SHADOW_ROOT / "pilot_evidence.json"
SHADOW_MANIFEST_PATH = SHADOW_ROOT / "run_manifest.json"
SHADOW_CHECKSUMS_PATH = SHADOW_ROOT / "SHA256SUMS"
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_causal_terminal_diagnostic.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_predictive_virtual_brake_v14_multijoint_"
    "shadow_only_diagnostic.py"
)
CREATED_AT = "2026-07-31T23:58:00+08:00"
SCHEMA = (
    "proofalign.predictive-virtual-brake-v14-multijoint-"
    "shadow-only-causal-terminal-diagnostic.v1"
)
REGISTERED_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "causal_development_integrity_nonpass"
)
TERMINAL_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "causal_identity_nonpass"
)
DIAGNOSTIC_COMPLETE_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "registered_calibration_nonpass_causal_identity_"
    "diagnostic_complete"
)
DIAGNOSTIC_NONPASS_CLASSIFICATION = (
    "predictive_virtual_brake_v14_multijoint_shadow_only_"
    "registered_calibration_nonpass_causal_identity_"
    "diagnostic_nonpass"
)
REGISTERED_CALIBRATION_GATE = (
    "v9_v14_prediction_execution_calibration"
)
MECHANISM_GATES = (
    "v9_shadow_only_metadata_matches",
    "v9_shadow_only_all_policy_steps_audited",
    "v9_shadow_only_l2_contract",
    "v9_shadow_only_disabled_arm_contract",
    "v9_shadow_only_zero_intervention_and_deadlock",
    "v9_shadow_restore_identity",
    "v9_exact_action_identity",
)
IDENTITY_GATES = (
    "required_bindings_match",
    "full_and_shadow_schedule_identity",
    "episode_identity_and_count",
    "full_episode_artifact_checksums",
    "shadow_episode_artifact_checksums",
    "full_trigger_support_present",
    "pre_divergence_trace_coverage",
    "pre_divergence_action_identity",
    "pre_divergence_risk_identity",
    "pre_divergence_margin_identity",
    "no_trigger_l2_deterministic_identity",
    "disabled_arm_deterministic_identity",
)


class PredictiveVirtualBrakeV14ShadowDiagnosticError(RuntimeError):
    """Raised when the frozen diagnostic inputs differ."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PredictiveVirtualBrakeV14ShadowDiagnosticError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise PredictiveVirtualBrakeV14ShadowDiagnosticError(
            f"required diagnostic input is absent: {path}"
        )


def _bool_gates(
    source: Mapping[str, Any],
    names: tuple[str, ...],
) -> dict[str, bool]:
    return {
        name: source.get(name) is True
        for name in names
    }


def build_diagnostic(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    for path in (
        PROTOCOL_PATH,
        REGISTERED_TERMINAL_PATH,
        SHADOW_EVIDENCE_PATH,
        SHADOW_MANIFEST_PATH,
        SHADOW_CHECKSUMS_PATH,
        SELF_PATH,
    ):
        _require_file(path)
    protocol = load_json_object(PROTOCOL_PATH)
    terminal = load_json_object(REGISTERED_TERMINAL_PATH)
    evidence = load_json_object(SHADOW_EVIDENCE_PATH)
    manifest = load_json_object(SHADOW_MANIFEST_PATH)
    if (
        evidence.get("classification") != REGISTERED_CLASSIFICATION
        or terminal.get("classification") != TERMINAL_CLASSIFICATION
        or manifest.get("status") != "complete"
        or len(evidence.get("episodes", ())) != 180
        or terminal.get("episode_count") != 180
        or evidence.get("protocol_id") != protocol.get("protocol_id")
    ):
        raise PredictiveVirtualBrakeV14ShadowDiagnosticError(
            "registered nonpass inputs differ from the completed run"
        )
    failed_registered_gates = sorted(
        name
        for name, passed in evidence["gate_results"].items()
        if passed is not True
    )
    if failed_registered_gates != [REGISTERED_CALIBRATION_GATE]:
        raise PredictiveVirtualBrakeV14ShadowDiagnosticError(
            "registered failure is not calibration-only"
        )
    mechanism_gates = _bool_gates(
        evidence["gate_results"],
        MECHANISM_GATES,
    )
    identity_gates = _bool_gates(
        terminal["gate_results"],
        IDENTITY_GATES,
    )
    mechanism_complete = all(mechanism_gates.values())
    identity_complete = all(identity_gates.values())
    identity = terminal["identity"]
    exact_identity = bool(
        identity_complete
        and identity[
            "pre_divergence_action_digest_mismatch_count"
        ]
        == 0
        and identity[
            "pre_divergence_risk_identity_mismatch_count"
        ]
        == 0
        and identity["maximum_pre_divergence_margin_error_rad"]
        == 0.0
        and identity["disabled_action_digest_mismatch_count"] == 0
        and identity["disabled_outcome_mismatch_count"] == 0
        and identity["maximum_disabled_margin_error_rad"] == 0.0
    )
    exposure = terminal["l2_safety_exposure"]
    safety_signal = bool(
        exact_identity
        and exposure["full_actual_crossing_count"] == 0
        and exposure["shadow_actual_crossing_count"] > 0
        and exposure["full_actual_below_floor_count"] == 0
        and exposure["shadow_actual_below_floor_count"] > 0
    )
    by_arm = terminal["by_arm"]
    full_success = sum(
        int(by_arm[arm]["full_task_success_count"])
        for arm in ("execution_only", "dual")
    )
    shadow_success = sum(
        int(by_arm[arm]["shadow_task_success_count"])
        for arm in ("execution_only", "dual")
    )
    full_unknown = sum(
        int(by_arm[arm]["full_unknown_or_deadlock_count"])
        for arm in ("execution_only", "dual")
    )
    shadow_unknown = sum(
        int(by_arm[arm]["shadow_unknown_or_deadlock_count"])
        for arm in ("execution_only", "dual")
    )
    maximum_error = float(
        evidence["aggregate"][
            "v14_maximum_prediction_execution_side_error_rad"
        ]
    )
    tolerance = float(
        protocol["v14_gates"][
            "maximum_prediction_execution_side_error_rad"
        ]
    )
    diagnostic_complete = bool(
        mechanism_complete
        and exact_identity
        and safety_signal
    )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    return {
        "schema": SCHEMA,
        "created_at": created_at,
        "classification": (
            DIAGNOSTIC_COMPLETE_CLASSIFICATION
            if diagnostic_complete
            else DIAGNOSTIC_NONPASS_CLASSIFICATION
        ),
        "registered_result": {
            "classification": REGISTERED_CLASSIFICATION,
            "passed": False,
            "failed_gates": failed_registered_gates,
            "prediction_execution_tolerance_rad": tolerance,
            "maximum_prediction_execution_side_error_rad": (
                maximum_error
            ),
            "maximum_to_tolerance_ratio": (
                maximum_error / tolerance
            ),
            "classification_revised": False,
        },
        "diagnostic_axes": {
            "mechanism_contract_complete": mechanism_complete,
            "causal_identity_diagnostic_complete": exact_identity,
            "descriptive_causal_safety_signal_observed": safety_signal,
            "confirmatory_claim_authorized": False,
        },
        "mechanism_gate_results": mechanism_gates,
        "identity_gate_results": identity_gates,
        "identity": identity,
        "l2_safety_exposure": exposure,
        "l2_task_availability_tradeoff": {
            "full_task_success_count": full_success,
            "shadow_task_success_count": shadow_success,
            "full_minus_shadow_task_success_count": (
                full_success - shadow_success
            ),
            "full_unknown_or_deadlock_count": full_unknown,
            "shadow_unknown_or_deadlock_count": shadow_unknown,
            "full_minus_shadow_unknown_or_deadlock_count": (
                full_unknown - shadow_unknown
            ),
            "l2_episode_count": 90,
        },
        "by_arm": by_arm,
        "causal_estimates": terminal["causal_estimates"],
        "bindings": {
            "protocol": {
                "path": PROTOCOL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(PROTOCOL_PATH),
            },
            "registered_terminal": {
                "path": REGISTERED_TERMINAL_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(REGISTERED_TERMINAL_PATH),
            },
            "shadow_evidence": {
                "path": SHADOW_EVIDENCE_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(SHADOW_EVIDENCE_PATH),
            },
            "shadow_manifest": {
                "path": SHADOW_MANIFEST_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(SHADOW_MANIFEST_PATH),
            },
            "shadow_checksums": {
                "path": SHADOW_CHECKSUMS_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(SHADOW_CHECKSUMS_PATH),
            },
        },
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
            "freezer_sha256": file_sha256(SELF_PATH),
        },
        "interpretation": (
            "The registered shadow-only study remains a calibration "
            "nonpass and is not reclassified. Separately, the frozen "
            "diagnostic shows exact Full/Shadow identity before the first "
            "Full trigger and exact disabled-arm replay, so the observed "
            "development contrast is consistent with the causal effect of "
            "granting virtual-brake intervention authority on this fixed "
            "schedule. The contrast is descriptive and outcome-disclosed; "
            "it must be tested on a new outcome-blind population."
        ),
        "claim_boundary": (
            "This post-outcome diagnostic cannot revise the registered "
            "0.002 rad calibration gate, authorize confirmation, or support "
            "deployment, actuator-authority, hardware, or physical-safety "
            "claims."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    diagnostic = build_diagnostic(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        ),
        source_commit=(
            str(retained["source"]["repository_commit"])
            if retained is not None
            else None
        ),
    )
    text = canonical_text(diagnostic)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise PredictiveVirtualBrakeV14ShadowDiagnosticError(
                f"shadow-only diagnostic is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
