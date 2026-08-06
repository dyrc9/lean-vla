#!/usr/bin/env python3
"""Freeze fresh held-out v15.8 model-mismatch qualification."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import (  # noqa: E402
    freeze_v15_incremental_adaptive_force_model_mismatch_qualification as base,
)
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_observed_force_calibrated_model_mismatch_qualification as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_observed_force_calibrated_model_mismatch_qualification.py"
)
OLD_MISMATCH_PROTOCOL = base.OUTPUT_PATH
OLD_MISMATCH_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_incremental_adaptive_force_"
    "model_mismatch_qualification_terminal_summary.json"
)
DEVELOPMENT_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_observed_force_calibrated_"
    "model_mismatch_development_terminal_summary.json"
)
PRIOR_POPULATION_PROTOCOLS = (*base.PRIOR_POPULATION_PROTOCOLS, OLD_MISMATCH_PROTOCOL)
SOURCE_PATHS = (
    *base.SOURCE_PATHS,
    "scripts/run_l2_predictive_virtual_brake_v15_observed_force_calibrated_recovery.py",
    "scripts/run_v15_observed_force_calibrated_model_mismatch_development.py",
    "scripts/run_v15_observed_force_calibrated_model_mismatch_qualification.py",
    "scripts/freeze_v15_observed_force_calibrated_model_mismatch_qualification.py",
    "tests/test_v15_observed_force_calibrated_recovery.py",
    "tests/test_v15_observed_force_calibrated_model_mismatch_qualification.py",
    "tests/test_freeze_v15_observed_force_calibrated_model_mismatch_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-8-observed-force-calibrated-"
    "model-mismatch-qualification-20260805"
)
CREATED_AT = "2026-08-05T16:30:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-8-fresh-observed-force-model-mismatch-qualification-v1"
)


class V15ObservedForceCalibratedFreezeError(RuntimeError):
    """Raised when the v15.8 qualification cannot be frozen."""


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15ObservedForceCalibratedFreezeError(
            f"v15.8 qualification binding is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def build_protocol(
    *, created_at: str = CREATED_AT, source_commit: str | None = None
) -> dict[str, Any]:
    replacements = {
        "SELF_PATH": SELF_PATH,
        "PRIOR_POPULATION_PROTOCOLS": PRIOR_POPULATION_PROTOCOLS,
        "SOURCE_PATHS": SOURCE_PATHS,
        "PROTOCOL_ID": PROTOCOL_ID,
        "CREATED_AT": CREATED_AT,
        "SELECTION_SALT": SELECTION_SALT,
    }
    originals = {name: getattr(base, name) for name in replacements}
    for name, value in replacements.items():
        setattr(base, name, value)
    try:
        protocol = base.build_protocol(
            created_at=created_at, source_commit=source_commit
        )
    finally:
        for name, value in originals.items():
            setattr(base, name, value)

    protocol["schema"] = runner.PROTOCOL_SCHEMA
    protocol["status"] = runner.AUTHORIZED_STATUS
    protocol["protocol_id"] = PROTOCOL_ID
    protocol["stage"] = (
        "fresh_globally_held_out_v15_8_observed_force_calibrated_"
        "model_mismatch_qualification"
    )
    protocol["pass_classification"] = (
        "predictive_virtual_brake_v15_8_observed_force_calibrated_"
        "model_mismatch_qualification_pass"
    )
    protocol["nonpass_classification"] = (
        "predictive_virtual_brake_v15_8_observed_force_calibrated_"
        "model_mismatch_qualification_nonpass"
    )
    protocol["fresh_output_root"] = (
        "results/proofalign_predictive_virtual_brake_v15_8_observed_force_"
        "calibrated_model_mismatch_qualification_20260805_fresh1"
    )
    for environment in protocol["environments"]:
        environment["environment_id"] = str(
            environment["environment_id"]
        ).replace("v15_7", "v15_8")
    protocol["required_bindings"].extend(
        [_binding(OLD_MISMATCH_TERMINAL), _binding(DEVELOPMENT_TERMINAL)]
    )
    protocol["selection"].pop(
        "model_mismatch_results_observed_before_freeze", None
    )
    protocol["selection"].update(
        {
            "v15_7_model_mismatch_results_observed_before_freeze": True,
            "v15_8_outcome_disclosed_development_results_observed_before_freeze": True,
            "v15_8_qualification_results_observed_before_freeze": False,
        }
    )
    protocol["design"].update(
        {
            "baselines": list(runner.BASELINES),
            "mechanism_parameters_unchanged_from_v15_7": False,
            "observed_force_shadow_calibration": True,
            "observed_force_shadow_calibration_interface": (
                recovery.CALIBRATION_INTERFACE
            ),
            "observed_force_shadow_model_bank": [
                dict(row) for row in recovery.MODEL_BANK
            ],
            "observed_force_selector_reads_actual_parameters": False,
            "observed_force_selector_reads_task_outcomes": False,
            "registered_force_thresholds_unchanged": True,
        }
    )
    protocol["gates"].update(
        {
            "expected_v15_8_policy_step_count": 26460,
            "calibration_nonminimum_bind_count_max": 0,
            "calibration_selected_residual_exceeds_nominal_count_max": 0,
        }
    )
    protocol["source"]["freezer"] = SELF_PATH.relative_to(REPO_ROOT).as_posix()
    protocol["source"]["freezer_sha256"] = file_sha256(SELF_PATH)
    protocol["claim_boundary"] = (
        "This preregistered qualification evaluates the frozen v15.8 "
        "observed-force shadow-calibration mechanism on 18 new globally "
        "held-out suite/task/init pairs that exclude every v15.7 model-"
        "mismatch qualification pair. Before each predictive rollout, the "
        "selector receives only pre-step constraint-force residuals for a "
        "fixed seven-model bank and binds the minimum-residual shadow; it "
        "does not receive actual parameter values or task outcomes. Actual "
        "containment, liveness, prediction-error, force, and latency gates "
        "remain unchanged, and calibration latency is included. A pass "
        "supports only empirical robustness to the registered bounded "
        "simulator mismatches; it does not support attacked-task utility, "
        "hard-real-time, hardware, actuator-authority, arbitrary model error, "
        "or physical-safety claims."
    )
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--source-commit")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise V15ObservedForceCalibratedFreezeError(
            "v15.8 model-mismatch qualification protocol already exists"
        )
    protocol = build_protocol(
        created_at=args.created_at, source_commit=args.source_commit
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_text(protocol), encoding="utf-8")
    print(
        canonical_text(
            {
                "protocol_path": output.relative_to(REPO_ROOT).as_posix(),
                "protocol_sha256": file_sha256(output),
                "protocol_id": protocol["protocol_id"],
                "environment_count": len(protocol["environments"]),
                "prior_exact_pair_count": protocol["selection"][
                    "prior_exact_pair_count"
                ],
            }
        ),
        end="",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
