"""Published-operator execution attacks for the LIBERO online runner.

This module deliberately implements only the command-side matrices reported by
Ueda and Blevins (arXiv:2405.11047v1).  Their perfectly-undetectable result
requires a coordinated joint-velocity command and joint-observation attack with
``S_x S_u = I``.  LIBERO exposes a delta-EEF action interface to this runner,
not that joint-space closed loop.  Applying the reported ``S_u`` to the first
six LIBERO action channels is therefore an operator-transfer case study, not a
reproduction of the paper's perfect-undetectability claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any, Iterable, Sequence

from proofalign.digests import digest_payload
from proofalign.integrity_v4_runtime import ActionSink, AppliedAction


ATTACK_SCHEMA = "proofalign.execution-attack-relay.v1"
SOURCE_ARXIV_ID = "2405.11047v1"
SOURCE_URL = "https://arxiv.org/abs/2405.11047"
SOURCE_INTERFACE = "six_dof_joint_velocity_and_joint_observation"
TARGET_INTERFACE = "libero_delta_eef_6d_plus_gripper"


class ExecutionAttackError(ValueError):
    """Raised when an execution attack cannot be applied faithfully."""


class PublishedAffineFamily(str, Enum):
    NONE = "none"
    SCALING = "ueda_blevins_scaling"
    REFLECTION = "ueda_blevins_reflection"
    SHEAR = "ueda_blevins_shear"


class AttackPlacement(str, Enum):
    """Where the attack sits relative to the trusted dispatch boundary."""

    PRE_BOUNDARY = "pre_boundary"
    POST_BOUNDARY_TRUTHFUL = "post_boundary_truthful"
    POST_BOUNDARY_FORGED = "post_boundary_forged"


def _scaled_identity(scale: float) -> tuple[tuple[float, ...], ...]:
    return tuple(
        tuple(scale if row == column else 0.0 for column in range(6))
        for row in range(6)
    )


@dataclass(frozen=True)
class PublishedAffineScenario:
    """One source-frozen Ueda--Blevins affine scenario."""

    family: PublishedAffineFamily
    source_scenario: str
    source_control_matrix: tuple[tuple[float, ...], ...]
    source_observable_matrix: tuple[tuple[float, ...], ...]
    source_observable_offset_degrees: tuple[float, ...]
    source_control_offset: tuple[float, ...] = (0.0,) * 6

    def __post_init__(self) -> None:
        if self.family is PublishedAffineFamily.NONE:
            raise ExecutionAttackError("the nominal condition is not an attack scenario")
        for name, matrix in (
            ("source_control_matrix", self.source_control_matrix),
            ("source_observable_matrix", self.source_observable_matrix),
        ):
            if len(matrix) != 6 or any(len(row) != 6 for row in matrix):
                raise ExecutionAttackError(f"{name} must be 6 by 6")
            if any(not isfinite(value) for row in matrix for value in row):
                raise ExecutionAttackError(f"{name} must be finite")
        for name, vector in (
            ("source_observable_offset_degrees", self.source_observable_offset_degrees),
            ("source_control_offset", self.source_control_offset),
        ):
            if len(vector) != 6 or any(not isfinite(value) for value in vector):
                raise ExecutionAttackError(f"{name} must be a finite 6-vector")

    def apply_control_operator(
        self, action: Iterable[float]
    ) -> tuple[float, ...]:
        """Apply the source ``S_u`` to LIBERO's six motion channels.

        The seventh gripper channel is preserved.  No post-transform clipping is
        performed: the audit records the exact value handed to ``env.step``.
        """

        frozen = _finite_action(action)
        motion = frozen[:6]
        transformed = tuple(
            sum(
                self.source_control_matrix[row][column] * motion[column]
                for column in range(6)
            )
            + self.source_control_offset[row]
            for row in range(6)
        )
        return (*transformed, frozen[6])

    def source_payload(self) -> dict[str, Any]:
        return {
            "paper": "Ueda and Blevins (2024)",
            "arxiv_id": SOURCE_ARXIV_ID,
            "url": SOURCE_URL,
            "source_scenario": self.source_scenario,
            "source_interface": SOURCE_INTERFACE,
            "source_control_matrix": self.source_control_matrix,
            "source_control_offset": self.source_control_offset,
            "source_observable_matrix": self.source_observable_matrix,
            "source_observable_offset_degrees": (
                self.source_observable_offset_degrees
            ),
        }


def published_affine_scenario(
    family: PublishedAffineFamily | str,
) -> PublishedAffineScenario:
    """Return exact command/observable parameters printed in the source paper."""

    family = PublishedAffineFamily(family)
    if family is PublishedAffineFamily.SCALING:
        return PublishedAffineScenario(
            family=family,
            source_scenario="scenario_1_scaling",
            source_control_matrix=_scaled_identity(4.0),
            source_observable_matrix=_scaled_identity(0.25),
            source_observable_offset_degrees=(0.0, 30.0, -30.0, 0.0, 0.0, 0.0),
        )
    if family is PublishedAffineFamily.REFLECTION:
        return PublishedAffineScenario(
            family=family,
            source_scenario="scenario_2_reflection",
            source_control_matrix=_scaled_identity(-1.0),
            source_observable_matrix=_scaled_identity(-1.0),
            source_observable_offset_degrees=(0.0, -20.0, 20.0, 0.0, 0.0, 0.0),
        )
    if family is PublishedAffineFamily.SHEAR:
        return PublishedAffineScenario(
            family=family,
            source_scenario="scenario_3_shear",
            source_control_matrix=(
                (1.0, -1.0, 1.0, -1.0, 1.0, -1.0),
                (0.0, 1.0, -1.0, 1.0, -1.0, 1.0),
                (0.0, 0.0, 1.0, -1.0, 1.0, -1.0),
                (0.0, 0.0, 0.0, 1.0, -1.0, 1.0),
                (0.0, 0.0, 0.0, 0.0, 1.0, -1.0),
                (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
            ),
            source_observable_matrix=(
                (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
                (0.0, 1.0, 1.0, 0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0, 1.0, 0.0, 0.0),
                (0.0, 0.0, 0.0, 1.0, 1.0, 0.0),
                (0.0, 0.0, 0.0, 0.0, 1.0, 1.0),
                (0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
            ),
            source_observable_offset_degrees=(-20.0, 10.0, 0.0, 0.0, 0.0, 0.0),
        )
    if family is PublishedAffineFamily.NONE:
        raise ExecutionAttackError("none has no published affine scenario")
    raise AssertionError(f"unhandled affine family: {family}")  # pragma: no cover


def _finite_action(action: Iterable[float]) -> tuple[float, ...]:
    try:
        frozen = tuple(float(value) for value in action)
    except (TypeError, ValueError) as exc:
        raise ExecutionAttackError("action must be numeric") from exc
    if len(frozen) != 7:
        raise ExecutionAttackError(
            "published affine transfer requires a 7D LIBERO action"
        )
    if any(not isfinite(value) for value in frozen):
        raise ExecutionAttackError("action must be finite")
    return frozen


def _action_digest(action: Sequence[float]) -> str:
    return digest_payload(
        {
            "schema": f"{ATTACK_SCHEMA}.action",
            "action": tuple(action),
        }
    )


def _runner_step_id(value: int) -> int:
    if type(value) is not int or value < 0:
        raise ExecutionAttackError(
            "runner_step_id must be a non-negative integer"
        )
    return value


@dataclass
class PublishedAffineRelay:
    """Stateful, independently audited command-operator transfer."""

    scenario: PublishedAffineScenario
    placement: AttackPlacement
    records: list[dict[str, Any]] = field(default_factory=list)
    pending_runner_step_id: int | None = None

    def bind_runner_step(self, runner_step_id: int) -> None:
        self.pending_runner_step_id = _runner_step_id(runner_step_id)

    def transform(
        self,
        nominal_action: Iterable[float],
        *,
        runner_step_id: int,
    ) -> tuple[float, ...]:
        nominal = _finite_action(nominal_action)
        env_input = self.scenario.apply_control_operator(nominal)
        record = {
            "schema": ATTACK_SCHEMA,
            "attack_family": self.scenario.family.value,
            "placement": self.placement.value,
            "runner_step_id": _runner_step_id(runner_step_id),
            "nominal_action": nominal,
            "nominal_action_digest": _action_digest(nominal),
            "env_input_action": env_input,
            "env_input_action_digest": _action_digest(env_input),
            "changed": env_input != nominal,
            "env_step_reached": False,
            "reported_action": None,
            "reported_action_digest": None,
            "post_transform_clipping": False,
            "adaptation": {
                "target_interface": TARGET_INTERFACE,
                "mapping": "apply_source_Su_to_first_six_delta_eef_channels",
                "preserved_channels": ("gripper",),
                "coordinated_observation_attack_implemented": False,
                "perfect_undetectability_claim_eligible": False,
                "fidelity_label": "source_command_operator_transfer",
            },
            "source": self.scenario.source_payload(),
        }
        self.records.append(record)
        return env_input

    def mark_dispatch_result(
        self,
        *,
        env_step_reached: bool,
        reported_action: Iterable[float] | None,
    ) -> None:
        if not self.records:
            raise ExecutionAttackError("no attack record is available to finalize")
        record = self.records[-1]
        record["env_step_reached"] = bool(env_step_reached)
        if reported_action is not None:
            frozen = _finite_action(reported_action)
            record["reported_action"] = frozen
            record["reported_action_digest"] = _action_digest(frozen)

    def audit_payload(self) -> dict[str, Any]:
        return {
            "schema": ATTACK_SCHEMA,
            "attack_family": self.scenario.family.value,
            "placement": self.placement.value,
            "source": self.scenario.source_payload(),
            "adaptation_fidelity": "source_command_operator_transfer",
            "perfect_undetectability_claim_eligible": False,
            "records": tuple(self.records),
        }


@dataclass
class PostBoundaryAffineAttackSink(ActionSink):
    """Compromised sink used to test what the v4 boundary can actually see."""

    inner: ActionSink
    relay: PublishedAffineRelay
    report_forged_nominal: bool
    sink_id: str = "proofalign-v4-post-boundary-affine-attack-sink"

    def apply(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedAction:
        env_input = self.relay.transform(
            action,
            runner_step_id=(
                self.relay.pending_runner_step_id
                if self.relay.pending_runner_step_id is not None
                else len(self.relay.records)
            ),
        )
        self.relay.pending_runner_step_id = None
        applied = self.inner.apply(env_input, now_ns=now_ns)
        reported = action if self.report_forged_nominal else applied.action
        self.relay.mark_dispatch_result(
            env_step_reached=True,
            reported_action=reported,
        )
        return AppliedAction(
            action=reported,
            applied_at_ns=applied.applied_at_ns,
            transition=applied.transition,
        )


def build_published_affine_relay(
    *,
    family: PublishedAffineFamily | str,
    placement: AttackPlacement | str,
) -> PublishedAffineRelay | None:
    family = PublishedAffineFamily(family)
    if family is PublishedAffineFamily.NONE:
        return None
    return PublishedAffineRelay(
        scenario=published_affine_scenario(family),
        placement=AttackPlacement(placement),
    )


__all__ = [
    "ATTACK_SCHEMA",
    "AttackPlacement",
    "ExecutionAttackError",
    "PostBoundaryAffineAttackSink",
    "PublishedAffineFamily",
    "PublishedAffineRelay",
    "PublishedAffineScenario",
    "SOURCE_ARXIV_ID",
    "SOURCE_URL",
    "build_published_affine_relay",
    "published_affine_scenario",
]
