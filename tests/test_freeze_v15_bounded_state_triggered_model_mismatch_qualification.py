from __future__ import annotations

from scripts import (
    freeze_v15_bounded_state_triggered_model_mismatch_qualification as freezer,
)


def test_freezer_adds_prior_v15_8_population() -> None:
    assert freezer.OLD_QUALIFICATION_PROTOCOL in (
        freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert freezer.ABORTED_FRESH1_PROTOCOL in (
        freezer.PRIOR_POPULATION_PROTOCOLS
    )
    assert freezer.FRESH2_PROTOCOL in freezer.PRIOR_POPULATION_PROTOCOLS
    assert freezer.FRESH3_PROTOCOL in freezer.PRIOR_POPULATION_PROTOCOLS


def test_freezer_declares_new_selection_salt() -> None:
    assert "v15-11" in freezer.SELECTION_SALT
    assert "v15-11" in freezer.PROTOCOL_ID
    assert "fresh4" in freezer.PROTOCOL_ID
