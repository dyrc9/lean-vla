"""Outcome-blind golden corpus for CTDA v2 Python/Lean wire parity."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from proofalign.ctda import digest_text
from proofalign.ctda_v2 import CORE_SCHEMA_VERSION, METHOD_ID
from proofalign.ctda_v2_wire import (
    V2WireEnvelope,
    V2WireStage,
    V2WireVerdict,
    make_v2_wire_envelope,
)


def _digest(label: str) -> str:
    return digest_text(f"ctda-v2-golden:{label}")


def _common() -> dict[str, Any]:
    return {"method_id": METHOD_ID, "schema_version": CORE_SCHEMA_VERSION}


def semantic_certificate_payload() -> dict[str, Any]:
    return {
        **_common(),
        "claim_digest": _digest("certificate-claim"),
        "certificate_digest": _digest("certificate"),
        "mission_root_digest": _digest("mission-root"),
        "episode_nonce": "episode-v2-golden",
        "phase": "approach",
        "residual_obligations": ["pick:mug"],
        "contract_version": "pick-contract-v2",
        "proof_state_episode_nonce": "episode-v2-golden",
        "proof_state_known": True,
        "proof_state_observed_at_ns": 10,
        "proof_started_at_ns": 20,
        "proof_completed_at_ns": 100,
        "proof_attestation_issued_at_ns": 100,
        "proof_attestation_subject_digest": _digest("certificate-claim"),
        "proof_producer_id": "proofalign-lean-kernel",
        "expected_proof_producer_id": "proofalign-lean-kernel",
        "proof_producer_version": "4.24.0-golden",
        "expected_proof_producer_version": "4.24.0-golden",
        "proof_authenticated": True,
        "fast_checker_digest": _digest("fast-checker"),
        "expected_fast_checker_digest": _digest("fast-checker"),
    }


def state_rebind_payload() -> dict[str, Any]:
    return {
        **_common(),
        "certificate_verdict": "proven",
        "certificate_digest": _digest("certificate"),
        "lease_digest": _digest("lease"),
        "lease_claim_digest": _digest("lease-claim"),
        "lease_certificate_digest": _digest("certificate"),
        "certificate_checker_digest": _digest("fast-checker"),
        "lease_checker_digest": _digest("fast-checker"),
        "certificate_mission_root_digest": _digest("mission-root"),
        "context_mission_root_digest": _digest("mission-root"),
        "certificate_episode_nonce": "episode-v2-golden",
        "activation_episode_nonce": "episode-v2-golden",
        "context_episode_nonce": "episode-v2-golden",
        "certificate_phase": "approach",
        "context_phase": "approach",
        "certificate_residual_obligations": ["pick:mug"],
        "context_residual_obligations": ["pick:mug"],
        "certificate_contract_version": "pick-contract-v2",
        "context_contract_version": "pick-contract-v2",
        "proof_completed_at_ns": 100,
        "activation_state_known": True,
        "activation_observed_at_ns": 101,
        "activation_max_sensor_age_ns": 1000,
        "activated_at_ns": 102,
        "now_ns": 105,
        "activated_control_epoch": 7,
        "valid_through_control_epoch": 15,
        "context_control_epoch": 7,
        "rebind_attestation_subject_digest": _digest("lease-claim"),
        "rebind_authenticated": True,
    }


def prefix_decision_payload() -> dict[str, Any]:
    return {
        **_common(),
        "lease_verdict": "proven",
        "certificate_digest": _digest("certificate"),
        "decision_certificate_digest": _digest("certificate"),
        "lease_digest": _digest("lease"),
        "decision_lease_digest": _digest("lease"),
        "context_episode_nonce": "episode-v2-golden",
        "decision_episode_nonce": "episode-v2-golden",
        "context_control_epoch": 7,
        "decision_control_epoch": 7,
        "activation_snapshot_digest": _digest("activation-snapshot"),
        "decision_state_snapshot_digest": _digest("activation-snapshot"),
        "safety_bundle_digest": _digest("safety-bundle"),
        "decision_safety_bundle_digest": _digest("safety-bundle"),
        "required_safety_channels_complete": True,
        "safety_unknown": False,
        "safety_violated": False,
        "decision_claim_digest": _digest("decision-claim"),
        "nominal_command_digest": _digest("nominal-command"),
        "intervention": "pass",
        "adjusted_command_digest": _digest("nominal-command"),
        "filter_application_digest": None,
        "filter_nominal_command_digest": None,
        "filter_adjusted_command_digest": None,
        "membership_attestation_subject_digest": _digest("decision-claim"),
        "membership_authenticated": True,
    }


def prefix_authorization_payload() -> dict[str, Any]:
    return {
        **_common(),
        "decision_verdict": "proven",
        "intervention": "pass",
        "decision_digest": _digest("decision"),
        "authorization_decision_digest": _digest("decision"),
        "certificate_digest": _digest("certificate"),
        "authorization_certificate_digest": _digest("certificate"),
        "lease_digest": _digest("lease"),
        "authorization_lease_digest": _digest("lease"),
        "context_episode_nonce": "episode-v2-golden",
        "authorization_episode_nonce": "episode-v2-golden",
        "decision_proposal_index": 0,
        "authorization_proposal_index": 0,
        "context_control_epoch": 7,
        "authorization_control_epoch": 7,
        "decision_adjusted_command_digest": _digest("nominal-command"),
        "authorized_command_digest": _digest("nominal-command"),
        "issued_at_ns": 104,
        "valid_until_ns": 130,
        "now_ns": 105,
        "authorization_claim_digest": _digest("authorization-claim"),
        "authorization_attestation_subject_digest": _digest("authorization-claim"),
        "authorization_authenticated": True,
        "authorization_unused": True,
    }


def dispatch_receipt_payload() -> dict[str, Any]:
    return {
        **_common(),
        "authorization_verdict": "proven",
        "authorization_digest": _digest("authorization"),
        "receipt_authorization_digest": _digest("authorization"),
        "authorization_episode_nonce": "episode-v2-golden",
        "receipt_episode_nonce": "episode-v2-golden",
        "authorization_proposal_index": 0,
        "receipt_proposal_index": 0,
        "authorization_control_epoch": 7,
        "receipt_control_epoch": 7,
        "decision_nominal_command_digest": _digest("nominal-command"),
        "receipt_nominal_command_digest": _digest("nominal-command"),
        "authorized_command_digest": _digest("nominal-command"),
        "executed_command_digest": _digest("nominal-command"),
        "issued_at_ns": 104,
        "valid_until_ns": 130,
        "dispatched_at_ns": 106,
        "receipt_actuator_subject_digest": _digest("actuator-subject"),
        "expected_actuator_subject_digest": _digest("actuator-subject"),
        "actuator_authenticated": True,
        "authorization_unused": True,
    }


def progress_update_payload() -> dict[str, Any]:
    return {
        **_common(),
        "certificate_digest": _digest("certificate"),
        "ledger_certificate_digest": _digest("certificate"),
        "before_snapshot_digest": _digest("activation-snapshot"),
        "ledger_last_snapshot_digest": _digest("activation-snapshot"),
        "after_episode_nonce": "episode-v2-golden",
        "ledger_episode_nonce": "episode-v2-golden",
        "last_state_epoch": 1,
        "after_state_epoch": 2,
        "after_state_known": True,
        "after_observed_at_ns": 110,
        "after_max_sensor_age_ns": 1000,
        "now_ns": 111,
        "progress_claim_digest": _digest("progress-claim"),
        "progress_attestation_subject_digest": _digest("progress-claim"),
        "progress_authenticated": True,
        "distance_before_um": 200_000,
        "distance_after_um": 180_000,
        "minimum_progress_um": 10_000,
        "elapsed_control_epochs": 1,
        "consecutive_nonprogress_control_epochs": 0,
        "max_nonprogress_control_epochs": 5,
        "cumulative_translation_um": 0,
        "translation_consumed_um": 5_000,
        "translation_budget_um": 100_000,
        "cumulative_motion_units": 0,
        "motion_consumed_units": 5,
        "motion_budget_units": 100,
    }


@dataclass(frozen=True)
class V2GoldenCase:
    case_id: str
    request: V2WireEnvelope
    expected: V2WireVerdict


def _mutated(
    payload: dict[str, Any], mutation: Callable[[dict[str, Any]], None]
) -> dict[str, Any]:
    retained = deepcopy(payload)
    mutation(retained)
    return retained


def build_v2_golden_corpus(checker_version_digest: str) -> tuple[V2GoldenCase, ...]:
    cases: list[tuple[str, V2WireStage, dict[str, Any], V2WireVerdict]] = []

    def add(
        case_id: str,
        stage: V2WireStage,
        payload: dict[str, Any],
        expected: V2WireVerdict,
    ) -> None:
        cases.append((case_id, stage, payload, expected))

    certificate = semantic_certificate_payload()
    add("certificate-proven", V2WireStage.SEMANTIC_CERTIFICATE, certificate, V2WireVerdict.PROVEN)
    add(
        "certificate-subject-tamper",
        V2WireStage.SEMANTIC_CERTIFICATE,
        _mutated(certificate, lambda value: value.__setitem__("proof_attestation_subject_digest", _digest("other"))),
        V2WireVerdict.REFUTED,
    )
    add(
        "certificate-unknown-state",
        V2WireStage.SEMANTIC_CERTIFICATE,
        _mutated(certificate, lambda value: value.__setitem__("proof_state_known", False)),
        V2WireVerdict.REFUTED,
    )

    rebind = state_rebind_payload()
    add("state-rebind-proven", V2WireStage.STATE_REBIND, rebind, V2WireVerdict.PROVEN)
    add(
        "state-rebind-cross-episode",
        V2WireStage.STATE_REBIND,
        _mutated(rebind, lambda value: value.__setitem__("context_episode_nonce", "replay")),
        V2WireVerdict.REFUTED,
    )
    add(
        "state-rebind-stale",
        V2WireStage.STATE_REBIND,
        _mutated(rebind, lambda value: value.__setitem__("now_ns", 1_102)),
        V2WireVerdict.REFUTED,
    )

    decision = prefix_decision_payload()
    add("decision-pass-proven", V2WireStage.PREFIX_DECISION, decision, V2WireVerdict.PROVEN)
    add(
        "decision-unknown-safety-pass",
        V2WireStage.PREFIX_DECISION,
        _mutated(decision, lambda value: value.__setitem__("safety_unknown", True)),
        V2WireVerdict.REFUTED,
    )
    projected = _mutated(
        decision,
        lambda value: value.update(
            {
                "intervention": "project_or_brake",
                "adjusted_command_digest": _digest("adjusted-command"),
                "filter_application_digest": _digest("filter-application"),
                "filter_nominal_command_digest": _digest("nominal-command"),
                "filter_adjusted_command_digest": _digest("wrong-adjusted-command"),
            }
        ),
    )
    add(
        "decision-filter-binding-tamper",
        V2WireStage.PREFIX_DECISION,
        projected,
        V2WireVerdict.REFUTED,
    )
    hard_block = _mutated(
        decision,
        lambda value: value.update(
            {
                "safety_violated": True,
                "intervention": "hard_block",
                "adjusted_command_digest": None,
                "membership_attestation_subject_digest": None,
                "membership_authenticated": False,
            }
        ),
    )
    add(
        "decision-observed-violation-hard-block",
        V2WireStage.PREFIX_DECISION,
        hard_block,
        V2WireVerdict.PROVEN,
    )

    authorization = prefix_authorization_payload()
    add(
        "authorization-proven",
        V2WireStage.PREFIX_AUTHORIZATION,
        authorization,
        V2WireVerdict.PROVEN,
    )
    add(
        "authorization-nondispatch-replan",
        V2WireStage.PREFIX_AUTHORIZATION,
        _mutated(authorization, lambda value: value.__setitem__("intervention", "replan")),
        V2WireVerdict.REFUTED,
    )
    add(
        "authorization-replay",
        V2WireStage.PREFIX_AUTHORIZATION,
        _mutated(authorization, lambda value: value.__setitem__("authorization_unused", False)),
        V2WireVerdict.REFUTED,
    )

    receipt = dispatch_receipt_payload()
    add("receipt-proven", V2WireStage.DISPATCH_RECEIPT, receipt, V2WireVerdict.PROVEN)
    add(
        "receipt-command-tamper",
        V2WireStage.DISPATCH_RECEIPT,
        _mutated(receipt, lambda value: value.__setitem__("executed_command_digest", _digest("other"))),
        V2WireVerdict.REFUTED,
    )
    add(
        "receipt-replay",
        V2WireStage.DISPATCH_RECEIPT,
        _mutated(receipt, lambda value: value.__setitem__("authorization_unused", False)),
        V2WireVerdict.REFUTED,
    )

    progress = progress_update_payload()
    add("progress-proven", V2WireStage.PROGRESS_UPDATE, progress, V2WireVerdict.PROVEN)
    add(
        "progress-no-progress-replan",
        V2WireStage.PROGRESS_UPDATE,
        _mutated(progress, lambda value: value.__setitem__("distance_after_um", 199_000)),
        V2WireVerdict.REPLAN,
    )
    add(
        "progress-unknown-replan",
        V2WireStage.PROGRESS_UPDATE,
        _mutated(
            progress,
            lambda value: value.update({"distance_before_um": None, "distance_after_um": None}),
        ),
        V2WireVerdict.REPLAN,
    )
    add(
        "progress-budget-hard-block",
        V2WireStage.PROGRESS_UPDATE,
        _mutated(progress, lambda value: value.__setitem__("translation_budget_um", 4_000)),
        V2WireVerdict.HARD_BLOCK,
    )
    add(
        "progress-binding-hard-block",
        V2WireStage.PROGRESS_UPDATE,
        _mutated(progress, lambda value: value.__setitem__("after_episode_nonce", "replay")),
        V2WireVerdict.HARD_BLOCK,
    )

    return tuple(
        V2GoldenCase(
            case_id,
            make_v2_wire_envelope(stage, checker_version_digest, payload),
            expected,
        )
        for case_id, stage, payload, expected in cases
    )


__all__ = [
    "V2GoldenCase",
    "build_v2_golden_corpus",
    "dispatch_receipt_payload",
    "prefix_authorization_payload",
    "prefix_decision_payload",
    "progress_update_payload",
    "semantic_certificate_payload",
    "state_rebind_payload",
]
