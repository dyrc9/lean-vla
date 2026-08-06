from __future__ import annotations

from scripts.monitor_and_launch_m2_victim import (
    PROJECT_PYTHON,
    qualified_gpu_indices,
    runner_command,
)


def _protocol() -> dict:
    return {
        "resource_budget": {
            "policy_gpu_count": 1,
            "egl_gpu_count": 1,
            "selected_gpu_prelaunch_memory_used_mib_max_exclusive": 1000,
        }
    }


def test_launcher_selects_lowest_two_qualified_gpu_indices() -> None:
    inventory = [
        {"index": 4, "memory_used_mib": 100},
        {"index": 0, "memory_used_mib": 3},
        {"index": 2, "memory_used_mib": 999},
        {"index": 1, "memory_used_mib": 1000},
    ]

    assert qualified_gpu_indices(_protocol(), inventory) == [0, 2]


def test_launcher_builds_explicit_victim_gpu_command() -> None:
    command = runner_command(
        "--preflight",
        gpu_indices=[0, 2],
    )

    assert command[0] == str(PROJECT_PYTHON)
    assert "--protocol" in command
    assert "--output-root" in command
    assert command[-5:] == [
        "--preflight",
        "--policy-gpu",
        "0",
        "--egl-gpu",
        "2",
    ]
