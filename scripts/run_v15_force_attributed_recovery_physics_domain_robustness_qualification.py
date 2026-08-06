#!/usr/bin/env python3
"""Qualify v15.3 recovery across frozen simulator-physics domains."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Iterator, Mapping

import numpy as np


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
    run_v15_force_attributed_recovery_stress_qualification as base,
)


PROTOCOL_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-physics-domain-robustness-qualification-protocol.v1"
)
EVIDENCE_SCHEMA = (
    "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
    "recovery-physics-domain-robustness-qualification-evidence.v1"
)
AUTHORIZED_STATUS = (
    "authorized_v15_3_force_attributed_recovery_"
    "physics_domain_robustness_qualification"
)
DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_force_attributed_"
    "recovery_physics_domain_robustness_qualification_protocol.json"
)
V15_BASELINE = base.V15_BASELINE
BASELINES = (
    "no_guard",
    "reactive_stop",
    "v14_predictive_brake",
    V15_BASELINE,
)
PHYSICS_CONDITIONS = (
    {
        "condition_id": "nominal",
        "arm_mass_scale": 1.0,
        "joint_damping_scale": 1.0,
        "arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "arm_mass_0_8x",
        "arm_mass_scale": 0.8,
        "joint_damping_scale": 1.0,
        "arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "arm_mass_1_2x",
        "arm_mass_scale": 1.2,
        "joint_damping_scale": 1.0,
        "arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "joint_damping_0_7x",
        "arm_mass_scale": 1.0,
        "joint_damping_scale": 0.7,
        "arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "joint_damping_1_3x",
        "arm_mass_scale": 1.0,
        "joint_damping_scale": 1.3,
        "arm_sliding_friction_scale": 1.0,
    },
    {
        "condition_id": "arm_friction_0_7x",
        "arm_mass_scale": 1.0,
        "joint_damping_scale": 1.0,
        "arm_sliding_friction_scale": 0.7,
    },
    {
        "condition_id": "arm_friction_1_3x",
        "arm_mass_scale": 1.0,
        "joint_damping_scale": 1.0,
        "arm_sliding_friction_scale": 1.3,
    },
)


class V15PhysicsDomainRobustnessError(RuntimeError):
    """Raised when physics-domain qualification differs."""


def _output_root(protocol: Mapping[str, Any]) -> Path:
    root = (REPO_ROOT / str(protocol["fresh_output_root"])).resolve()
    try:
        root.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise V15PhysicsDomainRobustnessError(
            "physics-domain output root escapes repository"
        ) from exc
    if root == REPO_ROOT.resolve():
        raise V15PhysicsDomainRobustnessError(
            "physics-domain output root resolves to repository"
        )
    return root


def _verify_protocol(protocol: Mapping[str, Any]) -> None:
    expected_authorization = {
        "simulator_action_dispatch": True,
        "policy_load": False,
        "task_outcome_read": False,
        "attacked_rollout": False,
        "physics_domain_robustness_claim": True,
        "model_mismatch_claim": False,
        "task_utility_claim": False,
        "real_time_claim": False,
    }
    if (
        protocol.get("schema") != PROTOCOL_SCHEMA
        or protocol.get("status") != AUTHORIZED_STATUS
        or protocol.get("execution_authorization")
        != expected_authorization
        or len(protocol.get("environments", ())) != 18
        or protocol["design"]["physics_conditions"]
        != [dict(row) for row in PHYSICS_CONDITIONS]
        or protocol["design"]["baselines"] != list(BASELINES)
        or protocol["design"]["doses"]
        != [dict(row) for row in base.calibration.v14.pilot.DOSES]
    ):
        raise V15PhysicsDomainRobustnessError(
            "unsupported or unauthorized physics-domain protocol"
        )
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / str(relative)
        if not path.is_file() or file_sha256(path) != expected:
            raise V15PhysicsDomainRobustnessError(
                f"physics-domain source differs: {relative}"
            )
    for binding in protocol["required_bindings"]:
        path = REPO_ROOT / str(binding["path"])
        if not path.is_file() or file_sha256(path) != binding["sha256"]:
            raise V15PhysicsDomainRobustnessError(
                f"physics-domain binding differs: {path}"
            )


def preflight(protocol: Mapping[str, Any], *, gpu: int) -> dict[str, Any]:
    blockers = []
    try:
        _verify_protocol(protocol)
    except V15PhysicsDomainRobustnessError as exc:
        blockers.append(str(exc))
    if base.calibration._git_status():
        blockers.append("worktree is not clean")
    root = _output_root(protocol)
    if root.exists():
        blockers.append("fresh physics-domain output root already exists")
    condition_count = len(protocol["design"]["physics_conditions"])
    return {
        "schema": (
            "proofalign.predictive-virtual-brake-v15.3-force-attributed-"
            "recovery-physics-domain-robustness-preflight.v1"
        ),
        "ready": not blockers,
        "blockers": blockers,
        "gpu": gpu,
        "environment_count": len(protocol["environments"]),
        "condition_count": condition_count,
        "expected_stress_lane_count": protocol["gates"][
            "expected_total_stress_lane_count"
        ],
        "expected_baseline_lane_count": protocol["gates"][
            "expected_total_baseline_lane_count"
        ],
        "output_root_absent": not root.exists(),
        "policy_load_authorized": False,
        "task_outcome_read_authorized": False,
        "model_mismatch_claim_authorized": False,
    }


def _stats(values: np.ndarray) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "minimum": float(np.min(array)) if array.size else None,
        "maximum": float(np.max(array)) if array.size else None,
        "mean": float(np.mean(array)) if array.size else None,
    }


def _apply_physics_condition(
    env: Any,
    robot: Any,
    vidx: np.ndarray,
    condition: Mapping[str, Any],
) -> dict[str, Any]:
    model = env.sim.model
    jidx = np.asarray(robot._ref_joint_indexes, dtype=int)
    body_ids = np.unique(
        np.asarray(model.jnt_bodyid[jidx], dtype=int)
    )
    geom_body_ids = np.asarray(model.geom_bodyid, dtype=int)
    geom_ids = np.flatnonzero(np.isin(geom_body_ids, body_ids))
    before_mass = np.asarray(model.body_mass[body_ids], dtype=np.float64).copy()
    before_damping = np.asarray(
        model.dof_damping[vidx], dtype=np.float64
    ).copy()
    before_friction = np.asarray(
        model.geom_friction[geom_ids, 0], dtype=np.float64
    ).copy()
    if (
        before_mass.size != 7
        or before_damping.size != 7
        or before_friction.size == 0
        or not np.isfinite(before_mass).all()
        or not np.isfinite(before_damping).all()
        or not np.isfinite(before_friction).all()
    ):
        raise V15PhysicsDomainRobustnessError(
            "physics-domain arm parameter support differs"
        )
    mass_scale = float(condition["arm_mass_scale"])
    damping_scale = float(condition["joint_damping_scale"])
    friction_scale = float(condition["arm_sliding_friction_scale"])
    expected_mass = before_mass * mass_scale
    expected_damping = before_damping * damping_scale
    expected_friction = before_friction * friction_scale
    model.body_mass[body_ids] = expected_mass
    model.dof_damping[vidx] = expected_damping
    model.geom_friction[geom_ids, 0] = expected_friction
    env.sim.forward()
    after_mass = np.asarray(model.body_mass[body_ids], dtype=np.float64).copy()
    after_damping = np.asarray(
        model.dof_damping[vidx], dtype=np.float64
    ).copy()
    after_friction = np.asarray(
        model.geom_friction[geom_ids, 0], dtype=np.float64
    ).copy()
    identity = bool(
        np.allclose(after_mass, expected_mass, rtol=0.0, atol=1e-12)
        and np.allclose(
            after_damping, expected_damping, rtol=0.0, atol=1e-12
        )
        and np.allclose(
            after_friction, expected_friction, rtol=0.0, atol=1e-12
        )
    )
    if not identity:
        raise V15PhysicsDomainRobustnessError(
            "physics-domain mutation lost exact expected identity"
        )
    return {
        "condition_id": str(condition["condition_id"]),
        "arm_joint_ids": jidx.tolist(),
        "arm_dof_ids": np.asarray(vidx, dtype=int).tolist(),
        "arm_body_ids": body_ids.tolist(),
        "arm_geom_ids": geom_ids.tolist(),
        "arm_mass_scale": mass_scale,
        "joint_damping_scale": damping_scale,
        "arm_sliding_friction_scale": friction_scale,
        "before_arm_body_mass": _stats(before_mass),
        "after_arm_body_mass": _stats(after_mass),
        "before_joint_damping": _stats(before_damping),
        "after_joint_damping": _stats(after_damping),
        "before_arm_sliding_friction": _stats(before_friction),
        "after_arm_sliding_friction": _stats(after_friction),
        "expected_parameter_identity": identity,
        "shadow_and_actual_share_perturbed_model": True,
        "model_mismatch_injected": False,
    }


def _run_environment(
    spec: Mapping[str, Any],
    condition: Mapping[str, Any],
    *,
    gpu: int,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    v14 = base.calibration.v14
    runtime = v14.base.load_libero_task_runtime(
        benchmark_name=str(spec["suite"]),
        task_id=int(spec["task_id"]),
        init_state_id=int(spec["init_state_id"]),
        bddl_file=str(REPO_ROOT / str(spec["bddl_path"])),
    )
    args = argparse.Namespace(
        env_img_res=64,
        camera_names="agentview",
        render_gpu_device_id=gpu,
        control_freq=20,
        horizon=1000,
        seed=int(spec["environment_seed"]),
    )
    env = v14.base.create_env(runtime, args)
    rows = []
    restore_failures = 0
    try:
        env.reset()
        env.set_init_state(runtime.init_state)
        robot, qidx, vidx, limits = v14._robot_arrays(env)
        physics_audit = _apply_physics_condition(
            env, robot, vidx, condition
        )
        condition_id = str(condition["condition_id"])
        base_environment_id = str(spec["environment_id"])
        environment_id = f"{base_environment_id}:{condition_id}"
        physics_audit.update(
            {
                "environment_id": environment_id,
                "base_environment_id": base_environment_id,
                "suite": str(spec["suite"]),
                "task_id": int(spec["task_id"]),
                "init_state_id": int(spec["init_state_id"]),
            }
        )
        canonical = v14.full.core.capture_warmstart_policy_shadow_snapshot(
            env,
            robot,
            source_id=f"v15.3-physics:{environment_id}:canonical",
        )
        for joint_index in range(v14.full.JOINT_COUNT):
            for side in v14.full.JOINT_SIDES:
                for dose in v14.pilot.DOSES:
                    restored = (
                        v14.full.core.
                        restore_warmstart_policy_shadow_snapshot(
                            env, robot, canonical
                        )
                    )
                    identity = v14.full.core._restore_identity(restored)
                    restore_failures += int(not identity)
                    if not identity:
                        raise V15PhysicsDomainRobustnessError(
                            "physics canonical restore lost identity"
                        )
                    v14.pilot._inject(
                        env,
                        robot,
                        qidx,
                        vidx,
                        limits,
                        joint_index=joint_index,
                        side=side,
                        dose=dose,
                    )
                    injected = (
                        v14.full.core.
                        capture_warmstart_policy_shadow_snapshot(
                            env,
                            robot,
                            source_id=(
                                f"v15.3-physics:{environment_id}:"
                                f"joint{joint_index}:{side}:{dose['dose']}"
                            ),
                        )
                    )
                    initial = v14.pilot._margin_matrix(env, qidx, limits)
                    baselines = {}
                    for baseline in BASELINES:
                        restored = (
                            v14.full.core.
                            restore_warmstart_policy_shadow_snapshot(
                                env, robot, injected
                            )
                        )
                        identity = v14.full.core._restore_identity(restored)
                        restore_failures += int(not identity)
                        if not identity:
                            raise V15PhysicsDomainRobustnessError(
                                "physics baseline restore lost identity"
                            )
                        if baseline == "no_guard":
                            result = v14._direct_result(
                                env, qidx, limits, reactive=False
                            )
                        elif baseline == "reactive_stop":
                            result = v14._direct_result(
                                env, qidx, limits, reactive=True
                            )
                        elif baseline == "v14_predictive_brake":
                            result = v14._run_screened(
                                env,
                                qidx,
                                limits,
                                baseline="predictive_brake",
                            )
                        elif baseline == V15_BASELINE:
                            result = base.force_development._run_screened(env)
                        else:
                            raise V15PhysicsDomainRobustnessError(
                                f"unsupported baseline: {baseline}"
                            )
                        baselines[baseline] = result
                    rows.append(
                        {
                            "environment_id": environment_id,
                            "base_environment_id": base_environment_id,
                            "condition_id": condition_id,
                            "suite": str(spec["suite"]),
                            "task_id": int(spec["task_id"]),
                            "init_state_id": int(spec["init_state_id"]),
                            "lane_id": (
                                f"{environment_id}:joint{joint_index}:"
                                f"{side}:{dose['dose']}"
                            ),
                            "joint_index": joint_index,
                            "side": side,
                            "dose": dict(dose),
                            "initial_joint_side_margins": (
                                v14.pilot._margin_rows(initial)
                            ),
                            "baselines": baselines,
                        }
                    )
    finally:
        if hasattr(env, "close"):
            env.close()
    return rows, restore_failures, physics_audit


@contextmanager
def _patched_baselines() -> Iterator[None]:
    original = base.BASELINES
    base.BASELINES = BASELINES
    try:
        yield
    finally:
        base.BASELINES = original


def _run_audited_environment(
    spec: Mapping[str, Any],
    condition: Mapping[str, Any],
    *,
    gpu: int,
    warnings: Any,
) -> tuple[list[dict[str, Any]], int, dict[str, Any], dict[str, Any]]:
    condition_id = str(condition["condition_id"])
    environment_id = f"{spec['environment_id']}:{condition_id}"
    warnings.environment_id = environment_id
    warnings.phase = "prebinding"
    contacts = base.calibration.audit._ContactAudit(environment_id)
    original_create = base.calibration.v14.base.create_env

    def audited_create(runtime: Any, args: Any) -> Any:
        warnings.phase = "prebinding"
        env = original_create(runtime, args)
        return base.calibration.audit._AuditedEnvironment(
            env, contacts=contacts, warnings=warnings
        )

    base.calibration.v14.base.create_env = audited_create
    try:
        rows, failures, physics = _run_environment(
            spec, condition, gpu=gpu
        )
    finally:
        base.calibration.v14.base.create_env = original_create
    return rows, failures, contacts.report(warnings), physics


def _condition_protocol(protocol: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(protocol))
    result["gates"] = {
        **dict(protocol["gates"]),
        "expected_environment_count": 18,
        "expected_stress_lane_count": 756,
        "expected_baseline_lane_count": 756 * len(BASELINES),
    }
    return result


def _analyze(
    protocol: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    *,
    restore_failures: Mapping[str, int],
    contact_reports: list[Mapping[str, Any]],
    physics_audits: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, bool]]:
    condition_results = {}
    condition_gates = {}
    normalized_protocol = _condition_protocol(protocol)
    with _patched_baselines():
        for condition in PHYSICS_CONDITIONS:
            condition_id = str(condition["condition_id"])
            subset = [
                row for row in rows if row["condition_id"] == condition_id
            ]
            contacts = [
                row
                for row in contact_reports
                if str(row["environment_id"]).endswith(
                    f":{condition_id}"
                )
            ]
            metrics, gates = base._analyze(
                normalized_protocol,
                subset,
                restore_failure_count=int(
                    restore_failures[condition_id]
                ),
                contact_reports=contacts,
            )
            condition_results[condition_id] = metrics
            condition_gates[condition_id] = gates
    audit_failures = sum(
        row.get("expected_parameter_identity") is not True
        or row.get("shadow_and_actual_share_perturbed_model") is not True
        or row.get("model_mismatch_injected") is not False
        for row in physics_audits
    )
    expected_lane_keys = None
    lane_identity = True
    for condition in PHYSICS_CONDITIONS:
        condition_id = str(condition["condition_id"])
        keys = {
            (
                str(row["base_environment_id"]),
                int(row["joint_index"]),
                str(row["side"]),
                str(row["dose"]["dose"]),
            )
            for row in rows
            if row["condition_id"] == condition_id
        }
        if expected_lane_keys is None:
            expected_lane_keys = keys
        else:
            lane_identity = bool(lane_identity and keys == expected_lane_keys)
    comparative = {}
    for condition_id, metrics in condition_results.items():
        aggregate = metrics["aggregate"]
        comparative[condition_id] = {
            "reactive_crossing_not_above_no_guard": (
                aggregate["reactive_stop_crossing_count"]
                <= aggregate["no_guard_crossing_count"]
            ),
            "v15_3_below_floor_not_above_reactive": (
                aggregate[f"{V15_BASELINE}_below_floor_count"]
                <= aggregate["reactive_stop_below_floor_count"]
            ),
            "v15_3_availability_not_below_v14": (
                aggregate[f"{V15_BASELINE}_executed_step_availability"]
                >= aggregate[
                    "v14_predictive_brake_executed_step_availability"
                ]
            ),
        }
    gates = {
        "expected_condition_count": (
            len(condition_results) == len(PHYSICS_CONDITIONS)
        ),
        "expected_total_stress_lane_count": (
            len(rows)
            == protocol["gates"]["expected_total_stress_lane_count"]
        ),
        "expected_total_baseline_lane_count": (
            len(rows) * len(BASELINES)
            == protocol["gates"]["expected_total_baseline_lane_count"]
        ),
        "physics_parameter_identity": audit_failures == 0,
        "physics_audit_coverage": (
            len(physics_audits)
            == len(PHYSICS_CONDITIONS) * len(protocol["environments"])
        ),
        "paired_lane_identity_across_conditions": lane_identity,
        "all_condition_registered_gates": all(
            value is True
            for values in condition_gates.values()
            for value in values.values()
        ),
        "all_condition_comparative_gates": all(
            value is True
            for values in comparative.values()
            for value in values.values()
        ),
    }
    return {
        "condition_results": condition_results,
        "condition_gate_results": condition_gates,
        "comparative_gate_results": comparative,
        "physics_parameter_audits": physics_audits,
        "physics_parameter_audit_failure_count": audit_failures,
        "paired_lane_identity_across_conditions": lane_identity,
        "restore_failure_count_by_condition": dict(restore_failures),
        "contact_reports": contact_reports,
    }, gates


def execute(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
    gpu: int,
) -> dict[str, Any]:
    report = preflight(protocol, gpu=gpu)
    if report["ready"] is not True:
        raise V15PhysicsDomainRobustnessError(
            "physics-domain preflight failed: "
            + "; ".join(report["blockers"])
        )
    base.calibration.v14._configure_environment(gpu)
    try:
        import mujoco
    except ImportError as exc:
        raise V15PhysicsDomainRobustnessError(
            "MuJoCo warning callback is unavailable"
        ) from exc
    previous = mujoco.get_mju_user_warning()
    warnings = base.calibration.audit._WarningAudit()
    rows = []
    contact_reports = []
    physics_audits = []
    restore_failures = {
        str(row["condition_id"]): 0 for row in PHYSICS_CONDITIONS
    }
    mujoco.set_mju_user_warning(warnings)
    try:
        for condition in PHYSICS_CONDITIONS:
            condition_id = str(condition["condition_id"])
            for spec in protocol["environments"]:
                observed, failures, contacts, physics = (
                    _run_audited_environment(
                        spec,
                        condition,
                        gpu=gpu,
                        warnings=warnings,
                    )
                )
                rows.extend(observed)
                restore_failures[condition_id] += failures
                contact_reports.append(contacts)
                physics_audits.append(physics)
    finally:
        mujoco.set_mju_user_warning(previous)
    analysis, gate_results = _analyze(
        protocol,
        rows,
        restore_failures=restore_failures,
        contact_reports=contact_reports,
        physics_audits=physics_audits,
    )
    passed = all(gate_results.values())
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "classification": (
            protocol["pass_classification"]
            if passed
            else protocol["nonpass_classification"]
        ),
        "qualification_pass": passed,
        "physics_domain_robustness_claim_authorized": passed,
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
        "gate_results": gate_results,
        "analysis": analysis,
        "lanes": rows,
        "claim_boundary": protocol["claim_boundary"],
    }
    root = _output_root(protocol)
    root.mkdir(parents=True, exist_ok=False)
    evidence_path = root / "qualification_evidence.json"
    evidence_path.write_text(canonical_text(evidence), encoding="utf-8")
    checksum_path = root / "SHA256SUMS"
    checksum_path.write_text(
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
        encoding="utf-8",
    )
    return evidence


def validate_results(
    protocol: Mapping[str, Any],
    *,
    protocol_path: Path,
) -> dict[str, Any]:
    _verify_protocol(protocol)
    root = _output_root(protocol)
    evidence_path = root / "qualification_evidence.json"
    checksum_path = root / "SHA256SUMS"
    if not evidence_path.is_file() or not checksum_path.is_file():
        raise V15PhysicsDomainRobustnessError(
            "physics-domain evidence is absent"
        )
    if checksum_path.read_text(encoding="utf-8") != (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    ):
        raise V15PhysicsDomainRobustnessError(
            "physics-domain checksum differs"
        )
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("schema") != EVIDENCE_SCHEMA
        or evidence.get("protocol_id") != protocol["protocol_id"]
        or evidence["protocol"]["sha256"] != file_sha256(protocol_path)
        or evidence["integrity"]
        != {
            "policy_loaded": False,
            "reward_read": False,
            "environment_done_read": False,
            "task_success_read": False,
            "cost_or_collision_read": False,
        }
    ):
        raise V15PhysicsDomainRobustnessError(
            "physics-domain evidence identity differs"
        )
    analysis, gate_results = _analyze(
        protocol,
        evidence["lanes"],
        restore_failures=evidence["analysis"][
            "restore_failure_count_by_condition"
        ],
        contact_reports=evidence["analysis"]["contact_reports"],
        physics_audits=evidence["analysis"][
            "physics_parameter_audits"
        ],
    )
    if (
        json_ready(analysis) != json_ready(evidence["analysis"])
        or gate_results != evidence["gate_results"]
    ):
        raise V15PhysicsDomainRobustnessError(
            "physics-domain evidence differs from recomputation"
        )
    return evidence


def json_ready(value: Any) -> Any:
    """Normalize through the canonical JSON encoder for exact comparison."""

    import json

    return json.loads(canonical_text(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--gpu", type=int, default=1)
    args = parser.parse_args(argv)
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    if args.preflight:
        payload = preflight(protocol, gpu=args.gpu)
    elif args.execute:
        payload = execute(
            protocol, protocol_path=protocol_path, gpu=args.gpu
        )
    else:
        payload = validate_results(protocol, protocol_path=protocol_path)
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
