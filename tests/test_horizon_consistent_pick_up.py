from __future__ import annotations

from types import SimpleNamespace

from proofalign.horizon_consistent_pick_up import (
    HORIZON_CHECKER_VERSION,
    HORIZON_EFFECT_OBSERVER_VERSION,
    HorizonConsistentSemanticExecutablePrefixChecker,
    HorizonConsistentSemanticPrefixEffectObserver,
    PICK_UP_PREFIX_PROGRESS_EFFECT,
    patched_semantic_wrapper_bindings,
)
from proofalign.semantic_local_checker import (
    EntityPosition,
    TrustedLocalObservation,
)
from proofalign.semantic_policy_wrapper import (
    TrustedSemanticPolicyWrapper,
)
from scripts import run_l2_execution_attack_eval_v4 as runner_v4
from scripts import run_liberosafety_pi05_openpi_eval as base_runner


BDDL = """
(define (problem transport)
  (:domain robosuite)
  (:objects red_mug_1 - red_mug plate_1 - plate)
  (:init (On red_mug_1 main_table_region))
  (:goal (And (On red_mug_1 plate_1)))
)
"""


def _observation(
    *,
    epoch: int,
    eef: tuple[float, float, float],
    closed: bool,
) -> TrustedLocalObservation:
    return TrustedLocalObservation(
        state_epoch=epoch,
        eef_position=eef,
        gripper_qpos=(
            (0.002, -0.002) if closed else (0.04, -0.04)
        ),
        entity_positions=(
            EntityPosition("red_mug_1", (0.15, 0.0, 0.25)),
            EntityPosition("plate_1", (0.40, 0.0, 0.25)),
        ),
    )


def test_v3_checker_promises_prefix_progress_not_completed_grasp() -> None:
    result = HorizonConsistentSemanticExecutablePrefixChecker().assess(
        semantic_subtask="pick_up(red_mug_1)",
        observation=_observation(
            epoch=0,
            eef=(0.14, 0.0, 0.25),
            closed=False,
        ),
        command=(0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        command_shape=(1, 7),
        expected_state_epoch=0,
    )

    assert result.semantic_compatible
    assert result.motion_atoms == ("grasp",)
    assert result.predicted_effect_atoms == (
        PICK_UP_PREFIX_PROGRESS_EFFECT,
    )
    assert "holding_target" not in result.predicted_effect_atoms


def test_v3_observer_accepts_nearness_without_synthesizing_holding() -> None:
    result = HorizonConsistentSemanticPrefixEffectObserver().observe(
        semantic_subtask="pick_up(red_mug_1)",
        before=_observation(
            epoch=0,
            eef=(0.14, 0.0, 0.25),
            closed=False,
        ),
        after=_observation(
            epoch=1,
            eef=(0.15, 0.0, 0.25),
            closed=False,
        ),
        prefix_complete=True,
    )

    assert PICK_UP_PREFIX_PROGRESS_EFFECT in (
        result.observed_effect_atoms
    )
    assert "holding_target" not in result.observed_effect_atoms


def test_v3_wrapper_patch_is_versioned_and_restored() -> None:
    from proofalign import semantic_policy_wrapper as wrapper_module

    original_checker = wrapper_module.SemanticExecutablePrefixChecker
    original_version = wrapper_module.LOCAL_CHECKER_VERSION
    with patched_semantic_wrapper_bindings():
        wrapper = TrustedSemanticPolicyWrapper(
            episode_nonce="horizon-test",
            trusted_task="put the red mug on the plate",
            bddl_text=BDDL,
        )
        assert isinstance(
            wrapper.checker,
            HorizonConsistentSemanticExecutablePrefixChecker,
        )
        assert wrapper_module.LOCAL_CHECKER_VERSION == (
            HORIZON_CHECKER_VERSION
        )
    assert wrapper_module.SemanticExecutablePrefixChecker is (
        original_checker
    )
    assert wrapper_module.LOCAL_CHECKER_VERSION == original_version
    assert HORIZON_EFFECT_OBSERVER_VERSION == "3"


def test_v4_runner_injects_versioned_bindings_only_for_l1(
    monkeypatch,
) -> None:
    from proofalign import semantic_policy_wrapper as wrapper_module

    original_observer = base_runner.SemanticPrefixEffectObserver
    original_checker = wrapper_module.SemanticExecutablePrefixChecker
    observed = {}

    def fake_v3_run_episode(**_kwargs):
        observed["observer"] = base_runner.SemanticPrefixEffectObserver
        observed["checker"] = (
            wrapper_module.SemanticExecutablePrefixChecker
        )
        observed["version"] = wrapper_module.LOCAL_CHECKER_VERSION
        return {"metadata": {}}

    monkeypatch.setattr(
        runner_v4.v3,
        "run_episode",
        fake_v3_run_episode,
    )
    payload = runner_v4.run_episode(
        args=SimpleNamespace(
            semantic_runtime=True,
            l1_semantic_alignment="on",
            l2_execution_integrity="on",
        )
    )

    assert observed["observer"] is (
        HorizonConsistentSemanticPrefixEffectObserver
    )
    assert observed["checker"] is (
        HorizonConsistentSemanticExecutablePrefixChecker
    )
    assert observed["version"] == HORIZON_CHECKER_VERSION
    assert base_runner.SemanticPrefixEffectObserver is original_observer
    assert (
        wrapper_module.SemanticExecutablePrefixChecker
        is original_checker
    )
    assert payload["metadata"][
        "horizon_consistent_pick_up_contract_active"
    ] is True
