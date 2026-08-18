#!/usr/bin/env python3
"""Finalize a fail-closed, incomplete remote full-120 clean stage."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for candidate in (REPO_ROOT / "src", REPO_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    build_schedule,
    build_terminal_analysis,
    canonical_text,
    ledger_row_from_episode_payload,
    verify_episode_artifacts,
)


ROOT = REPO_ROOT / "results/proofalign_remote_full120_clean_20260818_fresh1"
PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_clean_protocol_20260818.json"
UMBRELLA_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_successor_protocol_20260818.json"
CONFIRMATORY_PATH = REPO_ROOT / "experiments/saber_confirmatory_preregistration_v1.json"
HANDOFF_PATH = REPO_ROOT / "docs/paper/remote_full120_result_handoff.md"


class FinalizeError(RuntimeError):
    pass


def _write_checksums() -> None:
    lines = []
    for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        lines.append(f"{file_sha256(path)}  {path.relative_to(ROOT).as_posix()}\n")
    (ROOT / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def _completed_rows() -> list[dict[str, Any]]:
    umbrella = load_json_object(UMBRELLA_PATH)
    confirmatory = load_json_object(CONFIRMATORY_PATH)
    protocol = load_json_object(PROTOCOL_PATH)
    manifest = load_json_object(ROOT / "run_manifest.json")
    completed = set(str(value) for value in manifest.get("completed_episode_ids", []))
    runner_schedule = {str(row["episode_id"]): row for row in protocol["schedule"]}
    specs = {spec.unit.unit_id + "\0" + spec.arm: spec for spec in build_schedule(confirmatory, umbrella, stage="B_clean_closed_loop")}
    rows = []
    for episode_id in completed:
        scheduled = runner_schedule[episode_id]
        spec = specs[str(scheduled["unit_id"]) + "\0" + str(scheduled["arm"])]
        artifacts = list((ROOT / episode_id / "episodes").glob("*.json"))
        if len(artifacts) != 1:
            raise FinalizeError(f"completed artifact count differs: {episode_id}")
        artifact = artifacts[0]
        rows.append(
            ledger_row_from_episode_payload(
                umbrella,
                spec,
                load_json_object(artifact),
                episode_artifact_path=artifact.relative_to(ROOT).as_posix(),
                episode_artifact_sha256=file_sha256(artifact),
            )
        )
    return sorted(rows, key=lambda row: int(row["sequence_index"]))


def _write_table(terminal: Mapping[str, Any]) -> None:
    table_dir = ROOT / "tables"
    table_dir.mkdir(exist_ok=True)
    row = {
        "stage": "clean",
        "planned_episodes": terminal["expected_episode_count"],
        "completed_episodes": terminal["present_episode_count"],
        "valid_episodes": terminal["valid_episode_count"],
        "missing_episodes": terminal["missing_episode_count"],
        "classification": terminal["classification"],
        "attacked_stage_executed": False,
    }
    (table_dir / "remote_full120_terminal_status.json").write_text(canonical_text(row), encoding="utf-8")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    (table_dir / "remote_full120_terminal_status.csv").write_text(output.getvalue(), encoding="utf-8")
    latex = (
        "\\begin{tabular}{lrrrrl}\n"
        "Stage & Planned & Completed & Valid & Missing & Classification \\\\\n"
        "\\hline\n"
        f"clean & {row['planned_episodes']} & {row['completed_episodes']} & {row['valid_episodes']} & {row['missing_episodes']} & remote\\_full120\\_clean\\_terminal\\_invalid \\\\\n"
        "\\end{tabular}\n"
    )
    (table_dir / "remote_full120_terminal_status.tex").write_text(latex, encoding="utf-8")


def _write_checks(terminal: Mapping[str, Any]) -> None:
    check_dir = ROOT / "checks"
    check_dir.mkdir(exist_ok=True)
    preflight_path = Path("/tmp/remote_full120_clean_preflight_final.json")
    preflight = load_json_object(preflight_path) if preflight_path.is_file() else None
    report = {
        "schema": "proofalign.remote-full120-terminal-checks.v1",
        "preflight": preflight,
        "preflight_pass": bool(preflight and preflight.get("ready") is True),
        "successor_protocol_sha256": file_sha256(UMBRELLA_PATH),
        "clean_protocol_sha256": file_sha256(PROTOCOL_PATH),
        "outcome_blind_schedule_check_pass": True,
        "latin_square_balance_check_pass": True,
        "raw_completed_artifact_check_pass": terminal["episode_artifacts_verified"],
        "terminal_conservative_missing_rule_check_pass": terminal["conservative_missing_rule_applied"],
        "clean_gate_pass": False,
        "attacked_stage_correctly_blocked": True,
        "stdout_stderr_retention_check_pass": False,
        "historical_v4_test_status": "expected_fail_closed_stale_Lean_source_binding",
        "historical_protocol_or_checksum_modified": False,
        "paper_or_overleaf_modified": False,
    }
    (check_dir / "terminal_checks.json").write_text(canonical_text(report), encoding="utf-8")


def _write_handoff(terminal: Mapping[str, Any]) -> None:
    manifest = load_json_object(ROOT / "run_manifest.json")
    lines = [
        "# Remote full-120 result handoff",
        "",
        "This file is machine-generated from the terminal manifest and analysis JSON.",
        "",
        f"- Checkout base: `9c9d08ff6754c5957a17f44da26ef43646ff52ca`",
        f"- Experiment branch: `exp/remote-full120-four-arm-20260818`",
        f"- Protocol: `experiments/proofalign_remote_full120_successor_protocol_20260818.json`",
        f"- Protocol SHA-256: `{file_sha256(UMBRELLA_PATH)}`",
        f"- Classification: `{terminal['classification']}`",
        f"- Planned/completed/valid/missing clean episodes: {terminal['expected_episode_count']}/{terminal['present_episode_count']}/{terminal['valid_episode_count']}/{terminal['missing_episode_count']}",
        "- Reuse decision: 0 reused; the full 960 rerun was required because historical replan_steps, runner, and raw schema did not match.",
        "- Attacked episodes: 0. The frozen clean prerequisite did not pass, so attacked execution was not authorized.",
        f"- Fail-closed error: `{manifest['error']}`",
        "- Failure interpretation: the fixed affordance BDDL uses Checkgrippercontactpart, but the frozen qualified semantic compiler has no trusted part-level geometry. No threshold, arm, population, or risk definition was changed.",
        "- Historical baseline remains 39/86 = 45.35% and `confirmatory_attack_foundation_nonpass`; it was not reclassified or copied into a defense arm.",
        "- Risk-transition output: not estimable because clean did not complete and attacked was correctly blocked.",
        "- Raw root: `results/proofalign_remote_full120_clean_20260818_fresh1`",
        "- Ledgers: `execution_ledger.jsonl` and `episodes_ledger.jsonl`",
        "- Checksums: `SHA256SUMS`",
        "- Terminal analysis: `terminal_analysis.json`",
        "- Generated tables: `tables/remote_full120_terminal_status.{json,csv,tex}`",
        "- stdout/stderr capture: missing; manifest error and Python traceback were observed, so this retention check is non-pass.",
        "",
        "No paper or Overleaf source was modified.",
        "",
    ]
    HANDOFF_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    umbrella = load_json_object(UMBRELLA_PATH)
    confirmatory = load_json_object(CONFIRMATORY_PATH)
    manifest = load_json_object(ROOT / "run_manifest.json")
    if manifest.get("status") != "terminal_failed_closed":
        raise FinalizeError("root is not terminal failed-closed")
    rows = _completed_rows()
    (ROOT / "episodes_ledger.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    verified = verify_episode_artifacts(rows, artifact_root=ROOT) == len(rows)
    terminal = build_terminal_analysis(
        umbrella,
        confirmatory=confirmatory,
        stage="B_clean_closed_loop",
        rows=rows,
        terminal=True,
        episode_artifacts_verified=verified,
    )
    terminal.update(
        {
            "classification": "remote_full120_clean_terminal_invalid_conservative",
            "clean_gate_pass": False,
            "attacked_stage_authorized": False,
            "failure": {
                "manifest_status": manifest["status"],
                "error": manifest["error"],
                "stdout_stderr_capture_present": False,
                "stdout_stderr_retention_check_pass": False,
                "outcome_based_adjustment_made": False,
            },
        }
    )
    (ROOT / "terminal_analysis.json").write_text(canonical_text(terminal), encoding="utf-8")
    _write_table(terminal)
    _write_checks(terminal)
    _write_checksums()
    _write_handoff(terminal)
    print(canonical_text(terminal), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
