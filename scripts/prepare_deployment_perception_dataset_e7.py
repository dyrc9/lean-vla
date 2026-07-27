#!/usr/bin/env python3
"""Freeze and validate the E7 outcome-blind perception supervision contract."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import re
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deployment_perception_supervision_schema_e7.json"
)
PREFLIGHT_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deployment_perception_e7_protocol.json"
)
PREFLIGHT_EVIDENCE_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_deployment_perception_e7_preflight.json"
)
SCRIPT_PATH = (
    REPO_ROOT
    / "scripts"
    / "prepare_deployment_perception_dataset_e7.py"
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    "approach",
    "grasp",
    "transport",
    "pre_place",
    "release",
)
STRESS_GROUPS = (
    "nominal",
    "wrist_occluded",
    "base_occluded",
    "target_partially_visible",
    "destination_partially_visible",
    "novel_pose",
    "near_boundary",
)
FORBIDDEN_FIELD_NAMES = {
    "reward",
    "success",
    "task_success",
    "cost",
    "collision",
    "done",
    "return",
    "episode_outcome",
}


class PerceptionDatasetError(RuntimeError):
    """Raised when an E7 supervision artifact violates the frozen contract."""


def file_sha256(path: Path) -> str:
    hasher = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def canonical_text(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def build_schema() -> dict[str, Any]:
    return {
        "schema": (
            "proofalign.deployment-perception-supervision-contract-e7.v1"
        ),
        "schema_id": (
            "proofalign-deployment-perception-supervision-e7-20260725"
        ),
        "status": "frozen_before_collection_or_model_selection",
        "created_at": "2026-07-25T00:00:00+08:00",
        "preflight_bindings": {
            "protocol_path": str(
                PREFLIGHT_PROTOCOL_PATH.relative_to(REPO_ROOT)
            ),
            "protocol_sha256": file_sha256(
                PREFLIGHT_PROTOCOL_PATH
            ),
            "evidence_path": str(
                PREFLIGHT_EVIDENCE_PATH.relative_to(REPO_ROOT)
            ),
            "evidence_sha256": file_sha256(
                PREFLIGHT_EVIDENCE_PATH
            ),
        },
        "manifest_schema": (
            "proofalign.deployment-perception-dataset-e7.v1"
        ),
        "snapshot_schema": (
            "proofalign.deployment-perception-snapshot-e7.v1"
        ),
        "allowed_splits": (
            "development",
            "qualification",
        ),
        "allowed_stages": STAGES,
        "allowed_stress_groups": STRESS_GROUPS,
        "population_gates": {
            "minimum_tasks": 10,
            "minimum_trajectories_per_task": 20,
            "minimum_snapshots": 2000,
            "minimum_snapshots_per_stage": 200,
            "minimum_snapshots_per_non_nominal_stress_group": 100,
            "minimum_qualification_fraction": 0.30,
        },
        "grouping_rules": {
            "split_unit": "trajectory_and_scene",
            "trajectory_overlap_allowed": False,
            "scene_overlap_allowed": False,
            "threshold_selection_split": "development",
            "metric_reporting_split": "qualification",
        },
        "required_snapshot_fields": {
            "identity": (
                "schema",
                "case_id",
                "split",
                "task_id",
                "trajectory_id",
                "scene_id",
                "frame_index",
                "stage",
                "stress_group",
            ),
            "images": (
                "main_image",
                "wrist_image",
            ),
            "calibration": (
                "main_camera",
                "wrist_camera",
            ),
            "geometry": (
                "eef_position",
                "gripper_qpos",
                "target",
                "destination",
            ),
            "state_labels": (
                "visibility",
                "held_state",
                "contact_state",
            ),
            "provenance": (
                "label_provenance",
            ),
        },
        "asset_record_fields": (
            "path",
            "sha256",
            "shape",
            "dtype",
        ),
        "camera_record_fields": (
            "intrinsic_3x3",
            "extrinsic_4x4",
            "extrinsic_convention",
        ),
        "entity_record_fields": (
            "entity_id",
            "position_xyz",
            "orientation_xyzw",
            "instance_mask",
        ),
        "visibility_values": (
            "fully_visible",
            "partially_visible",
            "occluded",
            "out_of_view",
        ),
        "held_state_values": (
            "held",
            "not_held",
        ),
        "contact_state_values": (
            "no_contact",
            "target_contact",
            "destination_contact",
            "non_target_contact",
        ),
        "forbidden_field_names": tuple(
            sorted(FORBIDDEN_FIELD_NAMES)
        ),
        "label_provenance_requirements": {
            "allowed_sources": (
                "simulator_privileged_state_export",
                "calibrated_multiview_annotation",
                "manual_instance_annotation",
            ),
            "outcome_fields_read": False,
            "future_frames_used": False,
            "model_prediction_used_as_ground_truth": False,
        },
        "collection_authorization": {
            "existing_offline_data_export_authorized": True,
            "simulator_creation_authorized": False,
            "action_dispatch_authorized": False,
            "outcome_read_authorized": False,
            "model_training_authorized": False,
            "model_selection_authorized": False,
        },
        "source_binding": {
            "path": str(SCRIPT_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(SCRIPT_PATH),
        },
        "claim_boundary": (
            "This contract defines outcome-blind supervision and split "
            "requirements only. A conforming dataset is not itself a "
            "qualified perception model, deployment result, efficacy "
            "result, or physical-safety result."
        ),
    }


def validate_schema(schema: dict[str, Any]) -> None:
    if (
        schema.get("schema")
        != "proofalign.deployment-perception-supervision-contract-e7.v1"
    ):
        raise PerceptionDatasetError(
            "unsupported E7 supervision contract schema"
        )
    if schema["status"] != (
        "frozen_before_collection_or_model_selection"
    ):
        raise PerceptionDatasetError(
            "E7 supervision contract status changed"
        )
    if tuple(schema["allowed_stages"]) != STAGES:
        raise PerceptionDatasetError(
            "E7 stage vocabulary changed"
        )
    if tuple(schema["allowed_stress_groups"]) != STRESS_GROUPS:
        raise PerceptionDatasetError(
            "E7 stress vocabulary changed"
        )
    if set(schema["forbidden_field_names"]) != (
        FORBIDDEN_FIELD_NAMES
    ):
        raise PerceptionDatasetError(
            "E7 forbidden outcome fields changed"
        )
    authorization = schema["collection_authorization"]
    if authorization[
        "existing_offline_data_export_authorized"
    ] is not True:
        raise PerceptionDatasetError(
            "E7 offline export boundary changed"
        )
    if any(
        authorization[name]
        for name in (
            "simulator_creation_authorized",
            "action_dispatch_authorized",
            "outcome_read_authorized",
            "model_training_authorized",
            "model_selection_authorized",
        )
    ):
        raise PerceptionDatasetError(
            "E7 supervision contract authorizes external execution"
        )
    bindings = schema["preflight_bindings"]
    for path_key, digest_key in (
        ("protocol_path", "protocol_sha256"),
        ("evidence_path", "evidence_sha256"),
    ):
        path = REPO_ROOT / bindings[path_key]
        if not path.is_file() or file_sha256(path) != bindings[
            digest_key
        ]:
            raise PerceptionDatasetError(
                f"E7 preflight binding is stale: {path}"
            )
    source = schema["source_binding"]
    source_path = REPO_ROOT / source["path"]
    if (
        source_path != SCRIPT_PATH
        or not source_path.is_file()
        or file_sha256(source_path) != source["sha256"]
    ):
        raise PerceptionDatasetError(
            "E7 supervision validator source binding is stale"
        )


def _require_keys(
    value: dict[str, Any],
    names: tuple[str, ...] | list[str],
    *,
    context: str,
) -> None:
    missing = [name for name in names if name not in value]
    if missing:
        raise PerceptionDatasetError(
            f"{context} is missing fields: {missing}"
        )


def _finite_vector(
    value: Any,
    *,
    length: int,
    context: str,
) -> tuple[float, ...]:
    try:
        result = tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise PerceptionDatasetError(
            f"{context} must be numeric"
        ) from exc
    if len(result) != length or any(
        not isfinite(item) for item in result
    ):
        raise PerceptionDatasetError(
            f"{context} must contain {length} finite values"
        )
    return result


def _finite_matrix(
    value: Any,
    *,
    rows: int,
    columns: int,
    context: str,
) -> None:
    if not isinstance(value, list) or len(value) != rows:
        raise PerceptionDatasetError(
            f"{context} must have {rows} rows"
        )
    for index, row in enumerate(value):
        _finite_vector(
            row,
            length=columns,
            context=f"{context}[{index}]",
        )


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def _validate_asset(
    value: dict[str, Any],
    *,
    context: str,
    check_assets: bool,
    asset_root: Path | None,
) -> None:
    _require_keys(
        value,
        ("path", "sha256", "shape", "dtype"),
        context=context,
    )
    if not HEX64.fullmatch(str(value["sha256"])):
        raise PerceptionDatasetError(
            f"{context}.sha256 must be lowercase SHA-256"
        )
    shape = value["shape"]
    if (
        not isinstance(shape, list)
        or len(shape) not in (2, 3)
        or any(type(item) is not int or item <= 0 for item in shape)
    ):
        raise PerceptionDatasetError(
            f"{context}.shape is invalid"
        )
    if str(value["dtype"]) not in {"uint8", "bool"}:
        raise PerceptionDatasetError(
            f"{context}.dtype is unsupported"
        )
    if check_assets:
        if asset_root is None:
            raise PerceptionDatasetError(
                "asset_root is required when checking assets"
            )
        path = (asset_root / str(value["path"])).resolve()
        if not path.is_file() or file_sha256(path) != value["sha256"]:
            raise PerceptionDatasetError(
                f"{context} asset binding is stale: {path}"
            )


def _validate_camera(value: dict[str, Any], *, context: str) -> None:
    _require_keys(
        value,
        (
            "intrinsic_3x3",
            "extrinsic_4x4",
            "extrinsic_convention",
        ),
        context=context,
    )
    _finite_matrix(
        value["intrinsic_3x3"],
        rows=3,
        columns=3,
        context=f"{context}.intrinsic_3x3",
    )
    _finite_matrix(
        value["extrinsic_4x4"],
        rows=4,
        columns=4,
        context=f"{context}.extrinsic_4x4",
    )
    if value["extrinsic_convention"] not in {
        "camera_to_world",
        "camera_to_robot_base",
    }:
        raise PerceptionDatasetError(
            f"{context}.extrinsic_convention is unsupported"
        )


def _validate_entity(
    value: dict[str, Any],
    *,
    context: str,
    check_assets: bool,
    asset_root: Path | None,
) -> None:
    _require_keys(
        value,
        (
            "entity_id",
            "position_xyz",
            "orientation_xyzw",
            "instance_mask",
        ),
        context=context,
    )
    if not str(value["entity_id"]).strip():
        raise PerceptionDatasetError(
            f"{context}.entity_id is empty"
        )
    _finite_vector(
        value["position_xyz"],
        length=3,
        context=f"{context}.position_xyz",
    )
    _finite_vector(
        value["orientation_xyzw"],
        length=4,
        context=f"{context}.orientation_xyzw",
    )
    _validate_asset(
        value["instance_mask"],
        context=f"{context}.instance_mask",
        check_assets=check_assets,
        asset_root=asset_root,
    )


def validate_snapshot(
    snapshot: dict[str, Any],
    schema: dict[str, Any],
    *,
    check_assets: bool = False,
    asset_root: Path | None = None,
) -> None:
    required = schema["required_snapshot_fields"]
    for names in required.values():
        _require_keys(
            snapshot,
            names,
            context="E7 snapshot",
        )
    forbidden = _walk_keys(snapshot).intersection(
        FORBIDDEN_FIELD_NAMES
    )
    if forbidden:
        raise PerceptionDatasetError(
            f"E7 snapshot contains forbidden outcome fields: "
            f"{sorted(forbidden)}"
        )
    if snapshot["schema"] != schema["snapshot_schema"]:
        raise PerceptionDatasetError(
            "E7 snapshot schema changed"
        )
    for name in (
        "case_id",
        "task_id",
        "trajectory_id",
        "scene_id",
    ):
        if not str(snapshot[name]).strip():
            raise PerceptionDatasetError(
                f"E7 snapshot {name} is empty"
            )
    if snapshot["split"] not in schema["allowed_splits"]:
        raise PerceptionDatasetError(
            "E7 snapshot split is invalid"
        )
    if (
        type(snapshot["frame_index"]) is not int
        or snapshot["frame_index"] < 0
    ):
        raise PerceptionDatasetError(
            "E7 snapshot frame_index is invalid"
        )
    if snapshot["stage"] not in schema["allowed_stages"]:
        raise PerceptionDatasetError(
            "E7 snapshot stage is invalid"
        )
    if snapshot["stress_group"] not in schema[
        "allowed_stress_groups"
    ]:
        raise PerceptionDatasetError(
            "E7 snapshot stress_group is invalid"
        )
    _validate_asset(
        snapshot["main_image"],
        context="main_image",
        check_assets=check_assets,
        asset_root=asset_root,
    )
    _validate_asset(
        snapshot["wrist_image"],
        context="wrist_image",
        check_assets=check_assets,
        asset_root=asset_root,
    )
    _validate_camera(snapshot["main_camera"], context="main_camera")
    _validate_camera(
        snapshot["wrist_camera"],
        context="wrist_camera",
    )
    _finite_vector(
        snapshot["eef_position"],
        length=3,
        context="eef_position",
    )
    gripper = tuple(float(item) for item in snapshot["gripper_qpos"])
    if not gripper or any(not isfinite(item) for item in gripper):
        raise PerceptionDatasetError(
            "gripper_qpos must be non-empty and finite"
        )
    _validate_entity(
        snapshot["target"],
        context="target",
        check_assets=check_assets,
        asset_root=asset_root,
    )
    _validate_entity(
        snapshot["destination"],
        context="destination",
        check_assets=check_assets,
        asset_root=asset_root,
    )
    visibility = snapshot["visibility"]
    _require_keys(
        visibility,
        ("target", "destination"),
        context="visibility",
    )
    if any(
        visibility[name] not in schema["visibility_values"]
        for name in ("target", "destination")
    ):
        raise PerceptionDatasetError(
            "E7 visibility value is invalid"
        )
    if snapshot["held_state"] not in schema["held_state_values"]:
        raise PerceptionDatasetError(
            "E7 held_state is invalid"
        )
    if snapshot["contact_state"] not in schema[
        "contact_state_values"
    ]:
        raise PerceptionDatasetError(
            "E7 contact_state is invalid"
        )
    provenance = snapshot["label_provenance"]
    _require_keys(
        provenance,
        (
            "source",
            "source_artifact",
            "source_sha256",
            "annotator_or_exporter",
            "outcome_fields_read",
            "future_frames_used",
            "model_prediction_used_as_ground_truth",
        ),
        context="label_provenance",
    )
    requirements = schema["label_provenance_requirements"]
    if provenance["source"] not in requirements["allowed_sources"]:
        raise PerceptionDatasetError(
            "E7 label source is not allowed"
        )
    if not HEX64.fullmatch(str(provenance["source_sha256"])):
        raise PerceptionDatasetError(
            "E7 label source digest is invalid"
        )
    for name in (
        "outcome_fields_read",
        "future_frames_used",
        "model_prediction_used_as_ground_truth",
    ):
        if provenance[name] is not requirements[name]:
            raise PerceptionDatasetError(
                f"E7 label provenance violates {name}"
            )


def validate_manifest(
    manifest: dict[str, Any],
    schema: dict[str, Any],
    *,
    enforce_population: bool = True,
    check_assets: bool = False,
    asset_root: Path | None = None,
) -> dict[str, Any]:
    validate_schema(schema)
    _require_keys(
        manifest,
        (
            "schema",
            "dataset_id",
            "schema_binding",
            "created_before_model_selection",
            "snapshots",
        ),
        context="E7 manifest",
    )
    if manifest["schema"] != schema["manifest_schema"]:
        raise PerceptionDatasetError(
            "E7 manifest schema changed"
        )
    if manifest["created_before_model_selection"] is not True:
        raise PerceptionDatasetError(
            "E7 manifest was not frozen before model selection"
        )
    if manifest["schema_binding"] != {
        "path": str(SCHEMA_PATH.relative_to(REPO_ROOT)),
        "sha256": file_sha256(SCHEMA_PATH),
        "schema_id": schema["schema_id"],
    }:
        raise PerceptionDatasetError(
            "E7 manifest schema binding is stale"
        )
    snapshots = manifest["snapshots"]
    if not isinstance(snapshots, list) or not snapshots:
        raise PerceptionDatasetError(
            "E7 manifest snapshots must be non-empty"
        )
    for snapshot in snapshots:
        validate_snapshot(
            snapshot,
            schema,
            check_assets=check_assets,
            asset_root=asset_root,
        )
    case_ids = [str(row["case_id"]) for row in snapshots]
    if len(case_ids) != len(set(case_ids)):
        raise PerceptionDatasetError(
            "E7 manifest contains duplicate case IDs"
        )
    trajectory_splits: dict[str, set[str]] = {}
    scene_splits: dict[str, set[str]] = {}
    for row in snapshots:
        trajectory_splits.setdefault(
            str(row["trajectory_id"]),
            set(),
        ).add(str(row["split"]))
        scene_splits.setdefault(
            str(row["scene_id"]),
            set(),
        ).add(str(row["split"]))
    leaking_trajectories = sorted(
        key
        for key, splits in trajectory_splits.items()
        if len(splits) > 1
    )
    leaking_scenes = sorted(
        key
        for key, splits in scene_splits.items()
        if len(splits) > 1
    )
    if leaking_trajectories or leaking_scenes:
        raise PerceptionDatasetError(
            "E7 development/qualification leakage: "
            f"trajectories={leaking_trajectories}, "
            f"scenes={leaking_scenes}"
        )
    task_ids = {str(row["task_id"]) for row in snapshots}
    trajectory_counts: dict[str, set[str]] = {}
    for row in snapshots:
        trajectory_counts.setdefault(
            str(row["task_id"]),
            set(),
        ).add(str(row["trajectory_id"]))
    stage_counts = {
        stage: sum(row["stage"] == stage for row in snapshots)
        for stage in STAGES
    }
    stress_counts = {
        group: sum(
            row["stress_group"] == group for row in snapshots
        )
        for group in STRESS_GROUPS
    }
    qualification_count = sum(
        row["split"] == "qualification" for row in snapshots
    )
    gates = schema["population_gates"]
    population_gate_results = {
        "tasks": len(task_ids) >= gates["minimum_tasks"],
        "trajectories_per_task": all(
            len(values)
            >= gates["minimum_trajectories_per_task"]
            for values in trajectory_counts.values()
        )
        and len(trajectory_counts) >= gates["minimum_tasks"],
        "snapshots": len(snapshots) >= gates["minimum_snapshots"],
        "stages": all(
            count >= gates["minimum_snapshots_per_stage"]
            for count in stage_counts.values()
        ),
        "stress_groups": all(
            stress_counts[group]
            >= gates[
                "minimum_snapshots_per_non_nominal_stress_group"
            ]
            for group in STRESS_GROUPS
            if group != "nominal"
        ),
        "qualification_fraction": (
            qualification_count / len(snapshots)
            >= gates["minimum_qualification_fraction"]
        ),
    }
    if enforce_population and not all(
        population_gate_results.values()
    ):
        raise PerceptionDatasetError(
            "E7 population gates failed: "
            + ",".join(
                name
                for name, passed in population_gate_results.items()
                if not passed
            )
        )
    return {
        "schema": (
            "proofalign.deployment-perception-dataset-validation-e7.v1"
        ),
        "valid": (
            all(population_gate_results.values())
            if enforce_population
            else True
        ),
        "structurally_valid": True,
        "population_enforced": enforce_population,
        "snapshot_count": len(snapshots),
        "task_count": len(task_ids),
        "trajectory_count": len(trajectory_splits),
        "scene_count": len(scene_splits),
        "qualification_count": qualification_count,
        "stage_counts": stage_counts,
        "stress_counts": stress_counts,
        "population_gate_results": population_gate_results,
        "development_qualification_trajectory_overlap": [],
        "development_qualification_scene_overlap": [],
        "outcome_fields_present": False,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-schema", action="store_true")
    mode.add_argument("--check-schema", action="store_true")
    mode.add_argument("--validate-manifest", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument(
        "--structural-only",
        action="store_true",
        help="Skip frozen population gates; intended only for data debugging.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.write_schema:
            if SCHEMA_PATH.exists():
                raise PerceptionDatasetError(
                    f"refusing to replace frozen schema: {SCHEMA_PATH}"
                )
            SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
            SCHEMA_PATH.write_text(
                canonical_text(build_schema()),
                encoding="utf-8",
            )
            print(SCHEMA_PATH)
            return 0
        schema = json.loads(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
        validate_schema(schema)
        if args.check_schema:
            if SCHEMA_PATH.read_text(
                encoding="utf-8"
            ) != canonical_text(build_schema()):
                raise PerceptionDatasetError(
                    "E7 supervision schema is stale"
                )
            print(f"E7 supervision schema is current: {SCHEMA_PATH}")
            return 0
        manifest = json.loads(
            args.validate_manifest.read_text(encoding="utf-8")
        )
        report = validate_manifest(
            manifest,
            schema,
            enforce_population=not args.structural_only,
            check_assets=args.asset_root is not None,
            asset_root=args.asset_root,
        )
        print(json.dumps(report, indent=2))
        return 0
    except (
        KeyError,
        OSError,
        PerceptionDatasetError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
