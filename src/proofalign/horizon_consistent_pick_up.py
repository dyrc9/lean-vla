"""Versioned horizon-consistent pick-up checker and effect observer.

The historical v2 checker and observer remain byte-identical for frozen
evidence.  This successor changes only the positive effect promised by a
finite ``pick_up`` ActionBlock: the block must make trusted approach progress,
end near the target, or already exhibit a trusted held state.  A finite
close-near prefix no longer promises that a stable grasp has completed at the
same block boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Iterator

from proofalign.digests import digest_payload
from proofalign.semantic_effect_observer import (
    SemanticEffectObservation,
    SemanticEffectObserverConfig,
    SemanticPrefixEffectObserver,
)
from proofalign.semantic_local_checker import (
    LOCAL_CHECKER_ID,
    LocalActionAssessment,
    LocalCheckerConfig,
    SemanticExecutablePrefixChecker,
    parse_semantic_subtask,
)


HORIZON_CHECKER_VERSION = "3"
HORIZON_EFFECT_OBSERVER_VERSION = "3"
PICK_UP_PREFIX_PROGRESS_EFFECT = "pick_up_prefix_progress"


@dataclass(frozen=True)
class HorizonConsistentLocalCheckerConfig(LocalCheckerConfig):
    """v3 checker config with a distinct content-addressed identity."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": HORIZON_CHECKER_VERSION,
                **self.__dict__,
            }
        )


class HorizonConsistentSemanticExecutablePrefixChecker(
    SemanticExecutablePrefixChecker
):
    """Preserve v2 hard gates while refining the pick-up effect promise."""

    def __init__(
        self,
        config: LocalCheckerConfig | None = None,
    ) -> None:
        selected = (
            HorizonConsistentLocalCheckerConfig()
            if config is None
            else HorizonConsistentLocalCheckerConfig(**config.__dict__)
        )
        super().__init__(selected)

    def assess(self, **kwargs: Any) -> LocalActionAssessment:
        result = super().assess(**kwargs)
        semantic_subtask = kwargs.get("semantic_subtask")
        if (
            result.known
            and result.semantic_compatible
            and isinstance(semantic_subtask, str)
            and parse_semantic_subtask(semantic_subtask).verb == "pick_up"
        ):
            return replace(
                result,
                predicted_effect_atoms=(
                    PICK_UP_PREFIX_PROGRESS_EFFECT,
                ),
            )
        return result


@dataclass(frozen=True)
class HorizonConsistentEffectObserverConfig(
    SemanticEffectObserverConfig
):
    """v3 observer config with a distinct content-addressed identity."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "observer_id": (
                    "proofalign-libero-analytic-effect-observer"
                ),
                "observer_version": HORIZON_EFFECT_OBSERVER_VERSION,
                **self.__dict__,
            }
        )


class HorizonConsistentSemanticPrefixEffectObserver(
    SemanticPrefixEffectObserver
):
    """Add the derived pick-up prefix predicate without asserting grasp."""

    def __init__(
        self,
        config: SemanticEffectObserverConfig | None = None,
    ) -> None:
        selected = (
            HorizonConsistentEffectObserverConfig()
            if config is None
            else HorizonConsistentEffectObserverConfig(
                **config.__dict__
            )
        )
        super().__init__(selected)

    def observe(self, **kwargs: Any) -> SemanticEffectObservation:
        result = super().observe(**kwargs)
        semantic_subtask = kwargs.get("semantic_subtask")
        if (
            result.known
            and isinstance(semantic_subtask, str)
            and parse_semantic_subtask(semantic_subtask).verb == "pick_up"
            and any(
                atom in result.observed_effect_atoms
                for atom in (
                    "closer_to_target",
                    "near_target",
                    "holding_target",
                )
            )
        ):
            return replace(
                result,
                observed_effect_atoms=tuple(
                    dict.fromkeys(
                        (
                            *result.observed_effect_atoms,
                            PICK_UP_PREFIX_PROGRESS_EFFECT,
                        )
                    )
                ),
            )
        return result


@contextmanager
def patched_semantic_wrapper_bindings() -> Iterator[None]:
    """Temporarily inject only the v3 checker into the frozen wrapper."""

    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = (
        HorizonConsistentSemanticExecutablePrefixChecker
    )
    wrapper.LOCAL_CHECKER_VERSION = HORIZON_CHECKER_VERSION
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


__all__ = [
    "HORIZON_CHECKER_VERSION",
    "HORIZON_EFFECT_OBSERVER_VERSION",
    "PICK_UP_PREFIX_PROGRESS_EFFECT",
    "HorizonConsistentEffectObserverConfig",
    "HorizonConsistentLocalCheckerConfig",
    "HorizonConsistentSemanticExecutablePrefixChecker",
    "HorizonConsistentSemanticPrefixEffectObserver",
    "patched_semantic_wrapper_bindings",
]
