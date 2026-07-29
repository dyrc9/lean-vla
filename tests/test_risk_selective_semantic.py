from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from proofalign.integrity_v4_runtime import (
    ExecutionEvaluation,
    TransactionVerdict,
)
from proofalign.risk_selective_semantic import (
    RISK_SELECTIVE_CHECKER_VERSION,
    RiskSelectiveCandidatePolicy,
    RiskSelectiveSemanticExecutablePrefixChecker,
    RiskSelectiveSemanticPolicyWrapper,
    is_physical_risk_atom,
    patched_risk_selective_wrapper_bindings,
    risk_selective_effect_evaluation,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)
from proofalign.semantic_policy_wrapper import PolicyPromptMode
from proofalign.digests import digest_payload
from scripts import run_l2_execution_attack_eval as v1
from scripts import run_l2_execution_attack_eval_v6 as v6
from scripts import run_l2_execution_attack_eval_v8 as v8
from scripts import run_l2_execution_attack_eval_v9 as v9


def _observation(
    *,
    eef: tuple[float, float, float] = (0.0, 0.0, 0.30),
    target: tuple[float, float, float] = (0.20, 0.0, 0.30),
    destination: tuple[float, float, float] = (0.50, 0.0, 0.30),
    closed: bool = False,
    extra: tuple[EntityPosition, ...] = (),
) -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=0,
        eef_position=eef,
        gripper_qpos=(
            (0.0, 0.0) if closed else (0.04, -0.04)
        ),
        entity_positions=(
            EntityPosition("target_1", target),
            EntityPosition("plate_1", destination),
            *extra,
        ),
    )


def _command(
    *,
    translation: float = -0.10,
    gripper: float = -1.0,
) -> np.ndarray:
    return np.asarray(
        (
            translation,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            gripper,
        )
        * 10,
        dtype=np.float64,
    ).reshape(10, 7)


def test_risk_selective_checker_demotes_soft_progress_not_contact() -> None:
    checker = RiskSelectiveSemanticExecutablePrefixChecker()
    soft = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=_observation(),
        command=tuple(_command().reshape(-1)),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )
    contact = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=_observation(
            extra=(
                EntityPosition(
                    "left_hand_1", (-0.025, 0.0, 0.30)
                ),
            )
        ),
        command=tuple(_command().reshape(-1)),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert soft.known is True
    assert soft.semantic_compatible is True
    assert soft.violation_atoms == ()
    assert soft.progress_margin == checker.config.min_progress_m
    assert contact.semantic_compatible is False
    assert any(
        atom.startswith("unexpected_contact_neighborhood:")
        for atom in contact.violation_atoms
    )
    assert all(
        is_physical_risk_atom(atom)
        for atom in contact.violation_atoms
    )
    assert checker.config.__class__.__name__ == (
        "RiskSelectiveLocalCheckerConfig"
    )
    assert RISK_SELECTIVE_CHECKER_VERSION == "6"


def test_risk_selective_candidate_returns_exact_source_block() -> None:
    command = _command()

    class Inner:
        _rng = None

        def infer(self, _element: dict[str, object]) -> dict[str, object]:
            return {"actions": command.copy()}

    policy = RiskSelectiveCandidatePolicy(
        Inner(), candidate_count=1, replan_steps=10
    )
    policy.wrapper = SimpleNamespace(
        checker=RiskSelectiveSemanticExecutablePrefixChecker(),
        min_progress_margin=0.002,
        max_projection_l2=0.5,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            selected_subtask="pick_up(target_1)",
            artifact_digest="a" * 64,
        ),
        local_observation=_observation(),
        context=SimpleNamespace(state_epoch=0),
        release_destination=None,
    )

    result = policy.infer({})

    assert np.array_equal(result["actions"], command)
    audit = policy.audits[-1]
    assert audit["eligible_selected_source_candidate_index"] == 0
    assert audit["risk_selective"][
        "nominal_command_changed"
    ] is False
    assert audit["returned_action_chunk_sha256"] == audit[
        "returned_source_policy_chunk_sha256"
    ]


def test_risk_selective_candidate_marks_physical_risk_ineligible() -> None:
    command = _command()

    class Inner:
        _rng = None

        def infer(self, _element: dict[str, object]) -> dict[str, object]:
            return {"actions": command.copy()}

    policy = RiskSelectiveCandidatePolicy(
        Inner(), candidate_count=1, replan_steps=10
    )
    policy.wrapper = SimpleNamespace(
        checker=RiskSelectiveSemanticExecutablePrefixChecker(),
        min_progress_margin=0.002,
        max_projection_l2=0.5,
    )
    policy.request = SimpleNamespace(
        artifact=SimpleNamespace(
            selected_subtask="pick_up(target_1)",
            artifact_digest="a" * 64,
        ),
        local_observation=_observation(
            extra=(
                EntityPosition(
                    "left_hand_1", (-0.025, 0.0, 0.30)
                ),
            )
        ),
        context=SimpleNamespace(state_epoch=0),
        release_destination=None,
    )

    result = policy.infer({})

    # The candidate layer preserves provenance. The existing outer semantic
    # authorization rechecks this exact block and fails closed.
    assert np.array_equal(result["actions"], command)
    audit = policy.audits[-1]
    assert audit["eligible_selected_source_candidate_index"] is None
    assert audit["fallback_for_fail_closed_recheck"] is True
    assert audit["selection_reason"] == (
        "risk_selective_physical_gate_rejected"
    )
    assert audit["risk_selective"]["physical_risk_atoms"]


def test_risk_selective_effect_miss_replans_but_violation_rejects() -> None:
    missing = risk_selective_effect_evaluation(
        ExecutionEvaluation(
            TransactionVerdict.REJECT,
            ("expected effects missing: pick_up_prefix_progress",),
        )
    )
    violation = risk_selective_effect_evaluation(
        ExecutionEvaluation(
            TransactionVerdict.REJECT,
            ("observer violations: cost",),
        )
    )

    assert missing.verdict is TransactionVerdict.ALLOW
    assert missing.issues == (
        "advisory_replan:expected effects missing: "
        "pick_up_prefix_progress",
    )
    assert violation.verdict is TransactionVerdict.REJECT


def test_risk_selective_wrapper_preserves_full_task_and_fallback() -> None:
    bddl = """
    (define (problem test)
      (:goal (And (On target_1 plate_1)))
    )
    """
    full_task = "pick up target and put it on the plate"
    with patched_risk_selective_wrapper_bindings():
        wrapper = RiskSelectiveSemanticPolicyWrapper(
            episode_nonce="episode",
            trusted_task=full_task,
            bddl_text=bddl,
            prompt_mode=PolicyPromptMode.DEPLOYMENT,
        )
        normal = wrapper.begin_policy_call(
            proposal_index=0,
            local_observation=_observation(),
            trusted_observation_digest=digest_payload("normal"),
            external_policy_prompt=full_task,
            generated_at_ns=1,
        )
        finished = wrapper.begin_policy_call(
            proposal_index=1,
            local_observation=_observation(
                target=(0.50, 0.0, 0.30),
                destination=(0.50, 0.0, 0.30),
            ),
            trusted_observation_digest=digest_payload("finished"),
            external_policy_prompt=full_task,
            generated_at_ns=2,
        )

    assert normal.request is not None
    assert normal.request.exact_policy_prompt == full_task
    assert finished.request is not None
    assert finished.request.exact_policy_prompt == full_task
    assert finished.reason.startswith(
        "risk_selective_fallback_from_"
    )


def test_v9_patches_the_runtime_successor_symbols(
    monkeypatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_v8_run_episode(**_kwargs: object) -> dict[str, object]:
        observed["candidate"] = (
            v8.ContactPhaseReleaseH4CandidatePolicy
        )
        observed["wrapper"] = v6.H4ReleaseSemanticPolicyWrapper
        observed["boundary"] = v1.SingleUsePrefixDispatchBoundary
        return {"metadata": {}}

    monkeypatch.setattr(v8, "run_episode", fake_v8_run_episode)
    monkeypatch.setattr(v1, "_persist_annotated_episode", lambda _: None)
    payload = v9.run_episode(
        args=SimpleNamespace(
            l1_semantic_alignment="on",
            l2_execution_integrity="on",
            semantic_runtime=True,
        )
    )

    assert observed == {
        "candidate": RiskSelectiveCandidatePolicy,
        "wrapper": RiskSelectiveSemanticPolicyWrapper,
        "boundary": v9.RiskSelectivePrefixDispatchBoundary,
    }
    assert payload["metadata"]["runner_variant"] == v9.RUNNER_VARIANT
    assert payload["metadata"][
        "online_progress_projection_active"
    ] is False
