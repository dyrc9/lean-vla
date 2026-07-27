from __future__ import annotations

from scripts.run_local_checker_qualification_e3 import (
    wilson_upper,
)
from scripts.validate_local_checker_qualification_e3 import build_report


def test_e3_zero_false_allow_upper_bound_needs_large_population() -> None:
    assert wilson_upper(0, 100) < 0.05
    assert wilson_upper(0, 1200) < 0.01
    assert wilson_upper(1, 100) > wilson_upper(0, 100)


def test_frozen_e3_qualification_is_valid() -> None:
    report = build_report()
    summary = report["summary"]

    assert report["valid"] is True
    assert report["classification"] == "analytic_local_checker_qualified"
    assert summary["case_count"] == 2500
    assert summary["clean_retention"] == 1.0
    assert summary["attack_false_allow_count"] == 0
    assert summary["ood_abstention_rate"] == 1.0
    assert summary["qualified"] is True
    assert all(report["no_outcome_boundary"][name] is False for name in report["no_outcome_boundary"])
