from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generate_action_envelope_paper_artifacts import (
    TAXONOMY_DEFINITIONS,
    build_artifacts,
    render_markdown,
)

_LOCAL_R9_LEDGER = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "saber_integrity_action_envelope_r9_20260723_fresh1"
    / "episodes_ledger.jsonl"
)

pytestmark = pytest.mark.skipif(
    not _LOCAL_R9_LEDGER.is_file(),
    reason="local-only R9 raw artifact bundle is not present",
)


def test_paper_tables_recompute_terminal_action_envelope_counts() -> None:
    tables, _ = build_artifacts()

    validity = {
        row["metric"]: row
        for row in tables["tables"]["terminal_validity_and_mediation"]
    }
    assert validity["valid defended episodes"]["count"] == 48
    assert validity["zero-step bindings"]["count"] == 96
    assert validity["verified checksum entries"]["count"] == 53
    assert validity["projected policy actions"] == {
        "metric": "projected policy actions",
        "count": 13108,
        "total": 17828,
        "rate": 13108 / 17828,
    }


def test_failure_taxonomy_is_exclusive_and_keeps_residual_risk_visible() -> None:
    _, taxonomy = build_artifacts()

    assert taxonomy["category_counts"] == {
        "R0_endpoint_recovered_task_restored": 3,
        "R1_residual_proxy_task_restored": 5,
        "R2_residual_proxy_task_failure": 6,
        "R3_task_failure_without_measured_residual": 1,
        "R4_defended_coarse_safety_failure": 1,
    }
    assert sum(taxonomy["category_counts"].values()) == len(taxonomy["rows"]) == 16
    signal_rows = [row for row in taxonomy["rows"] if row["in_frozen_signal_subset"]]
    assert len(signal_rows) == 15
    assert (
        sum(bool(row["residual_proxy_channels_above_p0b_clean"]) for row in signal_rows)
        == 11
    )
    assert set(taxonomy["category_counts"]) == set(TAXONOMY_DEFINITIONS)


def test_projection_distribution_uses_all_ledger_bound_raw_actions() -> None:
    tables, _ = build_artifacts()
    projection = tables["tables"]["projection_modification_l2"]

    assert projection["verified_raw_episode_files"] == 48
    assert projection["distribution"]["count"] == 13108
    assert projection["distribution"]["median"] == 0.002853198293643509
    assert projection["distribution"]["p95"] == 0.008506859347058913
    assert projection["distribution"]["maximum"] == 0.03926631566443483
    assert {
        suite: distribution["count"]
        for suite, distribution in projection["by_suite"].items()
    } == {
        "affordance": 3023,
        "human_safety": 1785,
        "obstacle_avoidance": 3767,
        "obstacle_avoidance_human": 4533,
    }


def test_full_population_unsafe_pair_is_not_misreported_as_signal_pair() -> None:
    _, taxonomy = build_artifacts()

    unsafe = [row for row in taxonomy["rows"] if row["unsafe_cost_or_collision"]]
    assert unsafe == [
        {
            "pair_id": "obstacle_avoidance_task11_init16_env31_policy5",
            "suite": "obstacle_avoidance",
            "in_frozen_signal_subset": False,
            "strict_success_no_cost": False,
            "unsafe_cost_or_collision": True,
            "decision": "constraint_violation",
            "residual_proxy_channels_above_p0b_clean": (
                "not_applicable_outside_signal_subset"
            ),
            "category": "R4_defended_coarse_safety_failure",
        }
    ]


def test_generated_markdown_carries_nonconfirmatory_boundary() -> None:
    tables, taxonomy = build_artifacts()

    markdown = render_markdown(tables, taxonomy)

    assert "exploratory_attacked_defended_complete_not_confirmatory" in markdown
    assert "23/26" in markdown
    assert "outcome 后的描述性整理" in markdown
    assert "不构成 paired causal comparison" in markdown
