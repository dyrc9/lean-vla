from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofalign.models import SafetySpec, WorldState


ROOT = Path(__file__).resolve().parents[1]


def example_data(name: str) -> dict:
    return json.loads((ROOT / "examples" / "tasks" / name).read_text(encoding="utf-8"))


@pytest.fixture
def safe_state() -> WorldState:
    data = example_data("aag_safe_grasp.json")
    return WorldState.from_dict(data["initial_state"])


@pytest.fixture
def safe_spec() -> SafetySpec:
    data = example_data("aag_safe_grasp.json")
    return SafetySpec.from_dict(data["safety_spec"])
