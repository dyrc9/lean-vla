#!/usr/bin/env python3
"""Mechanically replay the virtual joint guard with corrected torque audit."""

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


from scripts import run_h3_virtual_joint_guard_beam_pilot_v12 as predecessor  # noqa: E402


base = predecessor.base
_canonical = predecessor._canonical
_load = predecessor._load

PREDECESSOR_ROOT = predecessor.OUTPUT_ROOT
OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_h3_virtual_joint_guard_beam_replayfix_v12_"
    "20260730"
)
ROW_SCHEMA = (
    "proofalign.h3-virtual-joint-guard-beam-replayfix-v12-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.h3-virtual-joint-guard-beam-replayfix-v12-summary.v1"
)


class H3VirtualJointGuardBeamReplayfixError(RuntimeError):
    """Raised when the corrected-audit mechanical replay must fail."""


def pilot_config() -> dict[str, Any]:
    base.policy_loader.read_checksums(PREDECESSOR_ROOT)
    prior = _load(PREDECESSOR_ROOT / "summary.json")
    if (
        prior.get("classification")
        != (
            "h3_virtual_joint_guard_beam_v12_"
            "engineering_pilot_complete"
        )
        or prior.get("h3_virtual_joint_guard_beam_success")
        is not False
        or prior.get("completed_cycle_counts")
        != {"10509": 1, "10510": 1}
        or prior.get("beam_configuration_count") != 8
        or prior.get("beam_configuration_qpos_identity_count") != 8
        or prior.get("beam_configuration_qvel_identity_count") != 8
        or prior.get("beam_controller_scope_restore_count") != 8
        or prior.get("beam_torque_bound_violation_count") != 200
        or prior.get("virtual_joint_guard_authorization_count") != 0
        or prior.get("active_warning_count") != 0
        or prior.get("active_contact_capacity_warning_count") != 0
        or prior.get("contact_capacity_saturation_count") != 0
        or prior.get("outcome_read_count") != 0
        or prior.get("live_policy_dispatch_count") != 0
        or prior.get("typed_recovery_env_step_count") != 0
    ):
        raise H3VirtualJointGuardBeamReplayfixError(
            "guard audit nonpass does not authorize mechanical replay"
        )
    config = deepcopy(predecessor.pilot_config())
    config["protocol_id"] = (
        "engineering-h3-virtual-joint-guard-beam-replayfix"
    )
    contract = config[
        "controller_contact_aware_vertex_exact_h1_contract"
    ]
    contract["torque_audit_replayfix"] = {
        "controller_output_semantics": (
            "OSC raw torque before SingleArm.control clipping"
        ),
        "actual_dispatch_semantics": (
            "SingleArm.control np.clip(raw, torque_limits) before ctrl"
        ),
        "record_raw_controller_torque": True,
        "record_downstream_clipped_torque": True,
        "bound_gate_target": "downstream_clipped_torque",
        "return_raw_to_original_robot_path": True,
        "effect_parameters_changed": False,
    }
    contract["beam_count_replayfix"] = (
        "Freeze parent count before expansion and retention."
    )
    config["receding_horizon"]["audit_replayfix"] = (
        "No guard, action, seed, floor, beam, controller, or success-gate "
        "change; correct only pre/post robot-layer torque semantics and "
        "depth count timing."
    )
    config["claim_boundary"] = (
        "This is a mechanical replay of v12.35 with identical guard "
        "margins, actions, seeds, simulator method, and gates. The only "
        "change is to distinguish raw OSC output from the torque that "
        "SingleArm.control clips before sim.data.ctrl, plus freezing "
        "parent counts before retention. It may report the guard effect "
        "that v12.35 never reached, but remains simulator virtual-stop "
        "engineering/shadow evidence and is not actuator-only, task "
        "utility, deployment, qualification, or physical-safety evidence."
    )
    return config


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    inherited = predecessor._summarize(rows)
    guard_success = inherited.pop(
        "h3_virtual_joint_guard_beam_success"
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
    execution_samples = [
        sample
        for fallback in authorized
        for sample in fallback[
            "execution_controller_substep_torque_audit"
        ]
    ]
    clipping_required_count = sum(
        sample["downstream_clipping_required"]
        for sample in execution_samples
    )
    clipped_bound_violation_count = sum(
        sample["torque_bound_violation"]
        for sample in execution_samples
    )
    method_success = bool(
        guard_success
        and execution_samples
        and clipping_required_count > 0
        and clipped_bound_violation_count == 0
    )
    inherited.update(
        {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "h3_virtual_joint_guard_beam_replayfix_v12_"
                "engineering_pilot_complete"
            ),
            "h3_virtual_joint_guard_beam_replayfix_success": (
                method_success
            ),
            "raw_controller_sample_count": len(execution_samples),
            "downstream_clipping_required_sample_count": (
                clipping_required_count
            ),
            "downstream_clipped_bound_violation_count": (
                clipped_bound_violation_count
            ),
            "beam_parent_counts": [
                depth["parent_count"]
                for fallback in [
                    fallback
                    for lane in rows[0]["lane_results"]
                    for cycle in lane["cycles"]
                    for fallback in cycle[
                        "contact_aware_vertex_exact_h1_fallbacks"
                    ]
                ]
                for depth in fallback["beam_search"][
                    "depth_summaries"
                ]
            ],
            "claim_boundary": pilot_config()["claim_boundary"],
        }
    )
    return inherited


def _validate() -> dict[str, Any]:
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    manifest = _load(OUTPUT_ROOT / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise H3VirtualJointGuardBeamReplayfixError(
            "replay manifest is incomplete"
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
        raise H3VirtualJointGuardBeamReplayfixError(
            "replay summary recomputation differs"
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
                predecessor._preflight(
                    config,
                    policy_gpu=args.gpu,
                    egl_gpu=args.egl_gpu,
                    output_root=OUTPUT_ROOT,
                    clean_worktree_label=(
                        "virtual joint-guard replayfix"
                    ),
                )
            )
        )
        return 0
    print(
        _canonical(
            predecessor._run(
                policy_gpu=args.gpu,
                egl_gpu=args.egl_gpu,
                config_builder=pilot_config,
                summarize=_summarize,
                output_root=OUTPUT_ROOT,
                row_schema=ROW_SCHEMA,
                summary_schema=SUMMARY_SCHEMA,
                source_version="v12.36",
                running_status=(
                    "running_no_outcome_h3_virtual_joint_guard_"
                    "beam_replayfix"
                ),
                error_type=(
                    H3VirtualJointGuardBeamReplayfixError
                ),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
