#!/usr/bin/env python3
"""Run/check the v12.5 integrated predictive-recovery fixed trace."""

from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from proofalign.digests import digest_payload  # noqa: E402
from proofalign.integrity_v4_models import command_digest  # noqa: E402
from proofalign.policy_prefix_shadow_v12 import (  # noqa: E402
    decide_policy_prefix_shadow,
)
from proofalign.predictive_recovery_runtime_v12 import (  # noqa: E402
    PredictiveRecoveryRouteVerdict,
    PredictiveRecoveryRuntime,
)
from proofalign.recoverable_alignment_v12 import (  # noqa: E402
    RecoveryCandidate,
    ShadowJointTrajectory,
    TrustedJointState,
    select_recovery_candidate,
)
from proofalign.recovery_runtime_v12 import (  # noqa: E402
    InMemoryRecoveryActionSink,
    RecoveryRuntimeVerdict,
)
from scripts.freeze_integrated_predictive_recovery_v12_fixed_trace import (  # noqa: E402
    FRESH_PILOT_LEDGER_PATH,
    OUTPUT_ROOT,
    PILOT_ROOT,
    PROTOCOL_ID,
    PROTOCOL_PATH,
    SCHEMA as PROTOCOL_SCHEMA,
    build_protocol,
    trace_population,
)


ROW_SCHEMA = (
    "proofalign.integrated-predictive-recovery-v12-"
    "fixed-trace-row.v1"
)
SUMMARY_SCHEMA = (
    "proofalign.integrated-predictive-recovery-v12-"
    "fixed-trace-summary.v1"
)


class IntegratedFixedTraceError(RuntimeError):
    """Raised when the integrated fixed trace must fail closed."""


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _git_status() -> str:
    completed = subprocess.run(
        ("git", "status", "--porcelain=v1"),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise IntegratedFixedTraceError("git status failed")
    return completed.stdout.strip()


def _state(
    entry: dict[str, Any],
    *,
    condition: str,
    epoch: int,
) -> TrustedJointState:
    qpos = [0.0] * 7
    if condition == "synthetic":
        joint = int(entry["synthetic"]["joint_index"])
        side = entry["synthetic"]["side"]
        qpos[joint] = -0.95 if side == "lower" else 0.95
    return TrustedJointState(
        state_epoch=epoch,
        qpos=tuple(qpos),
        qvel=(0.0,) * 7,
        joint_lower=(-1.0,) * 7,
        joint_upper=(1.0,) * 7,
        source_id=(
            f"integrated:{entry['base_pair_id']}:{condition}:{epoch}"
        ),
    )


def _decision(
    state: TrustedJointState,
    *,
    prefix_digest: str,
):
    trajectory = ShadowJointTrajectory(
        initial_state_digest=state.state_digest,
        action_block_digest=prefix_digest,
        positions=(state.qpos, state.qpos),
        predictor_id="source-digest-bound-integration-v12.5",
    )
    return decide_policy_prefix_shadow(state, trajectory)[0]


def _selection(
    state: TrustedJointState,
    *,
    joint_index: int,
    side: str,
):
    direction = 1.0 if side == "lower" else -1.0
    action = [0.0] * 7
    action[joint_index % 6] = 0.1 * direction
    action[6] = -1.0
    command = tuple(action + action)
    first = list(state.qpos)
    terminal = list(state.qpos)
    first[joint_index] = -0.7 if side == "lower" else 0.7
    terminal[joint_index] = (
        -0.4 if side == "lower" else 0.4
    )
    candidate = RecoveryCandidate(
        candidate_id=f"transaction-fixture-joint{joint_index}-{side}",
        command=command,
        command_shape=(2, 7),
        trajectory=ShadowJointTrajectory(
            initial_state_digest=state.state_digest,
            action_block_digest=command_digest(command),
            positions=(tuple(first), tuple(terminal)),
            predictor_id="integrated-recovery-transaction-fixture-v12.5",
        ),
    )
    return select_recovery_candidate(state, (candidate,))


def _base_row(
    entry: dict[str, Any],
    *,
    path: str,
    source: dict[str, Any],
    source_verdict_match: bool,
    expected_route: str,
    observed_route: str,
    route_digest: str,
    sink_apply_count: int,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": ROW_SCHEMA,
        "case_id": f"{entry['base_pair_id']}:{path}",
        "base_pair_id": entry["base_pair_id"],
        "suite": entry["suite"],
        "task_id": entry["task_id"],
        "init_state_id": entry["init_state_id"],
        "path": path,
        "valid": True,
        "source_case_id": source["source_case_id"],
        "source_row_sha256": source["source_row_sha256"],
        "source_prefix_digest": source["source_prefix_digest"],
        "source_decision_digest": source["source_decision_digest"],
        "source_verdict": source["source_verdict"],
        "source_verdict_match": source_verdict_match,
        "expected_route": expected_route,
        "observed_route": observed_route,
        "expected_route_match": expected_route == observed_route,
        "route_digest": route_digest,
        "sink_apply_count": sink_apply_count,
        "policy_load_count": 0,
        "policy_inference_count": 0,
        "policy_action_dispatch_count": 0,
        "simulator_create_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
        "details": details,
    }


def _run_path(
    entry: dict[str, Any],
    *,
    path: str,
    case_index: int,
) -> dict[str, Any]:
    synthetic = path.startswith("synthetic_")
    source = entry["synthetic" if synthetic else "nominal"]
    state = _state(
        entry,
        condition="synthetic" if synthetic else "nominal",
        epoch=case_index * 10,
    )
    decision = _decision(
        state, prefix_digest=source["source_prefix_digest"]
    )
    source_verdict_match = (
        decision.verdict.value == source["source_verdict"]
    )
    sink = InMemoryRecoveryActionSink()
    runtime = PredictiveRecoveryRuntime(sink)
    selection = None
    submitted = source["source_prefix_digest"]
    if path == "nominal_prefix_substitution":
        submitted = digest_payload(
            {
                "source_prefix_digest": submitted,
                "substitution": True,
            }
        )
    elif path == "synthetic_recovery_happy":
        selection = _selection(
            state,
            joint_index=int(source["joint_index"]),
            side=source["side"],
        )
    elif path == "synthetic_recovery_selection_substitution":
        other = _state(
            entry,
            condition="synthetic",
            epoch=case_index * 10 + 1,
        )
        selection = _selection(
            other,
            joint_index=int(source["joint_index"]),
            side=source["side"],
        )
    route = runtime.route(
        decision,
        state,
        submitted_policy_prefix_digest=submitted,
        recovery_selection=selection,
        now_ns=100_000 + case_index * 100,
    )
    details: dict[str, Any] = {
        "policy_shadow_decision_digest": decision.decision_digest,
        "policy_authorization_digest": (
            route.policy_authorization_digest
        ),
        "recovery_authorization_digest": (
            route.recovery_authorization_digest
        ),
        "issues": route.issues,
        "old_policy_authorization_accepted": False,
        "recovery_authorization_replay_accepted": False,
        "receipt_identity": None,
        "recovery_completed": None,
        "fresh_policy_authorization_allowed": None,
        "substituted_fresh_state_allowed": None,
    }
    if (
        route.verdict
        is PredictiveRecoveryRouteVerdict.ALLOW_POLICY_EXACT
    ):
        details["exact_prefix_authorized"] = (
            route.submitted_policy_prefix_digest
            == source["source_prefix_digest"]
        )
    elif (
        route.verdict
        is PredictiveRecoveryRouteVerdict.RECOVERY_OPENED
    ):
        assert selection is not None
        assert route.recovery_authorization is not None
        assert route.recovery_session is not None
        replay = runtime.boundary.open(
            runtime.gate,
            route.recovery_authorization,
            selection,
            now_ns=100_001 + case_index * 100,
        )
        details["recovery_authorization_replay_accepted"] = (
            replay.verdict is RecoveryRuntimeVerdict.ALLOW
        )
        for step_index in range(
            route.recovery_session.action_count
        ):
            dispatched = runtime.boundary.dispatch_next(
                route.recovery_session,
                route.recovery_session.action_at(step_index),
                now_ns=100_002 + case_index * 100 + step_index,
            )
            if dispatched.verdict is not RecoveryRuntimeVerdict.ALLOW:
                raise IntegratedFixedTraceError(
                    f"recovery dispatch failed: {dispatched.issues}"
                )
        joint = int(source["joint_index"])
        post_qpos = list(state.qpos)
        post_qpos[joint] = (
            -0.4 if source["side"] == "lower" else 0.4
        )
        post_state = TrustedJointState(
            state_epoch=state.state_epoch + 1,
            qpos=tuple(post_qpos),
            qvel=(0.0,) * 7,
            joint_lower=(-1.0,) * 7,
            joint_upper=(1.0,) * 7,
            source_id=f"{state.source_id}:recovered",
        )
        completed = runtime.coordinator.complete_recovery(
            route.recovery_session, post_state
        )
        fresh = digest_payload(
            {
                "case_id": entry["base_pair_id"],
                "authorization": "fresh-policy",
            }
        )
        fresh_allowed = (
            runtime.coordinator.fresh_policy_authorization_allowed(
                fresh, current_state=post_state
            )
        )
        substituted_allowed = (
            runtime.coordinator.fresh_policy_authorization_allowed(
                fresh,
                current_state=replace(
                    post_state, source_id="substituted"
                ),
            )
        )
        receipts = route.recovery_session.receipts
        details.update(
            {
                "old_policy_authorization_accepted": (
                    runtime.gate.policy_authorization_allowed(
                        route.policy_authorization_digest
                    )
                ),
                "receipt_identity": (
                    len(receipts)
                    == route.recovery_session.action_count
                    and all(
                        receipt.step_index == index
                        and receipt.applied_action
                        == route.recovery_session.action_at(index)
                        for index, receipt in enumerate(receipts)
                    )
                ),
                "recovery_completed": completed,
                "fresh_policy_authorization_allowed": fresh_allowed,
                "substituted_fresh_state_allowed": (
                    substituted_allowed
                ),
            }
        )
    expected = {
        "nominal_allow_exact": "allow_policy_exact",
        "nominal_prefix_substitution": "reject",
        "synthetic_recovery_happy": "recovery_opened",
        "synthetic_recovery_selection_substitution": "reject",
    }[path]
    return _base_row(
        entry,
        path=path,
        source=source,
        source_verdict_match=source_verdict_match,
        expected_route=expected,
        observed_route=route.verdict.value,
        route_digest=route.route_digest,
        sink_apply_count=len(sink.applied),
        details=details,
    )


def _summarize(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    pilot: bool,
) -> dict[str, Any]:
    by_path = {
        path: [row for row in rows if row["path"] == path]
        for path in config["population"]["paths_per_pair"]
    }
    recovery = by_path["synthetic_recovery_happy"]
    negative = (
        by_path["nominal_prefix_substitution"]
        + by_path["synthetic_recovery_selection_substitution"]
    )
    metrics = {
        "valid_case_count": sum(row["valid"] for row in rows),
        "source_verdict_match_rate": sum(
            row["source_verdict_match"] for row in rows
        )
        / len(rows),
        "expected_route_rate": sum(
            row["expected_route_match"] for row in rows
        )
        / len(rows),
        "nominal_exact_authorization_rate": sum(
            row["observed_route"] == "allow_policy_exact"
            and row["details"].get("exact_prefix_authorized") is True
            for row in by_path["nominal_allow_exact"]
        )
        / len(by_path["nominal_allow_exact"]),
        "prefix_substitution_reject_rate": sum(
            row["observed_route"] == "reject"
            for row in by_path["nominal_prefix_substitution"]
        )
        / len(by_path["nominal_prefix_substitution"]),
        "recovery_open_rate": sum(
            row["observed_route"] == "recovery_opened"
            for row in recovery
        )
        / len(recovery),
        "selection_substitution_reject_rate": sum(
            row["observed_route"] == "reject"
            for row in by_path[
                "synthetic_recovery_selection_substitution"
            ]
        )
        / len(
            by_path[
                "synthetic_recovery_selection_substitution"
            ]
        ),
        "recovery_completion_rate": sum(
            row["details"]["recovery_completed"] is True
            for row in recovery
        )
        / len(recovery),
        "receipt_identity_rate": sum(
            row["details"]["receipt_identity"] is True
            for row in recovery
        )
        / len(recovery),
        "fresh_policy_authorization_rate": sum(
            row["details"]["fresh_policy_authorization_allowed"]
            is True
            for row in recovery
        )
        / len(recovery),
        "old_policy_authorization_accept_count": sum(
            row["details"]["old_policy_authorization_accepted"]
            is True
            for row in recovery
        ),
        "recovery_authorization_replay_accept_count": sum(
            row["details"][
                "recovery_authorization_replay_accepted"
            ]
            is True
            for row in recovery
        ),
        "substituted_fresh_state_accept_count": sum(
            row["details"]["substituted_fresh_state_allowed"] is True
            for row in recovery
        ),
        "negative_path_sink_apply_count": sum(
            row["sink_apply_count"] for row in negative
        ),
        "recovery_sink_apply_count": sum(
            row["sink_apply_count"] for row in recovery
        ),
        "policy_load_count": 0,
        "policy_inference_count": 0,
        "policy_action_dispatch_count": 0,
        "simulator_create_count": 0,
        "outcome_read_count": 0,
        "runtime_exception_count": 0,
    }
    if pilot:
        return {
            "schema": SUMMARY_SCHEMA,
            "classification": (
                "integrated_predictive_recovery_v12_"
                "fixed_trace_pilot_complete"
            ),
            "qualification_pass": None,
            "valid_case_count": metrics["valid_case_count"],
            "metrics": metrics,
            "claim_boundary": (
                "This 3-pair engineering pilot is not qualification "
                "evidence and reads no task outcome."
            ),
        }
    gates = config["gates"]
    conditions = {
        name: value
        for name, value in (
            (
                "valid_case_count",
                metrics["valid_case_count"]
                >= gates["valid_case_count_min"],
            ),
            (
                "source_verdict_match",
                metrics["source_verdict_match_rate"]
                >= gates["source_verdict_match_rate_min"],
            ),
            (
                "expected_route",
                metrics["expected_route_rate"]
                >= gates["expected_route_rate_min"],
            ),
            (
                "nominal_exact_authorization",
                metrics["nominal_exact_authorization_rate"]
                >= gates["nominal_exact_authorization_rate_min"],
            ),
            (
                "prefix_substitution_reject",
                metrics["prefix_substitution_reject_rate"]
                >= gates["prefix_substitution_reject_rate_min"],
            ),
            (
                "recovery_open",
                metrics["recovery_open_rate"]
                >= gates["recovery_open_rate_min"],
            ),
            (
                "selection_substitution_reject",
                metrics["selection_substitution_reject_rate"]
                >= gates[
                    "selection_substitution_reject_rate_min"
                ],
            ),
            (
                "recovery_completion",
                metrics["recovery_completion_rate"]
                >= gates["recovery_completion_rate_min"],
            ),
            (
                "receipt_identity",
                metrics["receipt_identity_rate"]
                >= gates["receipt_identity_rate_min"],
            ),
            (
                "fresh_policy_authorization",
                metrics["fresh_policy_authorization_rate"]
                >= gates["fresh_policy_authorization_rate_min"],
            ),
            (
                "old_policy_authorization",
                metrics["old_policy_authorization_accept_count"]
                <= gates[
                    "old_policy_authorization_accept_count_max"
                ],
            ),
            (
                "recovery_authorization_replay",
                metrics[
                    "recovery_authorization_replay_accept_count"
                ]
                <= gates[
                    "recovery_authorization_replay_accept_count_max"
                ],
            ),
            (
                "substituted_fresh_state",
                metrics["substituted_fresh_state_accept_count"]
                <= gates[
                    "substituted_fresh_state_accept_count_max"
                ],
            ),
            (
                "negative_path_sink_apply",
                metrics["negative_path_sink_apply_count"]
                <= gates["negative_path_sink_apply_count_max"],
            ),
            (
                "policy_load_count",
                metrics["policy_load_count"]
                <= gates["policy_load_count_max"],
            ),
            (
                "policy_inference_count",
                metrics["policy_inference_count"]
                <= gates["policy_inference_count_max"],
            ),
            (
                "policy_action_dispatch_count",
                metrics["policy_action_dispatch_count"]
                <= gates["policy_action_dispatch_count_max"],
            ),
            (
                "simulator_create_count",
                metrics["simulator_create_count"]
                <= gates["simulator_create_count_max"],
            ),
            (
                "outcome_read_count",
                metrics["outcome_read_count"]
                <= gates["outcome_read_count_max"],
            ),
            (
                "runtime_exception_count",
                metrics["runtime_exception_count"]
                <= gates["runtime_exception_count_max"],
            ),
        )
    }
    passed = all(conditions.values())
    return {
        "schema": SUMMARY_SCHEMA,
        "protocol_id": config["protocol_id"],
        "classification": (
            "integrated_predictive_recovery_v12_fixed_trace_pass"
            if passed
            else "integrated_predictive_recovery_v12_fixed_trace_nonpass"
        ),
        "qualification_pass": passed,
        "metrics": metrics,
        "gate_conditions": conditions,
        "failed_gates": [
            name for name, value in conditions.items() if not value
        ],
        "outcomes_observed": False,
        "clean_rollout_authorized": False,
        "claim_boundary": config["claim_boundary"],
    }


def _pilot_config() -> dict[str, Any]:
    return {
        "schema": "proofalign.integrated-predictive-recovery-pilot.v1",
        "protocol_id": "engineering-pilot",
        "population": {
            "pair_count": 3,
            "integrated_case_count": 12,
            "paths_per_pair": [
                "nominal_allow_exact",
                "nominal_prefix_substitution",
                "synthetic_recovery_happy",
                "synthetic_recovery_selection_substitution",
            ],
            "pairs": trace_population(FRESH_PILOT_LEDGER_PATH),
        },
        "transaction": {
            "safe_margin_rad": 0.15,
        },
    }


def _verify_protocol() -> dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        raise IntegratedFixedTraceError(
            f"missing formal protocol: {PROTOCOL_PATH}"
        )
    observed = json.loads(PROTOCOL_PATH.read_text())
    expected = build_protocol()
    if observed != expected or observed["schema"] != PROTOCOL_SCHEMA:
        raise IntegratedFixedTraceError(
            "integrated fixed-trace protocol is stale"
        )
    return observed


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


def _validate_checksums(root: Path) -> None:
    expected = {
        name: digest
        for digest, name in (
            line.split("  ", 1)
            for line in (root / "SHA256SUMS").read_text().splitlines()
            if line.strip()
        )
    }
    observed = {
        path.name: _sha256(path)
        for path in root.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if expected != observed:
        raise IntegratedFixedTraceError("checksums differ")


def _run(
    config: dict[str, Any],
    *,
    output_root: Path,
    pilot: bool,
) -> dict[str, Any]:
    if output_root.exists():
        raise IntegratedFixedTraceError(
            f"fresh output root exists: {output_root}"
        )
    if not pilot and _git_status():
        raise IntegratedFixedTraceError(
            "formal integrated trace requires a clean worktree"
        )
    if shutil.disk_usage(REPO_ROOT).free / (1024**3) < 10:
        raise IntegratedFixedTraceError("free disk is below 10 GiB")
    output_root.mkdir(parents=True)
    ledger_path = output_root / "qualification_ledger.jsonl"
    rows = []
    paths = config["population"]["paths_per_pair"]
    for pair_index, entry in enumerate(
        config["population"]["pairs"]
    ):
        for path_index, path in enumerate(paths):
            row = _run_path(
                entry,
                path=path,
                case_index=pair_index * len(paths) + path_index,
            )
            rows.append(row)
            with ledger_path.open("a") as stream:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
    summary = _summarize(config, rows, pilot=pilot)
    (output_root / "summary.json").write_text(_canonical(summary))
    (output_root / "run_manifest.json").write_text(
        _canonical(
            {
                "schema": SUMMARY_SCHEMA + ".run-manifest",
                "status": "complete",
                "protocol_id": config["protocol_id"],
                "protocol_sha256": (
                    _sha256(PROTOCOL_PATH) if not pilot else None
                ),
                "row_count": len(rows),
                "policy_loaded": False,
                "policy_inference_performed": False,
                "policy_action_dispatched": False,
                "simulator_created": False,
                "outcomes_observed": False,
            }
        )
    )
    _write_checksums(output_root)
    return summary


def _validate(
    config: dict[str, Any],
    *,
    output_root: Path,
    pilot: bool,
) -> dict[str, Any]:
    _validate_checksums(output_root)
    manifest = json.loads(
        (output_root / "run_manifest.json").read_text()
    )
    if manifest.get("status") != "complete":
        raise IntegratedFixedTraceError("manifest is incomplete")
    rows = [
        json.loads(line)
        for line in (
            output_root / "qualification_ledger.jsonl"
        ).read_text().splitlines()
        if line.strip()
    ]
    retained = json.loads((output_root / "summary.json").read_text())
    recomputed = _summarize(config, rows, pilot=pilot)
    if retained != recomputed:
        raise IntegratedFixedTraceError("summary recomputation differs")
    return recomputed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    args = parser.parse_args()
    if args.pilot:
        if args.execute or args.validate_results:
            parser.error("--pilot cannot be combined with formal modes")
        payload = _run(
            _pilot_config(), output_root=PILOT_ROOT, pilot=True
        )
    else:
        if args.execute == args.validate_results:
            parser.error(
                "choose one of --execute or --validate-results"
            )
        config = _verify_protocol()
        if args.execute:
            payload = _run(
                config, output_root=OUTPUT_ROOT, pilot=False
            )
        else:
            payload = _validate(
                config, output_root=OUTPUT_ROOT, pilot=False
            )
    print(_canonical(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
