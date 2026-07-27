from __future__ import annotations

from scripts.validate_semantic_post_e5_readiness import (
    DEFAULT_PACKET,
    build_report,
    canonical_text,
)
from scripts.run_semantic_resource_smoke_e6 import (
    AUTHORIZED_PROTOCOL_PATH as E6_AUTHORIZED_PROTOCOL_PATH,
)


def test_post_e5_readiness_packet_is_current_and_no_outcome() -> None:
    report = build_report()

    assert report["no_outcome_stack_complete"] is True
    assert (
        report["benchmark_privileged_geometry_stack_qualified"]
        is True
    )
    assert report["deployment_stack_qualified"] is False
    assert report["outcome_rollout_ready"] is False
    assert report["outcome_rollout_authorized"] is False
    assert report["outcomes_observed_or_generated"] is False
    assert all(
        component["complete"]
        for component in report["components"].values()
    )
    e6 = report["components"]["e6_resource_smoke_preregistration"]
    assert e6["executor_ready"] is True
    assert e6["authorized_successor_protocol_absent"] is (
        not E6_AUTHORIZED_PROTOCOL_PATH.exists()
    )
    if E6_AUTHORIZED_PROTOCOL_PATH.exists():
        assert e6["execution_authorized"] is True
        assert e6["measurement_complete"] is True
        assert e6["measurement_qualified"] is True
        assert e6["classification"] == (
            "semantic_resource_smoke_qualified"
        )
    else:
        assert e6["execution_authorized"] is False
        assert e6["measurement_complete"] is False
        assert e6["authorized_successor_output_root_absent"] is True
    e7 = report["components"][
        "e7_deployment_perception_data_audit"
    ]
    assert e7["supervision_contract_current"] is True
    assert e7["dataset_qualification_runner_ready"] is True
    assert e7["qualification_ready"] is False
    e8 = report["components"]["e8_source_binding_audit"]
    assert e8["complete"] is True
    assert e8["commit_scope_complete"] is True
    assert e8["evidence_inventory_complete"] is True
    assert e8["openpi_tracked_worktree_clean"] is True
    assert e8["classification"] == (
        "semantic_source_binding_clean"
        if e8["clean_commit_bound"]
        else "semantic_source_binding_not_clean"
    )
    assert DEFAULT_PACKET.read_text(
        encoding="utf-8"
    ) == canonical_text(report)
