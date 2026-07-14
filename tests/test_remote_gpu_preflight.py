from __future__ import annotations

from pathlib import Path

import scripts.remote_gpu_preflight as preflight
from scripts.remote_gpu_preflight import (
    CommandResult,
    git_snapshot,
    parse_gpu_inventory,
    parse_libero_config_paths,
    validate_libero_config_paths,
    validate_gpu_selection,
)


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


def test_git_snapshot_rejects_parent_repository_as_nested_checkout(
    monkeypatch, tmp_path: Path
) -> None:
    nested = tmp_path / "external" / "LIBERO-Safety"
    nested.mkdir(parents=True)

    def fake_run_command(argv, *, cwd=None, timeout_seconds=120.0):
        assert tuple(argv) == ("git", "rev-parse", "--show-toplevel")
        assert cwd == nested
        return CommandResult(tuple(argv), 0, str(tmp_path), "")

    monkeypatch.setattr(preflight, "run_command", fake_run_command)

    snapshot = git_snapshot(nested)

    assert snapshot["head"] is None
    assert snapshot["top_level"] == str(tmp_path)
    assert "does not match requested checkout" in snapshot["error"]


def test_validate_libero_config_paths_rejects_standard_libero_root(
    tmp_path: Path,
) -> None:
    safety_root = tmp_path / "LIBERO-Safety"
    standard_root = tmp_path / "LIBERO"
    config_path = tmp_path / "config.yaml"
    text = "\n".join(
        (
            f"benchmark_root: {standard_root}/libero/libero",
            f"bddl_files: {standard_root}/libero/libero/bddl_files",
            f"init_states: {standard_root}/libero/libero/init_files",
            f"datasets: {standard_root}/libero/datasets",
            f"assets: {standard_root}/libero/libero/assets",
        )
    )

    blockers = validate_libero_config_paths(
        parse_libero_config_paths(text),
        config_path=config_path,
        libero_root=safety_root,
    )

    assert len(blockers) == 5
    assert all("points outside the selected LIBERO-Safety checkout" in item for item in blockers)


def test_parse_args_uses_isolated_libero_config_path(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LIBERO_CONFIG_PATH", str(tmp_path))

    args = preflight.parse_args(["--output", str(tmp_path / "preflight.json")])

    assert args.libero_config == str(tmp_path / "config.yaml")
