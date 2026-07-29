from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_contact_phase_pick_up_scale45_cotenant import (
    MEMORY_USED_LIMIT_MIB,
    OUTPUT_PATH,
    PREDECESSOR_PATH,
    build_protocol,
)
from scripts.run_contact_phase_pick_up_clean_pilot import (
    build_specs,
    validate_protocol,
)


def test_scale45_cotenant_changes_only_resource_context() -> None:
    predecessor = load_json_object(PREDECESSOR_PATH)
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)

    assert retained["schedule"] == predecessor["schedule"]
    assert retained["schedule_sha256"] == predecessor["schedule_sha256"]
    assert retained["workloads"] == predecessor["workloads"]
    assert retained["design"] == predecessor["design"]
    assert retained["gates"] == predecessor["gates"]
    assert retained["victim"] == predecessor["victim"]
    assert retained["episode_constants"] == predecessor[
        "episode_constants"
    ]
    assert retained["resource_gate"][
        "selected_gpu_memory_used_mib_max_exclusive"
    ] == MEMORY_USED_LIMIT_MIB
    assert retained["co_tenant_resource_exception"][
        "outcome_or_safety_gate_changed"
    ] is False


def test_scale45_cotenant_protocol_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_protocol(
        created_at=retained["created_at"],
        source_commit=retained["source"]["repository_commit"],
    )

    assert retained == rebuilt
    validate_protocol(retained, protocol_path=OUTPUT_PATH)
    assert len(build_specs(retained)) == 180
