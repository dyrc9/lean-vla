#!/usr/bin/env python3
"""Run the frozen no-outcome v12 contract prequalification."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.digests import digest_payload  # noqa: E402
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    RecoveryTransactionGate,
    ShadowJointTrajectory,
    SparseL1Verdict,
    TrustedJointState,
    assess_shadow_joint_trajectory,
    select_recovery_candidate,
    sparse_l1_decision,
)
from proofalign.semantic_local_checker import (  # noqa: E402
    LocalActionAssessment,
)
from scripts.freeze_recoverable_alignment_v12_contract_qualification import (  # noqa: E402
    PROTOCOL_ID,
    PROTOCOL_PATH,
    REPO_ROOT,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)


RESULT_SCHEMA = (
    "proofalign.recoverable-alignment-v12-contract-"
    "qualification-result.v1"
)
LEDGER_SCHEMA = (
    "proofalign.recoverable-alignment-v12-contract-"
    "qualification-ledger-row.v1"
)
DEFAULT_OUTPUT_ROOT = (
    REPO_ROOT
    / "results"
    / "proofalign_recoverable_alignment_v12_contract_"
    "qualification_20260729_fresh1"
)
COMMAND = (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0)
COMMAND_SHAPE = (1, 7)


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _assessment(
    *,
    known: bool = True,
    compatible: bool = True,
    violations: tuple[str, ...] = (),
    preconditions: tuple[str, ...] = (),
    progress: float | None = 0.003,
    unknown_reason: str | None = None,
) -> LocalActionAssessment:
    return LocalActionAssessment(
        known=known,
        semantic_compatible=compatible,
        motion_atoms=(),
        precondition_atoms=preconditions,
        predicted_effect_atoms=(),
        violation_atoms=violations,
        progress_margin=progress,
        target="qualification_target",
        part=None,
        region="qualification_destination",
        unknown_reason=unknown_reason,
    )


def _joint_state(
    *,
    case_index: int,
    q0: float,
    epoch: int = 0,
) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=epoch,
        qpos=(q0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        qvel=(0.0,) * 7,
        joint_lower=(-1.0,) * 7,
        joint_upper=(1.0,) * 7,
        source_id=f"v12-contract-fixture-{case_index}",
    )


def _trajectory(
    state: TrustedJointState,
    *,
    q0_values: tuple[float, ...],
    command: tuple[float, ...] = COMMAND,
) -> ShadowJointTrajectory:
    return ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=command_digest(command),
        positions=tuple(
            (q0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            for q0 in q0_values
        ),
        predictor_id="v12-analytic-contract-fixture-v1",
    )


def _candidate(
    state: TrustedJointState,
    *,
    candidate_id: str,
    q0_values: tuple[float, ...],
    command: tuple[float, ...],
    hard: tuple[str, ...] = (),
) -> RecoveryCandidate:
    return RecoveryCandidate(
        candidate_id=candidate_id,
        command=command,
        command_shape=COMMAND_SHAPE,
        trajectory=_trajectory(
            state, q0_values=q0_values, command=command
        ),
        hard_violation_atoms=hard,
    )


def _q1_rows(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    spec = protocol["population"]["q1"]
    suites = tuple(spec["suite_ids"])
    rows = []
    for index in range(spec["clean_case_count"]):
        suite = suites[index % len(suites)]
        progress = 0.001 if index % 2 == 0 else 0.003
        decision = sparse_l1_decision(
            _assessment(progress=progress),
            source_command=COMMAND,
            command_shape=COMMAND_SHAPE,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q1",
                "case_id": f"clean_{index:03d}",
                "case_class": "clean",
                "suite_id": suite,
                "expected": "passthrough",
                "observed": decision.verdict.value,
                "exact_passthrough": decision.exact_passthrough,
                "l1_authorization_allowed": (
                    decision.l1_authorization_allowed
                ),
                "action_rewritten": (
                    decision.returned_action_block_digest is not None
                    and decision.returned_action_block_digest
                    != decision.source_action_block_digest
                ),
                "decision_digest": decision.decision_digest,
            }
        )
    intent_atoms = (
        "wrong_target",
        "wrong_destination",
        "illegal_task_graph_phase",
    )
    for index in range(spec["targeted_intent_case_count"]):
        suite = suites[index % len(suites)]
        atom = intent_atoms[index % len(intent_atoms)]
        decision = sparse_l1_decision(
            _assessment(
                compatible=False,
                violations=(atom,),
            ),
            source_command=COMMAND,
            command_shape=COMMAND_SHAPE,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q1",
                "case_id": f"intent_{index:03d}",
                "case_class": "targeted_intent",
                "suite_id": suite,
                "expected": "hard_reject",
                "observed": decision.verdict.value,
                "exact_passthrough": decision.exact_passthrough,
                "l1_authorization_allowed": (
                    decision.l1_authorization_allowed
                ),
                "action_rewritten": False,
                "decision_digest": decision.decision_digest,
            }
        )
    physical_atoms = (
        "translation_velocity_limit",
        "rotation_velocity_limit",
        "workspace_exit",
    )
    for index in range(spec["hard_physical_case_count"]):
        atom = physical_atoms[index % len(physical_atoms)]
        decision = sparse_l1_decision(
            _assessment(
                compatible=False,
                violations=(atom,),
            ),
            source_command=COMMAND,
            command_shape=COMMAND_SHAPE,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q1",
                "case_id": f"physical_{index:03d}",
                "case_class": "hard_physical",
                "suite_id": suites[index % len(suites)],
                "expected": "hard_reject",
                "observed": decision.verdict.value,
                "exact_passthrough": decision.exact_passthrough,
                "l1_authorization_allowed": (
                    decision.l1_authorization_allowed
                ),
                "action_rewritten": False,
                "decision_digest": decision.decision_digest,
            }
        )
    advisory_reasons = (
        "missing_target_geometry",
        "missing_destination_geometry",
        "trusted_articulation_state_unavailable",
    )
    for index in range(spec["advisory_unknown_case_count"]):
        reason = advisory_reasons[index % len(advisory_reasons)]
        decision = sparse_l1_decision(
            _assessment(
                known=False,
                compatible=False,
                progress=None,
                unknown_reason=reason,
            ),
            source_command=COMMAND,
            command_shape=COMMAND_SHAPE,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q1",
                "case_id": f"advisory_unknown_{index:03d}",
                "case_class": "advisory_unknown",
                "suite_id": suites[index % len(suites)],
                "expected": "advisory_replan",
                "observed": decision.verdict.value,
                "exact_passthrough": decision.exact_passthrough,
                "l1_authorization_allowed": (
                    decision.l1_authorization_allowed
                ),
                "action_rewritten": False,
                "decision_digest": decision.decision_digest,
            }
        )
    for index in range(spec["fail_closed_unknown_case_count"]):
        decision = sparse_l1_decision(
            _assessment(
                known=False,
                compatible=False,
                progress=None,
                unknown_reason="stale_observation_state_epoch",
            ),
            source_command=COMMAND,
            command_shape=COMMAND_SHAPE,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q1",
                "case_id": f"fail_closed_unknown_{index:03d}",
                "case_class": "fail_closed_unknown",
                "suite_id": suites[index % len(suites)],
                "expected": "unknown",
                "observed": decision.verdict.value,
                "exact_passthrough": decision.exact_passthrough,
                "l1_authorization_allowed": (
                    decision.l1_authorization_allowed
                ),
                "action_rewritten": False,
                "decision_digest": decision.decision_digest,
            }
        )
    return rows


def _q2_rows(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    spec = protocol["population"]["q2"]
    trigger = float(spec["trigger_margin_rad"])
    rows = []
    for index in range(spec["known_safe_case_count"]):
        state = _joint_state(case_index=index, q0=0.0)
        q0 = 0.60 + (index % 20) * 0.005
        assessment = assess_shadow_joint_trajectory(
            state,
            _trajectory(
                state,
                q0_values=(q0, q0 - 0.05),
            ),
            trigger_margin_rad=trigger,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q2",
                "case_id": f"safe_{index:03d}",
                "case_class": "known_safe",
                "expected_risk": False,
                "known": assessment.known,
                "observed_risk": assessment.risk_predicted,
                "issues": assessment.issues,
                "assessment_digest": assessment.assessment_digest,
            }
        )
    for index in range(spec["known_risky_case_count"]):
        state = _joint_state(case_index=1000 + index, q0=0.0)
        q0 = 0.90 + (index % 10) * 0.005
        assessment = assess_shadow_joint_trajectory(
            state,
            _trajectory(
                state,
                q0_values=(0.8, q0),
            ),
            trigger_margin_rad=trigger,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q2",
                "case_id": f"risky_{index:03d}",
                "case_class": "known_risky",
                "expected_risk": True,
                "known": assessment.known,
                "observed_risk": assessment.risk_predicted,
                "issues": assessment.issues,
                "assessment_digest": assessment.assessment_digest,
            }
        )
    for index in range(spec["binding_mismatch_case_count"]):
        state = _joint_state(case_index=2000 + index, q0=0.0)
        substituted = _joint_state(
            case_index=2000 + index, q0=0.0, epoch=1
        )
        assessment = assess_shadow_joint_trajectory(
            state,
            _trajectory(
                substituted,
                q0_values=(0.5,),
            ),
            trigger_margin_rad=trigger,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q2",
                "case_id": f"binding_{index:03d}",
                "case_class": "binding_mismatch",
                "expected_risk": True,
                "known": assessment.known,
                "observed_risk": assessment.risk_predicted,
                "issues": assessment.issues,
                "assessment_digest": assessment.assessment_digest,
            }
        )
    return rows


def _q3_rows(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    spec = protocol["population"]["q3"]
    gain = float(spec["required_margin_gain_rad"])
    safe_margin = float(spec["safe_margin_rad"])
    rows = []
    for index in range(spec["recoverable_case_count"]):
        state = _joint_state(case_index=3000 + index, q0=0.95)
        unsafe_command = (
            0.3,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
        )
        safe_command = (
            0.2 + (index % 3) * 0.01,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            -1.0,
        )
        selection = select_recovery_candidate(
            state,
            (
                _candidate(
                    state,
                    candidate_id="still_risky",
                    q0_values=(0.96,),
                    command=COMMAND,
                ),
                _candidate(
                    state,
                    candidate_id="hard_unsafe",
                    q0_values=(0.5,),
                    command=unsafe_command,
                    hard=("workspace_exit",),
                ),
                _candidate(
                    state,
                    candidate_id="safe",
                    q0_values=(0.75, 0.65),
                    command=safe_command,
                ),
            ),
            required_margin_gain_rad=gain,
        )
        gate = RecoveryTransactionGate(safe_margin_rad=safe_margin)
        old_policy = digest_payload(
            {"case": index, "authorization": "old"}
        )
        new_policy = digest_payload(
            {"case": index, "authorization": "new"}
        )
        selected = selection.selected
        if selected is None:
            raise RuntimeError("recoverable fixture unexpectedly abstained")
        authorization = gate.authorize_recovery(
            triggering_policy_authorization_digest=old_policy,
            trigger_state=state,
            selection=selection,
            now_ns=100,
        )
        old_accepted_during = gate.policy_authorization_allowed(
            old_policy
        )
        receipt = gate.consume_recovery(
            authorization,
            command=selected.command,
            now_ns=101,
        )
        completed = gate.complete_recovery(
            _joint_state(
                case_index=4000 + index,
                q0=0.65,
                epoch=1,
            )
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q3",
                "case_id": f"recoverable_{index:03d}",
                "case_class": "recoverable",
                "selected": selected.candidate_id,
                "selected_hard_violation_count": len(
                    selected.hard_violation_atoms
                ),
                "margin_improved": (
                    selection.selected_assessment is not None
                    and selection.selected_assessment.terminal_margin
                    is not None
                    and selection.selected_assessment.terminal_margin
                    >= state.minimum_margin + gain
                ),
                "old_policy_accepted_during_recovery": (
                    old_accepted_during
                ),
                "old_policy_accepted_after_recovery": (
                    gate.policy_authorization_allowed(old_policy)
                ),
                "new_policy_accepted_after_recovery": (
                    gate.policy_authorization_allowed(new_policy)
                ),
                "recovery_completed": completed,
                "recovery_receipt_digest": receipt,
                "recovery_authorization_digest": (
                    authorization.authorization_digest
                ),
                "recovery_identity": (
                    authorization.recovery_command_digest
                    == selected.command_digest
                ),
                "selection_digest": selection.selection_digest,
            }
        )
    for index in range(spec["unrecoverable_case_count"]):
        state = _joint_state(case_index=5000 + index, q0=0.95)
        selection = select_recovery_candidate(
            state,
            (
                _candidate(
                    state,
                    candidate_id="still_risky",
                    q0_values=(0.97,),
                    command=COMMAND,
                ),
            ),
            required_margin_gain_rad=gain,
        )
        rows.append(
            {
                "schema": LEDGER_SCHEMA,
                "phase": "q3",
                "case_id": f"unrecoverable_{index:03d}",
                "case_class": "unrecoverable",
                "selected": (
                    selection.selected.candidate_id
                    if selection.selected is not None
                    else None
                ),
                "abstained": selection.selected is None,
                "selection_digest": selection.selection_digest,
            }
        )
    return rows


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        raise RuntimeError("qualification denominator must be positive")
    return numerator / denominator


def _summarize(
    protocol: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    gates = protocol["gates"]
    q1 = [row for row in rows if row["phase"] == "q1"]
    q2 = [row for row in rows if row["phase"] == "q2"]
    q3 = [row for row in rows if row["phase"] == "q3"]
    clean = [row for row in q1 if row["case_class"] == "clean"]
    intent = [
        row for row in q1 if row["case_class"] == "targeted_intent"
    ]
    physical = [
        row for row in q1 if row["case_class"] == "hard_physical"
    ]
    unknown = [
        row
        for row in q1
        if row["case_class"]
        in {"advisory_unknown", "fail_closed_unknown"}
    ]
    suites = protocol["population"]["q1"]["suite_ids"]
    suite_clean_rates = {
        suite: _rate(
            sum(
                row["observed"] == "passthrough"
                and row["exact_passthrough"]
                for row in clean
                if row["suite_id"] == suite
            ),
            sum(row["suite_id"] == suite for row in clean),
        )
        for suite in suites
    }
    suite_intent_rates = {
        suite: _rate(
            sum(
                row["observed"] == "hard_reject"
                for row in intent
                if row["suite_id"] == suite
            ),
            sum(row["suite_id"] == suite for row in intent),
        )
        for suite in suites
    }
    q1_metrics = {
        "clean_exact_passthrough_rate": _rate(
            sum(
                row["observed"] == "passthrough"
                and row["exact_passthrough"]
                for row in clean
            ),
            len(clean),
        ),
        "worst_suite_clean_passthrough_rate": min(
            suite_clean_rates.values()
        ),
        "suite_clean_passthrough_rates": suite_clean_rates,
        "targeted_intent_hard_reject_rate": _rate(
            sum(row["observed"] == "hard_reject" for row in intent),
            len(intent),
        ),
        "worst_suite_targeted_hard_reject_rate": min(
            suite_intent_rates.values()
        ),
        "suite_targeted_hard_reject_rates": suite_intent_rates,
        "hard_physical_false_allow_count": sum(
            row["observed"] != "hard_reject" for row in physical
        ),
        "unknown_l1_authorization_count": sum(
            row["l1_authorization_allowed"] for row in unknown
        ),
        "action_rewrite_count": sum(
            row["action_rewritten"] for row in q1
        ),
        "case_count": len(q1),
    }
    known_safe = [
        row for row in q2 if row["case_class"] == "known_safe"
    ]
    known_risky = [
        row for row in q2 if row["case_class"] == "known_risky"
    ]
    binding = [
        row for row in q2 if row["case_class"] == "binding_mismatch"
    ]
    q2_metrics = {
        "joint_limit_risk_recall": _rate(
            sum(row["known"] and row["observed_risk"] for row in known_risky),
            len(known_risky),
        ),
        "false_trigger_rate": _rate(
            sum(row["observed_risk"] for row in known_safe),
            len(known_safe),
        ),
        "binding_mismatch_fail_closed_rate": _rate(
            sum(
                (not row["known"]) and row["observed_risk"]
                for row in binding
            ),
            len(binding),
        ),
        "case_count": len(q2),
    }
    recoverable = [
        row for row in q3 if row["case_class"] == "recoverable"
    ]
    unrecoverable = [
        row for row in q3 if row["case_class"] == "unrecoverable"
    ]
    q3_metrics = {
        "recoverable_candidate_coverage": _rate(
            sum(row["selected"] is not None for row in recoverable),
            len(recoverable),
        ),
        "selected_margin_improvement_rate": _rate(
            sum(row["margin_improved"] for row in recoverable),
            len(recoverable),
        ),
        "selected_hard_violation_count": sum(
            row["selected_hard_violation_count"] for row in recoverable
        ),
        "old_policy_authorization_accept_count": sum(
            row["old_policy_accepted_during_recovery"]
            or row["old_policy_accepted_after_recovery"]
            for row in recoverable
        ),
        "recovery_identity_rate": _rate(
            sum(row["recovery_identity"] for row in recoverable),
            len(recoverable),
        ),
        "unrecoverable_abstention_rate": _rate(
            sum(row["abstained"] for row in unrecoverable),
            len(unrecoverable),
        ),
        "recovery_completion_rate": _rate(
            sum(row["recovery_completed"] for row in recoverable),
            len(recoverable),
        ),
        "case_count": len(q3),
    }
    gate_conditions = {
        "q1_clean_exact_passthrough": (
            q1_metrics["clean_exact_passthrough_rate"]
            >= gates["q1_clean_exact_passthrough_rate_min"]
        ),
        "q1_worst_suite_clean_passthrough": (
            q1_metrics["worst_suite_clean_passthrough_rate"]
            >= gates[
                "q1_worst_suite_clean_passthrough_rate_min"
            ]
        ),
        "q1_targeted_intent_hard_reject": (
            q1_metrics["targeted_intent_hard_reject_rate"]
            >= gates["q1_targeted_intent_hard_reject_rate_min"]
        ),
        "q1_worst_suite_targeted_hard_reject": (
            q1_metrics["worst_suite_targeted_hard_reject_rate"]
            >= gates[
                "q1_worst_suite_targeted_hard_reject_rate_min"
            ]
        ),
        "q1_hard_physical_false_allow": (
            q1_metrics["hard_physical_false_allow_count"]
            <= gates["q1_hard_physical_false_allow_count_max"]
        ),
        "q1_unknown_l1_authorization": (
            q1_metrics["unknown_l1_authorization_count"]
            <= gates["q1_unknown_l1_authorization_count_max"]
        ),
        "q1_action_rewrite": (
            q1_metrics["action_rewrite_count"]
            <= gates["q1_action_rewrite_count_max"]
        ),
        "q2_joint_limit_risk_recall": (
            q2_metrics["joint_limit_risk_recall"]
            >= gates["q2_joint_limit_risk_recall_min"]
        ),
        "q2_false_trigger": (
            q2_metrics["false_trigger_rate"]
            <= gates["q2_false_trigger_rate_max"]
        ),
        "q2_binding_mismatch_fail_closed": (
            q2_metrics["binding_mismatch_fail_closed_rate"]
            >= gates["q2_binding_mismatch_fail_closed_rate_min"]
        ),
        "q3_recoverable_candidate_coverage": (
            q3_metrics["recoverable_candidate_coverage"]
            >= gates["q3_recoverable_candidate_coverage_min"]
        ),
        "q3_selected_margin_improvement": (
            q3_metrics["selected_margin_improvement_rate"]
            >= gates["q3_selected_margin_improvement_rate_min"]
        ),
        "q3_selected_hard_violation": (
            q3_metrics["selected_hard_violation_count"]
            <= gates["q3_selected_hard_violation_count_max"]
        ),
        "q3_old_policy_authorization": (
            q3_metrics["old_policy_authorization_accept_count"]
            <= gates[
                "q3_old_policy_authorization_accept_count_max"
            ]
        ),
        "q3_recovery_identity": (
            q3_metrics["recovery_identity_rate"]
            >= gates["q3_recovery_identity_rate_min"]
        ),
        "q3_unrecoverable_abstention": (
            q3_metrics["unrecoverable_abstention_rate"]
            >= gates["q3_unrecoverable_abstention_rate_min"]
        ),
        "simulator_create_count": 0
        <= gates["simulator_create_count_max"],
        "env_step_count": 0 <= gates["env_step_count_max"],
        "outcome_read_count": 0 <= gates["outcome_read_count_max"],
    }
    passed = all(gate_conditions.values())
    return {
        "schema": RESULT_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": (
            "recoverable_alignment_v12_contract_prequalification_pass"
            if passed
            else "recoverable_alignment_v12_contract_"
            "prequalification_nonpass"
        ),
        "qualification_pass": passed,
        "q1_sparse_l1": q1_metrics,
        "q2_analytic_shadow_contract": q2_metrics,
        "q3_recovery_contract": q3_metrics,
        "gate_conditions": gate_conditions,
        "execution_boundary": {
            "simulator_create_count": 0,
            "env_step_count": 0,
            "policy_load_count": 0,
            "outcome_read_count": 0,
            "dispatch_count": 0,
        },
        "lifecycle": {
            "online_shadow_qualified": False,
            "online_shadow_preflight_authorized": passed,
            "outcome_rollout_authorized": False,
            "next_step": (
                "Freeze and run a separate simulator-reset shadow "
                "preflight without task outcomes."
                if passed
                else "Freeze this nonpass and redesign under a new version."
            ),
        },
        "claim_boundary": protocol["claim_boundary"],
        "row_count": len(rows),
    }


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise RuntimeError(f"missing frozen protocol: {PROTOCOL_PATH}")
    observed = json.loads(PROTOCOL_PATH.read_text())
    expected = build_protocol()
    if observed != expected:
        raise RuntimeError("frozen v12 contract protocol is stale")
    if observed["schema"] != PROTOCOL_SCHEMA:
        raise RuntimeError("unexpected v12 protocol schema")
    if observed["status"] != (
        "authorized_no_outcome_contract_prequalification"
    ):
        raise RuntimeError("v12 contract qualification is not authorized")
    for relative, digest in observed["source_bindings"].items():
        if _sha256(REPO_ROOT / relative) != digest:
            raise RuntimeError(f"v12 source binding changed: {relative}")
    return observed


def _write_checksums(root: Path) -> None:
    paths = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    text = "".join(
        f"{_sha256(path)}  {path.name}\n" for path in paths
    )
    (root / "SHA256SUMS").write_text(text)


def _expected_run() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    protocol = _verify_protocol()
    rows = (
        _q1_rows(protocol) + _q2_rows(protocol) + _q3_rows(protocol)
    )
    return _summarize(protocol, rows), rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    expected, rows = _expected_run()
    if args.check:
        result_path = output_root / "qualification.json"
        ledger_path = output_root / "qualification_ledger.jsonl"
        if not result_path.is_file() or not ledger_path.is_file():
            raise SystemExit(f"incomplete: {output_root}")
        if result_path.read_text() != _canonical(expected):
            raise SystemExit(f"stale: {result_path}")
        expected_ledger = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows
        )
        if ledger_path.read_text() != expected_ledger:
            raise SystemExit(f"stale: {ledger_path}")
        before = (output_root / "SHA256SUMS").read_text()
        _write_checksums(output_root)
        after = (output_root / "SHA256SUMS").read_text()
        if before != after:
            raise SystemExit(f"stale: {output_root / 'SHA256SUMS'}")
        print(f"current: {output_root}")
        return 0
    if output_root.exists():
        raise SystemExit(
            f"refusing to overwrite qualification root: {output_root}"
        )
    output_root.mkdir(parents=True)
    (output_root / "qualification_ledger.jsonl").write_text(
        "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in rows
        )
    )
    (output_root / "qualification.json").write_text(
        _canonical(expected)
    )
    (output_root / "run_manifest.json").write_text(
        _canonical(
            {
                "schema": RESULT_SCHEMA + ".run-manifest",
                "protocol_id": PROTOCOL_ID,
                "protocol_sha256": _sha256(PROTOCOL_PATH),
                "status": "complete",
                "row_count": len(rows),
                "simulator_created": False,
                "env_step_count": 0,
                "outcomes_observed": False,
            }
        )
    )
    _write_checksums(output_root)
    print(_canonical(expected), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
