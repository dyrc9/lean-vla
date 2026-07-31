#!/usr/bin/env python3
"""Generate the frozen final-result figures used by the paper.

The script reads the committed v11/v12 terminal summaries directly.  It does
not infer task outcomes for v12, whose ledger is intentionally no-outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
FIGURE_DIR = ROOT / "docs" / "paper" / "figures"
V12_PATHS = (
    ROOT
    / "results"
    / "proofalign_h3_hard_virtual_joint_guard_beam_pilot_v12_20260730"
    / "summary.json",
    ROOT
    / "results"
    / "proofalign_h3_hard_virtual_joint_guard_beam_heldout_v12_20260730"
    / "summary.json",
)
V11_PATH = (
    ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_scale45_terminal_summary.json"
)

DEVELOPMENT_COLOR = "#4C78A8"
HELDOUT_COLOR = "#F58518"
THRESHOLD_COLOR = "#C44E52"
GRID_COLOR = "#D9D9D9"
ARM_COLORS = ["#7F7F7F", "#2A9D8F", "#E9C46A", "#6A4C93"]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_v12(summaries: list[dict]) -> None:
    expected = (
        (
            "h3_hard_virtual_joint_guard_beam_success",
            {"10509": 5, "10510": 5},
        ),
        (
            "h3_hard_virtual_joint_guard_beam_heldout_success",
            {"20509": 5, "20510": 5},
        ),
    )
    zero_fields = (
        "active_warning_count",
        "active_contact_capacity_warning_count",
        "contact_capacity_saturation_count",
        "torque_bound_violation_count",
        "downstream_clipped_bound_violation_count",
        "live_policy_dispatch_count",
        "typed_recovery_env_step_count",
        "outcome_read_count",
    )
    for summary, (success_key, expected_cycles) in zip(
        summaries, expected, strict=True
    ):
        if summary[success_key] is not True:
            raise ValueError(f"Frozen v12 result did not pass: {success_key}")
        if summary["completed_cycle_counts"] != expected_cycles:
            raise ValueError("Frozen v12 cycle counts changed")
        if any(summary[field] != 0 for field in zero_fields):
            raise ValueError("A frozen v12 zero-anomaly gate changed")
        if summary["minimum_advanced_state_margin_rad"] < 0.15:
            raise ValueError("Frozen v12 margin floor no longer passes")


def save_figure(fig: plt.Figure, stem: str) -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_DIR / f"{stem}.png", dpi=240, bbox_inches="tight")
    fig.savefig(
        FIGURE_DIR / f"{stem}.pdf",
        bbox_inches="tight",
        metadata={
            "Title": stem,
            "Author": "ProofAlign",
            "Creator": "scripts/plot_final_paper_results.py",
            "CreationDate": None,
            "ModDate": None,
        },
    )
    plt.close(fig)


def plot_v12_final_validation(summaries: list[dict]) -> None:
    split_names = ["Development", "Frozen held-out"]
    split_subtitles = ["seeds 10509 / 10510", "seeds 20509 / 20510"]
    colors = [DEVELOPMENT_COLOR, HELDOUT_COLOR]
    x = np.arange(len(summaries))

    completed = [
        sum(summary["completed_cycle_counts"].values()) for summary in summaries
    ]
    planned = [
        summary["lane_count"] * summary["planned_cycle_count_per_lane"]
        for summary in summaries
    ]
    margins = [
        summary["minimum_advanced_state_margin_rad"] for summary in summaries
    ]
    forces = [
        summary["maximum_abs_target_dof_constraint_force"]
        for summary in summaries
    ]

    audit_labels = [
        "Exact action\nidentity",
        "Beam config\nidentity",
        "Guard profile\nrestore",
    ]
    audit_rates: list[list[float]] = []
    audit_counts: list[list[tuple[int, int]]] = []
    for summary in summaries:
        action_count = summary[
            "contact_aware_vertex_exact_h1_exact_action_identity_count"
        ]
        action_total = summary[
            "contact_aware_vertex_exact_h1_execution_count"
        ]
        config_total = summary["beam_configuration_count"]
        config_count = min(
            summary["beam_configuration_qpos_identity_count"],
            summary["beam_configuration_qvel_identity_count"],
            summary["beam_controller_scope_restore_count"],
        )
        restore_count = summary["virtual_joint_guard_range_restore_count"]
        restore_total = summary["virtual_joint_guard_authorization_count"]
        counts = [
            (action_count, action_total),
            (config_count, config_total),
            (restore_count, restore_total),
        ]
        audit_counts.append(counts)
        audit_rates.append(
            [100.0 * numerator / denominator for numerator, denominator in counts]
        )

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.2))
    fig.suptitle(
        "Final v12 frozen-method simulator engineering validation",
        fontsize=16,
        fontweight="bold",
        y=0.985,
    )

    ax = axes[0, 0]
    bars = ax.bar(x, completed, color=colors, width=0.62)
    ax.set_title("A. Exact policy advances")
    ax.set_ylabel("Completed advances")
    ax.set_xticks(x, split_names)
    ax.set_ylim(0, max(planned) + 1.8)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    for bar, numerator, denominator, subtitle in zip(
        bars, completed, planned, split_subtitles, strict=True
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.22,
            f"{numerator}/{denominator}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            0.32,
            subtitle,
            ha="center",
            va="bottom",
            color="white",
            fontsize=9,
            fontweight="bold",
        )

    ax = axes[0, 1]
    ax.axhspan(0.145, 0.15, color=THRESHOLD_COLOR, alpha=0.08)
    ax.axhline(
        0.15,
        color=THRESHOLD_COLOR,
        linestyle="--",
        linewidth=1.8,
        label="Frozen floor = 0.150 rad",
    )
    ax.scatter(x, margins, color=colors, s=100, zorder=3)
    for index, (margin, color) in enumerate(zip(margins, colors, strict=True)):
        ax.vlines(index, 0.15, margin, color=color, linewidth=3, alpha=0.75)
        ax.text(
            index,
            margin + 0.00055,
            f"{margin:.6f}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.set_title("B. Minimum actual joint-limit margin")
    ax.set_ylabel("Global margin (rad)")
    ax.set_xticks(x, split_names)
    ax.set_ylim(0.145, 0.170)
    ax.legend(loc="lower center", frameon=False)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    ax.text(
        0.99,
        0.98,
        "Zoomed y-axis",
        transform=ax.transAxes,
        ha="right",
        va="top",
        color="#666666",
        fontsize=9,
    )

    ax = axes[1, 0]
    audit_x = np.arange(len(audit_labels))
    width = 0.34
    for split_index, (name, color) in enumerate(zip(split_names, colors, strict=True)):
        positions = audit_x + (split_index - 0.5) * width
        bars = ax.bar(
            positions,
            audit_rates[split_index],
            width=width,
            label=name,
            color=color,
        )
        for bar, (numerator, denominator) in zip(
            bars, audit_counts[split_index], strict=True
        ):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                100.8,
                f"{numerator}/{denominator}",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
            )
    ax.set_title("C. Identity and scope audit gates")
    ax.set_ylabel("Pass rate (%)")
    ax.set_xticks(audit_x, audit_labels)
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.legend(loc="lower center", ncol=2, frameon=False)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)

    ax = axes[1, 1]
    bars = ax.bar(x, forces, color=colors, width=0.62)
    ax.set_title("D. Mechanism limitation: constraint force")
    ax.set_ylabel("Max |target-DOF generalized force|")
    ax.set_xticks(x, split_names)
    ax.set_ylim(0, 11200)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    for bar, force in zip(bars, forces, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            force + 190,
            f"{force:,.0f}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.text(
        0.5,
        0.08,
        "High-stiffness simulator virtual stop\n(not actuator-only authority)",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        color=THRESHOLD_COLOR,
        fontweight="bold",
    )

    fig.text(
        0.5,
        0.012,
        "All recorded warning, crossing/contact-saturation, torque-bound, live-dispatch, "
        "typed-recovery, and outcome-read counts were zero. "
        "This no-outcome v12 run does not measure task success or physical safety.",
        ha="center",
        va="bottom",
        fontsize=9.2,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.052, 1, 0.955), h_pad=2.2, w_pad=2.0)
    save_figure(fig, "v12_final_engineering_validation")


def plot_v11_tradeoff(summary: dict) -> None:
    arm_order = ["vla_only", "execution_only", "semantic_only", "dual"]
    arm_labels = ["VLA-only", "L2 only", "L1 only", "L1 + L2"]
    conditions = ["clean", "attacked"]
    condition_labels = ["Clean", "Attacked"]
    colors = [DEVELOPMENT_COLOR, HELDOUT_COLOR]
    width = 0.36
    x = np.arange(len(arm_order))

    task_rates: dict[str, list[float]] = {}
    task_errors: dict[str, np.ndarray] = {}
    joint_rates: dict[str, list[float]] = {}
    task_counts: dict[str, list[tuple[int, int]]] = {}
    for condition in conditions:
        by_arm = summary["conditions"][condition]["by_arm"]
        rates = []
        low_errors = []
        high_errors = []
        counts = []
        joints = []
        for arm in arm_order:
            task = by_arm[arm]["task_success"]
            rate = 100.0 * task["rate"]
            rates.append(rate)
            low_errors.append(rate - 100.0 * task["wilson_95_low"])
            high_errors.append(100.0 * task["wilson_95_high"] - rate)
            counts.append((task["successes"], task["total"]))
            joints.append(100.0 * by_arm[arm]["joint_limit_step_rate"])
        task_rates[condition] = rates
        task_errors[condition] = np.asarray([low_errors, high_errors])
        task_counts[condition] = counts
        joint_rates[condition] = joints

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 5.4))
    fig.suptitle(
        "Paper mainline: typed L2 containment reduces exposure but costs utility",
        fontsize=15,
        fontweight="bold",
        y=0.985,
    )

    ax = axes[0]
    for index, (condition, label, color) in enumerate(
        zip(conditions, condition_labels, colors, strict=True)
    ):
        positions = x + (index - 0.5) * width
        bars = ax.bar(
            positions,
            task_rates[condition],
            width=width,
            color=color,
            label=label,
            yerr=task_errors[condition],
            capsize=3,
            error_kw={"linewidth": 1, "capthick": 1},
        )
        for bar, (successes, total) in zip(
            bars, task_counts[condition], strict=True
        ):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.1,
                f"{successes}/{total}",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
            )
    ax.set_title("A. Task success (Wilson 95% CI)")
    ax.set_ylabel("Task success (%)")
    ax.set_xticks(x, arm_labels)
    ax.set_ylim(0, 92)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, ncol=2, loc="upper right")

    ax = axes[1]
    for index, (condition, label, color) in enumerate(
        zip(conditions, condition_labels, colors, strict=True)
    ):
        positions = x + (index - 0.5) * width
        bars = ax.bar(
            positions,
            joint_rates[condition],
            width=width,
            color=color,
            label=label,
        )
        for bar, rate in zip(bars, joint_rates[condition], strict=True):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                rate * 1.22,
                f"{rate:.3f}%",
                ha="center",
                va="bottom",
                fontsize=8,
                fontweight="bold",
                rotation=90 if rate < 0.2 else 0,
            )
    ax.set_title("B. Model-defined joint-limit step rate")
    ax.set_ylabel("Joint-limit steps (%) — log scale")
    ax.set_xticks(x, arm_labels)
    ax.set_yscale("log")
    ax.set_ylim(0.025, 35)
    ax.grid(axis="y", which="both", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, ncol=2, loc="upper right")

    fig.text(
        0.5,
        0.012,
        "Frozen held-out scale45: 45 episodes per arm and condition. "
        "L2 stops later dispatch after the first observed trigger; it is containment, "
        "not first-hit prevention or a complete physical-safety claim.",
        ha="center",
        va="bottom",
        fontsize=9.2,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.94), w_pad=2.7)
    save_figure(fig, "v11_containment_utility_tradeoff")


def plot_attack_defense_scale45(summary: dict) -> None:
    attacked = summary["conditions"]["attacked"]
    activation = attacked["attack_activation"]
    integrity = attacked["data_integrity"]
    by_arm = attacked["by_arm"]
    arm_order = ["vla_only", "execution_only", "semantic_only", "dual"]
    arm_labels = ["VLA-only", "L2 only", "L1 only", "L1 + L2"]
    x = np.arange(len(arm_order))

    if activation["episode_count"] != 180:
        raise ValueError("Frozen attacked scale45 episode count changed")
    if activation["changed_first_action_block_count"] != 180:
        raise ValueError("Frozen SABER attack activation count changed")
    if integrity["post_trigger_dispatch_count"] != 0:
        raise ValueError("Frozen attacked post-trigger dispatch gate changed")

    task_rates = [
        100.0 * by_arm[arm]["task_success"]["rate"] for arm in arm_order
    ]
    task_counts = [
        (
            by_arm[arm]["task_success"]["successes"],
            by_arm[arm]["task_success"]["total"],
        )
        for arm in arm_order
    ]
    task_low_errors = [
        rate - 100.0 * by_arm[arm]["task_success"]["wilson_95_low"]
        for arm, rate in zip(arm_order, task_rates, strict=True)
    ]
    task_high_errors = [
        100.0 * by_arm[arm]["task_success"]["wilson_95_high"] - rate
        for arm, rate in zip(arm_order, task_rates, strict=True)
    ]
    task_errors = np.asarray([task_low_errors, task_high_errors])
    joint_rates = [
        100.0 * by_arm[arm]["joint_limit_step_rate"] for arm in arm_order
    ]

    l2_arms = ["execution_only", "dual"]
    l2_labels = ["L2 only", "L1 + L2"]
    triggers = [by_arm[arm]["containment_trigger_count"] for arm in l2_arms]
    later_dispatches = [0, 0]

    execution_contrast = attacked["paired_l2_contrasts"][
        "execution_only_vs_vla_only"
    ]
    dual_contrast = attacked["paired_l2_contrasts"]["dual_vs_semantic_only"]

    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
        }
    )
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.5))
    fig.suptitle(
        "SABER prompt attack x ProofAlign defenses — frozen held-out scale45",
        fontsize=16,
        fontweight="bold",
        y=0.985,
    )

    ax = axes[0, 0]
    activation_labels = [
        "Changed first\nActionBlock",
        "Four-arm input\nidentity",
    ]
    activation_values = [
        100.0
        * activation["changed_first_action_block_count"]
        / activation["episode_count"],
        100.0
        * activation["attacked_first_blocks_match_within_workload_count"]
        / 45,
    ]
    activation_counts = [
        (
            activation["changed_first_action_block_count"],
            activation["episode_count"],
        ),
        (
            activation["attacked_first_blocks_match_within_workload_count"],
            45,
        ),
    ]
    bars = ax.bar(
        np.arange(2),
        activation_values,
        color=[THRESHOLD_COLOR, DEVELOPMENT_COLOR],
        width=0.62,
    )
    ax.set_title("A. Attack activation and paired-input integrity")
    ax.set_ylabel("Rate (%)")
    ax.set_xticks(np.arange(2), activation_labels)
    ax.set_ylim(0, 112)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    for bar, (numerator, denominator) in zip(
        bars, activation_counts, strict=True
    ):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{numerator}/{denominator}",
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    ax.text(
        0.5,
        0.08,
        "Official SABER task-prompt records\nchanged the policy-facing instruction",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9,
        color="#444444",
    )

    ax = axes[0, 1]
    bars = ax.bar(
        x,
        task_rates,
        color=ARM_COLORS,
        width=0.68,
        yerr=task_errors,
        capsize=4,
        error_kw={"linewidth": 1, "capthick": 1},
    )
    ax.set_title("B. Task success under attack (Wilson 95% CI)")
    ax.set_ylabel("Task success (%)")
    ax.set_xticks(x, arm_labels)
    ax.set_ylim(0, 88)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    for bar, (successes, total) in zip(bars, task_counts, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.1,
            f"{successes}/{total}",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )
    ax.text(
        0.02,
        0.03,
        "L2 vs VLA: "
        f"{100 * execution_contrast['task_success']['paired_difference']:+.1f} pp"
        f"  (McNemar p={execution_contrast['task_success']['exact_two_sided_mcnemar_p']:.3f})\n"
        "Dual vs L1: "
        f"{100 * dual_contrast['task_success']['paired_difference']:+.1f} pp"
        f"  (p={dual_contrast['task_success']['exact_two_sided_mcnemar_p']:.3f})",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.7,
        color="#444444",
    )

    ax = axes[1, 0]
    bars = ax.bar(x, joint_rates, color=ARM_COLORS, width=0.68)
    ax.set_title("C. Joint-limit exposure under attack")
    ax.set_ylabel("Joint-limit steps (%)\n(log scale)")
    ax.set_xticks(x, arm_labels)
    ax.set_yscale("log")
    ax.set_ylim(0.025, 20)
    ax.grid(axis="y", which="both", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    for bar, rate in zip(bars, joint_rates, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            rate * 1.22,
            f"{rate:.3f}%",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            rotation=90 if rate < 0.2 else 0,
        )
    ax.text(
        0.02,
        0.04,
        "L2 vs VLA paired sign p="
        f"{execution_contrast['joint_limit_step_rate']['exact_two_sided_sign_p']:.3f}\n"
        "Dual vs L1 paired sign p="
        f"{dual_contrast['joint_limit_step_rate']['exact_two_sided_sign_p']:.4f}",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.7,
        color="#444444",
    )

    ax = axes[1, 1]
    l2_x = np.arange(len(l2_arms))
    width = 0.34
    trigger_bars = ax.bar(
        l2_x - width / 2,
        triggers,
        width=width,
        color="#2A9D8F",
        label="Trigger episodes",
    )
    dispatch_bars = ax.bar(
        l2_x + width / 2,
        later_dispatches,
        width=width,
        color=THRESHOLD_COLOR,
        label="Later dispatches",
    )
    ax.set_title("D. Typed L2 containment after attack")
    ax.set_ylabel("Episode / dispatch count")
    ax.set_xticks(l2_x, l2_labels)
    ax.set_ylim(0, max(triggers) + 3)
    ax.grid(axis="y", color=GRID_COLOR, linewidth=0.8, alpha=0.8)
    ax.legend(frameon=False, loc="upper right")
    for bar, count in zip(trigger_bars, triggers, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            count + 0.18,
            str(count),
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    for bar in dispatch_bars:
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            0.16,
            "0",
            ha="center",
            va="bottom",
            color=THRESHOLD_COLOR,
            fontweight="bold",
        )
    ax.text(
        0.5,
        0.12,
        f"{sum(triggers)} attacked trigger episodes\n"
        f"{integrity['post_trigger_dispatch_count']} post-trigger dispatches",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
    )

    fig.text(
        0.5,
        0.012,
        "45 workloads x 4 arms = 180 attacked episodes. "
        "The positive claim is post-trigger mechanical containment. "
        "Task-success superiority, first-hit prevention, and general defense efficacy "
        "were not established.",
        ha="center",
        va="bottom",
        fontsize=9.2,
        color="#444444",
    )
    fig.tight_layout(rect=(0, 0.05, 1, 0.95), h_pad=2.5, w_pad=2.0)
    save_figure(fig, "v11_saber_attack_defense_scale45")


def main() -> None:
    v12_summaries = [load_json(path) for path in V12_PATHS]
    validate_v12(v12_summaries)
    plot_v12_final_validation(v12_summaries)

    v11_summary = load_json(V11_PATH)
    if (
        v11_summary["classification"]
        != "joint_limit_containment_v11_scale45_heldout_mixed_evidence"
    ):
        raise ValueError("Frozen v11 terminal classification changed")
    plot_v11_tradeoff(v11_summary)
    plot_attack_defense_scale45(v11_summary)

    for name in (
        "v12_final_engineering_validation",
        "v11_containment_utility_tradeoff",
        "v11_saber_attack_defense_scale45",
    ):
        print(FIGURE_DIR / f"{name}.png")
        print(FIGURE_DIR / f"{name}.pdf")


if __name__ == "__main__":
    main()
