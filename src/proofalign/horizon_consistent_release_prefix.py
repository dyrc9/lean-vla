"""Finite-horizon release-prefix contracts with unchanged completion guards."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import Any, Iterator

from proofalign.digests import digest_payload
from proofalign.horizon_consistent_pick_up import (
    HorizonConsistentSemanticExecutablePrefixChecker,
    HorizonConsistentSemanticPrefixEffectObserver,
)
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


RELEASE_PREFIX_CHECKER_VERSION = "4"
RELEASE_PREFIX_OBSERVER_VERSION = "4"
RELEASE_PREFIX_PROGRESS_EFFECT = "release_prefix_progress"


@dataclass(frozen=True)
class ReleasePrefixLocalCheckerConfig(LocalCheckerConfig):
    """Distinct v4 identity for the refined release promise."""

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "checker_id": LOCAL_CHECKER_ID,
                "checker_version": RELEASE_PREFIX_CHECKER_VERSION,
                **self.__dict__,
            }
        )


class ReleasePrefixSemanticExecutablePrefixChecker(
    HorizonConsistentSemanticExecutablePrefixChecker
):
    """Keep all v3 hard gates but promise only finite release progress."""

    def __init__(
        self,
        config: LocalCheckerConfig | None = None,
    ) -> None:
        selected = (
            ReleasePrefixLocalCheckerConfig()
            if config is None
            else ReleasePrefixLocalCheckerConfig(**config.__dict__)
        )
        SemanticExecutablePrefixChecker.__init__(self, selected)

    def assess(self, **kwargs: Any) -> LocalActionAssessment:
        result = super().assess(**kwargs)
        semantic_subtask = kwargs.get("semantic_subtask")
        if (
            result.known
            and result.semantic_compatible
            and isinstance(semantic_subtask, str)
            and parse_semantic_subtask(semantic_subtask).verb == "release"
        ):
            return replace(
                result,
                predicted_effect_atoms=(
                    RELEASE_PREFIX_PROGRESS_EFFECT,
                ),
            )
        return result


@dataclass(frozen=True)
class ReleasePrefixEffectObserverConfig(
    SemanticEffectObserverConfig
):
    """v4 observer identity and frozen opening-progress threshold."""

    min_gripper_opening_progress: float = 0.002

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.min_gripper_opening_progress <= 0:
            raise ValueError(
                "min_gripper_opening_progress must be positive"
            )

    @property
    def config_digest(self) -> str:
        return digest_payload(
            {
                "observer_id": (
                    "proofalign-libero-analytic-effect-observer"
                ),
                "observer_version": RELEASE_PREFIX_OBSERVER_VERSION,
                **self.__dict__,
            }
        )


class ReleasePrefixSemanticEffectObserver(
    HorizonConsistentSemanticPrefixEffectObserver
):
    """Observe gripper-opening progress without asserting completed release."""

    def __init__(
        self,
        config: SemanticEffectObserverConfig | None = None,
    ) -> None:
        selected = (
            ReleasePrefixEffectObserverConfig()
            if config is None
            else ReleasePrefixEffectObserverConfig(**config.__dict__)
        )
        SemanticPrefixEffectObserver.__init__(self, selected)

    def observe(self, **kwargs: Any) -> SemanticEffectObservation:
        result = super().observe(**kwargs)
        semantic_subtask = kwargs.get("semantic_subtask")
        before = kwargs.get("before")
        after = kwargs.get("after")
        if (
            result.known
            and isinstance(semantic_subtask, str)
            and parse_semantic_subtask(semantic_subtask).verb == "release"
            and before is not None
            and after is not None
            and (
                after.gripper_closedness
                - before.gripper_closedness
                >= self.config.min_gripper_opening_progress
                or "gripper_open" in result.observed_effect_atoms
                or "target_released" in result.observed_effect_atoms
            )
        ):
            return replace(
                result,
                observed_effect_atoms=tuple(
                    dict.fromkeys(
                        (
                            *result.observed_effect_atoms,
                            RELEASE_PREFIX_PROGRESS_EFFECT,
                        )
                    )
                ),
            )
        return result


@contextmanager
def patched_release_prefix_wrapper_bindings() -> Iterator[None]:
    """Temporarily inject the v4 checker into the semantic wrapper."""

    from proofalign import semantic_policy_wrapper as wrapper

    original_checker = wrapper.SemanticExecutablePrefixChecker
    original_version = wrapper.LOCAL_CHECKER_VERSION
    wrapper.SemanticExecutablePrefixChecker = (
        ReleasePrefixSemanticExecutablePrefixChecker
    )
    wrapper.LOCAL_CHECKER_VERSION = RELEASE_PREFIX_CHECKER_VERSION
    try:
        yield
    finally:
        wrapper.SemanticExecutablePrefixChecker = original_checker
        wrapper.LOCAL_CHECKER_VERSION = original_version


__all__ = [
    "RELEASE_PREFIX_CHECKER_VERSION",
    "RELEASE_PREFIX_OBSERVER_VERSION",
    "RELEASE_PREFIX_PROGRESS_EFFECT",
    "ReleasePrefixEffectObserverConfig",
    "ReleasePrefixLocalCheckerConfig",
    "ReleasePrefixSemanticEffectObserver",
    "ReleasePrefixSemanticExecutablePrefixChecker",
    "patched_release_prefix_wrapper_bindings",
]
