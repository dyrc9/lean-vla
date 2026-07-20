from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "safelibero_aegis_model_load_probe",
    ROOT / "scripts" / "safelibero_aegis_model_load_probe.py",
)
assert SPEC is not None and SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def test_gpu_inventory_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    output = "3, GPU-test, RTX 6000 Ada, 49140, 3, 0\n"
    monkeypatch.setattr(
        probe,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, output, ""),
    )
    assert probe._gpu_inventory() == [
        {
            "index": 3,
            "uuid": "GPU-test",
            "name": "RTX 6000 Ada",
            "memory_total_mib": 49140,
            "memory_used_mib": 3,
            "utilization_percent": 0,
        }
    ]


def test_gpu_process_inventory_handles_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        probe,
        "_run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    assert probe._gpu_compute_processes() == []


def test_protocol_file_digest_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned = tmp_path / "pinned.txt"
    pinned.write_text("original\n", encoding="utf-8")
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    protocol = {
        "sha256": {"pinned.txt": probe.sha256_file(pinned)},
        "implementation": {},
    }
    pinned.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(probe.ModelLoadProbeError, match="digest mismatch"):
        probe._verify_protocol_files(protocol)
