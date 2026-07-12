from __future__ import annotations

from scripts.remote_gpu_preflight import parse_gpu_inventory, validate_gpu_selection


def test_parse_gpu_inventory_uses_physical_indices() -> None:
    inventory = parse_gpu_inventory(
        "4, NVIDIA H100 80GB HBM3, 81559, 575.57.08\n"
        "5, NVIDIA H100 80GB HBM3, 81559, 575.57.08\n"
    )

    assert inventory == [
        {
            "index": 4,
            "name": "NVIDIA H100 80GB HBM3",
            "memory_total_mib": "81559",
            "driver_version": "575.57.08",
        },
        {
            "index": 5,
            "name": "NVIDIA H100 80GB HBM3",
            "memory_total_mib": "81559",
            "driver_version": "575.57.08",
        },
    ]


def test_validate_gpu_selection_fails_closed_for_missing_or_visible_relative_id() -> None:
    inventory = parse_gpu_inventory("4, H100, 81559, 575.57.08\n5, H100, 81559, 575.57.08")

    blockers, warnings = validate_gpu_selection(inventory, "0", None)

    assert "VLA_GPU=0 is absent from nvidia-smi physical GPU inventory" in blockers
    assert "EGL_GPU is not set" in blockers
    assert warnings == []


def test_validate_gpu_selection_warns_when_policy_and_egl_share_gpu() -> None:
    inventory = parse_gpu_inventory("2, A100, 81920, 570.1")

    blockers, warnings = validate_gpu_selection(inventory, "2", "2")

    assert blockers == []
    assert warnings == [
        "VLA and MuJoCo EGL share one physical GPU; verify memory headroom"
    ]
