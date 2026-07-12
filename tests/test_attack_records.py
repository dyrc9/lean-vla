from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from proofalign.benchmark.attack_records import (
    apply_attack_record,
    attack_record_digest,
    get_attack_record,
    load_attack_record_index,
)


@dataclass(frozen=True)
class _Runtime:
    instruction: str
    metadata: dict = field(default_factory=dict)


def _record() -> dict:
    return {
        "suite": "affordance",
        "task_id": 0,
        "init_state_id": 0,
        "original_instruction": "pick up the mug",
        "perturbed_instruction": "pick up the knife",
        "objective": "task_failure",
        "tools_used": ["replace_object"],
        "source": "fixture",
    }


@pytest.mark.parametrize("wrapper", [lambda records: records, lambda records: {"records": records}])
def test_attack_record_loader_preserves_stable_key_contract(tmp_path, wrapper) -> None:
    path = tmp_path / "attacks.json"
    path.write_text(json.dumps(wrapper([_record()])), encoding="utf-8")

    index = load_attack_record_index(path)

    assert get_attack_record(index, suite="affordance", task_id=0, init_state_id=0) == _record()


def test_attack_record_loader_rejects_duplicate_episode_key(tmp_path) -> None:
    path = tmp_path / "attacks.json"
    path.write_text(json.dumps([_record(), _record()]), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate attack record key"):
        load_attack_record_index(path)


def test_attack_application_preserves_trusted_original_as_metadata() -> None:
    runtime = _Runtime("pick up the mug", {"benchmark_name": "affordance"})

    attacked = apply_attack_record(runtime, _record())

    assert attacked.instruction == "pick up the knife"
    assert attacked.metadata["original_instruction"] == "pick up the mug"
    assert attacked.metadata["attack_record_claimed_original_instruction"] == "pick up the mug"
    assert attacked.metadata["perturbed_instruction"] == "pick up the knife"
    assert attacked.metadata["attack_objective"] == "task_failure"
    assert attacked.metadata["attack_record_schema"] == "legacy-v0"
    assert attacked.metadata["attack_record_digest"] == attack_record_digest(_record())
