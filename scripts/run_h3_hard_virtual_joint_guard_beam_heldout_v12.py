#!/usr/bin/env python3
"""Validate the frozen hard virtual joint guard on unseen policy seeds."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from scripts import run_h3_hard_virtual_joint_guard_beam_pilot_v12 as predecessor  # noqa: E402


guard_source = predecessor.guard_source
base = predecessor.base
_canonical = predecessor._canonical
_load = predecessor._load

PREDECESSOR_ROOT = predecessor.OUTPUT_ROOT
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_hard_virtual_joint_guard_beam_heldout_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-hard-virtual-joint-guard-beam-heldout-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-hard-virtual-joint-guard-beam-heldout-v12-summary.v1"
)
HELDOUT_LANE_BASE_SEEDS = (20_509, 20_510)


class H3HardVirtualJointGuardBeamHeldoutError(RuntimeError):
    """Raised when frozen unseen-seed validation must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_hard_virtual_joint_guard_beam_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_hard_virtual_joint_guard_beam_success"
        )
        is not True
        or prior.get("completed_cycle_counts")
        != {"10509": 5, "10510": 5}
        or prior.get("minimum_advanced_state_margin_rad", 0)
        < 0.15
        or prior.get(
            "contact_aware_vertex_exact_h1_exact_action_identity_count"
        )
        != prior.get(
            "contact_aware_vertex_exact_h1_execution_count"
        )
        or prior.get(
            "maximum_prediction_execution_margin_error_rad"
        )
        != 0
        or prior.get(
            "maximum_prediction_execution_target_joint_velocity_error_rad_s"
        )
        != 0
        or prior.get("beam_configuration_count")
        != prior.get("beam_configuration_qpos_identity_count")
        or prior.get("beam_configuration_count")
        != prior.get("beam_configuration_qvel_identity_count")
        or prior.get("beam_configuration_count")
        != prior.get("beam_controller_scope_restore_count")
        or prior.get("beam_torque_bound_violation_count") != 0
        or prior.get("virtual_joint_guard_profile_identity")
        is not True
        or prior.get("virtual_joint_guard_activation_sample_count", 0)
        <= 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3HardVirtualJointGuardBeamHeldoutError(
            "known-seed pass does not authorize held-out validation"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-hard-virtual-joint-guard-beam-heldout"
    )
    config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]["method_frozen_before_heldout"] = True
    config["receding_horizon"]["lane_base_seeds"] = list(
        HELDOUT_LANE_BASE_SEEDS
    )
    config["heldout_validation"] = {
        "lane_base_seeds": list(HELDOUT_LANE_BASE_SEEDS),
        "seed_overlap_with_development": False,
        "method_or_threshold_change": False,
        "required_completed_cycles_per_lane": 5,
        "minimum_advanced_state_margin_rad": 0.15,
        "all_existing_identity_and_zero_anomaly_gates_required": True,
    }
    config["claim_boundary"] = (
        "This is frozen-method unseen-seed validation of v12.37. Only "
        "the lane base seeds change from 10509/10510 to 20509/20510; "
        "guard margins, hard solref/solimp, exact source actions, beam, "
        "floor, controller, and every success/audit gate are unchanged. "
        "A pass supports repeatable simulator virtual-brake engineering/"
        "shadow evidence only. It does not establish actuator-only "
        "authority, task utility, deployment, qualification, or physical "
        "safety."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    inherited.pop(
        "h3_hard_virtual_joint_guard_beam_success"
    )
    development_seed_one_step_success = inherited.pop(
        "one_step_receding_floor_success"
    )
    fallbacks = [
        fallback
        for lane in rows[0]["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle[
            "contact_aware_vertex_exact_h1_fallbacks"
        ]
    ]
    authorized = [
        fallback for fallback in fallbacks if fallback["authorized"]
    ]
    beam_results = [
        fallback["beam_search"] for fallback in fallbacks
    ]
    execution_samples = [
        sample
        for fallback in authorized
        for sample in fallback[
            "execution_controller_substep_torque_audit"
        ]
    ]
    completed = inherited["completed_cycle_counts"]
    expected = {
        str(seed): 5 for seed in HELDOUT_LANE_BASE_SEEDS
    }
    profile_identity = bool(
        all(
            result["virtual_joint_guard_solref"]
            == list(predecessor.GUARD_SOLREF)
            and result["virtual_joint_guard_solimp"]
            == list(predecessor.GUARD_SOLIMP)
            for result in beam_results
        )
        and all(
            fallback["execution_configuration"][
                "guarded_joint_solref"
            ]
            == list(predecessor.GUARD_SOLREF)
            and fallback["execution_configuration"][
                "guarded_joint_solimp"
            ]
            == list(predecessor.GUARD_SOLIMP)
            and fallback["execution_controller_scope_restored"]
            is True
            for fallback in authorized
        )
    )
    activation_count = sum(
        sample["guard_constraint_near_or_active"]
        for sample in execution_samples
    )
    method_success = bool(
        rows[0]["receding_horizon_success"]
        and completed == expected
        and inherited["minimum_advanced_state_margin_rad"] >= 0.15
        and authorized
        and activation_count > 0
        and profile_identity
        and all(
            fallback["exact_action_identity"] is True
            and fallback[
                "prediction_execution_margin_error_rad"
            ]
            == 0
            and fallback[
                "prediction_execution_target_joint_velocity_error_rad_s"
            ]
            == 0
            and fallback["execution_configuration"][
                "configuration_qpos_identity"
            ]
            and fallback["execution_configuration"][
                "configuration_qvel_identity"
            ]
            for fallback in authorized
        )
        and all(
            result["selected"] is not None
            and len(result["selected"]["sequence"])
            == result["horizon"]
            and result["restore_identity"]
            and result["configuration_count"]
            == result["configuration_qpos_identity_count"]
            == result["configuration_qvel_identity_count"]
            == result["controller_scope_restore_count"]
            and result["torque_bound_violation_count"] == 0
            for result in beam_results
        )
        and inherited["active_warning_count"] == 0
        and inherited["active_contact_capacity_warning_count"] == 0
        and inherited["contact_capacity_saturation_count"] == 0
        and inherited["live_policy_dispatch_count"] == 0
        and inherited["typed_recovery_env_step_count"] == 0
        and inherited["outcome_read_count"] == 0
    )
    inherited.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_hard_virtual_joint_guard_beam_heldout_v12_"
                "engineering_validation_complete"
            ),
            "development_lane_base_seeds": [10_509, 10_510],
            "development_seed_one_step_success_before_heldout_recompute": (
                development_seed_one_step_success
            ),
            "heldout_lane_base_seeds": list(
                HELDOUT_LANE_BASE_SEEDS
            ),
            "seed_overlap_with_development": False,
            "method_frozen_before_heldout": True,
            "virtual_joint_guard_profile_identity": (
                profile_identity
            ),
            "virtual_joint_guard_activation_sample_count": (
                activation_count
            ),
            "h3_hard_virtual_joint_guard_beam_heldout_success": (
                method_success
            ),
            "one_step_receding_floor_success": method_success,
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return inherited


def _validate() -> dict[str, Any]:
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    manifest = _load(OUTPUT_ROOT / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise H3HardVirtualJointGuardBeamHeldoutError(
            "held-out manifest is incomplete"
        )
    rows = [
        json.loads(line)
        for line in (
            OUTPUT_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    retained = _load(OUTPUT_ROOT / "summary.json")
    recomputed = _summarize(rows)
    if retained != recomputed:
        raise H3HardVirtualJointGuardBeamHeldoutError(
            "held-out summary recomputation differs"
        )
    return recomputed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    if sum(
        (
            args.preflight,
            args.execute,
            args.validate_results,
        )
    ) != 1:
        parser.error(
            "choose exactly one of --preflight, --execute, "
            "--validate-results"
        )
    if args.validate_results:
        print(_canonical(_validate()))
        return 0
    if args.gpu is None or args.egl_gpu is None:
        parser.error("--gpu and --egl-gpu are required")
    config = pilot_config()
    if args.preflight:
        print(
            _canonical(
                guard_source._preflight(
                    config,
                    policy_gpu=args.gpu,
                    egl_gpu=args.egl_gpu,
                    output_root=OUTPUT_ROOT,
                    clean_worktree_label=(
                        "hard virtual joint-guard held-out validation"
                    ),
                )
            )
        )
        return 0
    print(
        _canonical(
            guard_source._run(
                policy_gpu=args.gpu,
                egl_gpu=args.egl_gpu,
                config_builder=pilot_config,
                summarize=_summarize,
                output_root=OUTPUT_ROOT,
                row_schema=ROW_SCHEMA,
                summary_schema=SUMMARY_SCHEMA,
                source_version="v12.38",
                running_status=(
                    "running_no_outcome_h3_hard_virtual_joint_guard_"
                    "beam_heldout"
                ),
                virtual_joint_guard_solref=predecessor.GUARD_SOLREF,
                virtual_joint_guard_solimp=predecessor.GUARD_SOLIMP,
                lane_base_seeds=HELDOUT_LANE_BASE_SEEDS,
                error_type=H3HardVirtualJointGuardBeamHeldoutError,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
