#!/usr/bin/env python3
"""Generate immutable L1 experiment tables and handoff artifacts from analysis."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import file_sha256, load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts.analyze_l1_task_conditioned_experiment import (  # noqa: E402
    RISK_CHANNELS,
    TRANSITION_CHANNELS,
)


class FinalizeError(RuntimeError):
    pass


def _git(*args: str) -> str:
    result = subprocess.run(
        ("git", *args), cwd=REPO_ROOT, text=True, capture_output=True
    )
    if result.returncode:
        raise FinalizeError(result.stderr.strip() or "git failed")
    return result.stdout.strip()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _percent(value: Any) -> str:
    return "n/a" if value is None else f"{100.0 * float(value):.2f}%"


def _csv(rows: list[Mapping[str, Any]], fields: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def _assert_analysis(analysis: Mapping[str, Any]) -> None:
    if analysis.get("risk_transition_definition", {}).get(
        "same_as_45_35_percent_baseline"
    ) is not True:
        raise FinalizeError("analysis is not bound to the registered risk definition")
    registered = analysis.get("registered_risk_analysis", {})
    if (
        registered.get("same_as_45_35_percent_baseline") is not True
        or tuple(registered.get("channels", ())) != TRANSITION_CHANNELS
    ):
        raise FinalizeError("registered four-channel risk analysis is absent")
    rows = analysis.get("episode_rows", ())
    pairs = analysis.get("paired_rows", ())
    if len(rows) != 960 or len(pairs) != 480:
        raise FinalizeError("held-out analysis must contain 960 episodes and 480 pairs")
    if set(analysis.get("condition_arm_summary", {})) != {"clean", "attacked"}:
        raise FinalizeError("clean/attacked summaries are incomplete")
    expected_arms = {"vla_only", "semantic_only", "execution_only", "dual"}
    for condition in ("clean", "attacked"):
        if set(analysis["condition_arm_summary"][condition]) != expected_arms:
            raise FinalizeError(f"four-arm summary is incomplete: {condition}")


def _table_rows(analysis: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    arms = ("vla_only", "semantic_only", "execution_only", "dual")
    condition_rows = []
    for condition in ("clean", "attacked"):
        for arm in arms:
            row = analysis["condition_arm_summary"][condition][arm]
            condition_rows.append(
                {
                    "condition": condition,
                    "arm": arm,
                    "episodes": row["episode_count"],
                    "terminal_exceptions": row["terminal_exception_count"],
                    "task_success_count": row["task_success_count"],
                    "task_success_rate": row["task_success_rate"],
                    "l1_interventions": row["l1_intervention_count"],
                    "qualified_no_dispatch_aborts": row[
                        "recovery_selected_kinds"
                    ].get("qualified_no_dispatch_abort", 0),
                    "l1_intervention_rate": row["l1_intervention_rate_per_policy_call"],
                    "l1_restore_complete_episodes": row["l1_restore_complete_episode_count"],
                    "typed_signal_complete": row["typed_risk_signal_complete_count"],
                    "contact_sum": row["risk_channel_sums"]["robot_contact_count"],
                    "joint_limit_step_sum": row["risk_channel_sums"]["joint_limit_violation_steps"],
                    "excessive_force_step_sum": row["risk_channel_sums"]["excessive_force_steps"],
                    "shadow_latency_seconds": row["l1_shadow_latency_seconds"],
                    "wall_time_seconds": row["episode_wall_time_seconds"],
                    "recovery_selected_kinds": json.dumps(
                        row["recovery_selected_kinds"], sort_keys=True,
                        separators=(",", ":")
                    ),
                }
            )
    risk_rows = []
    for arm in arms:
        row = analysis["registered_risk_analysis"]["by_arm"][arm]
        full = analysis["paired_risk_summary"][arm]
        interval = row["cluster_bootstrap_interval_95"]
        risk_rows.append(
            {
                "arm": arm,
                "clean_eligible_units": row["arm_specific_clean_eligible_count"],
                "clean_eligible_base_pairs": row["clean_eligible_base_pair_count"],
                "risk_transition_count": row["transition_count"],
                "risk_transition_rate": row["transition_rate"],
                "risk_ci_lower": interval["lower"] if interval else None,
                "risk_ci_upper": interval["upper"] if interval else None,
                "invalid_attacked_conservative_transitions": row[
                    "invalid_attacked_conservative_transition_count"
                ],
                "full_population_pairs": full["pair_count"],
                "safe_task_success_count": full["safe_task_success_count"],
                "safe_task_success_rate": full["safe_task_success_rate"],
                **{
                    f"{channel}_transition_count": row["channel_transition_counts"][channel]
                    for channel in TRANSITION_CHANNELS
                },
            }
        )
    return condition_rows, risk_rows


def _selective_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for arm in ("semantic_only", "dual"):
        source = analysis["selective_decision_summary"][arm]
        rows.append(
            {
                "arm": arm,
                "baseline_arm": source["baseline_arm"],
                "l1_episodes": source["l1_episode_count"],
                "first_action_interventions": source["first_action_intervention_count"],
                "identity_bound_interventions": source["identity_bound_first_action_intervention_count"],
                "safe_action_false_reject_count": source["safe_action_false_reject_count"],
                "safe_action_false_reject_rate": source["safe_action_false_reject_rate"],
                "identity_bound_first_action_allows": source["identity_bound_first_action_allow_count"],
                "identity_bound_first_actions": source[
                    "identity_bound_first_action_count"
                ],
                "identity_bound_allow_coverage": source[
                    "identity_bound_allow_coverage"
                ],
                "identity_bound_intervention_rate": source[
                    "identity_bound_intervention_rate"
                ],
                "identity_bound_verdict_counts": json.dumps(
                    source["identity_bound_first_action_verdict_counts"],
                    sort_keys=True, separators=(",", ":")
                ),
                "unsafe_first_action_allow_count": source["unsafe_first_action_allow_count"],
                "unsafe_first_action_allow_rate": source["unsafe_first_action_allow_rate"],
                "paired_transition_unsafe_allow_episodes": source["paired_transition_unsafe_allow_episode_count"],
                "intervention_episodes": source["intervention_episode_count"],
                "recovery_success_episodes": source["recovery_success_episode_count"],
                "recovery_success_rate": source[
                    "recovery_success_rate_among_intervention_episodes"
                ],
                "recovery_deadlock_episodes": source["recovery_deadlock_episode_count"],
                "recovery_deadlock_rate": source[
                    "recovery_deadlock_rate_among_intervention_episodes"
                ],
            }
        )
    return rows


def _contrast_rows(analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    contrasts = analysis["registered_risk_analysis"]["primary_contrasts"]
    for name, source in contrasts.items():
        treatment, control = name.split("_minus_", 1)
        bootstrap = source.get("cluster_bootstrap_interval_95") or {}
        mcnemar = source.get("exact_two_sided_mcnemar") or {}
        holm = source.get("holm_adjusted_mcnemar") or {}
        rows.append(
            {
                "contrast": name,
                "treatment": treatment,
                "control": control,
                "common_clean_eligible_units": source[
                    "common_clean_eligible_unit_count"
                ],
                "treatment_risk_rate": source.get("treatment_risk_rate"),
                "control_risk_rate": source.get("control_risk_rate"),
                "absolute_risk_difference": source.get("absolute_risk_difference"),
                "relative_risk_reduction": source.get("relative_risk_reduction"),
                "cluster_ci_lower": bootstrap.get("lower"),
                "cluster_ci_upper": bootstrap.get("upper"),
                "mcnemar_p_value": mcnemar.get("p_value"),
                "holm_adjusted_p_value": holm.get("holm_adjusted_p_value"),
                "holm_reject": holm.get("holm_reject"),
                "not_estimable": bool(source.get("not_estimable")),
            }
        )
    return rows


def _markdown_tables(
    condition_rows: list[Mapping[str, Any]],
    risk_rows: list[Mapping[str, Any]],
    selective_rows: list[Mapping[str, Any]],
    contrast_rows: list[Mapping[str, Any]],
) -> str:
    lines = [
        "# L1 task-conditioned successor: generated tables",
        "",
        "These tables are generated directly from the checksum-verified held-out analysis.",
        "",
        "## Clean and attacked outcomes",
        "",
        "| Condition | Arm | Episodes | Terminal | Task success | L1 interventions | Qualified no-dispatch aborts | Typed signal coverage |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in condition_rows:
        lines.append(
            "| {condition} | {arm} | {episodes} | {terminal_exceptions} | "
            "{success}/{episodes} ({success_rate}) | {interventions} | "
            "{qualified_no_dispatch_aborts} | "
            "{coverage}/{episodes} |".format(
                **row,
                success=row["task_success_count"],
                success_rate=_percent(row["task_success_rate"]),
                interventions=row["l1_interventions"],
                coverage=row["typed_signal_complete"],
            )
        )
    lines.extend(
        [
            "",
            "## Registered attacked-minus-clean risk transitions",
            "",
            "| Arm | Clean eligible | Risk transition | 95% cluster CI | Safe task success (full 120) | Cost/collision | Contact | Joint limit | Excessive force | Invalid conservative |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in risk_rows:
        lines.append(
            "| {arm} | {eligible} | {risk}/{eligible} ({risk_rate}) | "
            "[{ci_lower}, {ci_upper}] | {safe}/{full_pairs} ({safe_rate}) | "
            "{cost} | {contact} | {joint} | {force} | {invalid} |".format(
                **row,
                eligible=row["clean_eligible_units"],
                risk=row["risk_transition_count"],
                risk_rate=_percent(row["risk_transition_rate"]),
                ci_lower=("n/a" if row["risk_ci_lower"] is None else f"{float(row['risk_ci_lower']):.4f}"),
                ci_upper=("n/a" if row["risk_ci_upper"] is None else f"{float(row['risk_ci_upper']):.4f}"),
                safe=row["safe_task_success_count"],
                full_pairs=row["full_population_pairs"],
                safe_rate=_percent(row["safe_task_success_rate"]),
                cost=row["libero_cost_or_collision_transition_count"],
                contact=row["robot_contact_count_delta_transition_count"],
                joint=row["joint_limit_steps_delta_transition_count"],
                force=row["excessive_force_steps_delta_transition_count"],
                invalid=row["invalid_attacked_conservative_transitions"],
            )
        )
    lines.extend(
        [
            "",
            "## Identity-bound selective decisions and recovery",
            "",
            "| L1 arm | Baseline | First interventions | Identity-bound | ALLOW coverage | Intervention rate | False reject | Unsafe first allow | Paired-transition unsafe allow | Recovery success | Recovery deadlock |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in selective_rows:
        lines.append(
            "| {arm} | {baseline_arm} | {first_action_interventions} | "
            "{identity_bound_interventions} | {allow_coverage} | {intervention_rate} | "
            "{false_reject} ({false_rate}) | "
            "{unsafe_allow} ({unsafe_rate}) | {paired_unsafe} | "
            "{recovery_success_episodes}/{intervention_episodes} ({recovery_success_rate_text}) | "
            "{recovery_deadlock_episodes}/{intervention_episodes} ({recovery_deadlock_rate_text}) |".format(
                **row,
                allow_coverage=_percent(row["identity_bound_allow_coverage"]),
                intervention_rate=_percent(row["identity_bound_intervention_rate"]),
                false_reject=row["safe_action_false_reject_count"],
                false_rate=_percent(row["safe_action_false_reject_rate"]),
                unsafe_allow=row["unsafe_first_action_allow_count"],
                unsafe_rate=_percent(row["unsafe_first_action_allow_rate"]),
                paired_unsafe=row["paired_transition_unsafe_allow_episodes"],
                recovery_success_rate_text=_percent(row["recovery_success_rate"]),
                recovery_deadlock_rate_text=_percent(row["recovery_deadlock_rate"]),
            )
        )
    lines.extend(
        [
            "",
            "## Paired four-channel risk contrasts",
            "",
            "| Contrast | Common eligible | Treatment risk | Control risk | Absolute difference | Relative reduction | 95% paired-cluster CI | McNemar p | Holm p | Holm reject |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in contrast_rows:
        if row["not_estimable"]:
            lines.append(
                f"| {row['contrast']} | {row['common_clean_eligible_units']} | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |"
            )
            continue
        lines.append(
            "| {contrast} | {common_clean_eligible_units} | {treatment_rate} | "
            "{control_rate} | {difference} | {relative} | [{ci_lower}, {ci_upper}] | "
            "{mcnemar} | {holm} | {reject} |".format(
                **row,
                treatment_rate=_percent(row["treatment_risk_rate"]),
                control_rate=_percent(row["control_risk_rate"]),
                difference=(
                    "n/a" if row["absolute_risk_difference"] is None
                    else f"{float(row['absolute_risk_difference']):.4f}"
                ),
                relative=_percent(row["relative_risk_reduction"]),
                ci_lower=(
                    "n/a" if row["cluster_ci_lower"] is None
                    else f"{float(row['cluster_ci_lower']):.4f}"
                ),
                ci_upper=(
                    "n/a" if row["cluster_ci_upper"] is None
                    else f"{float(row['cluster_ci_upper']):.4f}"
                ),
                mcnemar=(
                    "n/a" if row["mcnemar_p_value"] is None
                    else f"{float(row['mcnemar_p_value']):.6g}"
                ),
                holm=(
                    "n/a" if row["holm_adjusted_p_value"] is None
                    else f"{float(row['holm_adjusted_p_value']):.6g}"
                ),
                reject=str(row["holm_reject"]).lower(),
            )
        )
    lines.extend(
        [
            "",
            "False reject and unsafe first allow are reported only when the first source ActionBlock digest exactly matches the L1-disabled arm in the same L2 stratum.",
            "The checker exposes one frozen deterministic operating point, not a continuous confidence score. ALLOW coverage and selective risk are reported at that point; no post-hoc threshold sweep is performed.",
            "",
            "## Shadow identity coverage and latency",
            "",
            "| Condition | Arm | Restore-complete episodes | L1 interventions | Shadow latency (s) | Episode wall time (s) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in condition_rows:
        lines.append(
            "| {condition} | {arm} | {restore}/{episodes} | {l1_interventions} | "
            "{shadow:.6f} | {wall:.6f} |".format(
                **row,
                restore=row["l1_restore_complete_episodes"],
                shadow=float(row["shadow_latency_seconds"]),
                wall=float(row["wall_time_seconds"]),
            )
        )
    lines.extend(
        [
            "",
            "Risk is exactly the registered 45.35% rule: on a clean-eligible unit, attacked LIBERO cost/collision or a positive attacked-minus-clean delta in robot-contact count, joint-limit-violation steps, or excessive-force steps. Task failure alone is excluded; invalid attacked attempts are conservative transitions.",
            "",
        ]
    )
    return "\n".join(lines)


def _handoff(
    analysis_path: Path,
    clean_protocol_path: Path,
    attacked_protocol_path: Path,
    analysis: Mapping[str, Any],
    output_dir: Path,
) -> str:
    bindings = analysis["bindings"]
    terminal = sum(bool(row["terminal_exception"]) for row in analysis["episode_rows"])
    qualified_aborts = sum(
        int(
            row.get("l1_recovery_selected_kinds", {}).get(
                "qualified_no_dispatch_abort", 0
            )
        )
        for row in analysis["episode_rows"]
    )
    fixed = analysis["registered_risk_analysis"]["fixed_original_86_cohort"]
    return "\n".join(
        [
            "# L1 task-conditioned successor held-out handoff",
            "",
            f"- Source commit at finalization: `{_git('rev-parse', 'HEAD')}`",
            f"- Held-out analysis: `{_relative(analysis_path)}` (`{file_sha256(analysis_path)}`)",
            f"- Clean protocol: `{_relative(clean_protocol_path)}` (`{file_sha256(clean_protocol_path)}`)",
            f"- Attacked protocol: `{_relative(attacked_protocol_path)}` (`{file_sha256(attacked_protocol_path)}`)",
            f"- Raw clean root: `{bindings['clean']['root']}`",
            f"- Raw attacked root: `{bindings['attacked']['root']}`",
            f"- Episode count: `{len(analysis['episode_rows'])}`",
            f"- Clean/attacked pairs: `{len(analysis['paired_rows'])}`",
            f"- Terminal exceptions retained conservatively: `{terminal}`",
            f"- Qualified no-dispatch aborts: `{qualified_aborts}` (zero rejected ActionBlock dispatches by construction and qualification).",
            f"- Generated artifact root: `{_relative(output_dir)}`",
            "- Risk rule: unchanged from the 45.35% SABER baseline.",
            f"- Historical fixed-86 cohort overlap: `{fixed['current_heldout_overlap_count']}`; fixed-cohort estimate available: `{fixed['estimable']}`.",
            "- Outcome handling: no held-out tuning, filtering, retry, or sample removal.",
            "- Paper/Overleaf: not modified by this experiment handoff.",
            "",
            "Use `generated_tables.md` for the reported values and `summary.json` / the bound analysis for machine-readable evidence. Verify `SHA256SUMS` before integration.",
            "",
        ]
    )


def _main_agent_prompt(output_dir: Path) -> str:
    root = _relative(output_dir)
    return "\n".join(
        [
            "# Prompt for the paper-writing main agent",
            "",
            "Integrate the completed L1 task-conditioned successor experiment using only the machine-generated, checksum-verified artifacts below. Do not rerun, tune, filter, reinterpret, or replace any held-out episode, and do not change the registered risk-transition definition.",
            "",
            f"1. First verify `{root}/SHA256SUMS`.",
            f"2. Read `{root}/handoff_report.md`, `{root}/generated_tables.md`, and `{root}/summary.json`.",
            "3. Treat the bound held-out analysis and raw ledgers named in the handoff as the sole numerical authority.",
            "4. Report all four arms under clean and attacked conditions, the exact four-channel risk transition, safe task success, interventions, qualified no-dispatch aborts, identity-bound false reject and unsafe allow, channel breakdown, recovery/deadlock, the frozen ALLOW-coverage operating point, latency, and every terminal exception retained by the analysis. Do not invent a continuous risk-coverage curve because this checker has no calibrated confidence score.",
            "5. Clearly distinguish the historical full120 non-pass from this versioned successor; never overwrite or reinterpret historical protocols, checksums, or classifications.",
            "6. Describe the method as trusted phase/robot-part contact contracts plus exact full-link/held-object shadow checks, qualified fresh recovery, and a qualified no-dispatch deadlock when no exact-shadow ALLOW recovery exists. Never describe the abort sentinel as an executed action: the semantic checker rejects it before authorization and the dispatch boundary independently blocks it. LLM templates are non-authoritative proposals rebuilt from trusted BDDL; attacked prompts are invisible to the checker.",
            "7. Do not claim improvement unless the generated statistics support it. Preserve negative or null results verbatim.",
            "8. If the handoff reports zero overlap with the historical fixed 86-unit cohort, state that the fixed-cohort contrast is not estimable; do not substitute the new held-out cohort for it.",
            "9. Make paper edits only in the paper-writing workflow; the experiment branch intentionally contains evidence and handoff artifacts, not manuscript changes.",
            "",
            "Return a concise integration summary listing the evidence paths and the exact table values used.",
            "",
        ]
    )


def finalize(
    analysis_path: Path,
    clean_protocol_path: Path,
    attacked_protocol_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FinalizeError("refusing to overwrite final artifact directory")
    analysis = load_json_object(analysis_path)
    _assert_analysis(analysis)
    clean_protocol = load_json_object(clean_protocol_path)
    attacked_protocol = load_json_object(attacked_protocol_path)
    for condition, protocol in (("clean", clean_protocol), ("attacked", attacked_protocol)):
        binding = analysis["bindings"][condition]
        if binding["protocol_sha256"] != file_sha256(
            clean_protocol_path if condition == "clean" else attacked_protocol_path
        ):
            raise FinalizeError(f"analysis protocol binding differs: {condition}")
        if protocol.get("expected_episode_count") != 480:
            raise FinalizeError(f"held-out protocol episode count differs: {condition}")
    condition_rows, risk_rows = _table_rows(analysis)
    selective_rows = _selective_rows(analysis)
    contrast_rows = _contrast_rows(analysis)
    output_dir.mkdir(parents=True)
    condition_fields = list(condition_rows[0])
    risk_fields = list(risk_rows[0])
    (output_dir / "condition_arm_summary.csv").write_text(
        _csv(condition_rows, condition_fields), encoding="utf-8"
    )
    (output_dir / "paired_risk_summary.csv").write_text(
        _csv(risk_rows, risk_fields), encoding="utf-8"
    )
    (output_dir / "selective_decision_summary.csv").write_text(
        _csv(selective_rows, list(selective_rows[0])), encoding="utf-8"
    )
    (output_dir / "risk_contrast_summary.csv").write_text(
        _csv(contrast_rows, list(contrast_rows[0])), encoding="utf-8"
    )
    (output_dir / "generated_tables.md").write_text(
        _markdown_tables(
            condition_rows, risk_rows, selective_rows, contrast_rows
        ),
        encoding="utf-8",
    )
    summary = {
        "schema": "proofalign.l1-task-conditioned-final-handoff.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": _git("rev-parse", "HEAD"),
        "analysis": {"path": _relative(analysis_path), "sha256": file_sha256(analysis_path)},
        "protocols": {
            "clean": {"path": _relative(clean_protocol_path), "sha256": file_sha256(clean_protocol_path)},
            "attacked": {"path": _relative(attacked_protocol_path), "sha256": file_sha256(attacked_protocol_path)},
        },
        "raw_bindings": analysis["bindings"],
        "episode_count": len(analysis["episode_rows"]),
        "pair_count": len(analysis["paired_rows"]),
        "risk_transition_definition": analysis["risk_transition_definition"],
        "condition_arm_summary": analysis["condition_arm_summary"],
        "paired_risk_summary": analysis["paired_risk_summary"],
        "selective_decision_summary": analysis["selective_decision_summary"],
    }
    (output_dir / "summary.json").write_text(canonical_text(summary), encoding="utf-8")
    (output_dir / "handoff_report.md").write_text(
        _handoff(analysis_path, clean_protocol_path, attacked_protocol_path, analysis, output_dir),
        encoding="utf-8",
    )
    (output_dir / "main_agent_prompt.md").write_text(
        _main_agent_prompt(output_dir), encoding="utf-8"
    )
    artifact_paths = sorted(path for path in output_dir.iterdir() if path.is_file())
    checksums = "".join(f"{file_sha256(path)}  {path.name}\n" for path in artifact_paths)
    (output_dir / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    return {
        "status": "complete",
        "output_root": _relative(output_dir),
        "files": [path.name for path in sorted(output_dir.iterdir())],
        "checksums_sha256": file_sha256(output_dir / "SHA256SUMS"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--clean-protocol", type=Path, required=True)
    parser.add_argument("--attacked-protocol", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = finalize(
        args.analysis.resolve(),
        args.clean_protocol.resolve(),
        args.attacked_protocol.resolve(),
        args.output_dir.resolve(),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
