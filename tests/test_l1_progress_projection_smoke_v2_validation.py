from __future__ import annotations

from scripts.validate_four_arm_v4_l1_progress_projection_smoke_v2 import (
    normalize_json_types,
)


def test_json_normalization_converts_nested_tuples_only() -> None:
    source = {
        "command_shape": (10, 7),
        "hard_violation_atoms": ("release_command_missing",),
        "nested": [{"empty": ()}],
    }

    assert normalize_json_types(source) == {
        "command_shape": [10, 7],
        "hard_violation_atoms": ["release_command_missing"],
        "nested": [{"empty": []}],
    }
