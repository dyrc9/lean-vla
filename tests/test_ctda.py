from __future__ import annotations

from dataclasses import fields, is_dataclass, replace

import pytest

from proofalign.action_abstraction import action_from_dict
from proofalign.ctda import (
    AbstractionLink,
    ActionProposalBinding,
    AuthorityEnvelope,
    CTDAChecker,
    CTDASupervisor,
    ContractExecution,
    ContractMonitorState,
    DigestAllowlistEvidenceVerifier,
    EvidenceAttestation,
    ExecutionReceipt,
    MissionSpec,
    MonitorVerdict,
    PlantSample,
    PlantTrace,
    PhaseObligation,
    PrefixAuthorization,
    PrefixCandidate,
    PrefixExecutionRecord,
    ReachableTube,
    SemanticSkillContract,
    StaticVerdict,
    SymbolicEvent,
    SymbolicEventTrace,
    TaskTransition,
    TimeBase,
    TruthValue,
    TraceAbstractionEvidence,
    advance_monitor_state,
    bind_mission_authority,
    contract_from_legacy_action,
    digest_payload,
    digest_text,
    filter_envelope_subject_digest,
    guard_subject_digest,
    mission_from_legacy,
    proposal_contract_subject_digest,
    semantic_witness_digest,
)
from proofalign.intent_parser import parse_intent
from proofalign.models import Object, ObjectPart, Pose, Region, WorldState


_VALID_UNTIL = 10**18


def _attestation(
    evidence_type: str,
    subject_digest: str,
    *,
    producer_id: str = "test-producer",
    producer_version: str = "1",
    assumptions: tuple[str, ...] = (),
    tag: str = "valid",
) -> EvidenceAttestation:
    return EvidenceAttestation(
        evidence_type=evidence_type,
        subject_digest=subject_digest,
        producer_id=producer_id,
        producer_version=producer_version,
        issued_at_ns=0,
        valid_until_ns=_VALID_UNTIL,
        payload_digest=digest_payload(
            {"type": evidence_type, "subject": subject_digest, "tag": tag}
        ),
        proof_digest=digest_text(f"proof:{evidence_type}:{subject_digest}:{tag}"),
        assumptions=assumptions,
    )


def _collect_attestations(value) -> tuple[EvidenceAttestation, ...]:
    found: list[EvidenceAttestation] = []

    def visit(item) -> None:
        if isinstance(item, EvidenceAttestation):
            found.append(item)
        elif is_dataclass(item):
            for descriptor in fields(item):
                visit(getattr(item, descriptor.name))
        elif isinstance(item, dict):
            for nested in item.values():
                visit(nested)
        elif isinstance(item, (tuple, list, set, frozenset)):
            for nested in item:
                visit(nested)

    visit(value)
    unique = {item.attestation_digest: item for item in found}
    return tuple(unique.values())


def _checker(mission: MissionSpec, *values) -> CTDAChecker:
    verifier = DigestAllowlistEvidenceVerifier()
    verifier.trust(*_collect_attestations((mission,) + values))
    return CTDAChecker(
        trusted_authorities=(mission.authority.authority_id,),
        evidence_verifier=verifier,
    )


def _trust(checker: CTDAChecker, *values) -> None:
    verifier = checker.evidence_verifier
    assert isinstance(verifier, DigestAllowlistEvidenceVerifier)
    verifier.trust(*_collect_attestations(values))


def _mission(*, authenticated: bool = True) -> MissionSpec:
    authority = AuthorityEnvelope(
        authority_id="libero-test-manifest",
        source="test-manifest",
        version="1",
        attestation_digest="unsigned",
        authenticated=False,
    )
    time_base = TimeBase(
        clock_id="test-monotonic",
        control_period_ns=10,
        max_jitter_ns=1,
        monitor_latency_ns=2,
        switch_latency_ns=3,
    )
    mission = MissionSpec(
        spec_id="mission-pick-mug",
        authority=authority,
        instruction_digest=digest_text("pick up the mug by the handle"),
        goal="holding:mug",
        phases=("approach", "holding"),
        transitions=(TaskTransition("approach", "Pick", "holding"),),
        initial_phase="approach",
        time_base=time_base,
        episode_nonce="episode-test-001",
        hard_invariants=("no_collision",),
        object_ids=("mug", "human_hand"),
        safe_parts=(("mug", "handle"),),
        default_must_preserve=("human_hand",),
        goal_atoms=("holding:mug",),
        goal_phases=("holding",),
        phase_obligations=(
            PhaseObligation(
                "obligation-pick-mug",
                "approach",
                "Pick",
                "holding",
                ("holding:mug", "phase:holding"),
                target="mug",
                part="handle",
                completes_goal=True,
            ),
        ),
    )
    if not authenticated:
        return mission
    return bind_mission_authority(
        mission,
        _attestation(
            "authority",
            mission.mission_claim_digest,
            producer_id="libero-test-manifest",
            producer_version="1",
        ),
    )


def _contract(mission: MissionSpec) -> SemanticSkillContract:
    return SemanticSkillContract(
        contract_id="contract-pick-mug",
        spec_id=mission.spec_id,
        spec_digest=mission.spec_digest,
        phase_before="approach",
        expected_next_phase="holding",
        skill="Pick",
        issued_at_ns=0,
        deadline_ns=1_000,
        target="mug",
        part="handle",
        guards=("target_visible",),
        guarantees=("holding:mug", "phase:holding"),
        may_modify=("mug",),
        must_preserve=("human_hand",),
        fallback_id="hold",
        semantic_pre_requirements=("grounding",),
        physical_pre_requirements=("tube", "fallback"),
        runtime_requirements=("observer", "timing"),
        post_requirements=("grasp",),
        advances_obligations=("obligation-pick-mug",),
    )


def _semantic_evidence(contract: SemanticSkillContract) -> tuple[EvidenceAttestation, ...]:
    return (_attestation("grounding", contract.contract_digest),)


def _guard_evidence(
    contract: SemanticSkillContract,
    state_digest: str,
    monitor: ContractMonitorState,
) -> tuple[EvidenceAttestation, ...]:
    subject = guard_subject_digest(
        contract,
        state_digest,
        monitor.monitor_state_digest,
    )
    return (_attestation("guard:target_visible", subject),)


def _candidate(
    mission: MissionSpec,
    contract: SemanticSkillContract,
    monitor: ContractMonitorState,
    *,
    proposal_admissible: bool | None = True,
    filter_preserves_contract: bool | None = True,
    proposal_index: int = 0,
) -> tuple[PrefixCandidate, str]:
    state_digest = digest_payload({"state": 0})
    proposal_digest = digest_payload({"raw_actions": [[0.1, 0.0, 0.0, -1.0]]})
    command_digest = digest_payload({"filtered_actions": [[0.1, 0.0, 0.0, -1.0]]})
    model_digest = digest_text("kinematic-model-v1")
    tube = ReachableTube(
        authorized_command_digest=command_digest,
        dynamics_model_digest=model_digest,
        duration_ns=80,
        fallback_id="hold",
        all_prefixes_safe=True,
        all_cut_states_recoverable=True,
        witness_digest=digest_text("tube-witness"),
        assumptions=("bounded_delta",),
    )
    tube = replace(
        tube,
        attestation=_attestation(
            "reachable_tube",
            tube.claim_digest,
            assumptions=tube.assumptions,
        ),
    )
    proposal = ActionProposalBinding(
        contract_id=contract.contract_id,
        contract_digest=contract.contract_digest,
        proposal_index=proposal_index,
        proposal_digest=proposal_digest,
        proposed_horizon_ns=100,
        issued_at_ns=10,
    )
    semantic_attestations = _semantic_evidence(contract)
    semantic_witness = semantic_witness_digest(
        mission,
        contract.phase_before,
        contract,
        semantic_attestations,
    )
    authorization = PrefixAuthorization(
        contract_id=contract.contract_id,
        contract_digest=contract.contract_digest,
        spec_digest=mission.spec_digest,
        episode_nonce=mission.episode_nonce,
        state_digest=state_digest,
        monitor_state_digest=monitor.monitor_state_digest,
        proposal_index=proposal_index,
        proposal_digest=proposal_digest,
        authorized_command_digest=command_digest,
        filter_policy_digest=digest_text("identity-filter-v1"),
        dynamics_model_digest=model_digest,
        time_base_digest=mission.time_base.time_base_digest,
        tube_digest=tube.tube_digest,
        max_authorized_duration_ns=50,
        fallback_id="hold",
        issued_at_ns=10,
        valid_until_ns=90,
        semantic_witness_digest=semantic_witness,
    )
    proposal_witness = digest_text("proposal-contract-witness")
    filter_witness = digest_text("filter-envelope-witness")
    proposal_contract_attestation = _attestation(
        "proposal_contract",
        proposal_contract_subject_digest(
            contract,
            proposal,
            proposal_admissible,
            proposal_witness,
        ),
    )
    filter_envelope_attestation = _attestation(
        "filter_envelope",
        filter_envelope_subject_digest(
            contract,
            proposal,
            authorization,
            filter_preserves_contract,
            filter_witness,
        ),
    )
    pre_attestations = (
        _attestation("tube", authorization.authorization_digest),
        _attestation("fallback", authorization.authorization_digest),
    )
    return (
        PrefixCandidate(
            proposal=proposal,
            authorization=authorization,
            tube=tube,
            proposal_contract_witness_digest=proposal_witness,
            filter_envelope_witness_digest=filter_witness,
            proposal_admissible=proposal_admissible,
            filter_preserves_contract=filter_preserves_contract,
            semantic_attestations=semantic_attestations,
            guard_attestations=_guard_evidence(contract, state_digest, monitor),
            proposal_contract_attestation=proposal_contract_attestation,
            filter_envelope_attestation=filter_envelope_attestation,
            pre_attestations=pre_attestations,
        ),
        state_digest,
    )


def _record(
    mission: MissionSpec,
    contract: SemanticSkillContract,
    monitor: ContractMonitorState,
    candidate: PrefixCandidate,
    *,
    events: tuple[SymbolicEvent, ...] | None = None,
    sample_timestamps: tuple[int, ...] = (20, 40),
    receipt_time: int | None = None,
) -> PrefixExecutionRecord:
    command_digest = candidate.authorization.authorized_command_digest
    samples = tuple(
        PlantSample(
            timestamp,
            (
                candidate.authorization.state_digest
                if index == 0
                else digest_payload({"state": index})
            ),
            command_digest,
            True,
            True,
            True,
        )
        for index, timestamp in enumerate(sample_timestamps)
    )
    plant_trace = PlantTrace(
        time_base_digest=mission.time_base.time_base_digest,
        samples=samples,
        observer_evidence_digest=digest_text("observer-evidence"),
    )
    plant_trace = replace(
        plant_trace,
        attestation=_attestation(
            "plant_trace",
            plant_trace.claim_digest,
            assumptions=candidate.tube.assumptions,
        ),
    )
    final_timestamp = sample_timestamps[-1]
    if events is None:
        events = (
            SymbolicEvent(final_timestamp, "holding:mug", True, object_id="mug"),
            SymbolicEvent(final_timestamp, "phase:holding", True),
        )
    links = tuple(
        AbstractionLink(
            index,
            len(samples) - 1,
            event.atom,
            digest_text(f"derive:{index}:{event.atom}"),
        )
        for index, event in enumerate(events)
    )
    abstraction = TraceAbstractionEvidence(
        plant_trace_digest=plant_trace.plant_trace_digest,
        time_base_digest=mission.time_base.time_base_digest,
        events_digest=digest_payload(events),
        links=links,
        producer_id="test-event-extractor",
        producer_version="1",
        witness_digest=digest_text("abstraction-witness"),
    )
    abstraction = replace(
        abstraction,
        attestation=_attestation(
            "trace_abstraction",
            abstraction.claim_digest,
            producer_id=abstraction.producer_id,
            producer_version=abstraction.producer_version,
        ),
    )
    event_trace = SymbolicEventTrace(
        time_base_digest=mission.time_base.time_base_digest,
        plant_trace_digest=plant_trace.plant_trace_digest,
        abstraction_evidence_digest=abstraction.abstraction_evidence_digest,
        events=events,
    )
    after_monitor = advance_monitor_state(
        contract, monitor, event_trace, candidate.proposal.proposal_index
    )
    receipt = ExecutionReceipt(
        authorization_digest=candidate.authorization.authorization_digest,
        authorized_command_digest=command_digest,
        executed_command_digest=command_digest,
        actuator_evidence_digest=digest_text("actuator-receipt"),
        executed_at_ns=(sample_timestamps[0] if receipt_time is None else receipt_time),
        within_authorized_error=True,
    )
    receipt = replace(
        receipt,
        attestation=_attestation("actuator_receipt", receipt.claim_digest),
    )
    runtime_attestations = (
        _attestation("observer", plant_trace.plant_trace_digest),
        _attestation("timing", plant_trace.plant_trace_digest),
    )
    return PrefixExecutionRecord(
        candidate=candidate,
        receipt=receipt,
        plant_trace=plant_trace,
        event_trace=event_trace,
        abstraction_evidence=abstraction,
        monitor_before_digest=monitor.monitor_state_digest,
        monitor_after_digest=after_monitor.monitor_state_digest,
        runtime_attestations=runtime_attestations,
    )


def _post_evidence(record: PrefixExecutionRecord) -> tuple[EvidenceAttestation, ...]:
    return (_attestation("grasp", record.event_trace.symbolic_event_trace_digest),)


def test_unauthenticated_mission_fails_closed() -> None:
    mission = _mission(authenticated=False)
    result = _checker(mission).check_mission_spec(mission, now_ns=20)

    assert result.verdict is StaticVerdict.REFUTED
    assert any("authority attestation" in issue for issue in result.issues)


def test_semantic_refinement_distinguishes_unknown_from_proven() -> None:
    mission = _mission()
    contract = _contract(mission)
    unknown_evidence: tuple[EvidenceAttestation, ...] = ()
    proven_evidence = _semantic_evidence(contract)
    checker = _checker(mission, unknown_evidence, proven_evidence)

    unknown = checker.check_semantic_refinement(
        mission, "approach", contract, unknown_evidence, now_ns=20
    )
    proven = checker.check_semantic_refinement(
        mission, "approach", contract, proven_evidence, now_ns=20
    )

    assert unknown.verdict is StaticVerdict.UNKNOWN
    assert any("grounding" in issue for issue in unknown.issues)
    assert proven.verdict is StaticVerdict.PROVEN


def test_prefix_authorization_binds_contract_and_rejects_replay() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    checker = _checker(mission, candidate)

    first = checker.check_prefix_pre(
        mission, contract, state_digest, monitor, candidate, now_ns=20
    )
    replay = checker.check_prefix_pre(
        mission, contract, state_digest, monitor, candidate, now_ns=20
    )

    assert first.verdict is StaticVerdict.PROVEN
    assert replay.verdict is StaticVerdict.REFUTED
    assert any("replay" in issue for issue in replay.issues)


@pytest.mark.parametrize(
    ("admissible", "preserved", "expected"),
    [
        (False, True, StaticVerdict.REFUTED),
        (True, False, StaticVerdict.REFUTED),
        (None, True, StaticVerdict.UNKNOWN),
        (True, None, StaticVerdict.UNKNOWN),
    ],
)
def test_prefix_requires_proposal_and_filter_envelope_witnesses(
    admissible: bool | None,
    preserved: bool | None,
    expected: StaticVerdict,
) -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(
        mission,
        contract,
        monitor,
        proposal_admissible=admissible,
        filter_preserves_contract=preserved,
    )

    result = _checker(mission, candidate).check_prefix_pre(
        mission, contract, state_digest, monitor, candidate, now_ns=20, commit=False
    )

    assert result.verdict is expected


def test_complete_record_checks_both_trace_domains_and_advances_phase() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    post_evidence = _post_evidence(record)
    checker = _checker(mission, candidate, record, post_evidence)

    pre = checker.check_prefix_pre(
        mission, contract, state_digest, monitor, candidate, now_ns=20
    )
    observed = checker.check_observed_prefix(mission, contract, record, now_ns=40)
    monitored = checker.monitor_step(
        mission, contract, monitor, record, evidence=post_evidence, now_ns=40
    )
    execution = ContractExecution(
        contract_id=contract.contract_id,
        spec_digest=mission.spec_digest,
        episode_nonce=mission.episode_nonce,
        initial_state_digest=state_digest,
        initial_monitor_state_digest=monitor.monitor_state_digest,
        prefixes=(record,),
    )
    chain = checker.check_execution_chain(execution, contract)
    audited = checker.check_contract_execution(
        mission,
        contract,
        execution,
        monitor,
        evidence=post_evidence,
        now_ns=40,
    )

    assert pre.verdict is StaticVerdict.PROVEN
    assert observed.verdict is StaticVerdict.PROVEN
    assert monitored.verdict is MonitorVerdict.COMPLETE
    assert monitored.monitor_state.phase == "holding"
    assert chain.verdict is StaticVerdict.PROVEN
    assert audited.verdict is MonitorVerdict.COMPLETE


def test_monitor_completes_guarantees_split_across_prefixes() -> None:
    mission = _mission()
    contract = _contract(mission)
    initial = ContractMonitorState.initial(mission, contract)
    first_candidate, _ = _candidate(mission, contract, initial, proposal_index=0)
    first_record = _record(
        mission,
        contract,
        initial,
        first_candidate,
        events=(SymbolicEvent(20, "holding:mug", True, object_id="mug"),),
        sample_timestamps=(15, 20),
    )
    first_checker = _checker(mission, first_candidate, first_record)

    first = first_checker.monitor_step(
        mission, contract, initial, first_record, now_ns=20
    )

    assert first.verdict is MonitorVerdict.SAFE_PENDING
    assert tuple(event.atom for event in first.monitor_state.accepted_events) == (
        "holding:mug",
    )

    second_candidate, _ = _candidate(
        mission, contract, first.monitor_state, proposal_index=1
    )
    second_record = _record(
        mission,
        contract,
        first.monitor_state,
        second_candidate,
        events=(SymbolicEvent(35, "phase:holding", True),),
        sample_timestamps=(30, 35),
    )
    post_evidence = _post_evidence(second_record)
    second_checker = _checker(
        mission, second_candidate, second_record, post_evidence
    )

    second = second_checker.monitor_step(
        mission,
        contract,
        first.monitor_state,
        second_record,
        evidence=post_evidence,
        now_ns=35,
    )

    assert second.verdict is MonitorVerdict.COMPLETE
    assert tuple(event.atom for event in second.monitor_state.accepted_events) == (
        "holding:mug",
        "phase:holding",
    )
    assert second.monitor_state.episode_nonce == mission.episode_nonce


def test_monitor_rejects_cross_prefix_timestamp_rollback() -> None:
    mission = _mission()
    contract = _contract(mission)
    initial = ContractMonitorState.initial(mission, contract)
    first_candidate, _ = _candidate(mission, contract, initial, proposal_index=0)
    first_record = _record(
        mission,
        contract,
        initial,
        first_candidate,
        events=(SymbolicEvent(20, "holding:mug", True, object_id="mug"),),
        sample_timestamps=(15, 20),
    )
    first = _checker(mission, first_candidate, first_record).monitor_step(
        mission, contract, initial, first_record, now_ns=20
    )
    assert first.verdict is MonitorVerdict.SAFE_PENDING

    second_candidate, _ = _candidate(
        mission, contract, first.monitor_state, proposal_index=1
    )
    rollback_record = _record(
        mission,
        contract,
        first.monitor_state,
        second_candidate,
        events=(SymbolicEvent(15, "phase:holding", True),),
        sample_timestamps=(10, 15),
    )
    result = _checker(mission, second_candidate, rollback_record).monitor_step(
        mission, contract, first.monitor_state, rollback_record, now_ns=15
    )

    assert result.verdict is MonitorVerdict.INCONSISTENT
    assert any("strictly extend" in issue for issue in result.issues)


def test_monitor_history_is_digest_bound() -> None:
    mission = _mission()
    contract = _contract(mission)
    initial = ContractMonitorState.initial(mission, contract)
    with_history = replace(
        initial,
        accepted_events=(SymbolicEvent(10, "holding:mug", True),),
        last_event_timestamp_ns=10,
    )

    assert with_history.verify_integrity()
    assert with_history.monitor_state_digest != initial.monitor_state_digest
    erased_history = replace(with_history, accepted_events=())
    assert not erased_history.history_is_well_formed()


def test_trace_abstraction_tampering_is_refuted() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    tampered_event_trace = replace(
        record.event_trace,
        plant_trace_digest=digest_text("another-plant-trace"),
    )

    result = _checker(mission, record).check_trace_abstraction(
        record.plant_trace, tampered_event_trace, record.abstraction_evidence
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("another plant trace" in issue for issue in result.issues)


def test_collision_event_violates_monitor_even_if_task_effect_completes() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(
        mission,
        contract,
        monitor,
        candidate,
        events=(
            SymbolicEvent(40, "collision", True),
            SymbolicEvent(40, "holding:mug", True, object_id="mug"),
            SymbolicEvent(40, "phase:holding", True),
        ),
    )

    post_evidence = _post_evidence(record)
    result = _checker(mission, record, post_evidence).monitor_step(
        mission, contract, monitor, record, evidence=post_evidence, now_ns=40
    )

    assert result.verdict is MonitorVerdict.VIOLATED
    assert any("collision" in issue for issue in result.issues)


def test_nonfinite_values_cannot_enter_digest_chain() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        digest_payload({"distance": float("nan")})


def test_digest_mapping_rejects_non_string_keys_instead_of_aliasing() -> None:
    with pytest.raises(TypeError, match="string keys"):
        digest_payload({1: "first", "1": "second"})


def test_default_checker_does_not_trust_self_asserted_authority() -> None:
    mission = _mission()

    result = CTDAChecker().check_mission_spec(mission, now_ns=20)

    assert result.verdict is StaticVerdict.REFUTED
    assert any("trusted authority set" in issue for issue in result.issues)


def test_unverified_semantic_attestation_cannot_satisfy_requirement() -> None:
    mission = _mission()
    contract = _contract(mission)
    evidence = _semantic_evidence(contract)
    checker = _checker(mission)  # Intentionally trust only the authority attestation.

    result = checker.check_semantic_refinement(
        mission, "approach", contract, evidence, now_ns=20
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("configured verifier" in issue for issue in result.issues)


def test_semantic_refinement_rejects_guarantee_unrelated_to_goal_obligation() -> None:
    mission = _mission()
    contract = replace(_contract(mission), guarantees=("holding:knife", "phase:holding"))
    evidence = _semantic_evidence(contract)

    result = _checker(mission, evidence).check_semantic_refinement(
        mission, "approach", contract, evidence, now_ns=20
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("do not imply obligation" in issue for issue in result.issues)


def test_prefix_rejects_missing_typed_tube_attestation() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    candidate = replace(candidate, tube=replace(candidate.tube, attestation=None))

    result = _checker(mission, candidate).check_prefix_pre(
        mission, contract, state_digest, monitor, candidate, now_ns=20, commit=False
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("reachable_tube attestation" in issue for issue in result.issues)


def test_offline_execution_reruns_precheck_and_rejects_wrong_semantic_witness() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    bad_authorization = replace(
        candidate.authorization,
        semantic_witness_digest=digest_text("wrong-semantic-witness"),
    )
    bad_record = replace(record, candidate=replace(candidate, authorization=bad_authorization))
    execution = ContractExecution(
        contract.contract_id,
        mission.spec_digest,
        mission.episode_nonce,
        state_digest,
        monitor.monitor_state_digest,
        (bad_record,),
    )
    post_evidence = _post_evidence(bad_record)

    result = _checker(mission, bad_record, post_evidence).check_contract_execution(
        mission,
        contract,
        execution,
        monitor,
        evidence=post_evidence,
        now_ns=40,
    )

    assert result.verdict is MonitorVerdict.VIOLATED
    assert any("semantic refinement witness" in issue for issue in result.issues)


def test_observed_trace_must_end_inside_authorization_window() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(
        mission,
        contract,
        monitor,
        candidate,
        sample_timestamps=(100,),
        receipt_time=20,
    )

    result = _checker(mission, record).check_observed_prefix(
        mission, contract, record, now_ns=100
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("authorization expiry" in issue for issue in result.issues)


def test_observed_timing_sla_cannot_be_disabled_without_bound_policy() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)

    result = _checker(mission, record).check_observed_prefix(
        mission,
        contract,
        record,
        now_ns=40,
        enforce_dispatch_observation_sla=False,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("diagnostic timing policy is not bound" in issue for issue in result.issues)


def test_deadline_is_checked_before_late_completion() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    post_evidence = _post_evidence(record)

    result = _checker(mission, record, post_evidence).monitor_step(
        mission,
        contract,
        monitor,
        record,
        evidence=post_evidence,
        now_ns=contract.deadline_ns + 1,
    )

    assert result.verdict is MonitorVerdict.VIOLATED
    assert any("deadline" in issue for issue in result.issues)


def test_symbolic_event_rejects_untyped_falsy_integer() -> None:
    with pytest.raises(TypeError, match="TruthValue"):
        SymbolicEvent(10, "holding:mug", 0)

    assert SymbolicEvent(10, "holding:mug", False).value is TruthValue.FALSE


def test_abstraction_requires_authenticated_producer_evidence() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)

    result = _checker(mission).check_trace_abstraction(
        record.plant_trace,
        record.event_trace,
        record.abstraction_evidence,
        now_ns=40,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("configured verifier" in issue for issue in result.issues)


def test_supervisor_blocks_parallel_authorization_and_latches_violation() -> None:
    mission = _mission()
    contract = _contract(mission)
    semantic_evidence = _semantic_evidence(contract)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    record = _record(
        mission,
        contract,
        monitor,
        candidate,
        events=(SymbolicEvent(40, "collision", True),),
    )
    checker = _checker(mission, semantic_evidence, candidate, record)
    supervisor = CTDASupervisor(mission, checker, now_ns=20)

    assert supervisor.activate_contract(
        contract, semantic_evidence, now_ns=20
    ).verdict is StaticVerdict.PROVEN
    assert supervisor.authorize_prefix(
        state_digest, candidate, now_ns=20
    ).verdict is StaticVerdict.PROVEN
    parallel = supervisor.authorize_prefix(state_digest, candidate, now_ns=20)
    violation = supervisor.observe_prefix(record, now_ns=40)
    after_violation = supervisor.authorize_prefix(state_digest, candidate, now_ns=50)

    assert parallel.verdict is StaticVerdict.REFUTED
    assert any("in flight" in issue for issue in parallel.issues)
    assert violation.verdict is MonitorVerdict.VIOLATED
    assert after_violation.verdict is StaticVerdict.REFUTED
    assert any("latched" in issue for issue in after_violation.issues)


def test_authority_attestation_is_bound_to_complete_unsigned_mission() -> None:
    mission = _mission()
    tampered = replace(mission, hard_invariants=())

    result = _checker(tampered).check_mission_spec(tampered, now_ns=20)

    assert tampered.verify_integrity()
    assert tampered.mission_claim_digest != mission.mission_claim_digest
    assert result.verdict is StaticVerdict.REFUTED
    assert any("another subject" in issue for issue in result.issues)


def test_episode_nonce_is_authority_signed_and_execution_bound() -> None:
    mission = _mission()
    tampered_mission = replace(mission, episode_nonce="another-episode")
    assert _checker(tampered_mission).check_mission_spec(
        tampered_mission, now_ns=20
    ).verdict is StaticVerdict.REFUTED

    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    execution = ContractExecution(
        contract.contract_id,
        mission.spec_digest,
        "another-episode",
        state_digest,
        monitor.monitor_state_digest,
        (record,),
    )
    post_evidence = _post_evidence(record)
    result = _checker(mission, record, post_evidence).check_contract_execution(
        mission,
        contract,
        execution,
        monitor,
        evidence=post_evidence,
        now_ns=40,
    )
    assert result.verdict is MonitorVerdict.VIOLATED
    assert any("episode" in issue for issue in result.issues)


def test_abstraction_attestation_binds_full_event_value_payload() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(
        mission,
        contract,
        monitor,
        candidate,
        events=(SymbolicEvent(40, "holding:mug", False, object_id="mug"),),
    )
    flipped = replace(
        record.event_trace,
        events=(SymbolicEvent(40, "holding:mug", True, object_id="mug"),),
    )

    result = _checker(mission, record).check_trace_abstraction(
        record.plant_trace,
        flipped,
        record.abstraction_evidence,
        now_ns=40,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("different symbolic events" in issue for issue in result.issues)


@pytest.mark.parametrize("field", ["proposal", "filter"])
def test_proposal_and_filter_attestations_bind_their_verdict(field: str) -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(
        mission,
        contract,
        monitor,
        proposal_admissible=(field != "proposal"),
        filter_preserves_contract=(field != "filter"),
    )
    flipped = (
        replace(candidate, proposal_admissible=True)
        if field == "proposal"
        else replace(candidate, filter_preserves_contract=True)
    )

    result = _checker(mission, flipped).check_prefix_pre(
        mission,
        contract,
        state_digest,
        monitor,
        flipped,
        now_ns=20,
        commit=False,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("another subject" in issue for issue in result.issues)


def test_all_runtime_optional_booleans_reject_integer_aliases() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)

    with pytest.raises(TypeError, match="bool or None"):
        replace(candidate.tube, all_prefixes_safe=0)
    with pytest.raises(TypeError, match="bool or None"):
        replace(candidate, proposal_admissible=0)
    with pytest.raises(TypeError, match="bool or None"):
        replace(record.receipt, within_authorized_error=0)
    with pytest.raises(TypeError, match="bool or None"):
        replace(record.plant_trace.samples[0], hard_invariants_hold=0)
    with pytest.raises(TypeError, match="must be bool"):
        replace(mission.phase_obligations[0], completes_goal=1)


def test_direct_monitor_step_cannot_bypass_failed_prefix_precheck() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    unsafe_candidate, _ = _candidate(
        mission,
        contract,
        monitor,
        proposal_admissible=False,
    )
    record = _record(mission, contract, monitor, unsafe_candidate)
    post_evidence = _post_evidence(record)

    result = _checker(mission, record, post_evidence).monitor_step(
        mission,
        contract,
        monitor,
        record,
        evidence=post_evidence,
        now_ns=40,
    )

    assert result.verdict is MonitorVerdict.VIOLATED
    assert any("outside the semantic contract" in issue for issue in result.issues)


def test_dynamic_guard_is_state_bound_and_checked_at_dispatch_time() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)
    stale_guards = tuple(
        replace(item, valid_until_ns=10) for item in candidate.guard_attestations
    )
    stale_candidate = replace(candidate, guard_attestations=stale_guards)

    stale = _checker(mission, stale_candidate).check_prefix_pre(
        mission,
        contract,
        state_digest,
        monitor,
        stale_candidate,
        now_ns=20,
        commit=False,
    )
    wrong_state_guard = _attestation(
        "guard:target_visible",
        guard_subject_digest(contract, digest_text("other-state"), monitor.monitor_state_digest),
    )
    wrong_candidate = replace(candidate, guard_attestations=(wrong_state_guard,))
    wrong_state = _checker(mission, wrong_candidate).check_prefix_pre(
        mission,
        contract,
        state_digest,
        monitor,
        wrong_candidate,
        now_ns=20,
        commit=False,
    )

    assert stale.verdict is StaticVerdict.REFUTED
    assert any("stale" in issue for issue in stale.issues)
    assert wrong_state.verdict is StaticVerdict.REFUTED
    assert any("another subject" in issue for issue in wrong_state.issues)


def test_dispatch_requires_remaining_window_for_full_prefix() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, state_digest = _candidate(mission, contract, monitor)

    result = _checker(mission, candidate).check_prefix_pre(
        mission,
        contract,
        state_digest,
        monitor,
        candidate,
        now_ns=80,
        commit=False,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("remaining authorization window" in issue for issue in result.issues)


def test_false_event_revokes_current_guarantee_before_completion() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(
        mission,
        contract,
        monitor,
        candidate,
        events=(
            SymbolicEvent(40, "holding:mug", True, object_id="mug"),
            SymbolicEvent(40, "holding:mug", False, object_id="mug"),
            SymbolicEvent(40, "phase:holding", True),
        ),
    )
    post_evidence = _post_evidence(record)

    result = _checker(mission, record, post_evidence).monitor_step(
        mission,
        contract,
        monitor,
        record,
        evidence=post_evidence,
        now_ns=40,
    )

    assert result.verdict is MonitorVerdict.SAFE_PENDING
    assert "holding:mug" not in result.monitor_state.completed_guarantees


def test_pick_contract_cannot_omit_mission_safe_part() -> None:
    mission = _mission()
    contract = replace(_contract(mission), part=None)
    evidence = _semantic_evidence(contract)

    result = _checker(mission, evidence).check_semantic_refinement(
        mission,
        "approach",
        contract,
        evidence,
        now_ns=20,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("part" in issue for issue in result.issues)


def test_complete_witness_binds_post_attestations_and_evaluation_time() -> None:
    mission = _mission()
    contract = _contract(mission)
    monitor = ContractMonitorState.initial(mission, contract)
    candidate, _ = _candidate(mission, contract, monitor)
    record = _record(mission, contract, monitor, candidate)
    subject = record.event_trace.symbolic_event_trace_digest
    first_evidence = (_attestation("grasp", subject, tag="post-a"),)
    second_evidence = (_attestation("grasp", subject, tag="post-b"),)
    checker = _checker(mission, record, first_evidence, second_evidence)

    first = checker.monitor_step(
        mission, contract, monitor, record, evidence=first_evidence, now_ns=40
    )
    second = checker.monitor_step(
        mission, contract, monitor, record, evidence=second_evidence, now_ns=40
    )

    assert first.verdict is MonitorVerdict.COMPLETE
    assert second.verdict is MonitorVerdict.COMPLETE
    assert first.witness_ref != second.witness_ref


def test_legacy_models_compile_into_frozen_mission_and_contract(safe_state, safe_spec) -> None:
    intent = parse_intent("pick up the mug by the handle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    unsigned_mission = mission_from_legacy(
        intent,
        safe_state,
        safe_spec,
        AuthorityEnvelope(
            "test-authority",
            "fixture",
            "1",
            "unsigned",
        ),
        TimeBase("test-clock", 10, 1, 1, 1),
        spec_id="legacy-pick",
        episode_nonce="legacy-episode-1",
    )
    mission = bind_mission_authority(
        unsigned_mission,
        _attestation(
            "authority",
            unsigned_mission.mission_claim_digest,
            producer_id="test-authority",
            producer_version="1",
        ),
    )
    contract = contract_from_legacy_action(
        mission,
        action,
        contract_id="legacy-contract",
        current_phase=mission.initial_phase,
        issued_at_ns=0,
        deadline_ns=1_000,
    )

    assert mission.frozen
    assert mission.verify_integrity()
    assert contract.verify_integrity()
    assert contract.target == "mug"
    assert contract.guarantees == ("holding:mug",)
    assert contract.advances_obligations


def test_legacy_mission_resolves_unique_libero_instance_and_directional_region(safe_spec) -> None:
    state = WorldState(
        objects={
            "fork_1": Object(
                "fork_1",
                "fork",
                Pose(0.1, 0.0, 0.0),
                {
                    "handle": ObjectPart("handle", safe_to_grasp=True),
                    "tines": ObjectPart("tines", safe_to_grasp=False, dangerous=True),
                },
            ),
            "plate_1": Object("plate_1", "plate", Pose(0.2, 0.0, 0.0), {"body": ObjectPart("body")}),
        },
        regions={
            "main_table_plate_region": Region("main_table_plate_region", Pose(0.2, 0.0, 0.0)),
            "main_table_plate_right_region": Region("main_table_plate_right_region", Pose(0.3, 0.0, 0.0)),
        },
    )

    mission = mission_from_legacy(
        parse_intent("pick up the fork and place it on the right of the plate"),
        state,
        safe_spec,
        AuthorityEnvelope("test-authority", "fixture", "1", "unsigned"),
        TimeBase("test-clock", 10, 1, 1, 1),
        spec_id="libero-affordance",
        episode_nonce="episode-1",
    )

    assert set(mission.goal_atoms) == {
        "released:fork_1",
        "in_region:fork_1:main_table_plate_right_region",
    }
    assert mission.phase_obligations[0].target == "fork_1"
    assert mission.phase_obligations[1].region == "main_table_plate_right_region"
