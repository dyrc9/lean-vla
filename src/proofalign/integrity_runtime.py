"""Five-component, three-transaction runtime for the minimal prototype.

The module has no simulator, GPU, socket, or hardware integration.  A caller
must provide an explicit ``CommandSink``; tests use ``InMemoryCommandSink``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from threading import Lock
from typing import Protocol

from proofalign.integrity_checker import ExactPrefixAuthorizer
from proofalign.integrity_intervention import InterventionPolicy
from proofalign.integrity_models import (
    ActionProposal,
    ActiveContract,
    ContractTransaction,
    CoreVerdict,
    DispatchReceipt,
    DispatchResult,
    EffectUpdateResult,
    ExecutionEvidence,
    MethodArm,
    MissionRoot,
    MonitorState,
    MonitorTransition,
    PrefixAuthorization,
    StateSnapshot,
    TrustedTaskArtifact,
    command_digest,
    freeze_command,
)


class FrozenMissionAdapter:
    """Finite adapter at the declared trusted task-artifact boundary."""

    def compile(self, artifact: TrustedTaskArtifact, *, episode_nonce: str) -> MissionRoot:
        if not isinstance(artifact, TrustedTaskArtifact):
            raise TypeError("artifact must be a TrustedTaskArtifact")
        return MissionRoot(
            source_id=artifact.source_id,
            source_version=artifact.source_version,
            artifact_digest=artifact.artifact_digest,
            instruction_digest=artifact.instruction_digest,
            episode_nonce=episode_nonce,
            phases=artifact.phases,
            initial_phase=artifact.initial_phase,
            templates=artifact.templates,
            hard_invariants=artifact.hard_invariants,
        )


class StaleMonitorTransaction(RuntimeError):
    pass


class PersistentContractMonitor:
    """Owns persistent contract state and atomically commits monitor updates."""

    def __init__(self, mission: MissionRoot) -> None:
        self.mission = mission
        self._state = MonitorState.initial(mission)
        self._active_contract: ActiveContract | None = None
        self._lock = Lock()

    @property
    def state(self) -> MonitorState:
        with self._lock:
            return self._state

    @property
    def active_contract(self) -> ActiveContract | None:
        with self._lock:
            return self._active_contract

    def certify_contract(self, *, now_ns: int) -> ContractTransaction:
        if now_ns < 0:
            raise ValueError("now_ns must be non-negative")
        with self._lock:
            before = self._state
            if self._active_contract is not None:
                if before.active_contract_digest != self._active_contract.contract_digest:
                    raise RuntimeError("monitor active-contract state is inconsistent")
                return ContractTransaction(
                    verdict=CoreVerdict.ALLOW,
                    before_state_digest=before.state_digest,
                    after_state=before,
                    contract=self._active_contract,
                )

            template = self.mission.template_for_phase(before.phase)
            if template is None:
                return ContractTransaction(
                    verdict=CoreVerdict.UNKNOWN,
                    before_state_digest=before.state_digest,
                    after_state=before,
                    contract=None,
                    issues=(f"unsupported phase {before.phase!r}",),
                )
            if template.obligation_id not in before.residual_obligations:
                return ContractTransaction(
                    verdict=CoreVerdict.REJECT,
                    before_state_digest=before.state_digest,
                    after_state=before,
                    contract=None,
                    issues=("phase obligation has already been discharged",),
                )

            contract = ActiveContract(
                mission_root_digest=self.mission.root_digest,
                episode_nonce=self.mission.episode_nonce,
                phase_before=template.phase_before,
                expected_next_phase=template.expected_next_phase,
                skill=template.skill,
                obligation_id=template.obligation_id,
                completion_atoms=template.completion_atoms,
                target=template.target,
                part=template.part,
                region=template.region,
                contract_version=template.contract_version,
                activated_at_ns=now_ns,
            )
            after = replace(
                before,
                active_contract_digest=contract.contract_digest,
                revision=before.revision + 1,
            )
            self._state = after
            self._active_contract = contract
            return ContractTransaction(
                verdict=CoreVerdict.ALLOW,
                before_state_digest=before.state_digest,
                after_state=after,
                contract=contract,
            )

    def commit_transition(self, transition: MonitorTransition) -> MonitorState:
        with self._lock:
            if transition.before_state_digest != self._state.state_digest:
                raise StaleMonitorTransaction("monitor state changed before effect commit")
            if self._active_contract is None:
                raise StaleMonitorTransaction("no active contract exists")
            if transition.contract_digest != self._active_contract.contract_digest:
                raise StaleMonitorTransaction("effect belongs to another contract")
            if transition.proposal_index <= self._state.last_proposal_index:
                raise StaleMonitorTransaction("effect proposal index is stale or replayed")
            after = transition.after_state
            if (
                after.mission_root_digest != self.mission.root_digest
                or after.episode_nonce != self.mission.episode_nonce
                or after.revision != self._state.revision + 1
            ):
                raise StaleMonitorTransaction("effect transition changes protected monitor identity")
            self._state = after
            if transition.verdict is CoreVerdict.COMPLETE:
                self._active_contract = None
            return self._state


@dataclass(frozen=True)
class AppliedCommand:
    command: tuple[float, ...]
    applied_at_ns: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "command", freeze_command(self.command))
        if type(self.applied_at_ns) is not int or self.applied_at_ns < 0:
            raise ValueError("applied_at_ns must be non-negative")


class CommandSink(Protocol):
    sink_id: str

    def apply(self, command: tuple[float, ...], *, now_ns: int) -> AppliedCommand:
        ...


class InMemoryCommandSink:
    """Test-only sink with no simulator, socket, or actuator capability."""

    sink_id = "proofalign-in-memory-no-action-sink"

    def __init__(self) -> None:
        self.applied: list[AppliedCommand] = []

    def apply(self, command: tuple[float, ...], *, now_ns: int) -> AppliedCommand:
        applied = AppliedCommand(command, now_ns)
        self.applied.append(applied)
        return applied


class SingleDispatchBoundary:
    """Consumes each authorization at most once and records the applied command."""

    def __init__(self, sink: CommandSink) -> None:
        self.sink = sink
        self._used_authorizations: set[str] = set()
        self._lock = Lock()

    def dispatch(
        self,
        authorization: PrefixAuthorization,
        command: tuple[float, ...],
        *,
        now_ns: int,
    ) -> DispatchResult:
        applied_candidate = freeze_command(command)
        applied_digest = command_digest(applied_candidate)
        issues: list[str] = []
        if not authorization.dispatchable:
            issues.append("prefix authorization is not dispatchable")
        if not authorization.is_fresh(now_ns):
            issues.append("prefix authorization is stale or not yet valid")
        if (
            authorization.arm.execution_enabled
            and applied_digest != authorization.final_command_digest
        ):
            issues.append("applied command differs from the exact authorized command")

        with self._lock:
            if authorization.authorization_digest in self._used_authorizations:
                issues.append("prefix authorization has already been consumed")
            if issues:
                return DispatchResult(CoreVerdict.REJECT, None, tuple(issues))
            # Mark used before calling the sink. A sink failure cannot make a
            # one-use authorization replayable.
            self._used_authorizations.add(authorization.authorization_digest)
            try:
                applied = self.sink.apply(applied_candidate, now_ns=now_ns)
            except Exception as exc:  # pragma: no cover - exercised by external sinks
                return DispatchResult(
                    CoreVerdict.UNKNOWN,
                    None,
                    (f"command sink failed: {type(exc).__name__}: {exc}",),
                )

        actual_digest = command_digest(applied.command)
        receipt = DispatchReceipt(
            authorization_digest=authorization.authorization_digest,
            episode_nonce=authorization.episode_nonce,
            proposal_index=authorization.proposal_index,
            authorized_command_digest=authorization.final_command_digest or applied_digest,
            applied_command_digest=actual_digest,
            applied_at_ns=applied.applied_at_ns,
            sink_id=self.sink.sink_id,
        )
        if authorization.arm.execution_enabled and actual_digest != authorization.final_command_digest:
            return DispatchResult(
                CoreVerdict.REJECT,
                receipt,
                ("command sink applied a command different from the exact authorization",),
            )
        if not authorization.is_fresh(applied.applied_at_ns):
            return DispatchResult(
                CoreVerdict.REJECT,
                receipt,
                ("command sink applied outside the authorization window",),
            )
        return DispatchResult(CoreVerdict.ALLOW, receipt)


class EffectObserverUpdater:
    """Checks execution/effect evidence and atomically updates the monitor."""

    def check_and_update(
        self,
        *,
        mission: MissionRoot,
        monitor: PersistentContractMonitor,
        contract: ActiveContract,
        authorization: PrefixAuthorization,
        receipt: DispatchReceipt,
        evidence: ExecutionEvidence,
    ) -> EffectUpdateResult:
        before = monitor.state
        issues: list[str] = []

        if not evidence.known:
            return EffectUpdateResult(
                CoreVerdict.UNKNOWN,
                before,
                before,
                (f"execution evidence is unknown: {evidence.unknown_reason}",),
            )
        if not authorization.dispatchable:
            issues.append("effect references a non-dispatchable authorization")
        if contract.mission_root_digest != mission.root_digest:
            issues.append("contract is bound to another mission")
        if before.active_contract_digest != contract.contract_digest:
            issues.append("monitor does not contain the active contract")

        if authorization.arm.execution_enabled:
            if authorization.mission_root_digest != mission.root_digest:
                issues.append("authorization is bound to another mission")
            if authorization.contract_digest != contract.contract_digest:
                issues.append("authorization is bound to another contract")
            if authorization.episode_nonce != mission.episode_nonce:
                issues.append("authorization is bound to another episode")
            if authorization.monitor_state_digest != before.state_digest:
                issues.append("authorization is bound to a stale monitor state")
            if receipt.authorization_digest != authorization.authorization_digest:
                issues.append("receipt is bound to another authorization")
            if evidence.authorization_digest != authorization.authorization_digest:
                issues.append("effect evidence is bound to another authorization")
            if evidence.receipt_digest != receipt.receipt_digest:
                issues.append("effect evidence is bound to another receipt")
            if receipt.episode_nonce != mission.episode_nonce or evidence.episode_nonce != mission.episode_nonce:
                issues.append("receipt/effect evidence is bound to another episode")
            if (
                receipt.proposal_index != authorization.proposal_index
                or evidence.proposal_index != authorization.proposal_index
            ):
                issues.append("receipt/effect evidence is bound to another proposal")
            if receipt.applied_command_digest != authorization.final_command_digest:
                issues.append("applied command differs from exact authorization")
            if evidence.observed_command_digest != receipt.applied_command_digest:
                issues.append("observed command differs from dispatch receipt")
            if not (
                authorization.issued_at_ns
                <= receipt.applied_at_ns
                <= authorization.valid_until_ns
            ):
                issues.append("dispatch receipt falls outside the authorization window")
            if evidence.observed_at_ns < receipt.applied_at_ns:
                issues.append("effect observation predates the applied command")

        if issues:
            return EffectUpdateResult(CoreVerdict.REJECT, before, before, tuple(issues))

        observed_atoms = set(before.completed_atoms)
        observed_atoms.update(evidence.observed_atoms)
        completion_observed = set(contract.completion_atoms).issubset(observed_atoms)
        checked_complete = completion_observed and not evidence.violation
        verdict = (
            CoreVerdict.REJECT
            if evidence.violation
            else CoreVerdict.COMPLETE if checked_complete else CoreVerdict.PENDING
        )

        residual = tuple(
            item
            for item in before.residual_obligations
            if not (checked_complete and item == contract.obligation_id)
        )
        after = replace(
            before,
            phase=contract.expected_next_phase if checked_complete else before.phase,
            residual_obligations=residual,
            active_contract_digest=None if checked_complete else contract.contract_digest,
            completed_atoms=tuple(sorted(observed_atoms)),
            history_evidence_digests=before.history_evidence_digests
            + (evidence.evidence_digest,),
            last_proposal_index=authorization.proposal_index,
            revision=before.revision + 1,
        )
        transition = MonitorTransition(
            verdict=verdict,
            before_state_digest=before.state_digest,
            after_state=after,
            contract_digest=contract.contract_digest,
            proposal_index=authorization.proposal_index,
            evidence_digest=evidence.evidence_digest,
        )
        try:
            committed = monitor.commit_transition(transition)
        except StaleMonitorTransaction as exc:
            return EffectUpdateResult(
                CoreVerdict.UNKNOWN,
                before,
                monitor.state,
                (str(exc),),
            )
        return EffectUpdateResult(verdict, before, committed)


@dataclass
class ProofAlignPrototype:
    """Facade exposing exactly the three public method transactions."""

    arm: MethodArm
    mission: MissionRoot
    monitor: PersistentContractMonitor
    authorizer: ExactPrefixAuthorizer
    dispatch_boundary: SingleDispatchBoundary
    effect_updater: EffectObserverUpdater

    @classmethod
    def create(
        cls,
        *,
        arm: MethodArm,
        artifact: TrustedTaskArtifact,
        episode_nonce: str,
        authorizer: ExactPrefixAuthorizer,
        sink: CommandSink,
        mission_adapter: FrozenMissionAdapter | None = None,
    ) -> "ProofAlignPrototype":
        adapter = mission_adapter or FrozenMissionAdapter()
        mission = adapter.compile(artifact, episode_nonce=episode_nonce)
        return cls(
            arm=arm,
            mission=mission,
            monitor=PersistentContractMonitor(mission),
            authorizer=authorizer,
            dispatch_boundary=SingleDispatchBoundary(sink),
            effect_updater=EffectObserverUpdater(),
        )

    def certify_contract(self, *, now_ns: int) -> ContractTransaction:
        return self.monitor.certify_contract(now_ns=now_ns)

    def authorize_exact_prefix(
        self,
        *,
        proposal: ActionProposal,
        state: StateSnapshot,
        now_ns: int,
        intervention_policy: InterventionPolicy | None = None,
    ) -> PrefixAuthorization:
        contract = self.monitor.active_contract
        if contract is None:
            raise RuntimeError("certify_contract must succeed before prefix authorization")
        return self.authorizer.authorize(
            arm=self.arm,
            mission=self.mission,
            contract=contract,
            monitor=self.monitor.state,
            proposal=proposal,
            state=state,
            now_ns=now_ns,
            intervention_policy=intervention_policy,
        )

    def dispatch(
        self,
        authorization: PrefixAuthorization,
        command: tuple[float, ...],
        *,
        now_ns: int,
    ) -> DispatchResult:
        return self.dispatch_boundary.dispatch(authorization, command, now_ns=now_ns)

    def check_effect_update(
        self,
        *,
        authorization: PrefixAuthorization,
        receipt: DispatchReceipt,
        evidence: ExecutionEvidence,
    ) -> EffectUpdateResult:
        contract = self.monitor.active_contract
        if contract is None:
            state = self.monitor.state
            return EffectUpdateResult(
                CoreVerdict.UNKNOWN,
                state,
                state,
                ("no active contract exists",),
            )
        return self.effect_updater.check_and_update(
            mission=self.mission,
            monitor=self.monitor,
            contract=contract,
            authorization=authorization,
            receipt=receipt,
            evidence=evidence,
        )


__all__ = [
    "AppliedCommand",
    "CommandSink",
    "EffectObserverUpdater",
    "FrozenMissionAdapter",
    "InMemoryCommandSink",
    "PersistentContractMonitor",
    "ProofAlignPrototype",
    "SingleDispatchBoundary",
    "StaleMonitorTransaction",
]
