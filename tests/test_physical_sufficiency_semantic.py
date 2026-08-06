from __future__ import annotations

from types import SimpleNamespace

from proofalign.integrity_v4_runtime import (
    ExecutionEvaluation,
    TransactionVerdict,
)
from proofalign.physical_sufficiency_semantic import (
    ADVISORY_UNKNOWN_PREFIX,
    PHYSICAL_SUFFICIENCY_CHECKER_VERSION,
    PhysicalSufficiencyCandidatePolicy,
    PhysicalSufficiencyPrefixDispatchBoundary,
    PhysicalSufficiencySemanticExecutablePrefixChecker,
    physical_sufficiency_effect_evaluation,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)
from scripts import run_l2_execution_attack_eval_v9 as v9
from scripts import run_l2_execution_attack_eval_v10 as v10


def _observation() -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.3),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("flat_stove_1", (0.2, 0.0, 0.3)),
            EntityPosition("obstacle_1", (0.8, 0.8, 0.3)),
        ),
    )


def _command(value: float = 0.01) -> tuple[float, ...]:
    return (value, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0) * 10


def test_articulation_unknown_runs_physical_sufficiency_screen() -> None:
    checker = PhysicalSufficiencySemanticExecutablePrefixChecker()
    result = checker.assess(
        semantic_subtask="actuate(flat_stove_1,turn_on)",
        observation=_observation(),
        command=_command(),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert result.known is True
    assert result.semantic_compatible is True
    assert result.violation_atoms == ()
    assert result.predicted_effect_atoms == ()
    assert (
        f"{ADVISORY_UNKNOWN_PREFIX}"
        "trusted_articulation_state_unavailable"
    ) in result.precondition_atoms
    assert checker.config.__class__.__name__ == (
        "PhysicalSufficiencyLocalCheckerConfig"
    )
    assert PHYSICAL_SUFFICIENCY_CHECKER_VERSION == "7"


def test_articulation_unknown_keeps_velocity_gate_hard() -> None:
    checker = PhysicalSufficiencySemanticExecutablePrefixChecker()
    result = checker.assess(
        semantic_subtask="actuate(flat_stove_1,turn_on)",
        observation=_observation(),
        command=_command(2.0),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert result.known is True
    assert result.semantic_compatible is False
    assert "translation_velocity_limit" in result.violation_atoms


def test_soft_observed_move_predicate_replans_but_cost_is_hard() -> None:
    soft = physical_sufficiency_effect_evaluation(
        ExecutionEvaluation(
            TransactionVerdict.REJECT,
            ("observer violations: target_not_held_after_move",),
        )
    )
    cost = physical_sufficiency_effect_evaluation(
        ExecutionEvaluation(
            TransactionVerdict.REJECT,
            ("observer violations: cost",),
        )
    )
    incomplete = physical_sufficiency_effect_evaluation(
        ExecutionEvaluation(
            TransactionVerdict.REJECT,
            ("authorized prefix was not completely consumed",),
        )
    )

    assert soft.verdict is TransactionVerdict.ALLOW
    assert soft.issues == (
        "advisory_replan:observer violations: "
        "target_not_held_after_move",
    )
    assert cost.verdict is TransactionVerdict.REJECT
    assert incomplete.verdict is TransactionVerdict.REJECT


def test_v10_patches_v9_runtime_symbols(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_v9_run_episode(**_kwargs: object) -> dict[str, object]:
        observed["candidate"] = v9.RiskSelectiveCandidatePolicy
        observed["bindings"] = (
            v9.patched_risk_selective_wrapper_bindings
        )
        observed["boundary"] = (
            v9.RiskSelectivePrefixDispatchBoundary
        )
        return {"metadata": {}}

    monkeypatch.setattr(v9, "run_episode", fake_v9_run_episode)
    monkeypatch.setattr(v10.v1, "_persist_annotated_episode", lambda _: None)
    payload = v10.run_episode(
        args=SimpleNamespace(
            l1_semantic_alignment="on",
            l2_execution_integrity="on",
            semantic_runtime=True,
        )
    )

    assert observed["candidate"] is PhysicalSufficiencyCandidatePolicy
    assert observed["boundary"] is (
        PhysicalSufficiencyPrefixDispatchBoundary
    )
    assert (
        observed["bindings"]
        is v10.patched_physical_sufficiency_wrapper_bindings
    )
    assert payload["metadata"]["runner_variant"] == v10.RUNNER_VARIANT
