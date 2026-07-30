#!/usr/bin/env python3
"""Evaluate a hard scoped simulator virtual joint-stop beam."""

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


from scripts import run_h3_virtual_joint_guard_beam_replayfix_v12 as predecessor  # noqa: E402


guard_source = predecessor.predecessor
base = predecessor.base
_canonical = predecessor._canonical
_load = predecessor._load

PREDECESSOR_ROOT = predecessor.OUTPUT_ROOT
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_hard_virtual_joint_guard_beam_pilot_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-hard-virtual-joint-guard-beam-pilot-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-hard-virtual-joint-guard-beam-pilot-v12-summary.v1"
)
GUARD_SOLREF = (0.004, 1.0)
GUARD_SOLIMP = (0.999, 0.9999, 0.001, 0.5, 2.0)


class H3HardVirtualJointGuardBeamPilotError(RuntimeError):
    """Raised when the hard virtual joint-stop must fail closed."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    velocities = prior.get(
        "best_velocity_terminal_toward_velocities_rad_s"
    )
    if (
        prior.get("classification")
        != (
            "h3_virtual_joint_guard_beam_replayfix_v12_"
            "engineering_pilot_complete"
        )
        or prior.get(
            "h3_virtual_joint_guard_beam_replayfix_success"
        )
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("beam_configuration_count") != 56
        or prior.get("beam_configuration_qpos_identity_count") != 56
        or prior.get("beam_configuration_qvel_identity_count") != 56
        or prior.get("beam_controller_scope_restore_count") != 56
        or prior.get("beam_torque_bound_violation_count") != 0
        or prior.get("beam_parent_counts")
        != [1, 4, 16, 1, 4, 16]
        or not isinstance(velocities, list)
        or velocities[1] < 2.52
        or velocities[4] < 2.52
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3HardVirtualJointGuardBeamPilotError(
            "soft-guard nonpass does not authorize hard guard"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-hard-virtual-joint-guard-beam-pilot"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["virtual_joint_guard_solref"] = list(GUARD_SOLREF)
    contract["virtual_joint_guard_solimp"] = list(GUARD_SOLIMP)
    contract["virtual_joint_guard_profile_rule"] = (
        "Only while the scoped guard range is active, set the target "
        "joint limit solref to [0.004, 1.0] and solimp to "
        "[0.999, 0.9999, 0.001, 0.5, 2.0]. The time constant is twice "
        "the frozen 0.002-second physics timestep. Restore the original "
        "range, solref, and solimp exactly before leaving each branch."
    )
    contract["effect_parameters_changed"] = (
        "Only the virtual-stop constraint profile; margins, actions, "
        "seeds, floor, beam, and success gates are unchanged."
    )
    config["receding_horizon"].update(
        {
            "contact_aware_vertex_beam_virtual_joint_guard_solref": list(
                GUARD_SOLREF
            ),
            "contact_aware_vertex_beam_virtual_joint_guard_solimp": list(
                GUARD_SOLIMP
            ),
        }
    )
    config["claim_boundary"] = (
        "This result-informed pilot compares a harder simulator virtual "
        "joint stop against the v12.36 default-soft stop. It changes only "
        "the scoped target-joint limit solref/solimp and restores both "
        "exactly with the original range. Guard margins, exact source "
        "action bytes, seeds, floor, beam, controller, and gates are "
        "unchanged. Even a pass is simulator virtual-brake engineering/"
        "shadow evidence, not actuator-only authority, task utility, "
        "deployment, qualification, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    replay_success = inherited.pop(
        "h3_virtual_joint_guard_beam_replayfix_success"
    )
    authorized = [
        fallback
        for lane in rows[0]["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle[
            "contact_aware_vertex_exact_h1_fallbacks"
        ]
        if fallback["authorized"]
    ]
    beam_results = [
        fallback["beam_search"]
        for lane in rows[0]["lane_results"]
        for cycle in lane["cycles"]
        for fallback in cycle[
            "contact_aware_vertex_exact_h1_fallbacks"
        ]
    ]
    profile_identity = bool(
        all(
            result["virtual_joint_guard_solref"]
            == list(GUARD_SOLREF)
            and result["virtual_joint_guard_solimp"]
            == list(GUARD_SOLIMP)
            for result in beam_results
        )
        and all(
            fallback["execution_configuration"][
                "guarded_joint_solref"
            ]
            == list(GUARD_SOLREF)
            and fallback["execution_configuration"][
                "guarded_joint_solimp"
            ]
            == list(GUARD_SOLIMP)
            and fallback["execution_controller_scope_restored"]
            is True
            for fallback in authorized
        )
    )
    method_success = bool(
        replay_success and authorized and profile_identity
    )
    inherited.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_hard_virtual_joint_guard_beam_v12_"
                "engineering_pilot_complete"
            ),
            "virtual_joint_guard_solref": list(GUARD_SOLREF),
            "virtual_joint_guard_solimp": list(GUARD_SOLIMP),
            "virtual_joint_guard_profile_identity": (
                profile_identity
            ),
            "h3_hard_virtual_joint_guard_beam_success": (
                method_success
            ),
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return inherited


def _validate() -> dict[str, Any]:
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    manifest = _load(OUTPUT_ROOT / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise H3HardVirtualJointGuardBeamPilotError(
            "hard-guard manifest is incomplete"
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
        raise H3HardVirtualJointGuardBeamPilotError(
            "hard-guard summary recomputation differs"
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
                        "hard virtual joint-guard pilot"
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
                source_version="v12.37",
                running_status=(
                    "running_no_outcome_h3_hard_virtual_joint_guard_beam"
                ),
                virtual_joint_guard_solref=GUARD_SOLREF,
                virtual_joint_guard_solimp=GUARD_SOLIMP,
                error_type=H3HardVirtualJointGuardBeamPilotError,
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
