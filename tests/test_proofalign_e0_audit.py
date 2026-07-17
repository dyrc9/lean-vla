from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.audit_proofalign_e0 import (
    E0AuditError,
    _match_task_file,
    validate_protocol_structure,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = REPO_ROOT / "experiments" / "proofalign_e0_protocol.json"


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_e0_protocol_classifies_every_task_once_and_freezes_zero_pilot() -> None:
    expanded = validate_protocol_structure(_protocol())

    assert len(expanded["universe"]) == 75
    assert len(expanded["structural"]) == 13
    assert len(expanded["supported"]) == 0
    assert len(expanded["ambiguous"]) == 3
    assert len(expanded["unsupported"]) == 72


def test_e0_protocol_keeps_structural_compile_separate_from_support() -> None:
    protocol = _protocol()
    expanded = validate_protocol_structure(protocol)
    compiled_but_unsupported = {
        (suite, task_id)
        for suite, task_ids in protocol["classification"][
            "unsupported_but_structurally_compiled"
        ].items()
        for task_id in task_ids
    }

    assert len(compiled_but_unsupported) == 10
    assert compiled_but_unsupported <= expanded["structural"]
    assert not (compiled_but_unsupported & expanded["supported"])


def test_e0_protocol_rejects_overlap() -> None:
    protocol = _protocol()
    protocol["classification"]["supported"] = {"affordance": [0]}

    with pytest.raises(E0AuditError, match="overlaps"):
        validate_protocol_structure(protocol)


def test_e0_protocol_requires_pilot_to_equal_supported_set() -> None:
    protocol = _protocol()
    protocol["e1"]["pilot_units"] = [
        {"suite": "affordance", "task_id": 0, "init_state_id": 0}
    ]

    with pytest.raises(E0AuditError, match="pilot units"):
        validate_protocol_structure(protocol)


def test_bddl_file_resolution_allows_unique_upstream_name_drift(tmp_path: Path) -> None:
    directory = tmp_path / "L2"
    directory.mkdir()
    shortened = directory / "place_the_knife_on_the_cabinet.bddl"
    shortened.write_text("(:language place the knife on the cabinet)", encoding="utf-8")

    resolved = _match_task_file(
        directory,
        "place_the_knife_on_the_cabinet_so_it_is_easy_to_grab",
        ".bddl",
    )

    assert resolved == shortened
