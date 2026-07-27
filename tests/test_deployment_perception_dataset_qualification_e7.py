from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from scripts.prepare_deployment_perception_dataset_e7 import (
    SCHEMA_PATH,
    STAGES,
    STRESS_GROUPS,
    canonical_text,
    file_sha256,
)
from scripts.run_deployment_perception_dataset_qualification_e7 import (
    PerceptionQualificationError,
    audit_assets,
    build_evidence,
    main as qualification_main,
)


def test_e7_dataset_qualification_runner_contract_is_current() -> None:
    assert qualification_main(["--check-contract"]) == 0


def _asset(path: Path, root: Path, array: np.ndarray) -> dict:
    relative = path.relative_to(root)
    return {
        "path": str(relative),
        "sha256": file_sha256(path),
        "shape": list(array.shape),
        "dtype": str(array.dtype),
    }


def _camera() -> dict:
    return {
        "intrinsic_3x3": [
            [100.0, 0.0, 2.0],
            [0.0, 100.0, 2.0],
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


def _write_population(
    root: Path,
) -> tuple[Path, Path, dict]:
    asset_root = root / "assets"
    asset_root.mkdir()
    rgb = np.arange(48, dtype=np.uint8).reshape(4, 4, 3)
    mask = np.zeros((4, 4), dtype=bool)
    mask[1:3, 1:3] = True
    rgb_path = asset_root / "rgb.png"
    mask_path = asset_root / "mask.png"
    Image.fromarray(rgb, mode="RGB").save(rgb_path)
    Image.fromarray(mask).save(mask_path)
    rgb_record = _asset(rgb_path, asset_root, rgb)
    mask_record = _asset(mask_path, asset_root, mask)
    source_sha256 = sha256(
        b"frozen-outcome-blind-source"
    ).hexdigest()
    snapshots = []
    for index in range(2000):
        task_index = index // 200
        within_task = index % 200
        trajectory_index = within_task // 10
        frame_index = within_task % 10
        task_id = f"task-{task_index:02d}"
        trajectory_id = (
            f"{task_id}-trajectory-{trajectory_index:02d}"
        )
        scene_id = f"{task_id}-scene-{trajectory_index:02d}"
        split = (
            "qualification"
            if trajectory_index < 6
            else "development"
        )
        entity = {
            "entity_id": "red_mug_1",
            "position_xyz": [0.1, 0.0, 0.5],
            "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
            "instance_mask": mask_record,
        }
        snapshots.append(
            {
                "schema": (
                    "proofalign.deployment-perception-snapshot-e7.v1"
                ),
                "case_id": f"case-{index:04d}",
                "split": split,
                "task_id": task_id,
                "trajectory_id": trajectory_id,
                "scene_id": scene_id,
                "frame_index": frame_index,
                "stage": STAGES[index % len(STAGES)],
                "stress_group": STRESS_GROUPS[
                    index % len(STRESS_GROUPS)
                ],
                "main_image": rgb_record,
                "wrist_image": rgb_record,
                "main_camera": _camera(),
                "wrist_camera": _camera(),
                "eef_position": [0.0, 0.0, 0.5],
                "gripper_qpos": [0.04, -0.04],
                "target": entity,
                "destination": {
                    **entity,
                    "entity_id": "plate_1",
                    "position_xyz": [0.4, 0.0, 0.5],
                },
                "visibility": {
                    "target": "fully_visible",
                    "destination": "fully_visible",
                },
                "held_state": "not_held",
                "contact_state": "no_contact",
                "label_provenance": {
                    "source": (
                        "calibrated_multiview_annotation"
                    ),
                    "source_artifact": "offline-e7-fixture",
                    "source_sha256": source_sha256,
                    "annotator_or_exporter": "e7-test-exporter",
                    "outcome_fields_read": False,
                    "future_frames_used": False,
                    "model_prediction_used_as_ground_truth": False,
                },
            }
        )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = {
        "schema": schema["manifest_schema"],
        "dataset_id": "e7-population-fixture",
        "schema_binding": {
            "path": (
                "experiments/"
                "proofalign_deployment_perception_supervision_schema_e7.json"
            ),
            "sha256": file_sha256(SCHEMA_PATH),
            "schema_id": schema["schema_id"],
        },
        "created_before_model_selection": True,
        "snapshots": snapshots,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        canonical_text(manifest),
        encoding="utf-8",
    )
    return manifest_path, asset_root, manifest


def test_e7_dataset_qualification_checks_population_assets_and_split(
    tmp_path: Path,
) -> None:
    manifest_path, asset_root, _ = _write_population(tmp_path)

    evidence = build_evidence(manifest_path, asset_root)

    assert evidence["dataset_contract_qualified"] is True
    assert evidence["perception_model_qualified"] is False
    assert evidence["validation"]["snapshot_count"] == 2000
    assert evidence["validation"]["task_count"] == 10
    assert evidence["validation"]["trajectory_count"] == 200
    assert evidence["validation"]["qualification_count"] == 600
    assert all(
        evidence["validation"][
            "population_gate_results"
        ].values()
    )
    assert evidence["asset_audit"]["asset_reference_count"] == 8000
    assert evidence["asset_audit"]["unique_asset_count"] == 2
    assert evidence["outcomes_read"] is False
    assert evidence["simulator_created"] is False

    output_root = tmp_path / "evidence"
    assert (
        qualification_main(
            [
                "--write",
                "--manifest",
                str(manifest_path),
                "--asset-root",
                str(asset_root),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )
    assert (
        qualification_main(
            [
                "--check",
                "--manifest",
                str(manifest_path),
                "--asset-root",
                str(asset_root),
                "--output-root",
                str(output_root),
            ]
        )
        == 0
    )


def test_e7_dataset_asset_audit_rejects_path_traversal(
    tmp_path: Path,
) -> None:
    _, asset_root, manifest = _write_population(tmp_path)
    manifest["snapshots"][0]["main_image"] = {
        **manifest["snapshots"][0]["main_image"],
        "path": "../escape.png",
    }

    with pytest.raises(
        PerceptionQualificationError,
        match="traversal-free",
    ):
        audit_assets(manifest, asset_root)
