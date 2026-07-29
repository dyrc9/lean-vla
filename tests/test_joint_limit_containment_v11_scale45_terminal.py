from __future__ import annotations

from pathlib import Path

from proofalign.benchmark.confirmatory import load_json_object
from scripts.freeze_joint_limit_containment_v11_scale45_terminal import (
    OUTPUT_PATH,
    _exact_two_sided_binomial_p,
    build_summary,
)


def test_exact_paired_test_examples() -> None:
    assert _exact_two_sided_binomial_p(0, 0) == 1.0
    assert _exact_two_sided_binomial_p(15, 1) == (
        0.000518798828125
    )
    assert _exact_two_sided_binomial_p(11, 0) == 0.0009765625


def test_scale45_terminal_is_current_when_present() -> None:
    if not Path(OUTPUT_PATH).is_file():
        return
    retained = load_json_object(OUTPUT_PATH)
    rebuilt = build_summary()
    assert retained == rebuilt
    assert retained["mechanism_decision"][
        "first_hit_prevention_claim"
    ] is False
    assert set(retained["conditions"]) == {"clean", "attacked"}
    assert all(
        value["data_integrity"]["episode_count"] == 180
        for value in retained["conditions"].values()
    )
