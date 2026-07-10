from __future__ import annotations

from proofalign.checker import _lean_nat_lower, _lean_nat_upper


def test_outward_rounding_never_rounds_measurement_toward_safety() -> None:
    assert _lean_nat_lower(0.209) == "20"
    assert _lean_nat_upper(0.209) == "21"


def test_outward_rounding_is_conservative_at_threshold_boundary() -> None:
    measured = int(_lean_nat_lower(0.200_001))
    required = int(_lean_nat_upper(0.200_001))

    assert measured == 20
    assert required == 21
    assert measured < required


def test_nonfinite_measurements_and_requirements_fail_closed() -> None:
    assert _lean_nat_lower(float("nan")) == "0"
    assert _lean_nat_lower(float("inf")) == "0"
    assert int(_lean_nat_upper(float("nan"))) > 0
    assert int(_lean_nat_upper(float("inf"))) > 0


def test_negative_values_are_clamped_to_nat_zero() -> None:
    assert _lean_nat_lower(-0.5) == "0"
    assert _lean_nat_upper(-0.5) == "0"
