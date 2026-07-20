from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "safelibero_aegis_scene_probe",
    ROOT / "scripts" / "safelibero_aegis_scene_probe.py",
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_array_digest_is_order_independent_and_value_sensitive() -> None:
    first = {"b": np.array([2], dtype=np.int32), "a": np.array([1], dtype=np.int32)}
    reordered = {"a": first["a"], "b": first["b"]}
    changed = {"a": first["a"], "b": np.array([3], dtype=np.int32)}
    assert probe._digest_arrays(first) == probe._digest_arrays(reordered)
    assert probe._digest_arrays(first) != probe._digest_arrays(changed)


def test_array_digest_binds_dtype_and_shape() -> None:
    vector = {"value": np.array([1, 2], dtype=np.int32)}
    matrix = {"value": np.array([[1, 2]], dtype=np.int32)}
    floating = {"value": np.array([1, 2], dtype=np.float32)}
    assert probe._digest_arrays(vector) != probe._digest_arrays(matrix)
    assert probe._digest_arrays(vector) != probe._digest_arrays(floating)


def test_gpu_snapshot_parses_physical_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    output = "5, GPU-egl, NVIDIA RTX 6000 Ada Generation, 49140, 3, 0\n"
    monkeypatch.setattr(
        probe,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )
    assert probe._gpu_snapshot(5)["uuid"] == "GPU-egl"
    assert probe._gpu_snapshot(5)["memory_used_mib"] == 3


def test_pinned_scene_file_tamper_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned = tmp_path / "scene.bddl"
    pinned.write_text("original", encoding="utf-8")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    protocol = {
        "pinned_files": {
            "bddl": {"path": "scene.bddl", "sha256": probe.sha256_file(pinned)}
        },
        "implementation": {},
    }
    pinned.write_text("tampered", encoding="utf-8")
    with pytest.raises(probe.SceneProbeError, match="digest mismatch"):
        probe._verify_files(protocol)
