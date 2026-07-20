"""Deterministic fast checker and exact-prefix authorization transaction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from proofalign.ctda import digest_payload
from proofalign.integrity_intervention import InterventionPolicy, PassThroughIntervention
from proofalign.integrity_models import (
    ActionProposal,
    ActiveContract,
    CoreVerdict,
    InterventionKind,
    LayerCheck,
    LayerVerdict,
    MethodArm,
    MissionRoot,
    MonitorState,
    PrefixAuthorization,
    StateSnapshot,
    command_digest,
)


class FastIntegrityChecker(Protocol):
    """Consumer-side checker used by the online prototype.

    A future Lean-backed claim requires an explicit refinement/equivalence
    artifact for the concrete implementation of this interface.
    """

    checker_id: str
    checker_version: str

    def check_intent(
        self,
        mission: MissionRoot,
        contract: ActiveContract,
        proposal: ActionProposal,
        final_command: tuple[float, ...],
    ) -> LayerCheck:
        ...

    def check_execution_pre(
        self,
        mission: MissionRoot,
        contract: ActiveContract,
        proposal: ActionProposal,
        final_command: tuple[float, ...],
        state: StateSnapshot,
        monitor: MonitorState,
        now_ns: int,
    ) -> LayerCheck:
        ...


@dataclass(frozen=True)
class DeterministicFastChecker:
    """Finite, conservative checker for the minimal exact-task prototype.

    It checks typed skill/target/part/region equality for Intent–Plan integrity
    and freshness/transaction/final-command bindings for execution pre-checks.
    It deliberately makes no collision, reachability, perception, or continuous
    dynamics claim.
    """

    checker_id: str = "proofalign-deterministic-fast-checker"
    checker_version: str = "1"

    def _result(self, layer: str, issues: list[str], payload: dict[str, object]) -> LayerCheck:
        if issues:
            verdict = (
                LayerVerdict.UNKNOWN
                if any(issue.startswith("unknown:") for issue in issues)
                else LayerVerdict.REFUTED
            )
            return LayerCheck(verdict, tuple(issues))
        return LayerCheck(
            LayerVerdict.PROVEN,
            witness_digest=digest_payload(
                {
                    "checker_id": self.checker_id,
                    "checker_version": self.checker_version,
                    "layer": layer,
                    **payload,
                }
            ),
        )

    def check_intent(
        self,
        mission: MissionRoot,
        contract: ActiveContract,
        proposal: ActionProposal,
        final_command: tuple[float, ...],
    ) -> LayerCheck:
        issues: list[str] = []
        if contract.mission_root_digest != mission.root_digest:
            issues.append("contract is bound to another mission root")
        if contract.episode_nonce != mission.episode_nonce:
            issues.append("contract is bound to another episode")
        if proposal.episode_nonce != mission.episode_nonce:
            issues.append("proposal is bound to another episode")
        if proposal.skill != contract.skill:
            issues.append(f"skill {proposal.skill!r} is not authorized as {contract.skill!r}")
        for name in ("target", "part", "region"):
            expected = getattr(contract, name)
            actual = getattr(proposal, name)
            if expected is not None and actual is None:
                issues.append(f"unknown: proposal omits required {name}")
            elif expected is not None and actual != expected:
                issues.append(f"{name} {actual!r} is not authorized as {expected!r}")
            elif expected is None and actual is not None:
                issues.append(f"proposal introduces unauthorized {name} {actual!r}")
        return self._result(
            "intent_plan",
            issues,
            {
                "mission_root_digest": mission.root_digest,
                "contract_digest": contract.contract_digest,
                "proposal_digest": proposal.proposal_digest,
                "final_command_digest": command_digest(final_command),
            },
        )

    def check_execution_pre(
        self,
        mission: MissionRoot,
        contract: ActiveContract,
        proposal: ActionProposal,
        final_command: tuple[float, ...],
        state: StateSnapshot,
        monitor: MonitorState,
        now_ns: int,
    ) -> LayerCheck:
        issues: list[str] = []
        freshness_issue = state.freshness_issue(now_ns)
        if freshness_issue is not None:
            issues.append(f"unknown: {freshness_issue}")
        if state.episode_nonce != mission.episode_nonce:
            issues.append("state is bound to another episode")
        if monitor.mission_root_digest != mission.root_digest:
            issues.append("monitor is bound to another mission root")
        if monitor.episode_nonce != mission.episode_nonce:
            issues.append("monitor is bound to another episode")
        if monitor.phase != contract.phase_before:
            issues.append("monitor phase does not match active contract")
        if monitor.active_contract_digest != contract.contract_digest:
            issues.append("monitor does not contain the active contract")
        if proposal.proposal_index <= monitor.last_proposal_index:
            issues.append("proposal index is stale or replayed")
        if proposal.episode_nonce != mission.episode_nonce:
            issues.append("proposal is bound to another episode")
        return self._result(
            "plan_execution_pre",
            issues,
            {
                "mission_root_digest": mission.root_digest,
                "contract_digest": contract.contract_digest,
                "proposal_digest": proposal.proposal_digest,
                "proposal_index": proposal.proposal_index,
                "state_snapshot_digest": state.snapshot_digest,
                "monitor_state_digest": monitor.state_digest,
                "final_command_digest": command_digest(final_command),
                "now_ns": now_ns,
            },
        )


@dataclass(frozen=True)
class ExactPrefixAuthorizer:
    checker: FastIntegrityChecker
    authorization_ttl_ns: int = 100_000_000

    def __post_init__(self) -> None:
        if type(self.authorization_ttl_ns) is not int or self.authorization_ttl_ns <= 0:
            raise ValueError("authorization_ttl_ns must be a positive integer")

    def authorize(
        self,
        *,
        arm: MethodArm,
        mission: MissionRoot,
        contract: ActiveContract,
        monitor: MonitorState,
        proposal: ActionProposal,
        state: StateSnapshot,
        now_ns: int,
        intervention_policy: InterventionPolicy | None = None,
    ) -> PrefixAuthorization:
        if now_ns < 0:
            raise ValueError("now_ns must be non-negative")
        policy = intervention_policy or PassThroughIntervention()
        intervention = policy.apply(proposal, state)
        final_command = intervention.final_command
        nominal_digest = command_digest(proposal.command)

        if final_command is None:
            intent_check = LayerCheck.disabled()
            execution_check = LayerCheck.disabled()
            verdict = (
                CoreVerdict.UNKNOWN
                if intervention.kind is InterventionKind.REPLAN
                else CoreVerdict.REJECT
            )
        else:
            intent_check = (
                self.checker.check_intent(mission, contract, proposal, final_command)
                if arm.intent_enabled
                else LayerCheck.disabled()
            )
            execution_check = (
                self.checker.check_execution_pre(
                    mission,
                    contract,
                    proposal,
                    final_command,
                    state,
                    monitor,
                    now_ns,
                )
                if arm.execution_enabled
                else LayerCheck.disabled()
            )
            enabled = tuple(
                check
                for check, required in (
                    (intent_check, arm.intent_enabled),
                    (execution_check, arm.execution_enabled),
                )
                if required
            )
            if any(check.verdict is LayerVerdict.REFUTED for check in enabled):
                verdict = CoreVerdict.REJECT
            elif any(check.verdict is LayerVerdict.UNKNOWN for check in enabled):
                verdict = CoreVerdict.UNKNOWN
            else:
                verdict = CoreVerdict.ALLOW

        return PrefixAuthorization(
            arm=arm,
            verdict=verdict,
            mission_root_digest=mission.root_digest,
            contract_digest=contract.contract_digest,
            episode_nonce=mission.episode_nonce,
            state_snapshot_digest=state.snapshot_digest,
            monitor_state_digest=monitor.state_digest,
            proposal_index=proposal.proposal_index,
            proposal_digest=proposal.proposal_digest,
            nominal_command_digest=nominal_digest,
            final_command=final_command,
            final_command_digest=(
                None if final_command is None else command_digest(final_command)
            ),
            intervention=intervention,
            intent_check=intent_check,
            execution_check=execution_check,
            issued_at_ns=now_ns,
            valid_until_ns=now_ns + self.authorization_ttl_ns,
        )


__all__ = [
    "DeterministicFastChecker",
    "ExactPrefixAuthorizer",
    "FastIntegrityChecker",
]
