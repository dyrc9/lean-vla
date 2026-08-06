from __future__ import annotations

from scripts import run_predictive_virtual_brake_v13_attacked_shadow_only as attacked_shadow


def test_attacked_shadow_patches_inner_metric_source() -> None:
    original = attacked_shadow.attacker.clean._v11_metrics

    with attacked_shadow._patched_attacker():
        assert (
            attacked_shadow.attacker.clean._v11_metrics
            is attacked_shadow._attacked_shadow_metrics
        )
        with attacked_shadow.attacker._patched_inherited():
            assert (
                attacked_shadow.attacker.inherited.base._v10_metrics
                is attacked_shadow._attacked_shadow_metrics
            )

    assert attacked_shadow.attacker.clean._v11_metrics is original


def test_attacked_shadow_enrichment_keeps_claim_exploratory(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        attacked_shadow,
        "_BASE_ATTACK_ENRICH",
        lambda _protocol, evidence: dict(evidence),
    )
    payload = attacked_shadow._attacked_shadow_enrich(
        {},
        {"pilot_complete": True},
    )

    assert payload["pilot_complete"] is True
    assert payload["shadow_only_ablation"] is True
    assert payload["guard_candidate_evaluation_enabled"] is False
    assert payload["guard_intervention_enabled"] is False
    assert payload["efficacy_pass_declared"] is False
    assert payload["confirmatory_claim_authorized"] is False
