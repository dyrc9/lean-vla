from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from proofalign.contact_phase_pick_up import (
    CONTACT_PHASE_CHECKER_VERSION,
    ContactPhaseCandidatePolicy,
    ContactPhaseReleaseH4CandidatePolicy,
    ContactPhaseSemanticExecutablePrefixChecker,
    contact_phase_replay_eligible,
)
from proofalign.horizon_consistent_release_h4 import (
    HorizonConsistentReleaseH4CandidatePolicy,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)
from scripts import run_l2_execution_attack_eval_v3 as v3


REPO_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = (
    REPO_ROOT
    / "results"
    / "proofalign_horizon_consistent_v7_four_arm_initial_"
    "20260728_fresh2"
    / "initial_evidence.json"
)


def _observation() -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=0,
        eef_position=(0.0, 0.0, 0.30),
        gripper_qpos=(0.04, -0.04),
        entity_positions=(
            EntityPosition("target_1", (0.03, 0.0, 0.30)),
        ),
    )


def _command(*, close: float, translation: float) -> tuple[float, ...]:
    return (
        (translation, 0.0, 0.0, 0.0, 0.0, 0.0, close)
        * 10
    )


def test_contact_phase_checker_credits_only_compatible_pick_up() -> None:
    checker = ContactPhaseSemanticExecutablePrefixChecker()
    result = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=_observation(),
        command=_command(close=1.0, translation=-0.01),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert result.known is True
    assert result.semantic_compatible is True
    assert result.violation_atoms == ()
    assert result.progress_margin == checker.config.min_progress_m
    assert "pick_up_contact_phase_compatible" in (
        result.precondition_atoms
    )
    assert checker.config.config_digest
    assert CONTACT_PHASE_CHECKER_VERSION == "5"


def test_contact_phase_checker_does_not_credit_noncontact_retreat() -> None:
    checker = ContactPhaseSemanticExecutablePrefixChecker()
    result = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=_observation(),
        command=_command(close=-1.0, translation=-0.01),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert result.semantic_compatible is False
    assert result.progress_margin < checker.config.min_progress_m
    assert "pick_up_contact_phase_compatible" not in (
        result.precondition_atoms
    )


def test_contact_phase_checker_preserves_hard_violation() -> None:
    checker = ContactPhaseSemanticExecutablePrefixChecker()
    result = checker.assess(
        semantic_subtask="pick_up(target_1)",
        observation=_observation(),
        command=_command(close=1.0, translation=2.0),
        command_shape=(10, 7),
        expected_state_epoch=0,
    )

    assert result.semantic_compatible is False
    assert "translation_velocity_limit" in result.violation_atoms


def test_contact_phase_policy_composes_before_h4_release() -> None:
    mro = ContactPhaseReleaseH4CandidatePolicy.mro()

    assert mro.index(HorizonConsistentReleaseH4CandidatePolicy) < (
        mro.index(v3.OnlineProgressProjectionCandidatePolicy)
    )
    assert mro.index(
        __import__(
            "proofalign.contact_phase_pick_up",
            fromlist=["ContactPhaseCandidatePolicy"],
        ).ContactPhaseCandidatePolicy
    ) < mro.index(v3.OnlineProgressProjectionCandidatePolicy)


def test_contact_phase_policy_recovers_exact_unchanged_block() -> None:
    command = np.asarray(
        _command(close=1.0, translation=-0.02),
        dtype=np.float64,
    ).reshape(10, 7)

    class Inner:
        _rng = None

        def infer(self, element: dict[str, object]) -> dict[str, object]:
            return {"actions": command.copy()}

    policy = ContactPhaseCandidatePolicy(
        Inner(),
        candidate_count=1,
        replan_steps=10,
    )
    policy.wrapper = SimpleNamespace(
        checker=ContactPhaseSemanticExecutablePrefixChecker(),
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
    assert audit["contact_phase_bypass"]["authorized"] is True
    assert audit["contact_phase_bypass"]["command_changed"] is False
    assert audit["eligible_selected_source_candidate_index"] == 0
    assert audit["candidates"][0]["progress_projection"]["reason"] == (
        "semantic_projection_budget_exceeded"
    )
    assert audit["candidates"][0]["checked"][
        "eligible_under_fixed_gate"
    ] is True


def test_v7_initial_replay_recovers_only_zero_hard_budget_cases() -> None:
    if not EVIDENCE_PATH.is_file():
        return
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    recovered = []
    hard_recovered = []
    for artifact in evidence["episodes"]:
        episode = json.loads(
            (REPO_ROOT / artifact["path"]).read_text(encoding="utf-8")
        )
        for frame in episode["observation_frame_audits"]:
            audit = frame.get("online_progress_projection_v3")
            if not isinstance(audit, dict):
                continue
            for candidate in audit["candidates"]:
                if contact_phase_replay_eligible(candidate):
                    recovered.append(
                        (
                            episode["metadata"]["benchmark_name"],
                            episode["metadata"]["four_arm_label"],
                        )
                    )
                    if candidate["nominal_checked"][
                        "hard_violation_atoms"
                    ]:
                        hard_recovered.append(candidate)

    assert sorted(recovered) == [
        ("human_safety", "dual"),
        ("human_safety", "semantic_only"),
        ("obstacle_avoidance", "dual"),
        ("obstacle_avoidance", "semantic_only"),
    ]
    assert hard_recovered == []
