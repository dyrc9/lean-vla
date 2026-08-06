from __future__ import annotations

from pathlib import Path

from scripts import run_four_arm_v4_l1_repair_qualification_v2 as v2


def test_v2_preflight_adds_exact_runtime_device_mapping(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        v2,
        "_BASE_PREFLIGHT",
        lambda protocol, protocol_path, gpu: {
            "schema": "v1",
            "ready": True,
            "blockers": [],
        },
    )
    expected = {
        "selected_cuda_physical_index": 3,
        "selected_egl_device_ordinal": 3,
    }
    monkeypatch.setattr(
        v2,
        "_runtime_device_state",
        lambda gpu: expected,
    )

    report = v2.preflight({}, protocol_path=Path("protocol.json"), gpu=3)

    assert report["ready"]
    assert report["runtime_device"] is expected
    assert report["schema"].endswith(".v2")


def test_v2_preflight_fails_closed_on_runtime_mapping_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        v2,
        "_BASE_PREFLIGHT",
        lambda protocol, protocol_path, gpu: {
            "schema": "v1",
            "ready": True,
            "blockers": [],
        },
    )

    def fail(_gpu: int) -> dict:
        raise v2.RepairQualificationV2Error("mapping differs")

    monkeypatch.setattr(v2, "_runtime_device_state", fail)

    report = v2.preflight({}, protocol_path=Path("protocol.json"), gpu=3)

    assert not report["ready"]
    assert report["runtime_device"] is None
    assert "mapping differs" in report["blockers"][0]


def test_v2_args_use_frozen_egl_ordinal(monkeypatch, tmp_path) -> None:
    sentinel = object()
    args = type("Args", (), {"render_gpu_device_id": 0})()
    monkeypatch.setattr(
        v2,
        "_BASE_ARGS",
        lambda protocol, output_root: (
            args if protocol is sentinel else None
        ),
    )
    monkeypatch.setattr(
        v2,
        "_DEVICE_STATE",
        {"selected_egl_device_ordinal": 3},
    )

    observed = v2._args(sentinel, output_root=tmp_path)

    assert observed is args
    assert observed.render_gpu_device_id == 3
