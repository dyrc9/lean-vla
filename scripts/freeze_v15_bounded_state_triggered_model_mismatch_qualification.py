#!/usr/bin/env python3
"""Freeze fresh held-out v15.11 bounded model-mismatch qualification."""

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
    freeze_v15_observed_force_calibrated_model_mismatch_qualification as base,
)
from scripts import (  # noqa: E402
    run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery as recovery,
)
from scripts import (  # noqa: E402
    run_v15_bounded_state_triggered_model_mismatch_qualification as runner,
)


OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = REPO_ROOT / "scripts" / Path(__file__).name
OLD_QUALIFICATION_PROTOCOL = base.OUTPUT_PATH
ABORTED_FRESH1_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_protocol.json"
)
ABORTED_FRESH1_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_fresh1_pre_execution_abort_summary.json"
)
FRESH2_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_protocol_fresh2.json"
)
FRESH2_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_fresh2_terminal_summary.json"
)
FRESH3_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_protocol_fresh3.json"
)
FRESH3_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_qualification_fresh3_terminal_summary.json"
)
OLD_QUALIFICATION_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_observed_force_calibrated_"
    "model_mismatch_qualification_terminal_summary.json"
)
DEVELOPMENT_TERMINAL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_11_bounded_state_triggered_"
    "model_mismatch_development_terminal_summary.json"
)
PRIOR_POPULATION_PROTOCOLS = (
    *base.PRIOR_POPULATION_PROTOCOLS,
    OLD_QUALIFICATION_PROTOCOL,
    ABORTED_FRESH1_PROTOCOL,
    FRESH2_PROTOCOL,
    FRESH3_PROTOCOL,
)
SOURCE_PATHS = (
    *base.SOURCE_PATHS,
    "scripts/run_l2_predictive_virtual_brake_v15_pre_step_calibrated_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_rolling_prebound_recovery.py",
    "scripts/run_l2_predictive_virtual_brake_v15_bounded_state_triggered_recovery.py",
    "scripts/run_v15_bounded_state_triggered_model_mismatch_development.py",
    "scripts/run_v15_bounded_state_triggered_model_mismatch_qualification.py",
    "scripts/freeze_v15_bounded_state_triggered_model_mismatch_qualification.py",
    "tests/test_v15_bounded_state_triggered_recovery.py",
    "tests/test_v15_bounded_state_triggered_model_mismatch_qualification.py",
    "tests/test_freeze_v15_bounded_state_triggered_model_mismatch_qualification.py",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-11-bounded-state-triggered-"
    "model-mismatch-qualification-20260806-fresh4"
)
CREATED_AT = "2026-08-06T03:15:00+08:00"
SELECTION_SALT = (
    "proofalign-v15-11-fresh-bounded-state-triggered-model-mismatch-"
    "qualification-v4"
)


class V15BoundedStateTriggeredFreezeError(RuntimeError):
    """Raised when the v15.11 qualification cannot be frozen."""


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15BoundedStateTriggeredFreezeError(
            f"v15.11 qualification binding is absent: {path}"
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
        "fresh_globally_held_out_v15_11_bounded_state_triggered_"
        "model_mismatch_qualification"
    )
    protocol["pass_classification"] = (
        "predictive_virtual_brake_v15_11_bounded_state_triggered_"
        "model_mismatch_qualification_pass"
    )
    protocol["nonpass_classification"] = (
        "predictive_virtual_brake_v15_11_bounded_state_triggered_"
        "model_mismatch_qualification_nonpass"
    )
    protocol["fresh_output_root"] = (
        "results/proofalign_predictive_virtual_brake_v15_11_bounded_state_"
        "triggered_model_mismatch_qualification_20260806_fresh4"
    )
    for environment in protocol["environments"]:
        environment["environment_id"] = str(
            environment["environment_id"]
        ).replace("v15_8", "v15_11")
    protocol["required_bindings"].extend(
        [
            _binding(OLD_QUALIFICATION_TERMINAL),
            _binding(DEVELOPMENT_TERMINAL),
            _binding(ABORTED_FRESH1_TERMINAL),
            _binding(FRESH2_TERMINAL),
            _binding(FRESH3_TERMINAL),
        ]
    )
    protocol["selection"].update(
        {
            "v15_8_qualification_results_observed_before_freeze": True,
            "v15_11_outcome_disclosed_development_results_observed_before_freeze": True,
            "v15_11_qualification_results_observed_before_freeze": False,
        }
    )
    protocol["design"].update(
        {
            "baselines": list(runner.BASELINES),
            "bounded_state_triggered_recovery": True,
            "state_trigger_margin_rad": recovery.STATE_TRIGGER_MARGIN_RAD,
            "state_target_offset_rad": recovery.STATE_TARGET_OFFSET_RAD,
            "maximum_guarded_candidate_rollouts_per_action": (
                recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS
            ),
            "unguarded_shadow_rollout_active": False,
            "rolling_prebound_observed_force_calibration": True,
            "source_action_changed": False,
            "task_outcome_read": False,
            "registered_force_thresholds_unchanged": True,
            "guard_candidates_order_thresholds_actions_unchanged": False,
            "proactive_trigger_and_force_thresholds_unchanged_from_v15_6": False,
            "proactive_trigger_margin_rad": recovery.STATE_TRIGGER_MARGIN_RAD,
            "conditional_extended_recovery_activation_required": False,
            "force_rejection_activation_required": False,
        }
    )
    protocol["gates"].update(
        {
            "expected_v15_11_policy_step_count": 26460,
            "expected_v15_11_calibration_evaluation_count": 31752,
            "maximum_guarded_candidate_rollouts_per_action": (
                recovery.MAX_GUARDED_CANDIDATE_ROLLOUTS
            ),
            "unguarded_shadow_rollout_count_max": 0,
            "minimum_v15_11_dynamic_motion_generator_step_count": 1,
            "minimum_extended_recovery_evaluated_count": 0,
            "minimum_extended_recovery_selected_count": 0,
            "minimum_force_rejected_base_eligible_candidate_count": 0,
        }
    )
    protocol["source"]["freezer"] = SELF_PATH.relative_to(
        REPO_ROOT
    ).as_posix()
    protocol["source"]["freezer_sha256"] = file_sha256(SELF_PATH)
    protocol["claim_boundary"] = (
        "This preregistered qualification evaluates the frozen v15.11 "
        "bounded state-triggered recovery on 18 new globally held-out "
        "suite/task/init pairs excluding all earlier populations, across "
        "seven registered bounded simulator model conditions. It preserves "
        "the source action and registered safety and force thresholds, uses "
        "no unguarded shadow rollout, and permits at most two guarded "
        "candidate rollouts per action. A pass supports only empirical "
        "robustness to this registered simulator qualification; it does not "
        "support attacked-task utility, hard-real-time, hardware, actuator-"
        "authority, arbitrary model error, or physical-safety claims."
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
        raise V15BoundedStateTriggeredFreezeError(
            "v15.11 model-mismatch qualification protocol already exists"
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
