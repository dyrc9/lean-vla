from __future__ import annotations

from scripts.generate_semantic_source_binding_e8 import (
    DEFAULT_PACKET,
    build_report,
    canonical_text,
)


def test_e8_source_binding_audit_is_current_and_read_only() -> None:
    report = build_report()

    assert report["commit_scope_complete"] is True
    assert report["evidence_inventory_complete"] is True
    assert report["openpi_binding"]["tracked_worktree_clean"] is True
    assert report["not_bound_path_count"] == len(
        report["not_bound_paths"]
    )
    assert report["clean_commit_bound"] is (
        report["commit_scope_bound_to_head"]
        and report["evidence_inventory_complete"]
        and report["openpi_binding"]["tracked_worktree_clean"]
    )
    assert report["classification"] == (
        "semantic_source_binding_clean"
        if report["clean_commit_bound"]
        else "semantic_source_binding_not_clean"
    )
    assert report["outcomes_observed_or_generated"] is False
    assert report["policy_loaded"] is False
    assert report["simulator_created"] is False
    assert report["actions_dispatched"] is False
    assert DEFAULT_PACKET.read_text(
        encoding="utf-8"
    ) == canonical_text(report)
