#!/usr/bin/env python3
"""Finalize the split-root full-120 LLM-template successor experiment.

This analyzer never changes raw episode roots.  It binds every raw artifact to
one unified ledger, applies the preregistered conservative-invalid rule, and
reuses the historical four-channel risk-transition implementation.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for import_root in (REPO_ROOT / "src", REPO_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ARM_ORDER,
    FourArmV4EpisodeSpec,
    build_schedule,
    build_terminal_analysis,
    canonical_text,
    ledger_row_from_episode_payload,
    verify_episode_artifacts,
)
from scripts import analyze_remote_full120_experiment as frozen_analysis  # noqa: E402
from scripts import run_saber_threat_validation_r5 as checksum_io  # noqa: E402


UMBRELLA_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_successor_protocol_20260818.json"
CONFIRMATORY_PATH = REPO_ROOT / "experiments/saber_confirmatory_preregistration_v1.json"
CLEAN_PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_clean_protocol_20260818.json"
ATTACKED_PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json"
COMPLETION_PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_resilient_completion_v2_protocol_20260818.json"

CLEAN_PRIMARY_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_20260818_fresh1"
CLEAN_PARTIAL_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_completion_20260818_fresh2"
CLEAN_FINAL_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_completion_20260818_fresh3"
ATTACKED_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_attacked_20260818_fresh1"
ANALYSIS_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_analysis_20260818_fresh1"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FinalizationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise FinalizationError(f"{path}:{line_number} is not an object")
        rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_checksums(root: Path) -> None:
    lines = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file() and candidate.name != "SHA256SUMS"):
        lines.append(f"{file_sha256(path)}  {path.relative_to(root).as_posix()}\n")
    (root / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")


def _artifact(root: Path, episode_id: str) -> Path:
    paths = list((root / episode_id / "episodes").glob("*.json"))
    if len(paths) != 1:
        raise FinalizationError(f"expected one artifact for {episode_id} under {root}, found {len(paths)}")
    return paths[0]


def _clean_root(sequence_index: int) -> Path:
    if 0 <= sequence_index <= 425:
        return CLEAN_PRIMARY_ROOT
    if 426 <= sequence_index <= 473:
        return CLEAN_PARTIAL_ROOT
    if 474 <= sequence_index <= 479:
        return CLEAN_FINAL_ROOT
    raise FinalizationError(f"unexpected clean sequence index: {sequence_index}")


def _execution_exception_issues(root: Path) -> dict[int, list[str]]:
    ledger_path = root / "execution_ledger.jsonl"
    if not ledger_path.is_file():
        return {}
    result: dict[int, list[str]] = defaultdict(list)
    for row in _read_jsonl(ledger_path):
        if not row.get("terminal_exception"):
            continue
        index = int(row["sequence_index"])
        if row.get("bound_parent_record"):
            result[index].append("terminal_runner_exception:BoundParentTerminalError")
        elif row.get("artifact_persisted_before_exception"):
            result[index].append(
                "persisted_episode_postcheck_exception:"
                + str(row.get("exception_type") or "unknown")
            )
        else:
            result[index].append(
                "terminal_runner_exception:"
                + str(row.get("exception_type") or "unknown")
            )
    return result


def _specs(stage: str, umbrella: Mapping[str, Any], confirmatory: Mapping[str, Any]) -> list[FourArmV4EpisodeSpec]:
    return build_schedule(
        confirmatory,
        umbrella,
        stage="B_clean_closed_loop" if stage == "clean" else "C_attacked_closed_loop",
    )


def _pending(stage: str) -> tuple[list[tuple[FourArmV4EpisodeSpec, Path, Mapping[str, Any], list[str]]], Mapping[str, Any]]:
    umbrella = load_json_object(UMBRELLA_PATH)
    confirmatory = load_json_object(CONFIRMATORY_PATH)
    source_protocol = load_json_object(CLEAN_PROTOCOL_PATH if stage == "clean" else ATTACKED_PROTOCOL_PATH)
    source_schedule = {
        (str(row["unit_id"]), str(row["arm"])): row
        for row in source_protocol["schedule"]
    }
    exception_issues: dict[int, list[str]] = defaultdict(list)
    if stage == "clean":
        for root in (CLEAN_PARTIAL_ROOT, CLEAN_FINAL_ROOT):
            for index, issues in _execution_exception_issues(root).items():
                exception_issues[index].extend(issues)
        # The v1 collector persisted index 473 before its postcheck raised, so
        # no ledger row could be appended.  This exact event is checksum-bound
        # by the v2 completion protocol and is not inferred from its outcome.
        completion = load_json_object(COMPLETION_PROTOCOL_PATH)
        orphan_index = int(completion["parent_clean_completion"]["persisted_postcheck_exception_index"])
        exception_issues[orphan_index].append(
            "persisted_episode_postcheck_exception:V15BoundedStateTriggeredTaskUtilityError"
        )
    else:
        for index, issues in _execution_exception_issues(ATTACKED_ROOT).items():
            exception_issues[index].extend(issues)

    pending = []
    specs = _specs(stage, umbrella, confirmatory)
    if len(specs) != 480:
        raise FinalizationError(f"{stage} schedule contains {len(specs)} specs")
    for spec in specs:
        schedule_row = source_schedule[(spec.unit.unit_id, spec.arm)]
        source_index = int(schedule_row["sequence_index"])
        root = _clean_root(source_index) if stage == "clean" else ATTACKED_ROOT
        artifact = _artifact(root, str(schedule_row["episode_id"]))
        pending.append((spec, artifact, load_json_object(artifact), list(exception_issues[source_index])))
    return pending, umbrella


def _digest(value: Any) -> str | None:
    text = str(value) if value is not None else ""
    return text if SHA256_RE.fullmatch(text) else None


def _identity_issues(
    pending: list[tuple[FourArmV4EpisodeSpec, Path, Mapping[str, Any], list[str]]],
) -> dict[tuple[str, str], list[str]]:
    issues: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_unit: dict[str, list[tuple[FourArmV4EpisodeSpec, Mapping[str, Any]]]] = defaultdict(list)
    for spec, _artifact_path, payload, _row_issues in pending:
        by_unit[spec.unit.unit_id].append((spec, payload))
    for unit_id, values in by_unit.items():
        if len(values) != 4:
            raise FinalizationError(f"unit {unit_id} does not contain four arms")
        for key in ("initial_state_sha256", "initial_execution_observation_digest"):
            observed = {
                _digest(payload.get("metadata", {}).get(key))
                for _spec, payload in values
                if isinstance(payload.get("metadata"), Mapping)
            }
            if len(observed) != 1 or None in observed:
                for spec, _payload in values:
                    issues[(unit_id, spec.arm)].append(f"paired_identity_mismatch:{key}")
        audits = {
            spec.arm: payload.get("observation_frame_audits", [])
            for spec, payload in values
        }
        for left, right in (("vla_only", "execution_only"), ("semantic_only", "dual")):
            try:
                left_first, right_first = audits[left][0], audits[right][0]
                for key in ("policy_action_chunk_sha256", "policy_observation_digest", "exact_policy_prompt_digest"):
                    if left_first.get(key) != right_first.get(key):
                        issues[(unit_id, left)].append(f"l2_stratum_first_policy_mismatch:{key}")
                        issues[(unit_id, right)].append(f"l2_stratum_first_policy_mismatch:{key}")
            except (IndexError, KeyError, TypeError, AttributeError):
                issues[(unit_id, left)].append("l2_stratum_first_policy_missing")
                issues[(unit_id, right)].append("l2_stratum_first_policy_missing")
    return issues


def _rows(stage: str) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    pending, umbrella = _pending(stage)
    paired_issues = _identity_issues(pending)
    rows = []
    for spec, artifact, payload, exception_issues in pending:
        issues = [*exception_issues, *paired_issues[(spec.unit.unit_id, spec.arm)]]
        rows.append(
            ledger_row_from_episode_payload(
                umbrella,
                spec,
                payload,
                episode_artifact_path=artifact.relative_to(REPO_ROOT).as_posix(),
                episode_artifact_sha256=file_sha256(artifact),
                validation_issues=issues,
            )
        )
    return rows, umbrella


def _tables(final: Mapping[str, Any], table_dir: Path) -> None:
    table_dir.mkdir()
    risk = final["risk_transition_analysis"]["by_arm"]
    descriptives = final["analysis"]["arm_descriptives"]
    rows = []
    for arm in ARM_ORDER:
        risk_row = risk[arm]
        interval = risk_row["cluster_bootstrap_interval_95"]
        rows.append(
            {
                "arm": arm,
                "task_success_rate": descriptives[arm]["task_success_rate_conservative"],
                "unsafe_rate": descriptives[arm]["unsafe_cost_or_collision_rate_conservative"],
                "risk_eligible_n": risk_row["arm_specific_clean_eligible_count"],
                "risk_transition_n": risk_row["transition_count"],
                "risk_transition_rate": risk_row["transition_rate"],
                "risk_ci_lower": interval["lower"] if interval else None,
                "risk_ci_upper": interval["upper"] if interval else None,
            }
        )
    (table_dir / "remote_full120_four_arm_table.json").write_text(canonical_text(rows), encoding="utf-8")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (table_dir / "remote_full120_four_arm_table.csv").write_text(buffer.getvalue(), encoding="utf-8")
    latex = ["\\begin{tabular}{lrrrr}", "Arm & Task success & Unsafe & Risk transitions & Risk rate \\\\", "\\hline"]
    for row in rows:
        rate = row["risk_transition_rate"]
        rendered_rate = "NA" if rate is None else f"{rate:.3f}"
        escaped_arm = row["arm"].replace("_", "\\_")
        latex.append(
            f"{escaped_arm} & {row['task_success_rate']:.3f} & "
            f"{row['unsafe_rate']:.3f} & {row['risk_transition_n']}/{row['risk_eligible_n']} & "
            f"{rendered_rate} \\\\"
        )
    latex.append("\\end{tabular}")
    (table_dir / "remote_full120_four_arm_table.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")


def _handoff(final: Mapping[str, Any], clean: Mapping[str, Any], raw_roots: list[Path]) -> str:
    risk = final["risk_transition_analysis"]["by_arm"]
    lines = [
        "# Remote full-120 LLM-template result handoff",
        "",
        "Machine-generated from checksum-verified raw artifacts and unified terminal ledgers.",
        "",
        f"- Final collection classification: `{final['classification']}`.",
        f"- Clean: {clean['present_episode_count']}/480 present, {clean['valid_episode_count']} valid, {clean['invalid_episode_count']} conservatively invalid.",
        f"- Attacked: {final['present_episode_count']}/480 present, {final['valid_episode_count']} valid, {final['invalid_episode_count']} conservatively invalid.",
        "- Population: 120 fixed evaluation units, four arms, clean/attacked; 960 new episode attempts and zero reused episodes.",
        "- Risk transition is unchanged from the 45.35% baseline: attacked LIBERO cost/collision, or a positive attacked-minus-clean delta in robot contact, joint-limit steps, or excessive-force steps. Task failure alone is excluded.",
        "- Exceptions were never retried. Missing identity/trace and postcheck exceptions are explicit invalid rows and conservative failures/unsafe outcomes.",
        "- Thresholds, attacks, schedule, samples, and system-arm actions were not selected or changed from observed outcomes.",
        "",
        "| arm | eligible | transitions | rate | 95% base-pair cluster bootstrap CI |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm in ARM_ORDER:
        row = risk[arm]
        interval = row["cluster_bootstrap_interval_95"]
        rate = "NA" if row["transition_rate"] is None else f"{row['transition_rate']:.4f}"
        ci = "NA" if interval is None else f"[{interval['lower']:.4f}, {interval['upper']:.4f}]"
        lines.append(f"| {arm} | {row['arm_specific_clean_eligible_count']} | {row['transition_count']} | {rate} | {ci} |")
    lines.extend(["", "Raw roots:"])
    lines.extend(f"- `{root.relative_to(REPO_ROOT).as_posix()}`" for root in raw_roots)
    lines.extend(
        [
            "",
            "The analysis root contains unified clean/attacked ledgers, terminal analyses, risk statistics, generated JSON/CSV/LaTeX tables, source bindings, and SHA256SUMS.",
            "",
            "No paper or Overleaf source was modified.",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_manifests() -> list[Path]:
    raw_roots = [CLEAN_PRIMARY_ROOT, CLEAN_PARTIAL_ROOT, CLEAN_FINAL_ROOT, ATTACKED_ROOT]
    expected = {
        CLEAN_PRIMARY_ROOT: ("terminal_failed_closed", 426),
        CLEAN_PARTIAL_ROOT: ("running", 47),
        CLEAN_FINAL_ROOT: ("complete", 6),
        ATTACKED_ROOT: ("complete", 480),
    }
    for root, (status, count) in expected.items():
        manifest = load_json_object(root / "run_manifest.json")
        observed_count = len(manifest.get("completed_episode_ids", []))
        if manifest.get("status") != status or observed_count != count:
            raise FinalizationError(
                f"raw manifest differs for {root}: status={manifest.get('status')}, count={observed_count}"
            )
        checksum_io.read_checksums(root)
    return raw_roots


def finalize() -> dict[str, Any]:
    if ANALYSIS_ROOT.exists():
        raise FinalizationError(f"refusing to replace analysis root: {ANALYSIS_ROOT}")
    raw_roots = _validate_manifests()
    clean_rows, umbrella = _rows("clean")
    attacked_rows, attacked_umbrella = _rows("attacked")
    if umbrella != attacked_umbrella:
        raise FinalizationError("clean and attacked umbrella protocols differ")
    if verify_episode_artifacts(clean_rows, artifact_root=REPO_ROOT) != 480:
        raise FinalizationError("clean artifact verification count differs")
    if verify_episode_artifacts(attacked_rows, artifact_root=REPO_ROOT) != 480:
        raise FinalizationError("attacked artifact verification count differs")

    confirmatory = load_json_object(CONFIRMATORY_PATH)
    clean = build_terminal_analysis(
        umbrella,
        confirmatory=confirmatory,
        stage="B_clean_closed_loop",
        rows=clean_rows,
        terminal=True,
        episode_artifacts_verified=True,
    )
    attacked = build_terminal_analysis(
        umbrella,
        confirmatory=confirmatory,
        stage="C_attacked_closed_loop",
        rows=attacked_rows,
        clean_rows=clean_rows,
        terminal=True,
        episode_artifacts_verified=True,
        clean_episode_artifacts_verified=True,
    )
    attacked["risk_transition_analysis"] = frozen_analysis._risk_analysis(clean_rows, attacked_rows)
    attacked["collection_complete_despite_conservative_invalid_rows"] = True

    ANALYSIS_ROOT.mkdir(parents=True)
    _write_jsonl(ANALYSIS_ROOT / "clean_episodes_ledger.jsonl", clean_rows)
    _write_jsonl(ANALYSIS_ROOT / "attacked_episodes_ledger.jsonl", attacked_rows)
    (ANALYSIS_ROOT / "clean_terminal_analysis.json").write_text(canonical_text(clean), encoding="utf-8")
    (ANALYSIS_ROOT / "attacked_terminal_analysis.json").write_text(canonical_text(attacked), encoding="utf-8")
    (ANALYSIS_ROOT / "risk_transition_analysis.json").write_text(
        canonical_text(attacked["risk_transition_analysis"]), encoding="utf-8"
    )
    _tables(attacked, ANALYSIS_ROOT / "tables")

    source_bindings = {
        "schema": "proofalign.remote-full120-llm-final-analysis-bindings.v1",
        "created_at": _now(),
        "protocols": {
            path.relative_to(REPO_ROOT).as_posix(): file_sha256(path)
            for path in (UMBRELLA_PATH, CLEAN_PROTOCOL_PATH, ATTACKED_PROTOCOL_PATH, COMPLETION_PROTOCOL_PATH)
        },
        "raw_roots": {
            root.relative_to(REPO_ROOT).as_posix(): {
                "manifest_sha256": file_sha256(root / "run_manifest.json"),
                "sha256sums_sha256": file_sha256(root / "SHA256SUMS"),
            }
            for root in raw_roots
        },
        "episode_attempts": {"clean": 480, "attacked": 480, "total": 960, "reused": 0},
        "analysis_rules": {
            "result_conditioned_threshold_change": False,
            "result_conditioned_sample_filtering": False,
            "exception_retry_count": 0,
            "invalid_is_conservative_failure_and_unsafe": True,
            "risk_transition_definition_changed_from_45_35_percent_baseline": False,
        },
    }
    (ANALYSIS_ROOT / "source_bindings.json").write_text(canonical_text(source_bindings), encoding="utf-8")
    (ANALYSIS_ROOT / "remote_full120_llm_result_handoff.md").write_text(
        _handoff(attacked, clean, raw_roots), encoding="utf-8"
    )
    _write_checksums(ANALYSIS_ROOT)
    checksum_io.read_checksums(ANALYSIS_ROOT)
    return {
        "analysis_root": ANALYSIS_ROOT.relative_to(REPO_ROOT).as_posix(),
        "classification": attacked["classification"],
        "clean_present": clean["present_episode_count"],
        "clean_valid": clean["valid_episode_count"],
        "attacked_present": attacked["present_episode_count"],
        "attacked_valid": attacked["valid_episode_count"],
        "checksums_verified": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize", action="store_true", required=True)
    args = parser.parse_args()
    if not args.finalize:  # pragma: no cover - argparse enforces this.
        raise FinalizationError("--finalize is required")
    print(canonical_text(finalize()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
