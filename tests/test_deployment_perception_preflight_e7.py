from __future__ import annotations

import json

import pytest

from scripts.prepare_deployment_perception_dataset_e7 import (
    SCHEMA_PATH as SUPERVISION_SCHEMA_PATH,
    PerceptionDatasetError,
    build_schema as build_supervision_schema,
    canonical_text as supervision_canonical_text,
    file_sha256,
    validate_manifest,
    validate_schema as validate_supervision_schema,
    validate_snapshot,
)
from scripts.run_deployment_perception_preflight_e7 import (
    EVIDENCE_PATH,
    PROTOCOL_PATH,
    build_evidence,
    build_protocol,
    canonical_text,
    validate_protocol,
)


def test_e7_protocol_and_preflight_evidence_are_current() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    validate_protocol(protocol)
    assert PROTOCOL_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_protocol())
    assert EVIDENCE_PATH.read_text(
        encoding="utf-8"
    ) == canonical_text(build_evidence(protocol))


def test_e7_blocks_qualification_on_missing_supervision() -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    evidence = build_evidence(protocol)

    assert (
        evidence["classification"]
        == "deployment_perception_data_inadequate"
    )
    assert evidence["qualification_ready"] is False
    assert evidence["missing_requirement_ids"] == [
        "camera_intrinsics",
        "camera_extrinsics",
        "target_identity_localization",
        "destination_geometry",
        "visibility_occlusion",
        "held_contact_state",
        "independent_qualification_split",
    ]
    assert evidence["gate_results"]["outcome_blind_labels"] is True
    assert evidence["training_performed"] is False
    assert evidence["policy_loaded"] is False
    assert evidence["simulator_created"] is False
    assert evidence["actions_dispatched"] is False
    assert evidence["outcomes_read"] is False


def _asset(path: str, *, mask: bool = False) -> dict:
    return {
        "path": path,
        "sha256": "a" * 64,
        "shape": [256, 256] if mask else [256, 256, 3],
        "dtype": "bool" if mask else "uint8",
    }


def _camera() -> dict:
    return {
        "intrinsic_3x3": [
            [100.0, 0.0, 128.0],
            [0.0, 100.0, 128.0],
            [0.0, 0.0, 1.0],
        ],
        "extrinsic_4x4": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        "extrinsic_convention": "camera_to_world",
    }


def _snapshot(
    *,
    case_id: str = "case-001",
    split: str = "development",
    trajectory_id: str = "trajectory-001",
    scene_id: str = "scene-001",
) -> dict:
    entity = {
        "entity_id": "red_mug_1",
        "position_xyz": [0.1, 0.0, 0.5],
        "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
        "instance_mask": _asset("masks/red-mug.png", mask=True),
    }
    return {
        "schema": (
            "proofalign.deployment-perception-snapshot-e7.v1"
        ),
        "case_id": case_id,
        "split": split,
        "task_id": "task-01",
        "trajectory_id": trajectory_id,
        "scene_id": scene_id,
        "frame_index": 0,
        "stage": "approach",
        "stress_group": "nominal",
        "main_image": _asset("images/main.jpg"),
        "wrist_image": _asset("images/wrist.jpg"),
        "main_camera": _camera(),
        "wrist_camera": _camera(),
        "eef_position": [0.0, 0.0, 0.5],
        "gripper_qpos": [0.04, -0.04],
        "target": entity,
        "destination": {
            **entity,
            "entity_id": "plate_1",
            "position_xyz": [0.4, 0.0, 0.5],
            "instance_mask": _asset("masks/plate.png", mask=True),
        },
        "visibility": {
            "target": "fully_visible",
            "destination": "fully_visible",
        },
        "held_state": "not_held",
        "contact_state": "no_contact",
        "label_provenance": {
            "source": "simulator_privileged_state_export",
            "source_artifact": "offline-demo-001",
            "source_sha256": "b" * 64,
            "annotator_or_exporter": "proofalign-exporter-v1",
            "outcome_fields_read": False,
            "future_frames_used": False,
            "model_prediction_used_as_ground_truth": False,
        },
    }


def _manifest(snapshots: list[dict]) -> dict:
    schema = json.loads(
        SUPERVISION_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    return {
        "schema": schema["manifest_schema"],
        "dataset_id": "unit-e7",
        "schema_binding": {
            "path": (
                "experiments/"
                "proofalign_deployment_perception_supervision_schema_e7.json"
            ),
            "sha256": file_sha256(SUPERVISION_SCHEMA_PATH),
            "schema_id": schema["schema_id"],
        },
        "created_before_model_selection": True,
        "snapshots": snapshots,
    }


def test_e7_supervision_contract_is_current_and_structurally_valid() -> None:
    schema = json.loads(
        SUPERVISION_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    validate_supervision_schema(schema)
    assert SUPERVISION_SCHEMA_PATH.read_text(
        encoding="utf-8"
    ) == supervision_canonical_text(build_supervision_schema())

    snapshot = _snapshot()
    validate_snapshot(snapshot, schema)
    report = validate_manifest(
        _manifest([snapshot]),
        schema,
        enforce_population=False,
    )
    assert report["structurally_valid"] is True
    assert report["outcome_fields_present"] is False


def test_e7_supervision_rejects_outcome_fields_and_split_leakage() -> None:
    schema = json.loads(
        SUPERVISION_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    with_outcome = _snapshot()
    with_outcome["reward"] = 1.0
    with pytest.raises(
        PerceptionDatasetError,
        match="forbidden outcome fields",
    ):
        validate_snapshot(with_outcome, schema)

    development = _snapshot()
    qualification = _snapshot(
        case_id="case-002",
        split="qualification",
        trajectory_id="trajectory-001",
        scene_id="scene-001",
    )
    with pytest.raises(
        PerceptionDatasetError,
        match="development/qualification leakage",
    ):
        validate_manifest(
            _manifest([development, qualification]),
            schema,
            enforce_population=False,
        )
