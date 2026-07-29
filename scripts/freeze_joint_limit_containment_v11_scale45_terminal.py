#!/usr/bin/env python3
"""Build the held-out clean/attacked scale45 terminal analysis."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts.freeze_joint_limit_containment_v11_terminal import (  # noqa: E402
    _exact_two_sided_binomial_p,
    _wilson,
)


SCHEMA = (
    "proofalign.joint-limit-containment-v11-scale45-terminal-summary.v1"
)
CONDITIONS = {
    "clean": (
        REPO_ROOT
        / "results"
        / "proofalign_joint_limit_containment_v11_clean_"
        "scale45_20260729_fresh1"
    ),
    "attacked": (
        REPO_ROOT
        / "results"
        / "proofalign_joint_limit_containment_v11_attacked_"
        "scale45_20260730_fresh1"
    ),
}
EXPECTED_CLASSIFICATIONS = {
    "clean": (
        "joint_limit_containment_v11_clean_scale45_data_complete"
    ),
    "attacked": (
        "joint_limit_containment_v11_attacked_scale45_data_complete"
    ),
}
ARM_ORDER = (
    "vla_only",
    "semantic_only",
    "execution_only",
    "dual",
)
PAIRED_L2_CONTRASTS = (
    ("execution_only", "vla_only"),
    ("dual", "semantic_only"),
)
EXPECTED_EPISODES = 180
EXPECTED_PAIRS = 45
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_"
    "scale45_terminal_summary.json"
)


class JointLimitScale45TerminalError(RuntimeError):
    """Raised when scale45 terminal evidence is inconsistent."""


def _load_rows(
    condition: str,
) -> tuple[Mapping[str, Any], list[dict[str, Any]]]:
    root = CONDITIONS[condition]
    evidence_path = root / "pilot_evidence.json"
    evidence = load_json_object(evidence_path)
    if (
        evidence.get("classification")
        != EXPECTED_CLASSIFICATIONS[condition]
        or evidence.get("pilot_complete") is not True
    ):
        raise JointLimitScale45TerminalError(
            f"{condition} scale45 evidence is not terminal-complete"
        )
    per_episode = {
        str(row["episode_id"]): row
        for row in evidence["per_episode"]
    }
    rows = []
    for artifact in evidence["episodes"]:
        episode_id = str(artifact["episode_id"])
        path = REPO_ROOT / str(artifact["path"])
        if (
            episode_id not in per_episode
            or not path.is_file()
            or file_sha256(path) != artifact["sha256"]
        ):
            raise JointLimitScale45TerminalError(
                f"{condition} episode binding differs: {episode_id}"
            )
        episode = load_json_object(path)
        policy_rows = [
            row
            for row in episode["trace"]
            if row.get("phase") == "policy"
        ]
        joint_limit_steps = sum(
            bool(
                row.get("saber_constraint_signals", {}).get(
                    "joint_limit_violation"
                )
            )
            for row in policy_rows
        )
        containment_rows = [
            row["joint_limit_containment"]
            for row in policy_rows
            if isinstance(
                row.get("joint_limit_containment"), Mapping
            )
        ]
        trigger_count = sum(
            bool(row.get("halt_before_next_dispatch"))
            for row in containment_rows
        )
        row = per_episode[episode_id]
        rows.append(
            {
                "condition": condition,
                "episode_id": episode_id,
                "base_pair_id": str(row["base_pair_id"]),
                "arm": str(row["arm"]),
                "task_success": bool(episode["task_success"]),
                "unsafe_cost_or_collision": bool(
                    episode["unsafe_cost_or_collision"]
                ),
                "decision": str(episode["decision"]),
                "policy_step_count": len(policy_rows),
                "joint_limit_step_count": joint_limit_steps,
                "joint_limit_episode": bool(joint_limit_steps),
                "containment_trigger_count": trigger_count,
                "observer_step_count": len(containment_rows),
            }
        )
    if len(rows) != EXPECTED_EPISODES:
        raise JointLimitScale45TerminalError(
            f"{condition} does not contain 180 episodes"
        )
    if Counter(row["arm"] for row in rows) != {
        arm: EXPECTED_PAIRS for arm in ARM_ORDER
    }:
        raise JointLimitScale45TerminalError(
            f"{condition} arm balance differs"
        )
    return evidence, rows


def _arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for arm in ARM_ORDER:
        selected = [row for row in rows if row["arm"] == arm]
        successes = sum(row["task_success"] for row in selected)
        policy_steps = sum(
            row["policy_step_count"] for row in selected
        )
        joint_limit_steps = sum(
            row["joint_limit_step_count"] for row in selected
        )
        result[arm] = {
            "task_success": _wilson(successes, len(selected)),
            "policy_step_count": policy_steps,
            "joint_limit_step_count": joint_limit_steps,
            "joint_limit_step_rate": (
                joint_limit_steps / policy_steps
            ),
            "joint_limit_episode_count": sum(
                row["joint_limit_episode"] for row in selected
            ),
            "containment_trigger_count": sum(
                row["containment_trigger_count"]
                for row in selected
            ),
            "unsafe_cost_or_collision_count": sum(
                row["unsafe_cost_or_collision"]
                for row in selected
            ),
            "decision_counts": dict(
                sorted(
                    Counter(
                        row["decision"] for row in selected
                    ).items()
                )
            ),
        }
    return result


def _paired_summary(
    rows: list[dict[str, Any]],
    treatment: str,
    control: str,
) -> dict[str, Any]:
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        pairs.setdefault(row["base_pair_id"], {})[
            row["arm"]
        ] = row
    if (
        len(pairs) != EXPECTED_PAIRS
        or any(
            set(arms) != set(ARM_ORDER)
            for arms in pairs.values()
        )
    ):
        raise JointLimitScale45TerminalError(
            "paired scale45 arm population differs"
        )
    both_success = treatment_only = control_only = both_fail = 0
    lower = higher = equal = 0
    rate_differences = []
    treatment_trigger_control_success = 0
    for arms in pairs.values():
        treated = arms[treatment]
        reference = arms[control]
        t_success = treated["task_success"]
        c_success = reference["task_success"]
        both_success += int(t_success and c_success)
        treatment_only += int(t_success and not c_success)
        control_only += int(not t_success and c_success)
        both_fail += int(not t_success and not c_success)
        difference = (
            treated["joint_limit_step_count"]
            / treated["policy_step_count"]
            - reference["joint_limit_step_count"]
            / reference["policy_step_count"]
        )
        rate_differences.append(difference)
        lower += int(difference < 0)
        higher += int(difference > 0)
        equal += int(difference == 0)
        treatment_trigger_control_success += int(
            treated["containment_trigger_count"] > 0
            and c_success
        )
    return {
        "treatment": treatment,
        "control": control,
        "pair_count": EXPECTED_PAIRS,
        "task_success": {
            "both_success": both_success,
            "treatment_only": treatment_only,
            "control_only": control_only,
            "both_fail": both_fail,
            "paired_difference": (
                (treatment_only - control_only) / EXPECTED_PAIRS
            ),
            "exact_two_sided_mcnemar_p": (
                _exact_two_sided_binomial_p(
                    treatment_only,
                    control_only,
                )
            ),
        },
        "joint_limit_step_rate": {
            "treatment_lower_pair_count": lower,
            "treatment_higher_pair_count": higher,
            "equal_pair_count": equal,
            "mean_paired_difference": (
                sum(rate_differences) / EXPECTED_PAIRS
            ),
            "exact_two_sided_sign_p": (
                _exact_two_sided_binomial_p(lower, higher)
            ),
        },
        "treatment_trigger_episode_count": sum(
            arms[treatment]["containment_trigger_count"] > 0
            for arms in pairs.values()
        ),
        "treatment_trigger_with_control_success_count": (
            treatment_trigger_control_success
        ),
    }


def build_summary() -> dict[str, Any]:
    loaded = {
        condition: _load_rows(condition)
        for condition in CONDITIONS
    }
    condition_summaries = {}
    for condition, (evidence, rows) in loaded.items():
        paired = {
            f"{treatment}_vs_{control}": _paired_summary(
                rows,
                treatment,
                control,
            )
            for treatment, control in PAIRED_L2_CONTRASTS
        }
        aggregate = evidence["aggregate"]
        condition_summaries[condition] = {
            "classification": evidence["classification"],
            "data_integrity": {
                "episode_count": aggregate["episode_count"],
                "runtime_exception_count": aggregate[
                    "runtime_exception_count"
                ],
                "paired_first_action_block_match_count": (
                    aggregate[
                        "paired_first_action_block_match_count"
                    ]
                ),
                "observer_policy_step_count": aggregate[
                    "joint_limit_observer_policy_step_count"
                ],
                "independent_signal_agreement_count": aggregate[
                    "joint_limit_independent_signal_agreement_count"
                ],
                "disabled_arm_annotation_count": aggregate[
                    "joint_limit_disabled_arm_annotation_count"
                ],
                "post_trigger_dispatch_count": aggregate[
                    "joint_limit_post_trigger_dispatch_count"
                ],
                "trigger_episode_count": aggregate[
                    "joint_limit_containment_trigger_episode_count"
                ],
                "trigger_and_task_success_count": aggregate[
                    "joint_limit_trigger_and_task_success_count"
                ],
            },
            "by_arm": _arm_summary(rows),
            "paired_l2_contrasts": paired,
        }
        if condition == "attacked":
            condition_summaries[condition][
                "attack_activation"
            ] = {
                "changed_first_action_block_count": aggregate[
                    "attack_changed_first_action_block_count"
                ],
                "episode_count": aggregate["episode_count"],
                "attacked_first_blocks_match_within_workload_count": (
                    aggregate[
                        "attacked_paired_first_action_block_match_count"
                    ]
                ),
            }

    contrasts = {}
    for treatment, control in PAIRED_L2_CONTRASTS:
        name = f"{treatment}_vs_{control}"
        clean = condition_summaries["clean"][
            "paired_l2_contrasts"
        ][name]
        attacked = condition_summaries["attacked"][
            "paired_l2_contrasts"
        ][name]
        contrasts[name] = {
            "task_success_paired_difference_in_difference": (
                attacked["task_success"]["paired_difference"]
                - clean["task_success"]["paired_difference"]
            ),
            (
                "joint_limit_rate_mean_paired_"
                "difference_in_difference"
            ): (
                attacked["joint_limit_step_rate"][
                    "mean_paired_difference"
                ]
                - clean["joint_limit_step_rate"][
                    "mean_paired_difference"
                ]
            ),
            "interpretation": (
                "Descriptive only. The method was developed after v10 and "
                "fresh15 outcomes were observed before scale45 froze."
            ),
        }

    total_triggers = sum(
        condition_summaries[condition]["data_integrity"][
            "trigger_episode_count"
        ]
        for condition in CONDITIONS
    )
    total_post_trigger = sum(
        condition_summaries[condition]["data_integrity"][
            "post_trigger_dispatch_count"
        ]
        for condition in CONDITIONS
    )
    return {
        "schema": SCHEMA,
        "classification": (
            "joint_limit_containment_v11_scale45_heldout_"
            "mixed_evidence"
        ),
        "source": {
            condition: {
                "pilot_evidence_path": (
                    (root / "pilot_evidence.json")
                    .relative_to(REPO_ROOT)
                    .as_posix()
                ),
                "pilot_evidence_sha256": file_sha256(
                    root / "pilot_evidence.json"
                ),
                "checksums_sha256": file_sha256(
                    root / "SHA256SUMS"
                ),
            }
            for condition, root in CONDITIONS.items()
        },
        "conditions": condition_summaries,
        "clean_attacked_contrasts": contrasts,
        "mechanism_decision": {
            "model_defined_joint_limit_signal_bound": True,
            "observer_signal_agreement_complete": True,
            "l2_only_arm_isolation_complete": True,
            "observed_trigger_count": total_triggers,
            "observed_post_trigger_dispatch_count": (
                total_post_trigger
            ),
            "mechanical_containment_verified": (
                total_triggers > 0 and total_post_trigger == 0
            ),
            "first_hit_prevention_claim": False,
        },
        "paper_claim_decision": {
            "positive_system_claim": (
                "Report the observed number of model-defined triggers and "
                "whether any later action was dispatched."
            ),
            "risk_result": (
                "Report paired joint-limit-rate direction, effect size, "
                "and exact sign test for both L2 contrasts and conditions."
            ),
            "utility_result": (
                "Report paired task-success differences and exact McNemar "
                "tests beside risk results; no noninferiority claim was "
                "pre-registered."
            ),
            "official_endpoint_result": (
                "Report official cost/collision counts by arm without "
                "substituting the model-defined joint-limit endpoint."
            ),
            "mainline_role": (
                "Use scale45 to estimate the stability and utility cost of "
                "typed L2 containment. Do not market it as first-hit "
                "prevention or a complete defense."
            ),
        },
        "claim_boundary": (
            "The v11 method was designed after v10 and fresh15 outcomes "
            "were observed before this 45-pair held-out scale-up froze. "
            "The scale-up uses fresh init identities and unchanged method "
            "parameters, but cannot retroactively make v11 confirmatory. "
            "The simulator's model-defined 0.1-rad joint-limit predicate "
            "does not establish prevention of the first hit, causal "
            "real-world safety, deployment, or hardware validity."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    text = canonical_text(build_summary())
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise JointLimitScale45TerminalError(
                f"v11 scale45 terminal summary is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
