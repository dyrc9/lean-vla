#!/usr/bin/env python3
"""Run/validate the frozen v12.6 simulator-integrated qualification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from scripts import run_simulator_integrated_predictive_recovery_v12_pilot as base
from scripts import saber_io
from scripts.freeze_simulator_integrated_predictive_recovery_v12_qualification import (
    OUTPUT_ROOT,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    _canonical,
    _load,
    build_protocol,
)


ROW_SCHEMA = (
    "proofalign.simulator-integrated-predictive-recovery-v12-"
    "qualification-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.simulator-integrated-predictive-recovery-v12-"
    "qualification-summary.v1"
)


class SimulatorIntegratedQualificationError(RuntimeError):
    """Raised when the formal v12.6 run must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise SimulatorIntegratedQualificationError(
            f"missing protocol: {PROTOCOL_PATH}"
        )
    retained = _load(PROTOCOL_PATH)
    expected = build_protocol()
    if (
        retained != expected
        or retained.get("schema") != PROTOCOL_SCHEMA
    ):
        raise SimulatorIntegratedQualificationError(
            "formal protocol is stale"
        )
    for group in ("source_bindings", "runtime_bindings"):
        for relative, expected_digest in retained[group].items():
            path = base.REPO_ROOT / relative
            if not path.is_file() or _sha256(path) != expected_digest:
                raise SimulatorIntegratedQualificationError(
                    f"{group} differs: {relative}"
                )
    return retained


def _gate(
    observed: float | int,
    threshold: float | int,
    *,
    comparison: str,
) -> dict[str, Any]:
    if comparison == "min":
        passed = observed >= threshold
    elif comparison == "max":
        passed = observed <= threshold
    else:
        raise ValueError(f"unexpected comparison: {comparison}")
    return {
        "observed": observed,
        "threshold": threshold,
        "comparison": comparison,
        "passed": passed,
    }


def evaluate_gates(
    protocol: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    gates = protocol["gates"]
    mapping = {
        "valid_case_count_min": ("valid_case_count", "min"),
        "nominal_allow_exact_rate_min": (
            "nominal_allow_exact_rate",
            "min",
        ),
        "synthetic_recovery_route_rate_min": (
            "synthetic_recovery_route_rate",
            "min",
        ),
        "initial_shadow_risk_agreement_rate_min": (
            "initial_shadow_risk_agreement_rate",
            "min",
        ),
        "initial_shadow_repeat_within_tolerance_rate_min": (
            "initial_shadow_repeat_within_tolerance_rate",
            "min",
        ),
        "initial_shadow_restore_identity_rate_min": (
            "initial_shadow_restore_identity_rate",
            "min",
        ),
        "recovery_candidate_coverage_rate_min": (
            "recovery_candidate_coverage_rate",
            "min",
        ),
        "recovery_shadow_restore_identity_rate_min": (
            "recovery_shadow_restore_identity_rate",
            "min",
        ),
        "receipt_identity_rate_min": (
            "receipt_identity_rate",
            "min",
        ),
        "recovery_completion_rate_min": (
            "recovery_completion_rate",
            "min",
        ),
        "recovery_terminal_safe_rate_min": (
            "recovery_terminal_safe_rate",
            "min",
        ),
        "post_recovery_policy_inference_rate_min": (
            "post_recovery_policy_inference_rate",
            "min",
        ),
        "post_recovery_shadow_risk_agreement_rate_min": (
            "post_recovery_shadow_risk_agreement_rate",
            "min",
        ),
        "post_recovery_fresh_authorization_rate_min": (
            "post_recovery_fresh_authorization_rate",
            "min",
        ),
        "post_recovery_allow_exact_count_min": (
            "post_recovery_allow_exact_count",
            "min",
        ),
        "recovery_joint_limit_crossing_count_max": (
            "recovery_joint_limit_crossing_count",
            "max",
        ),
        "old_policy_authorization_accept_count_max": (
            "old_policy_authorization_accept_count",
            "max",
        ),
        "recovery_authorization_replay_accept_count_max": (
            "recovery_authorization_replay_accept_count",
            "max",
        ),
        "substituted_post_state_authorization_accept_count_max": (
            "substituted_post_state_authorization_accept_count",
            "max",
        ),
        "contact_capacity_saturation_count_max": (
            "contact_capacity_saturation_count",
            "max",
        ),
        "mujoco_active_warning_count_max": (
            "mujoco_active_warning_count",
            "max",
        ),
        "mujoco_active_contact_capacity_warning_count_max": (
            "mujoco_active_contact_capacity_warning_count",
            "max",
        ),
        "set_init_state_wrapper_call_count_max": (
            "set_init_state_wrapper_call_count",
            "max",
        ),
        "live_policy_dispatch_count_max": (
            "live_policy_dispatch_count",
            "max",
        ),
        "outcome_read_count_max": (
            "outcome_read_count",
            "max",
        ),
        "runtime_exception_count_max": (
            "runtime_exception_count",
            "max",
        ),
        "policy_load_count_max": ("policy_load_count", "max"),
        "policy_inference_count_max": (
            "policy_inference_count",
            "max",
        ),
    }
    if set(mapping) != set(gates):
        raise SimulatorIntegratedQualificationError(
            "formal gate mapping differs from protocol"
        )
    return {
        gate_name: _gate(
            metrics[metric_name],
            gates[gate_name],
            comparison=comparison,
        )
        for gate_name, (metric_name, comparison) in mapping.items()
    }


def build_summary(
    protocol: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = dict(base._summarize(rows)["metrics"])
    metrics["post_recovery_allow_exact_count"] = metrics[
        "post_recovery_shadow_verdict_counts"
    ].get("allow_exact", 0)
    gates = evaluate_gates(protocol, metrics)
    passed = all(gate["passed"] for gate in gates.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "classification": (
            "simulator_integrated_predictive_recovery_v12_"
            + ("qualification_pass" if passed else "qualification_nonpass")
        ),
        "qualification_pass": passed,
        "valid_case_count": metrics["valid_case_count"],
        "metrics": metrics,
        "gates": gates,
        "outcomes_observed": False,
        "clean_rollout_authorized": False,
        "claim_boundary": protocol["claim_boundary"],
        "lifecycle": {
            "terminal": False,
            "overwrite_allowed": False,
            "outcome_rollout_authorized": False,
            "clean_rollout_authorized": False,
            "next_step": (
                protocol["lifecycle"]["next_step_if_pass"]
                if passed
                else protocol["lifecycle"]["next_step_if_nonpass"]
            ),
        },
    }


def _preflight(
    protocol: dict[str, Any],
    *,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    return base.fresh._preflight(
        protocol,
        output_root=OUTPUT_ROOT,
        policy_gpu=policy_gpu,
        egl_gpu=egl_gpu,
        formal=True,
    )


def _run(*, policy_gpu: int, egl_gpu: int) -> dict[str, Any]:
    protocol = _verify_protocol()
    preflight = _preflight(
        protocol, policy_gpu=policy_gpu, egl_gpu=egl_gpu
    )
    if not preflight["ready"]:
        raise SimulatorIntegratedQualificationError(
            f"formal preflight failed: {preflight['blockers']}"
        )
    device = base.fresh._configure_gpu(policy_gpu, egl_gpu)
    OUTPUT_ROOT.mkdir(parents=True)
    runtime_config = base.policy_loader.ensure_libero_runtime_config(
        OUTPUT_ROOT
    )
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    args = base.fresh._args(
        protocol,
        output_root=OUTPUT_ROOT,
        render_gpu_device_id=int(
            device["selected_egl_device_ordinal"]
        ),
    )
    manifest_path = OUTPUT_ROOT / "run_manifest.json"
    ledger_path = OUTPUT_ROOT / "qualification_ledger.jsonl"
    manifest = {
        "schema": SUMMARY_SCHEMA + ".run-manifest",
        "status": "loading_policy",
        "created_at": saber_io.utc_now(),
        "formal": True,
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": _sha256(PROTOCOL_PATH),
        "source_commit": protocol["source_commit"],
        "policy_gpu": policy_gpu,
        "egl_gpu": egl_gpu,
        "device": device,
        "preflight": preflight,
        "runtime_config": runtime_config,
        "outcomes_observed": False,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy, jax, image_tools, runner = base.policy_loader.load_policy(
            base._policy_protocol(protocol), args
        )
        import mujoco

        previous_warning_callback = mujoco.get_mju_user_warning()
        warning_audit = base.MujocoWarningAudit()
        mujoco.set_mju_user_warning(warning_audit)
        manifest["status"] = (
            "running_formal_no_outcome_simulator_recovery"
        )
        saber_io.atomic_json(manifest_path, manifest)
        rows = []
        try:
            for pair_index, pair in enumerate(
                protocol["population"]["pairs"]
            ):
                for condition_index, condition in enumerate(
                    ("nominal", "synthetic_joint_pressure")
                ):
                    row = base._run_case(
                        protocol,
                        pair,
                        condition=condition,
                        pair_index=pair_index,
                        case_index=pair_index * 2 + condition_index,
                        policy=policy,
                        jax=jax,
                        image_tools=image_tools,
                        runner=runner,
                        args=args,
                        warning_audit=warning_audit,
                        row_schema=ROW_SCHEMA,
                    )
                    rows.append(row)
                    saber_io.append_ledger(ledger_path, row)
        finally:
            mujoco.set_mju_user_warning(previous_warning_callback)
        summary = build_summary(protocol, rows)
        saber_io.atomic_json(OUTPUT_ROOT / "summary.json", summary)
        manifest["status"] = "complete"
        manifest["classification"] = summary["classification"]
        manifest["qualification_pass"] = summary["qualification_pass"]
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        base.policy_loader.write_checksums(OUTPUT_ROOT)
        return summary
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        base.policy_loader.write_checksums(OUTPUT_ROOT)
        raise


def _validate() -> dict[str, Any]:
    protocol = _verify_protocol()
    base.policy_loader.read_checksums(OUTPUT_ROOT)
    manifest = _load(OUTPUT_ROOT / "run_manifest.json")
    if (
        manifest.get("status") != "complete"
        or manifest.get("protocol_sha256") != _sha256(PROTOCOL_PATH)
    ):
        raise SimulatorIntegratedQualificationError(
            "formal manifest is incomplete or unbound"
        )
    rows = [
        json.loads(line)
        for line in (
            OUTPUT_ROOT / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    retained = _load(OUTPUT_ROOT / "summary.json")
    recomputed = build_summary(protocol, rows)
    if retained != recomputed:
        raise SimulatorIntegratedQualificationError(
            "formal summary recomputation differs"
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
        (args.preflight, args.execute, args.validate_results)
    ) != 1:
        parser.error(
            "choose one of --preflight, --execute, or --validate-results"
        )
    if args.validate_results:
        payload = _validate()
    else:
        if args.gpu is None or args.egl_gpu is None:
            parser.error(
                "--preflight/--execute require --gpu and --egl-gpu"
            )
        protocol = _verify_protocol()
        if args.preflight:
            payload = _preflight(
                protocol,
                policy_gpu=args.gpu,
                egl_gpu=args.egl_gpu,
            )
        else:
            payload = _run(
                policy_gpu=args.gpu, egl_gpu=args.egl_gpu
            )
    print(_canonical(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
