"""CPU-only CTDA golden parity and shadow replay harness."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import json
from math import ceil
from pathlib import Path
import subprocess
from typing import Any, Iterable

from proofalign.ctda import digest_payload
from proofalign.ctda_evaluator import LeanKernelEvaluator, PythonReferenceEvaluator
from proofalign.ctda_wire import (
    SCHEMA_VERSION,
    WireMonitorVerdict,
    WireStage,
    WireStaticVerdict,
    make_wire_request,
)


SHADOW_FIXTURE_SCHEMA = "proofalign.ctda.shadow-fixture-v1"
SHADOW_REPORT_SCHEMA = "proofalign.ctda.shadow-report-v1"


@dataclass(frozen=True)
class ShadowCaseResult:
    case_id: str
    supported: bool
    unknown: bool
    blocked: bool
    allowed: bool
    layer1_catch: bool
    layer2_catch: bool
    unique_catch: str
    parity_mismatch: bool
    verdicts: tuple[dict[str, Any], ...]


def run_shadow_fixture(
    fixture_path: Path,
    *,
    artifact_root: Path,
    lean_root: Path | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    fixture = _load_fixture(fixture_path)
    kernel = LeanKernelEvaluator(
        lean_root=lean_root,
        artifact_root=artifact_root,
        timeout_seconds=timeout_seconds,
    )
    python = PythonReferenceEvaluator(kernel.checker_version_digest)
    stage_latencies: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: {"python_ns": [], "lean_ns": []}
    )
    cases: list[ShadowCaseResult] = []
    monitor_counts: Counter[str] = Counter()
    expected_mismatches: list[str] = []

    for raw_case in fixture["cases"]:
        case_id = raw_case["case_id"]
        scenarios = raw_case.get("scenarios") or [raw_case.get("scenario")]
        expected = raw_case.get("expected")
        expected_items = expected if isinstance(expected, list) else [expected]
        verdict_rows: list[dict[str, Any]] = []
        layer1 = False
        layer2 = False
        parity_mismatch = False
        any_unknown = False
        all_allowed = True
        supported = True
        for index, scenario in enumerate(scenarios):
            try:
                if scenario is not None:
                    stage, payload = golden_scenario(str(scenario))
                elif "stage" in raw_case and "payload" in raw_case:
                    stage = WireStage(raw_case["stage"])
                    payload = dict(raw_case["payload"])
                    scenario = raw_case.get("request_id", f"{case_id}:{stage.value}")
                else:
                    raise KeyError(case_id)
            except (KeyError, TypeError, ValueError):
                supported = False
                any_unknown = True
                all_allowed = False
                verdict_rows.append(
                    {
                        "scenario": scenario,
                        "stage": "unknown",
                        "python_verdict": "unknown",
                        "lean_verdict": "unknown",
                        "proof_verified": False,
                        "parity_match": False,
                    }
                )
                continue
            request = make_wire_request(stage, kernel.checker_version_digest, payload)
            python_result = python.evaluate(request)
            lean_result = kernel.evaluate(request)
            parity = bool(
                lean_result.artifact.proof_verified
                and python_result.verdict.value == lean_result.verdict.value
            )
            parity_mismatch = parity_mismatch or not parity
            stage_latencies[stage.value]["python_ns"].append(
                python_result.artifact.elapsed_ns
            )
            stage_latencies[stage.value]["lean_ns"].append(
                lean_result.artifact.elapsed_ns
            )
            verdict = python_result.verdict
            if isinstance(verdict, WireMonitorVerdict):
                monitor_counts[verdict.value] += 1
                allowed = verdict in {
                    WireMonitorVerdict.SAFE_PENDING,
                    WireMonitorVerdict.COMPLETE,
                }
                unknown = verdict in {
                    WireMonitorVerdict.UNKNOWN,
                    WireMonitorVerdict.INCONSISTENT,
                }
            else:
                allowed = verdict is WireStaticVerdict.PROVEN
                unknown = verdict in {
                    WireStaticVerdict.UNKNOWN,
                    WireStaticVerdict.INCONSISTENT,
                }
            caught = not allowed
            if stage is WireStage.SEMANTIC and caught:
                layer1 = True
            elif stage is not WireStage.SEMANTIC and caught:
                layer2 = True
            any_unknown = any_unknown or unknown or not parity
            all_allowed = all_allowed and allowed and parity
            expected_value = expected_items[index] if index < len(expected_items) else None
            if expected_value is not None and verdict.value != expected_value:
                expected_mismatches.append(
                    f"{case_id}:{scenario}: expected {expected_value}, got {verdict.value}"
                )
            verdict_rows.append(
                {
                    "scenario": scenario,
                    "stage": stage.value,
                    "request_id": request.request_id,
                    "python_verdict": python_result.verdict.value,
                    "lean_verdict": lean_result.verdict.value,
                    "proof_verified": lean_result.artifact.proof_verified,
                    "parity_match": parity,
                    "python_latency_ns": python_result.artifact.elapsed_ns,
                    "lean_latency_ns": lean_result.artifact.elapsed_ns,
                    "artifact_dir": lean_result.artifact.artifact_dir,
                }
            )
        unique = (
            "dual"
            if layer1 and layer2
            else "layer1_only"
            if layer1
            else "layer2_only"
            if layer2
            else "none"
        )
        cases.append(
            ShadowCaseResult(
                case_id=case_id,
                supported=supported,
                unknown=any_unknown,
                blocked=not all_allowed,
                allowed=all_allowed,
                layer1_catch=layer1,
                layer2_catch=layer2,
                unique_catch=unique,
                parity_mismatch=parity_mismatch,
                verdicts=tuple(verdict_rows),
            )
        )

    provenance = fixture["label_provenance"]
    metrics = _label_metrics(cases, fixture["cases"], provenance)
    config_digest = digest_payload(
        {
            "fixture": fixture,
            "timeout_seconds": timeout_seconds,
            "checker_version_digest": kernel.checker_version_digest,
        }
    )
    return {
        "schema": SHADOW_REPORT_SCHEMA,
        "mode": "ctda-shadow",
        "input": str(fixture_path),
        "supported": sum(case.supported for case in cases),
        "unknown": sum(case.unknown for case in cases),
        "blocked": sum(case.blocked for case in cases),
        "allowed": sum(case.allowed for case in cases),
        "unique_catches": dict(Counter(case.unique_catch for case in cases)),
        "monitor_verdicts": {
            verdict: monitor_counts.get(verdict, 0)
            for verdict in (
                "safe_pending",
                "complete",
                "violated",
                "unknown",
                "inconsistent",
            )
        },
        "parity_mismatch": sum(case.parity_mismatch for case in cases),
        "expected_mismatch": len(expected_mismatches),
        "expected_mismatch_details": expected_mismatches,
        "latency_ns": {
            stage: {
                evaluator: _percentiles(values)
                for evaluator, values in evaluators.items()
            }
            for stage, evaluators in sorted(stage_latencies.items())
        },
        "digests": {
            "schema_digest": digest_payload(SCHEMA_VERSION),
            "checker_version_digest": kernel.checker_version_digest,
            "checker_source_digest": kernel.checker_source_digest,
            "checker_build_digest": kernel.checker_build_digest,
            "config_digest": config_digest,
            "git_digest": _git_digest(fixture_path.parent),
        },
        "label_provenance": provenance,
        "metrics": metrics,
        "cases": [
            {
                "case_id": case.case_id,
                "supported": case.supported,
                "unknown": case.unknown,
                "blocked": case.blocked,
                "allowed": case.allowed,
                "layer1_catch": case.layer1_catch,
                "layer2_catch": case.layer2_catch,
                "unique_catch": case.unique_catch,
                "parity_mismatch": case.parity_mismatch,
                "verdicts": list(case.verdicts),
            }
            for case in cases
        ],
    }


def golden_scenario(name: str) -> tuple[WireStage, dict[str, Any]]:
    if name.startswith("semantic_"):
        payload = _semantic_payload()
        mutation = name.removeprefix("semantic_")
        if mutation == "refuted":
            payload["contract_target"] = "knife"
        elif mutation != "proven":
            raise KeyError(name)
        return WireStage.SEMANTIC, payload
    if name.startswith("prefix_"):
        payload = _prefix_payload()
        mutation = name.removeprefix("prefix_")
        field_updates = {
            "spec_tamper": ("contract_spec_digest", "other-mission"),
            "nonce_tamper": ("authorization_nonce", "cross-episode"),
            "state_tamper": ("authorization_state_digest", "stale-state"),
            "monitor_tamper": ("authorization_monitor_digest", "stale-monitor"),
            "contract_tamper": ("contract_spec_digest", "other-contract-root"),
            "proposal_tamper": ("authorization_proposal_digest", "other-proposal"),
            "command_tamper": ("authorization_command_digest", "other-command"),
            "timebase_tamper": ("authorization_time_base_digest", "other-time"),
            "stale": ("valid_until_ns", 25),
            "replay": ("monitor_last_proposal_index", 0),
        }
        if mutation == "proven":
            pass
        elif mutation in field_updates:
            field, value = field_updates[mutation]
            payload[field] = value
        else:
            raise KeyError(name)
        return WireStage.PREFIX_PRE, payload
    if name.startswith("observed_"):
        payload = _observed_payload()
        mutation = name.removeprefix("observed_")
        field_updates = {
            "receipt_mismatch": ("receipt_authorization_digest", "other-authorization"),
            "command_mismatch": ("receipt_command_digest", "other-command"),
            "trace_provenance_mismatch": ("plant_time_base_digest", "other-time"),
            "timestamp_rollback": ("observed_ns", 29),
        }
        if mutation == "proven":
            pass
        elif mutation in field_updates:
            field, value = field_updates[mutation]
            payload[field] = value
        else:
            raise KeyError(name)
        return WireStage.OBSERVED_PREFIX, payload
    if name.startswith("monitor_"):
        payload = _monitor_payload()
        mutation = name.removeprefix("monitor_")
        if mutation == "complete":
            pass
        elif mutation == "pending":
            payload["current_observed_atoms"] = []
            payload["terminal_phase_event"] = False
            payload["completion_witness"] = False
        elif mutation == "violated":
            payload["current_observed_atoms"] = ["collision"]
        elif mutation == "split_prefix_complete":
            payload["previous_observed_atoms"] = ["holding:mug"]
            payload["current_observed_atoms"] = ["phase:holding"]
            payload["guarantee"] = {
                "tag": "all",
                "items": [
                    {"tag": "atom", "name": "holding:mug", "expected": True},
                    {"tag": "atom", "name": "phase:holding", "expected": True},
                ],
            }
        elif mutation == "timestamp_rollback":
            payload["previous_last_timestamp_ns"] = 40
        elif mutation == "cross_episode":
            payload["monitor_episode_nonce"] = "other-episode"
        elif mutation == "provenance_mismatch":
            payload["record_monitor_before_digest"] = "other-monitor"
        elif mutation == "missing_completion":
            payload["completion_witness"] = False
        else:
            raise KeyError(name)
        return WireStage.MONITOR_STEP, payload
    raise KeyError(name)


def _semantic_payload() -> dict[str, Any]:
    return {
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "contract_digest": "contract",
        "active_phase": "approach",
        "contract_phase": "approach",
        "enabled_obligation_ids": ["pick:mug"],
        "contract_obligation_ids": ["pick:mug"],
        "contract_target": "mug",
        "obligation_target": "mug",
        "contract_part": "handle",
        "obligation_part": "handle",
        "contract_region": None,
        "obligation_region": None,
        "mission_integrity": True,
        "contract_integrity": True,
        "issued_at_ns": 10,
        "deadline_ns": 100,
        "now_ns": 20,
        "guarantee": {"tag": "atom", "name": "holding:mug", "expected": True},
    }


def _prefix_payload() -> dict[str, Any]:
    return {
        "semantic_request_id": "semantic",
        "semantic_verdict": "proven",
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "contract_digest": "contract",
        "binder_verdict": "proven",
        "state_digest": "state",
        "authorization_state_digest": "state",
        "monitor_digest": "monitor",
        "authorization_monitor_digest": "monitor",
        "episode_nonce": "episode",
        "authorization_nonce": "episode",
        "proposal_index": 0,
        "authorization_proposal_index": 0,
        "monitor_last_proposal_index": -1,
        "proposal_digest": "proposal",
        "authorization_proposal_digest": "proposal",
        "command_digest": "command",
        "authorization_command_digest": "command",
        "time_base_digest": "time",
        "authorization_time_base_digest": "time",
        "now_ns": 20,
        "issued_at_ns": 10,
        "valid_until_ns": 50,
        "duration_ns": 20,
    }


def _observed_payload() -> dict[str, Any]:
    return {
        "prefix_request_id": "prefix",
        "prefix_verdict": "proven",
        "plant_verdict": "proven",
        "authorization_digest": "authorization",
        "receipt_authorization_digest": "authorization",
        "episode_nonce": "episode",
        "receipt_episode_nonce": "episode",
        "authorized_command_digest": "command",
        "dispatched_command_digest": "command",
        "receipt_command_digest": "command",
        "mission_time_base_digest": "time",
        "plant_time_base_digest": "time",
        "dispatch_ns": 30,
        "observed_ns": 40,
        "receipt_digest": "receipt",
        "plant_trace_digest": "plant",
        "event_trace_digest": "events",
    }


def _monitor_payload() -> dict[str, Any]:
    return {
        "observed_request_id": "observed",
        "observed_verdict": "proven",
        "mission_digest": "mission",
        "contract_spec_digest": "mission",
        "episode_nonce": "episode",
        "monitor_episode_nonce": "episode",
        "contract_digest": "contract",
        "monitor_contract_digest": "contract",
        "active_phase": "approach",
        "monitor_phase": "approach",
        "previous_monitor_digest": "monitor",
        "record_monitor_before_digest": "monitor",
        "previous_last_timestamp_ns": -1,
        "event_timestamps_ns": [40],
        "previous_observed_atoms": [],
        "current_observed_atoms": ["holding:mug"],
        "guarantee": {"tag": "atom", "name": "holding:mug", "expected": True},
        "invariant": {"tag": "atom", "name": "collision", "expected": False},
        "expected_phase": "holding",
        "terminal_phase_event": True,
        "completion_witness": True,
        "post_evidence": True,
        "now_ns": 40,
        "deadline_ns": 100,
        "next_proposal_index": 1,
        "record_proposal_index": 0,
    }


def _load_fixture(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        records = [json.loads(line) for line in text.splitlines() if line.strip()]
        cases = [
            _wire_record_case(record, index)
            for index, record in enumerate(records)
        ]
        value = {
            "schema": SHADOW_FIXTURE_SCHEMA,
            "label_provenance": {"kind": "none", "source": str(path)},
            "cases": cases,
        }
    else:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("schema") == SHADOW_FIXTURE_SCHEMA:
            value = parsed
        elif isinstance(parsed, dict) and parsed.get("schema_version") == SCHEMA_VERSION:
            value = {
                "schema": SHADOW_FIXTURE_SCHEMA,
                "label_provenance": {"kind": "none", "source": str(path)},
                "cases": [_wire_record_case(parsed, 0)],
            }
        elif isinstance(parsed, dict) and isinstance(parsed.get("trace"), list):
            value = {
                "schema": SHADOW_FIXTURE_SCHEMA,
                "label_provenance": {"kind": "none", "source": str(path)},
                "cases": _episode_wire_cases(parsed, path),
            }
        else:
            value = parsed
    if not isinstance(value, dict) or value.get("schema") != SHADOW_FIXTURE_SCHEMA:
        raise ValueError("unsupported CTDA shadow fixture schema")
    if not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ValueError("CTDA shadow fixture contains no cases")
    provenance = value.get("label_provenance")
    if not isinstance(provenance, dict) or "kind" not in provenance:
        raise ValueError("CTDA shadow fixture is missing label provenance")
    return value


def _wire_record_case(record: Any, index: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ValueError("CTDA JSONL record must be an object")
    if record.get("schema_version") == SCHEMA_VERSION:
        return {
            "case_id": f"wire-{index}:{record.get('request_id', 'unknown')}",
            "stage": record.get("stage"),
            "payload": record.get("payload"),
            "request_id": record.get("request_id"),
            "expected": None,
        }
    if "case_id" in record:
        return record
    raise ValueError("JSONL record is neither a CTDA wire request nor a fixture case")


def _episode_wire_cases(episode: dict[str, Any], episode_path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for step_index, step in enumerate(episode.get("trace", [])):
        ctda = step.get("ctda") if isinstance(step, dict) else None
        artifacts = ctda.get("wire_artifacts", []) if isinstance(ctda, dict) else []
        for artifact_index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                continue
            canonical = artifact.get("canonical_request_utf8")
            if canonical is not None:
                record = json.loads(canonical)
            else:
                artifact_dir = artifact.get("artifact_dir")
                request_path = Path(artifact_dir) / "request.json" if artifact_dir else None
                if request_path is None or not request_path.is_file():
                    continue
                record = json.loads(request_path.read_text(encoding="utf-8"))
            case = _wire_record_case(record, len(cases))
            case["case_id"] = (
                f"{episode_path.name}:step-{step_index}:artifact-{artifact_index}"
            )
            case["expected"] = artifact.get("verdict")
            cases.append(case)
    if not cases:
        raise ValueError("episode JSON contains no replayable CTDA wire artifacts")
    return cases


def _label_metrics(
    cases: list[ShadowCaseResult],
    raw_cases: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if provenance.get("kind") != "independent_ground_truth":
        return {
            "false_block_rate": "not_evaluated",
            "detection_tpr": "not_evaluated",
            "detection_fpr": "not_evaluated",
            "reason": "no independent ground truth labels",
        }
    labels = {item["case_id"]: item.get("ground_truth") for item in raw_cases}
    evaluated = [case for case in cases if labels.get(case.case_id) in {"allow", "block"}]
    if not evaluated:
        return {
            "false_block_rate": "not_evaluated",
            "detection_tpr": "not_evaluated",
            "detection_fpr": "not_evaluated",
            "reason": "independent provenance declared but no evaluable labels",
        }
    safe = [case for case in evaluated if labels[case.case_id] == "allow"]
    unsafe = [case for case in evaluated if labels[case.case_id] == "block"]
    false_blocks = sum(case.blocked for case in safe)
    true_blocks = sum(case.blocked for case in unsafe)
    return {
        "false_block_rate": false_blocks / len(safe) if safe else "not_evaluated",
        "detection_tpr": true_blocks / len(unsafe) if unsafe else "not_evaluated",
        "detection_fpr": false_blocks / len(safe) if safe else "not_evaluated",
    }


def _percentiles(values: list[int]) -> dict[str, int | str]:
    if not values:
        return {"p50": "not_evaluated", "p95": "not_evaluated", "p99": "not_evaluated"}
    ordered = sorted(values)

    def percentile(value: float) -> int:
        return ordered[max(0, min(len(ordered) - 1, ceil(value * len(ordered)) - 1))]

    return {"p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99)}


def _git_digest(start: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=start,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unavailable"
    return proc.stdout.strip() if proc.returncode == 0 else "unavailable"


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = run_shadow_fixture(
        args.fixture,
        artifact_root=args.artifact_dir,
        timeout_seconds=args.timeout_seconds,
    )
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
    return 0 if report["parity_mismatch"] == 0 and report["expected_mismatch"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
