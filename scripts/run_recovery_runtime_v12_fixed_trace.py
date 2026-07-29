#!/usr/bin/env python3
"""Run/check the frozen v12.2 zero-policy recovery fixed trace."""

from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.digests import digest_payload  # noqa: E402
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    RecoveryTransactionGate,
    RecoverableAlignmentV12Error,
    ShadowJointTrajectory,
    TrustedJointState,
    select_recovery_candidate,
)
from proofalign.recovery_runtime_v12 import (  # noqa: E402
    AppliedRecoveryAction,
    InMemoryRecoveryActionSink,
    RecoveryRuntimeCoordinator,
    RecoveryRuntimeVerdict,
    SingleUseRecoveryDispatchBoundary,
)
from scripts.freeze_recovery_runtime_v12_fixed_trace import (  # noqa: E402
    OUTPUT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
)


ROW_SCHEMA = "proofalign.recovery-runtime-v12-fixed-trace-row.v1"
RESULT_SCHEMA = "proofalign.recovery-runtime-v12-fixed-trace-result.v1"
COMMAND = (
    0.1,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
    0.2,
    0.0,
    0.0,
    0.0,
    0.0,
    0.0,
    -1.0,
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _state(epoch: int, qpos: float = 0.95) -> TrustedJointState:
    return TrustedJointState(
        state_epoch=epoch,
        qpos=(qpos,),
        qvel=(0.0,),
        joint_lower=(-1.0,),
        joint_upper=(1.0,),
        source_id=f"fixed-trace-state-{epoch}-{qpos}",
    )


def _selection(state: TrustedJointState):
    candidate = RecoveryCandidate(
        candidate_id="escape",
        command=COMMAND,
        command_shape=(2, 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(COMMAND),
            positions=((0.7,), (0.4,)),
            predictor_id="fixed-trace-v12.2",
        ),
    )
    return select_recovery_candidate(state, (candidate,))


def _context(
    sink: Any | None = None,
    *,
    ttl_ns: int = 5_000_000_000,
) -> dict[str, Any]:
    trigger = _state(4)
    selection = _selection(trigger)
    selected_sink = sink or InMemoryRecoveryActionSink()
    gate = RecoveryTransactionGate(safe_margin_rad=0.15)
    boundary = SingleUseRecoveryDispatchBoundary(selected_sink)
    coordinator = RecoveryRuntimeCoordinator(
        gate=gate,
        boundary=boundary,
    )
    old_policy = digest_payload({"authorization": "old-policy"})
    authorization, opened = coordinator.trigger_and_open(
        triggering_policy_authorization_digest=old_policy,
        trigger_state=trigger,
        selection=selection,
        now_ns=100,
        ttl_ns=ttl_ns,
    )
    if (
        opened.verdict is not RecoveryRuntimeVerdict.ALLOW
        or opened.session is None
    ):
        raise RuntimeError("fixed-trace fixture failed to open")
    return {
        "trigger": trigger,
        "selection": selection,
        "sink": selected_sink,
        "gate": gate,
        "boundary": boundary,
        "coordinator": coordinator,
        "old_policy": old_policy,
        "authorization": authorization,
        "session": opened.session,
    }


def _dispatch_all(context: dict[str, Any]) -> bool:
    session = context["session"]
    for index in range(session.action_count):
        result = context["boundary"].dispatch_next(
            session,
            session.action_at(index),
            now_ns=101 + index,
        )
        if result.verdict is not RecoveryRuntimeVerdict.ALLOW:
            return False
    return session.complete


def _base_row(
    case_id: str,
    expected: str,
    observed: str,
    *,
    receipt_identity: bool | None = None,
    old_policy_accepted: bool = False,
    replay_accepted: bool = False,
    recovery_sink_apply_count: int = 0,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": ROW_SCHEMA,
        "case_id": case_id,
        "expected_classification": expected,
        "observed_classification": observed,
        "valid": True,
        "expected_match": observed == expected,
        "receipt_identity": receipt_identity,
        "old_policy_authorization_accepted": old_policy_accepted,
        "recovery_authorization_replay_accepted": replay_accepted,
        "recovery_sink_apply_count": recovery_sink_apply_count,
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "simulator_create_count": 0,
        "outcome_read_count": 0,
        "details": details or {},
    }


def _happy(case_id: str, expected: str) -> dict[str, Any]:
    context = _context()
    complete = _dispatch_all(context)
    recovered = _state(5, qpos=0.4)
    completion = context["coordinator"].complete_recovery(
        context["session"], recovered
    )
    fresh = digest_payload({"authorization": "fresh-policy"})
    fresh_allowed = context[
        "coordinator"
    ].fresh_policy_authorization_allowed(
        fresh, current_state=recovered
    )
    receipts = context["session"].receipts
    identity = (
        complete
        and completion
        and len(receipts) == 2
        and all(
            row.step_index == index
            and row.applied_action
            == context["session"].action_at(index)
            for index, row in enumerate(receipts)
        )
    )
    old_accepted = context["gate"].policy_authorization_allowed(
        context["old_policy"]
    )
    observed = (
        "allow"
        if identity and fresh_allowed and not old_accepted
        else "reject"
    )
    return _base_row(
        case_id,
        expected,
        observed,
        receipt_identity=identity,
        old_policy_accepted=old_accepted,
        recovery_sink_apply_count=len(context["sink"].applied),
        details={
            "completion": completion,
            "fresh_policy_allowed": fresh_allowed,
            "receipt_count": len(receipts),
        },
    )


def _authorization_replay(
    case_id: str, expected: str
) -> dict[str, Any]:
    context = _context()
    replay = context["boundary"].open(
        context["gate"],
        context["authorization"],
        context["selection"],
        now_ns=101,
    )
    accepted = replay.verdict is RecoveryRuntimeVerdict.ALLOW
    return _base_row(
        case_id,
        expected,
        "allow" if accepted else "reject",
        replay_accepted=accepted,
        details={"issues": replay.issues},
    )


def _step_substitution(
    case_id: str, expected: str
) -> dict[str, Any]:
    context = _context()
    session = context["session"]
    action = session.action_at(0)
    substituted = (action[0] + 0.5,) + action[1:]
    result = context["boundary"].dispatch_next(
        session, substituted, now_ns=101
    )
    return _base_row(
        case_id,
        expected,
        (
            "reject"
            if result.verdict is RecoveryRuntimeVerdict.REJECT
            and len(context["sink"].applied) == 0
            else "allow"
        ),
        recovery_sink_apply_count=len(context["sink"].applied),
        details={"issues": result.issues},
    )


def _cross_boundary(
    case_id: str, expected: str
) -> dict[str, Any]:
    context = _context()
    other = SingleUseRecoveryDispatchBoundary(
        InMemoryRecoveryActionSink()
    )
    result = other.dispatch_next(
        context["session"],
        context["session"].action_at(0),
        now_ns=101,
    )
    return _base_row(
        case_id,
        expected,
        (
            "reject"
            if result.verdict is RecoveryRuntimeVerdict.REJECT
            else "allow"
        ),
        details={"issues": result.issues},
    )


class _SubstitutingSink:
    sink_id = "fixed-trace-substituting-sink"

    def __init__(self) -> None:
        self.apply_count = 0

    def apply_recovery(
        self, action: tuple[float, ...], *, now_ns: int
    ) -> AppliedRecoveryAction:
        self.apply_count += 1
        return AppliedRecoveryAction(
            action=(action[0] + 0.5,) + action[1:],
            applied_at_ns=now_ns,
        )


def _sink_substitution(
    case_id: str, expected: str
) -> dict[str, Any]:
    sink = _SubstitutingSink()
    context = _context(sink)
    result = context["boundary"].dispatch_next(
        context["session"],
        context["session"].action_at(0),
        now_ns=101,
    )
    return _base_row(
        case_id,
        expected,
        (
            "reject"
            if result.verdict is RecoveryRuntimeVerdict.REJECT
            else "allow"
        ),
        recovery_sink_apply_count=sink.apply_count,
        details={"issues": result.issues},
    )


def _expired(case_id: str, expected: str) -> dict[str, Any]:
    context = _context(ttl_ns=1)
    result = context["boundary"].dispatch_next(
        context["session"],
        context["session"].action_at(0),
        now_ns=102,
    )
    return _base_row(
        case_id,
        expected,
        (
            "reject"
            if result.verdict is RecoveryRuntimeVerdict.REJECT
            else "allow"
        ),
        details={"issues": result.issues},
    )


def _incomplete(case_id: str, expected: str) -> dict[str, Any]:
    context = _context()
    try:
        context["coordinator"].complete_recovery(
            context["session"], _state(5, qpos=0.4)
        )
        observed = "allow"
        issue = None
    except RecoverableAlignmentV12Error as exc:
        observed = "reject"
        issue = str(exc)
    return _base_row(
        case_id,
        expected,
        observed,
        details={"issue": issue},
    )


def _stale_epoch(case_id: str, expected: str) -> dict[str, Any]:
    context = _context()
    _dispatch_all(context)
    stale = replace(context["trigger"], qpos=(0.4,))
    try:
        context["coordinator"].complete_recovery(
            context["session"], stale
        )
        observed = "allow"
        issue = None
    except RecoverableAlignmentV12Error as exc:
        observed = "reject"
        issue = str(exc)
    return _base_row(
        case_id,
        expected,
        observed,
        recovery_sink_apply_count=len(context["sink"].applied),
        details={"issue": issue},
    )


def _unsafe_post(case_id: str, expected: str) -> dict[str, Any]:
    context = _context()
    _dispatch_all(context)
    unsafe = _state(5, qpos=0.9)
    completion = context["coordinator"].complete_recovery(
        context["session"], unsafe
    )
    fresh = digest_payload({"authorization": "fresh-policy"})
    fresh_allowed = context[
        "coordinator"
    ].fresh_policy_authorization_allowed(
        fresh, current_state=unsafe
    )
    observed = (
        "reject" if not completion and not fresh_allowed else "allow"
    )
    return _base_row(
        case_id,
        expected,
        observed,
        recovery_sink_apply_count=len(context["sink"].applied),
        details={
            "completion": completion,
            "fresh_policy_allowed": fresh_allowed,
        },
    )


def _fresh_policy_binding(
    case_id: str, expected: str
) -> dict[str, Any]:
    context = _context()
    _dispatch_all(context)
    recovered = _state(5, qpos=0.4)
    context["coordinator"].complete_recovery(
        context["session"], recovered
    )
    fresh = digest_payload({"authorization": "fresh-policy"})
    exact_allowed = context[
        "coordinator"
    ].fresh_policy_authorization_allowed(
        fresh, current_state=recovered
    )
    substituted = replace(recovered, source_id="substituted")
    substituted_allowed = context[
        "coordinator"
    ].fresh_policy_authorization_allowed(
        fresh, current_state=substituted
    )
    observed = (
        "allow_exact_only"
        if exact_allowed and not substituted_allowed
        else "reject"
    )
    return _base_row(
        case_id,
        expected,
        observed,
        recovery_sink_apply_count=len(context["sink"].applied),
        details={
            "exact_state_allowed": exact_allowed,
            "substituted_state_allowed": substituted_allowed,
        },
    )


RUNNERS: dict[str, Callable[[str, str], dict[str, Any]]] = {
    "happy_exact": _happy,
    "authorization_replay": _authorization_replay,
    "step_substitution": _step_substitution,
    "cross_boundary_session": _cross_boundary,
    "sink_substitution": _sink_substitution,
    "expired_before_dispatch": _expired,
    "incomplete_completion": _incomplete,
    "stale_observation_epoch": _stale_epoch,
    "unsafe_post_state": _unsafe_post,
    "fresh_policy_state_binding": _fresh_policy_binding,
}


def _expected_run() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    protocol = build_protocol()
    if protocol["schema"] != PROTOCOL_SCHEMA:
        raise RuntimeError("unexpected v12.2 fixed-trace protocol schema")
    rows = [
        RUNNERS[spec["case_id"]](
            spec["case_id"],
            spec["expected_classification"],
        )
        for spec in protocol["cases"]
    ]
    valid = sum(row["valid"] for row in rows)
    matches = sum(row["expected_match"] for row in rows)
    happy = [row for row in rows if row["case_id"] == "happy_exact"]
    metrics = {
        "valid_case_count": valid,
        "expected_classification_rate": matches / len(rows),
        "happy_receipt_identity_rate": (
            sum(row["receipt_identity"] is True for row in happy)
            / len(happy)
        ),
        "old_policy_authorization_accept_count": sum(
            row["old_policy_authorization_accepted"] for row in rows
        ),
        "recovery_authorization_replay_accept_count": sum(
            row["recovery_authorization_replay_accepted"]
            for row in rows
        ),
        "recovery_sink_apply_count": sum(
            row["recovery_sink_apply_count"] for row in rows
        ),
        "policy_load_count": 0,
        "policy_action_dispatch_count": 0,
        "simulator_create_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
    }
    gates = protocol["gates"]
    conditions = {
        "valid_case_count": metrics["valid_case_count"]
        >= gates["valid_case_count_min"],
        "expected_classification": metrics[
            "expected_classification_rate"
        ]
        >= gates["expected_classification_rate_min"],
        "happy_receipt_identity": metrics[
            "happy_receipt_identity_rate"
        ]
        >= gates["happy_receipt_identity_rate_min"],
        "old_policy_authorization": metrics[
            "old_policy_authorization_accept_count"
        ]
        <= gates["old_policy_authorization_accept_count_max"],
        "recovery_authorization_replay": metrics[
            "recovery_authorization_replay_accept_count"
        ]
        <= gates["recovery_authorization_replay_accept_count_max"],
        "policy_load_count": metrics["policy_load_count"]
        <= gates["policy_load_count_max"],
        "policy_action_dispatch_count": metrics[
            "policy_action_dispatch_count"
        ]
        <= gates["policy_action_dispatch_count_max"],
        "simulator_create_count": metrics["simulator_create_count"]
        <= gates["simulator_create_count_max"],
        "outcome_read_count": metrics["outcome_read_count"]
        <= gates["outcome_read_count_max"],
        "runtime_exception_count": metrics["runtime_exception_count"]
        <= gates["runtime_exception_count_max"],
    }
    passed = all(conditions.values())
    result = {
        "schema": RESULT_SCHEMA,
        "protocol_id": PROTOCOL_ID,
        "classification": (
            "recovery_runtime_v12_fixed_trace_pass"
            if passed
            else "recovery_runtime_v12_fixed_trace_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "execution_boundary": {
            "policy_load_count": 0,
            "policy_action_dispatch_count": 0,
            "simulator_create_count": 0,
            "outcome_read_count": 0,
            "recovery_sink_apply_count": metrics[
                "recovery_sink_apply_count"
            ],
        },
        "claim_boundary": protocol["claim_boundary"],
        "lifecycle": {
            "terminal": True,
            "outcome_rollout_authorized": False,
            "clean_rollout_authorized": False,
            "multi_joint_simulator_preflight_authorized": passed,
            "next_step": (
                protocol["lifecycle"]["next_step_if_pass"]
                if passed
                else protocol["lifecycle"]["next_step_if_nonpass"]
            ),
        },
    }
    return result, rows


def _write_checksums(root: Path) -> None:
    files = sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (root / "SHA256SUMS").write_text(
        "".join(
            f"{_sha256(path)}  {path.name}\n" for path in files
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    protocol_text = _canonical(build_protocol())
    if (
        not PROTOCOL_PATH.is_file()
        or PROTOCOL_PATH.read_text() != protocol_text
    ):
        raise SystemExit("v12.2 fixed-trace protocol is missing or stale")
    result, rows = _expected_run()
    result_text = _canonical(result)
    ledger_text = "".join(
        json.dumps(row, sort_keys=True) + "\n" for row in rows
    )
    if args.check:
        if not OUTPUT_ROOT.is_dir():
            raise SystemExit(f"missing: {OUTPUT_ROOT}")
        if (OUTPUT_ROOT / "result.json").read_text() != result_text:
            raise SystemExit("v12.2 fixed-trace result is stale")
        if (OUTPUT_ROOT / "ledger.jsonl").read_text() != ledger_text:
            raise SystemExit("v12.2 fixed-trace ledger is stale")
        print(f"current: {OUTPUT_ROOT}")
        return 0
    if OUTPUT_ROOT.exists():
        raise SystemExit(
            f"refusing to overwrite fixed-trace root: {OUTPUT_ROOT}"
        )
    OUTPUT_ROOT.mkdir(parents=True)
    (OUTPUT_ROOT / "result.json").write_text(result_text)
    (OUTPUT_ROOT / "ledger.jsonl").write_text(ledger_text)
    (OUTPUT_ROOT / "run_manifest.json").write_text(
        _canonical(
            {
                "schema": RESULT_SCHEMA + ".run-manifest",
                "protocol_id": PROTOCOL_ID,
                "protocol_sha256": _sha256(PROTOCOL_PATH),
                "status": "complete",
                "row_count": len(rows),
                "policy_loaded": False,
                "policy_action_dispatched": False,
                "simulator_created": False,
                "outcomes_observed": False,
            }
        )
    )
    _write_checksums(OUTPUT_ROOT)
    print(result_text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
