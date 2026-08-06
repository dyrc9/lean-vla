from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_contact_phase_pick_up_qualification import (
    OUTPUT_PATH,
    build_protocol,
)
from scripts.run_contact_phase_pick_up_qualification import (
    build_result,
)


def test_contact_phase_qualification_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    result = build_result(retained, protocol_path=OUTPUT_PATH)
    assert result["qualification_pass"] is True
    assert result["aggregate"][
        "recovered_unique_source_block_count"
    ] == 2
    assert result["aggregate"][
        "recovered_hard_violation_atom_count"
    ] == 0
    assert result["aggregate"]["command_change_count"] == 0
