from __future__ import annotations

from scripts.monitor_and_launch_contact_phase_scale45 import (
    OPENPI_PYTHON,
    PROTOCOL_PATH,
    RUNNER_PATH,
    qualified_gpu_indices,
    runner_command,
)


def test_scale45_launcher_selects_two_least_used_qualified_gpus() -> None:
    protocol = {
        "resource_gate": {
            "selected_gpu_memory_used_mib_max_exclusive": 1024
        }
    }
    inventory = [
        {"index": 0, "memory_used_mib": 900},
        {"index": 1, "memory_used_mib": 1100},
        {"index": 2, "memory_used_mib": 50},
        {"index": 3, "memory_used_mib": 0},
    ]

    assert qualified_gpu_indices(protocol, inventory) == [3, 2]


def test_scale45_launcher_uses_frozen_protocol_and_openpi_python() -> None:
    command = runner_command(
        "--execute",
        [3, 1],
        python=OPENPI_PYTHON,
    )

    assert command == [
        str(OPENPI_PYTHON),
        str(RUNNER_PATH),
        "--execute",
        "--protocol",
        str(PROTOCOL_PATH),
        "--policy-gpu",
        "3",
        "--egl-gpu",
        "1",
    ]
