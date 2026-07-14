from __future__ import annotations

from dataclasses import replace

import pytest

from proofalign.action_abstraction import action_from_dict
from proofalign.ctda import (
    AuthorityEnvelope,
    EvidenceAttestation,
    MonitorVerdict,
    StaticVerdict,
    TimeBase,
    digest_text,
)
from proofalign.ctda_runtime import (
    ConditionalKinematicConfig,
    CTDARuntimeSession,
    ExactAllowlistEvidenceIssuer,
    RawProposalBinderConfig,
)
from proofalign.intent_parser import parse_intent


def _authority() -> AuthorityEnvelope:
    return AuthorityEnvelope(
        "libero-test",
        "fixture",
        "1",
        digest_text("fixture-attestation"),
        authenticated=False,
    )


def _time_base() -> TimeBase:
    return TimeBase("test-clock", 20_000_000, 1_000_000, 1_000_000, 2_000_000)


def _session(safe_state, safe_spec, *, fallback_verified: bool) -> CTDARuntimeSession:
    intent = parse_intent("pick up the mug by the handle")
    config = ConditionalKinematicConfig(
        fallback_verified=fallback_verified,
        fallback_witness_digest=(digest_text("verified-hold") if fallback_verified else ""),
        fallback_action=((0.0, 0.0, 0.0, 0.0) if fallback_verified else ()),
    )
    return CTDARuntimeSession.from_legacy(
        intent,
        safe_state,
        safe_spec,
        _authority(),
        _time_base(),
        spec_id="runtime-pick",
        episode_nonce="runtime-pick-episode",
        config=config,
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
    )


def _held_state(safe_state):
    after = safe_state.clone()
    after.gripper_holding = "mug"
    after.objects["mug"].held_by = "gripper"
    return after


def test_runtime_fails_closed_without_verified_fallback(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=False)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = session.prepare_prefix(
        action, safe_state, ([0.1, 0.0, 0.0, -1.0],), safe_spec, now_ns=1_000_000
    )

    assert result.check.verdict is StaticVerdict.REFUTED
    assert any("recoverable" in issue for issue in result.check.issues)
    assert result.prepared is None


def test_runtime_authorizes_then_completes_pick_contract(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.1, 0.0, 0.0, -1.0]

    prepared = session.prepare_prefix(action, safe_state, (raw,), safe_spec, now_ns=1_000_000)
    assert prepared.check.verdict is StaticVerdict.PROVEN
    assert prepared.prepared is not None

    monitored, record = session.observe_prefix(
        prepared.prepared,
        (_held_state(safe_state),),
        (raw,),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )

    assert record.verify_integrity()
    assert record.receipt.executed_at_ns == 2_000_000
    assert record.plant_trace.samples[0].timestamp_ns == 3_000_000
    assert record.candidate.semantic_attestations
    assert record.candidate.pre_attestations
    assert record.runtime_attestations
    assert record.receipt.attestation is not None
    assert record.plant_trace.attestation is not None
    assert record.abstraction_evidence.attestation is not None
    assert monitored.verdict is MonitorVerdict.COMPLETE
    assert session.supervisor.active_contract is None
    assert session.supervisor.active_phase == "holding"


def test_runtime_rejects_command_outside_kinematic_model(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = session.prepare_prefix(
        action, safe_state, ([5.0, 0.0, 0.0, -1.0],), safe_spec, now_ns=1_000_000
    )

    assert result.check.verdict is StaticVerdict.REFUTED
    assert any("unsafe prefix" in issue for issue in result.check.issues)


def test_runtime_detects_authorized_executed_command_mismatch(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    proposed = [0.1, 0.0, 0.0, -1.0]
    prepared = session.prepare_prefix(
        action, safe_state, (proposed,), safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None

    monitored, _ = session.observe_prefix(
        prepared.prepared,
        (_held_state(safe_state),),
        ([0.2, 0.0, 0.0, -1.0],),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )

    assert monitored.verdict is MonitorVerdict.VIOLATED
    assert any("authorized error" in issue for issue in monitored.issues)


def test_runtime_persists_pending_contract_across_policy_proposals(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    first_raw = [0.1, 0.0, 0.0, -1.0]
    first = session.prepare_prefix(
        action, safe_state, (first_raw,), safe_spec, now_ns=1_000_000
    )
    assert first.prepared is not None
    intermediate = safe_state.clone()

    pending, _ = session.observe_prefix(
        first.prepared,
        (intermediate,),
        (first_raw,),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )
    second = session.prepare_prefix(
        action,
        intermediate,
        ([0.0, 0.0, 0.0, -1.0],),
        safe_spec,
        now_ns=50_000_000,
    )

    assert pending.verdict is MonitorVerdict.SAFE_PENDING
    assert session.supervisor.active_contract is not None
    assert second.check.verdict is StaticVerdict.PROVEN
    assert second.prepared is not None
    assert second.prepared.candidate.proposal.proposal_index == 1


def test_paper_contract_and_verdict_ignore_policy_symbolic_metadata(
    safe_state, safe_spec
) -> None:
    trusted = _session(safe_state, safe_spec, fallback_verified=True)
    tampered = _session(safe_state, safe_spec, fallback_verified=True)
    raw = ([0.1, 0.0, 0.0, -1.0],)
    trusted_metadata = action_from_dict(
        {"type": "Pick", "object": "mug", "part": "handle"}
    )
    adversarial_metadata = action_from_dict(
        {"type": "Place", "object": "knife", "region": "attacker_region"}
    )

    first = trusted.prepare_prefix(
        trusted_metadata, safe_state, raw, safe_spec, now_ns=1_000_000
    )
    second = tampered.prepare_prefix(
        adversarial_metadata, safe_state, raw, safe_spec, now_ns=1_000_000
    )

    assert first.check.verdict is second.check.verdict is StaticVerdict.PROVEN
    assert trusted.supervisor.mission.spec_digest == tampered.supervisor.mission.spec_digest
    assert trusted.supervisor.active_contract is not None
    assert tampered.supervisor.active_contract is not None
    assert (
        trusted.supervisor.active_contract.contract_digest
        == tampered.supervisor.active_contract.contract_digest
    )
    assert first.prepared is not None and second.prepared is not None
    assert (
        first.prepared.candidate.proposal_contract_witness_digest
        == second.prepared.candidate.proposal_contract_witness_digest
    )


def test_trusted_instruction_or_registry_change_invalidates_old_contract(
    safe_state, safe_spec
) -> None:
    original = _session(safe_state, safe_spec, fallback_verified=True)
    raw = ([0.1, 0.0, 0.0, -1.0],)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    prepared = original.prepare_prefix(
        action, safe_state, raw, safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None
    old_contract = original.supervisor.active_contract
    assert old_contract is not None

    changed_intent = replace(
        parse_intent("pick up the mug by the handle"),
        raw_instruction="trusted benchmark instruction revision",
    )
    revised = CTDARuntimeSession.from_legacy(
        changed_intent,
        safe_state,
        safe_spec,
        _authority(),
        _time_base(),
        spec_id="runtime-pick",
        episode_nonce="runtime-pick-episode",
        config=original.config,
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
    )
    changed_registry = safe_state.clone()
    changed_registry.objects.pop("knife")
    registry_revision = CTDARuntimeSession.from_legacy(
        parse_intent("pick up the mug by the handle"),
        changed_registry,
        safe_spec,
        _authority(),
        _time_base(),
        spec_id="runtime-pick",
        episode_nonce="runtime-pick-episode",
        config=original.config,
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
    )

    assert revised.supervisor.mission.spec_digest != original.supervisor.mission.spec_digest
    assert (
        registry_revision.supervisor.mission.spec_digest
        != original.supervisor.mission.spec_digest
    )
    stale = revised.supervisor.checker.check_semantic_refinement(
        revised.supervisor.mission,
        revised.supervisor.active_phase,
        old_contract,
        now_ns=1_000_000,
    )
    assert stale.verdict is StaticVerdict.REFUTED


@pytest.mark.parametrize(
    ("mutate_state", "raw", "issue"),
    [
        (lambda state: state, ([-0.1, -0.1, 0.0, 0.0],), "moves away"),
        (
            lambda state: _state_holding(state, "knife"),
            ([0.1, 0.0, 0.0, -1.0],),
            "wrong held object",
        ),
    ],
)
def test_raw_binder_fails_closed_on_wrong_target_gripper_or_held_object(
    safe_state, safe_spec, mutate_state, raw, issue
) -> None:
    state = mutate_state(safe_state.clone())
    session = _session(safe_state, safe_spec, fallback_verified=True)
    untrusted_metadata = action_from_dict(
        {"type": "Pick", "object": "knife", "part": "blade"}
    )

    result = session.prepare_prefix(
        untrusted_metadata, state, raw, safe_spec, now_ns=1_000_000
    )

    assert result.check.verdict is StaticVerdict.REFUTED
    assert result.prepared is None
    assert any(issue in item for item in result.check.issues)
    assert session.proposal_index == 0
    assert session.supervisor.active_phase == "approach"


def test_raw_binder_supports_libero_panda_positive_close_direction(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    session.config = replace(
        session.config,
        raw_binder=RawProposalBinderConfig(
            version="libero-panda-test",
            gripper_close_threshold=0.2,
            gripper_open_threshold=-0.2,
            close_direction=1,
        ),
    )

    result = session.prepare_prefix(
        action_from_dict({"type": "Pick", "object": "mug", "part": "handle"}),
        safe_state,
        ([0.1, 0.0, 0.0, -1.0],),
        safe_spec,
        now_ns=1_000_000,
    )

    assert result.check.verdict is StaticVerdict.PROVEN


def _enable_cumulative_bounded_stutter(session: CTDARuntimeSession) -> None:
    translation_scale_m = 0.05
    model_error_m = 0.0001
    session.config = replace(
        session.config,
        translation_scale_m=translation_scale_m,
        model_error_m=model_error_m,
        raw_binder=RawProposalBinderConfig(
            version="libero-panda-cumulative-bounded-stutter-test",
            gripper_close_threshold=0.2,
            gripper_open_threshold=-0.2,
            close_direction=1,
            translation_scale_m=translation_scale_m,
            stutter_translation_bound_m=model_error_m,
            stutter_motion_command_bound=model_error_m / translation_scale_m,
            stutter_no_progress_limit=3,
        ),
    )


def test_bounded_stutter_accumulates_authorized_budget_without_phase_advance(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(session)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [
        -2.9359772193421688e-05,
        -3.973322361683698e-05,
        2.783448300552882e-05,
        -4.214741228427549e-05,
        -3.560969454670382e-05,
        -4.817225890894894e-05,
        -1.0,
    ]

    prepared = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=1_000_000
    )

    assert prepared.check.verdict is StaticVerdict.PROVEN
    assert prepared.prepared is not None
    assert prepared.prepared.bounded_stutter is True
    assert prepared.prepared.bounded_stutter_count_before == 0
    assert prepared.prepared.candidate.bounded_stutter is True
    assert prepared.prepared.candidate.bounded_stutter_index == 0
    candidate = prepared.prepared.candidate
    assert candidate.bounded_stutter_no_progress_limit == 3
    assert candidate.bounded_stutter_translation_consumed_before_m == 0.0
    assert candidate.bounded_stutter_translation_m > 0.0
    assert candidate.bounded_stutter_translation_budget_m == 0.0001
    assert candidate.bounded_stutter_motion_consumed_before == 0.0
    assert candidate.bounded_stutter_motion_command_norm > 0.0
    assert candidate.bounded_stutter_motion_budget == 0.002
    assert session.bounded_stutter_count == 1

    monitored, _ = session.observe_prefix(
        prepared.prepared,
        (safe_state.clone(),),
        (raw,),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )

    assert monitored.verdict is MonitorVerdict.SAFE_PENDING
    assert session.supervisor.active_phase == "approach"
    assert session.supervisor.active_contract is not None
    assert session.bounded_stutter_count == 1
    assert session.supervisor.active_phase == "approach"

    second = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=4_000_000
    )
    assert second.check.verdict is StaticVerdict.PROVEN
    assert second.prepared is not None
    assert second.prepared.candidate.bounded_stutter_index == 1
    assert (
        second.prepared.bounded_stutter_translation_before_m
        == prepared.prepared.bounded_stutter_translation_after_m
    )
    assert (
        second.prepared.bounded_stutter_motion_before
        == prepared.prepared.bounded_stutter_motion_after
    )
    assert session.bounded_stutter_count == 2


def test_bounded_stutter_fails_closed_on_unexpected_contract_progress(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(session)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]
    prepared = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None
    assert prepared.prepared.bounded_stutter is True

    with pytest.raises(RuntimeError, match="bounded stutter produced contract progress"):
        session.observe_prefix(
            prepared.prepared,
            (_held_state(safe_state),),
            (raw,),
            safe_spec,
            dispatch_ns=2_000_000,
            observation_times_ns=(3_000_000,),
        )

    assert session.supervisor.active_phase == "approach"
    assert session.bounded_stutter_count == 1


def test_bounded_stutter_refuses_cumulative_command_path_overrun(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(session)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.0, 0.0, 0.0, 0.0011, 0.0, 0.0, -1.0]

    first = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=1_000_000
    )
    assert first.prepared is not None
    monitored, _ = session.observe_prefix(
        first.prepared,
        (safe_state.clone(),),
        (raw,),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )
    assert monitored.verdict is MonitorVerdict.SAFE_PENDING

    overrun = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=4_000_000
    )
    assert overrun.check.verdict is StaticVerdict.REFUTED
    assert overrun.prepared is None
    assert any(
        "command-path budget is exceeded" in issue
        for issue in overrun.check.issues
    )
    assert session.bounded_stutter_motion_consumed == pytest.approx(0.0011)


def test_bounded_stutter_has_persistent_no_progress_limit(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(session)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0]

    for index in range(3):
        start = 1_000_000 + index * 3_000_000
        prepared = session.prepare_prefix(
            action, safe_state, (raw,), safe_spec, now_ns=start
        )
        assert prepared.prepared is not None
        monitored, _ = session.observe_prefix(
            prepared.prepared,
            (safe_state.clone(),),
            (raw,),
            safe_spec,
            dispatch_ns=start + 1_000_000,
            observation_times_ns=(start + 2_000_000,),
        )
        assert monitored.verdict is MonitorVerdict.SAFE_PENDING

    exhausted = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=11_000_000
    )
    assert exhausted.check.verdict is StaticVerdict.REFUTED
    assert exhausted.prepared is None
    assert any(
        "persistent bounded-stutter no-progress limit is exhausted" in issue
        for issue in exhausted.check.issues
    )


def test_bounded_stutter_reset_cannot_refund_budget_or_deadline(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(session)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.0, 0.0, 0.0, 0.0011, 0.0, 0.0, -1.0]

    first = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=1_000_000
    )
    assert first.prepared is not None
    original_deadline = session.bounded_stutter_deadline_ns
    assert original_deadline is not None

    session.reset()
    assert session.bounded_stutter_count == 1
    assert session.bounded_stutter_motion_consumed == pytest.approx(0.0011)
    assert session.bounded_stutter_deadline_ns == original_deadline
    overrun = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=2_000_000
    )
    assert overrun.check.verdict is StaticVerdict.REFUTED
    assert any("command-path budget is exceeded" in issue for issue in overrun.check.issues)

    session.reset()
    expired = session.prepare_prefix(
        action, safe_state, (raw,), safe_spec, now_ns=original_deadline + 1
    )
    assert expired.check.verdict is StaticVerdict.REFUTED
    assert any("original bounded-stutter contract deadline" in issue for issue in expired.check.issues)


def test_bounded_stutter_does_not_admit_large_rotation_or_translation(
    safe_state, safe_spec
) -> None:
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    rotation_session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(rotation_session)
    rotation = rotation_session.prepare_prefix(
        action,
        safe_state,
        ([0.0, 0.0, 0.0, 0.01, 0.0, 0.0, -1.0],),
        safe_spec,
        now_ns=1_000_000,
    )
    assert rotation.check.verdict is StaticVerdict.UNKNOWN
    assert rotation.prepared is None

    translation_session = _session(safe_state, safe_spec, fallback_verified=True)
    _enable_cumulative_bounded_stutter(translation_session)
    translation = translation_session.prepare_prefix(
        action,
        safe_state,
        ([-0.1, -0.1, 0.0, 0.0, 0.0, 0.0, -1.0],),
        safe_spec,
        now_ns=1_000_000,
    )
    assert translation.check.verdict is StaticVerdict.REFUTED
    assert translation.prepared is None
    assert any("moves away" in issue for issue in translation.check.issues)


def test_bounded_stutter_must_fit_frozen_model_error() -> None:
    binder = RawProposalBinderConfig(
        stutter_translation_bound_m=0.001,
        stutter_motion_command_bound=0.02,
        stutter_no_progress_limit=3,
    )
    with pytest.raises(ValueError, match="model-error allowance"):
        ConditionalKinematicConfig(model_error_m=0.0001, raw_binder=binder)

    with pytest.raises(ValueError, match="enabled together"):
        RawProposalBinderConfig(stutter_translation_bound_m=0.0001)


def test_raw_binder_rejects_release_outside_mission_region(
    safe_state, safe_spec
) -> None:
    held = _state_holding(safe_state.clone(), "mug")
    session = CTDARuntimeSession.from_legacy(
        parse_intent("place the mug on the plate"),
        held,
        safe_spec,
        _authority(),
        _time_base(),
        spec_id="runtime-place",
        episode_nonce="runtime-place-episode",
        config=ConditionalKinematicConfig(
            fallback_verified=True,
            fallback_witness_digest=digest_text("verified-hold"),
            fallback_action=(0.0, 0.0, 0.0, 0.0),
        ),
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
    )

    result = session.prepare_prefix(
        action_from_dict({"type": "Place", "object": "knife", "region": "attacker"}),
        held,
        ([0.0, 0.0, 0.0, 1.0],),
        safe_spec,
        now_ns=1_000_000,
    )

    assert result.check.verdict is StaticVerdict.REFUTED
    assert any("releases outside" in issue for issue in result.check.issues)
    assert session.proposal_index == 0
    assert session.supervisor.active_phase == "holding"


def _state_holding(state, object_id: str):
    state.gripper_holding = object_id
    state.objects[object_id].held_by = "gripper"
    return state


def test_runtime_from_legacy_fails_closed_without_evidence_issuer(safe_state, safe_spec) -> None:
    intent = parse_intent("pick up the mug by the handle")

    with pytest.raises(ValueError, match="typed evidence issuer"):
        CTDARuntimeSession.from_legacy(
            intent,
            safe_state,
            safe_spec,
            _authority(),
            _time_base(),
            spec_id="missing-issuer",
            episode_nonce="missing-issuer-episode",
            now_ns=0,
        )


def test_runtime_exact_allowlist_rejects_forged_attestation(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    prepared = session.prepare_prefix(
        action, safe_state, ([0.1, 0.0, 0.0, -1.0],), safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None
    candidate = prepared.prepared.candidate
    original = candidate.proposal_contract_attestation
    assert original is not None
    forged = EvidenceAttestation(
        evidence_type=original.evidence_type,
        subject_digest=original.subject_digest,
        producer_id=original.producer_id,
        producer_version=original.producer_version,
        issued_at_ns=original.issued_at_ns,
        valid_until_ns=original.valid_until_ns,
        payload_digest=digest_text("forged-payload"),
        proof_digest=digest_text("forged-proof"),
        assumptions=original.assumptions,
    )
    forged_candidate = replace(candidate, proposal_contract_attestation=forged)
    contract = session.supervisor.active_contract
    monitor = session.supervisor.monitor_state
    assert contract is not None and monitor is not None

    result = session.supervisor.checker.check_prefix_pre(
        session.supervisor.mission,
        contract,
        prepared.prepared.state_digest,
        monitor,
        forged_candidate,
        now_ns=1_000_000,
        commit=False,
    )

    assert result.verdict is StaticVerdict.REFUTED
    assert any("not authenticated" in issue for issue in result.issues)


def test_runtime_rejects_stale_authority_attestation(safe_state, safe_spec) -> None:
    intent = parse_intent("pick up the mug by the handle")
    session = CTDARuntimeSession.from_legacy(
        intent,
        safe_state,
        safe_spec,
        _authority(),
        _time_base(),
        spec_id="stale-authority",
        episode_nonce="stale-authority-episode",
        config=ConditionalKinematicConfig(
            fallback_verified=True,
            fallback_witness_digest=digest_text("verified-hold"),
            fallback_action=(0.0, 0.0, 0.0, 0.0),
            evidence_validity_ns=10,
        ),
        evidence_issuer=ExactAllowlistEvidenceIssuer(),
        now_ns=0,
    )
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = session.prepare_prefix(
        action, safe_state, ([0.1, 0.0, 0.0, -1.0],), safe_spec, now_ns=20
    )

    assert result.check.verdict is StaticVerdict.REFUTED
    assert any("authority attestation is stale" in issue for issue in result.check.issues)


def test_fallback_switch_receipt_binds_pre_and_post_state(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator_attestation = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=_held_state(safe_state),
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator_attestation,
    )

    assert receipt.succeeded is True
    assert receipt.command_application == "typed_simulator_applied"
    assert receipt.verify_integrity()
    assert receipt.attestation is not None
    assert session.evidence_issuer is not None
    assert session.evidence_issuer.verifier.verify(receipt.attestation)

    tampered = replace(receipt, state_after_digest=digest_text("different-post-state"))
    assert not tampered.verify_integrity()


def test_fallback_success_is_computed_and_rejects_clearance_below_margin(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )
    unsafe_after = safe_state.clone()
    unsafe_after.min_distance_to_obstacle = safe_spec.safety_margin / 2

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=unsafe_after,
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator,
    )

    assert receipt.succeeded is False
    assert receipt.postcondition.distance_thresholds_hold is False
    assert receipt.postcondition.mission_invariants_hold is False


def test_fallback_ignores_irrelevant_unknown_clearance_observations(
    safe_state, safe_spec
) -> None:
    affordance_spec = replace(safe_spec, protected_objects=[])
    session = _session(safe_state, affordance_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )
    after = safe_state.clone()
    after.notes.extend(
        (
            "ctda_unknown_observation:min_distance_to_human_hand",
            "ctda_unknown_observation:min_distance_to_obstacle",
        )
    )

    receipt = session.record_fallback_switch(
        trigger="pending contract",
        state_before=safe_state,
        state_after=after,
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=affordance_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator,
    )

    assert receipt.succeeded is True
    assert receipt.verify_integrity()
    assert receipt.postcondition.observation_complete is True
    assert receipt.postcondition.distance_thresholds_hold is True
    assert receipt.postcondition.human_clearance_m is None
    assert receipt.postcondition.obstacle_clearance_m is None
    assert receipt.postcondition.required_observations == ("collision", "cost")
    assert receipt.postcondition.issues == ()


@pytest.mark.parametrize(
    ("protected_object", "missing_observation"),
    (
        ("human_hand", "min_distance_to_human_hand"),
        ("obstacle", "min_distance_to_obstacle"),
    ),
)
def test_fallback_missing_suite_required_clearance_fails_closed(
    safe_state, safe_spec, protected_object, missing_observation
) -> None:
    suite_spec = replace(safe_spec, protected_objects=[protected_object])
    session = _session(safe_state, suite_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )
    after = safe_state.clone()
    after.notes.append(f"ctda_unknown_observation:{missing_observation}")

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=after,
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=suite_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator,
    )

    assert receipt.succeeded is False
    assert receipt.verify_integrity()
    assert receipt.postcondition.observation_complete is False
    assert receipt.postcondition.distance_thresholds_hold is False
    assert receipt.postcondition.mission_invariants_hold is False
    assert missing_observation in receipt.postcondition.required_observations
    assert any(
        missing_observation in issue for issue in receipt.postcondition.issues
    )


def test_fallback_without_actuator_evidence_is_requested_only(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=safe_state,
        command=session.fallback_command(),
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
    )

    assert receipt.command_application == "requested_only"
    assert receipt.applied_command_digest is None
    assert receipt.actuator_attestation is None
    assert receipt.succeeded is False


def test_fallback_switch_latency_uses_violation_trigger_and_fails_closed(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=safe_state,
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=_time_base().switch_latency_ns + 1,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator,
    )

    assert receipt.postcondition.proven is True
    assert receipt.succeeded is False
    assert receipt.observed_at_ns - receipt.triggered_at_ns > receipt.switch_latency_bound_ns


def test_fallback_observation_failure_is_unknown_and_attempt_is_persisted(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=2, applied_at_ns=2
    )

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=None,
        command=command,
        triggered_at_ns=0,
        requested_at_ns=1,
        dispatched_at_ns=2,
        observed_at_ns=3,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
        observation_error="camera unavailable",
        actuator_attestation=actuator,
    )

    assert receipt.succeeded is False
    assert receipt.postcondition.observation_complete is False
    assert receipt.state_after_digest != receipt.state_before_digest
    assert session.last_fallback_receipt is receipt
    assert session.supervisor.active_contract is None
    assert session.supervisor.monitor_state is None
    assert session.active_execution is None
    assert session.supervisor.terminal_verdict is MonitorVerdict.INCONSISTENT


def test_fallback_atomically_abandons_active_contract_and_authorization(
    safe_state, safe_spec
) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    prepared = session.prepare_prefix(
        action, safe_state, ([0.1, 0.0, 0.0, -1.0],), safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None
    assert session.supervisor.active_contract is not None
    assert session.supervisor.pending_authorization_digest is not None
    assert session.supervisor.monitor_state is not None
    assert session.active_execution is not None
    command = session.fallback_command()
    actuator = session.attest_fallback_actuation(
        command, dispatched_at_ns=1_100_002, applied_at_ns=1_100_002
    )

    receipt = session.record_fallback_switch(
        trigger="monitor violation",
        state_before=safe_state,
        state_after=safe_state,
        command=command,
        triggered_at_ns=1_100_000,
        requested_at_ns=1_100_001,
        dispatched_at_ns=1_100_002,
        observed_at_ns=1_100_003,
        safety_spec=safe_spec,
        environment_info={"cost": {}},
        actuator_attestation=actuator,
    )

    assert receipt.active_contract_digest is not None
    assert receipt.pending_authorization_digest is not None
    assert receipt.active_execution_digest is not None
    assert receipt.monitor_state_digest is not None
    assert session.supervisor.active_contract is None
    assert session.supervisor.pending_authorization_digest is None
    assert session.supervisor.monitor_state is None
    assert session.active_execution is None
    assert session.supervisor.terminal_verdict is MonitorVerdict.VIOLATED


def test_verified_hold_fallback_must_stay_inside_command_envelope() -> None:
    with pytest.raises(ValueError, match="command envelope"):
        ConditionalKinematicConfig(
            max_command_abs=1.0,
            fallback_verified=True,
            fallback_witness_digest=digest_text("hold"),
            fallback_action=(0.0, 0.0, 0.0, 2.0),
        )
    with pytest.raises(ValueError, match="hold fallback"):
        ConditionalKinematicConfig(
            fallback_verified=True,
            fallback_witness_digest=digest_text("hold"),
            fallback_action=(0.1, 0.0, 0.0, 0.0),
        )


def test_runtime_rejects_authorization_replay(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    prepared = session.prepare_prefix(
        action, safe_state, ([0.1, 0.0, 0.0, -1.0],), safe_spec, now_ns=1_000_000
    )
    assert prepared.prepared is not None
    contract = session.supervisor.active_contract
    monitor = session.supervisor.monitor_state
    assert contract is not None and monitor is not None

    replay = session.supervisor.checker.check_prefix_pre(
        session.supervisor.mission,
        contract,
        prepared.prepared.state_digest,
        monitor,
        prepared.prepared.candidate,
        now_ns=1_000_000,
        commit=True,
    )

    assert replay.verdict is StaticVerdict.REFUTED
    assert any("replay" in issue for issue in replay.issues)


def test_runtime_uses_real_dispatch_time_and_rejects_expired_window(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.1, 0.0, 0.0, -1.0]
    prepared = session.prepare_prefix(action, safe_state, (raw,), safe_spec, now_ns=1_000_000)
    assert prepared.prepared is not None

    monitored, record = session.observe_prefix(
        prepared.prepared,
        (_held_state(safe_state),),
        (raw,),
        safe_spec,
        dispatch_ns=50_000_000,
        observation_times_ns=(51_000_000,),
    )

    assert record.receipt.executed_at_ns == 50_000_000
    assert monitored.verdict is MonitorVerdict.VIOLATED
    assert any(
        "authorization" in issue and ("stale" in issue or "window" in issue)
        for issue in monitored.issues
    )


def test_runtime_missing_observation_is_unknown_not_certified(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    unknown_state = safe_state.clone()
    unknown_state.notes.append("ctda_unknown_observation:min_distance_to_obstacle")
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})

    result = session.prepare_prefix(
        action,
        unknown_state,
        ([0.1, 0.0, 0.0, -1.0],),
        safe_spec,
        now_ns=1_000_000,
    )

    assert result.check.verdict is StaticVerdict.UNKNOWN
    assert result.prepared is None
    assert any("prefix safety witness is missing" in issue for issue in result.check.issues)


def test_runtime_detects_observed_motion_outside_kinematic_model(safe_state, safe_spec) -> None:
    session = _session(safe_state, safe_spec, fallback_verified=True)
    action = action_from_dict({"type": "Pick", "object": "mug", "part": "handle"})
    raw = [0.1, 0.0, 0.0, -1.0]
    prepared = session.prepare_prefix(action, safe_state, (raw,), safe_spec, now_ns=1_000_000)
    assert prepared.prepared is not None
    after = _held_state(safe_state)
    after.robot_pose = after.objects["mug"].pose

    monitored, record = session.observe_prefix(
        prepared.prepared,
        (after,),
        (raw,),
        safe_spec,
        dispatch_ns=2_000_000,
        observation_times_ns=(3_000_000,),
    )

    assert monitored.verdict is MonitorVerdict.VIOLATED
    assert any(
        "left the certified tube" in issue or "model assumption" in issue
        for issue in monitored.issues
    )
    diagnostics = record.plant_trace.samples[0].kinematic_diagnostics
    assert diagnostics is not None
    assert diagnostics.cumulative_translation_bound_m == pytest.approx(0.005)
    assert diagnostics.model_error_allowance_m == 0.0
    assert diagnostics.cumulative_displacement_limit_m == pytest.approx(0.005)
    assert diagnostics.cumulative_observed_displacement_m is not None
    assert diagnostics.cumulative_displacement_margin_m is not None
    assert diagnostics.cumulative_displacement_margin_m < 0.0
