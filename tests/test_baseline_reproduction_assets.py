from __future__ import annotations

import json
from pathlib import Path
import pickle

import numpy as np
import pytest

from scripts.baseline_reproduction_assets import (
    AssetError,
    inspect_fiper_rollouts,
    inspect_safe_rollouts,
    tree_manifest,
    verify_tree_manifest,
)


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        pickle.dump(payload, handle)


def test_tree_manifest_is_deterministic_and_verifiable(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    root.mkdir()
    (root / "b.bin").write_bytes(b"b")
    (root / "a.bin").write_bytes(b"a")
    manifest = tree_manifest(root)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert [item["path"] for item in manifest["entries"]] == ["a.bin", "b.bin"]
    assert verify_tree_manifest(manifest_path)["tree_sha256"] == manifest["tree_sha256"]

    (root / "a.bin").write_bytes(b"changed")
    with pytest.raises(AssetError, match="differs"):
        verify_tree_manifest(manifest_path)


def safe_env_record(*, success: bool, calls: int, episode: int) -> dict[str, object]:
    return {
        "task_suite_name": "libero_10",
        "task_id": 0,
        "task_description": "fixture",
        "episode_idx": episode,
        "episode_success": success,
        "model_infer_times": calls,
        "replan_steps": 5,
    }


def test_safe_inspection_requires_explicit_trust_and_matches_policy_count(tmp_path: Path) -> None:
    dump(tmp_path / "env_records" / "ep0.pkl", safe_env_record(success=True, calls=1, episode=0))
    dump(tmp_path / "env_records" / "ep1.pkl", safe_env_record(success=False, calls=1, episode=1))
    for index in range(2):
        dump(
            tmp_path / "policy_records" / f"step_{index}_meta.pkl",
            {
                "pre_velocity": np.zeros((10, 50, 8), dtype=np.float32),
                "actions": np.zeros((50, 7), dtype=np.float32),
            },
        )

    with pytest.raises(AssetError, match="refusing"):
        inspect_safe_rollouts(tmp_path, trust_pickle=False, expected_episodes=2)

    report = inspect_safe_rollouts(tmp_path, trust_pickle=True, expected_episodes=2)
    assert report["valid"] is True
    assert report["success_count"] == report["failure_count"] == 1
    assert report["pre_velocity_shapes"] == [[10, 50, 8]]


def fiper_rollout(success: bool) -> dict[str, object]:
    return {
        "metadata": {"successful": success, "rollout_subtype": "id" if success else "ood"},
        "rollout": [
            {
                "obs_embedding": np.zeros((4,), dtype=np.float32),
                "action_pred": np.zeros((8, 3), dtype=np.float32),
            }
        ],
    }


def test_fiper_inspection_requires_successful_threshold_subset_and_mixed_test(tmp_path: Path) -> None:
    task = "sorting"
    for split in ("calibration", "test"):
        for index in range(5):
            success = True if split == "calibration" else index % 2 == 0
            dump(
                tmp_path / task / "rollouts" / split / f"rollout_{index}.pkl",
                fiper_rollout(success),
            )

    report = inspect_fiper_rollouts(
        tmp_path,
        tasks=[task],
        trust_pickle=True,
        minimum_files=5,
    )
    assert report["tasks"][task]["calibration"]["failure_count"] == 0
    assert report["tasks"][task]["test"]["failure_count"] == 2

    calibration_dir = tmp_path / task / "rollouts" / "calibration"
    dump(calibration_dir / "rollout_0.pkl", fiper_rollout(False))
    report = inspect_fiper_rollouts(tmp_path, tasks=[task], trust_pickle=True, minimum_files=5)
    assert report["tasks"][task]["calibration"]["failure_count"] == 1

    for path in calibration_dir.glob("*.pkl"):
        dump(path, fiper_rollout(False))
    with pytest.raises(AssetError, match="no successful"):
        inspect_fiper_rollouts(tmp_path, tasks=[task], trust_pickle=True, minimum_files=5)


def test_fiper_inspection_recognizes_robot_wrapped_action_shape(tmp_path: Path) -> None:
    task = "push_t"
    for split in ("calibration", "test"):
        for index in range(5):
            success = split == "calibration" or index % 2 == 0
            rollout = fiper_rollout(success)
            rollout["rollout"][0]["action_pred"] = [np.zeros((256, 16, 3), dtype=np.float32)]
            dump(tmp_path / task / "rollouts" / split / f"rollout_{index}.pkl", rollout)

    report = inspect_fiper_rollouts(tmp_path, tasks=[task], trust_pickle=True, minimum_files=5)
    assert report["tasks"][task]["calibration"]["action_pred_shapes"] == [[1, 256, 16, 3]]
