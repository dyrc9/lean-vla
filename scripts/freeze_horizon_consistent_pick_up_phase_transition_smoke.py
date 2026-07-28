#!/usr/bin/env python3
"""Freeze only the v3 pick-up-to-move phase-transition smoke."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts.run_horizon_consistent_pick_up_phase_transition_smoke import (  # noqa: E402
    PROTOCOL_SCHEMA,
)


PARENT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "regression_smoke_terminal_summary.json"
)
REGRESSION_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "regression_smoke_protocol.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_horizon_consistent_pick_up_"
    "phase_transition_smoke_protocol.json"
)
SOURCE_PATHS = (
    "src/proofalign/horizon_consistent_pick_up.py",
    "scripts/run_l2_execution_attack_eval_v4.py",
    "scripts/run_horizon_consistent_pick_up_regression_smoke.py",
    "scripts/run_horizon_consistent_pick_up_phase_transition_smoke.py",
    "scripts/freeze_horizon_consistent_pick_up_phase_transition_smoke.py",
    "tests/test_horizon_consistent_pick_up.py",
    "tests/test_horizon_consistent_pick_up_smoke.py",
)
CREATED_AT = "2026-07-28T17:45:00+08:00"


class HorizonPhaseTransitionFreezeError(RuntimeError):
    """Raised when phase-transition authorization cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise HorizonPhaseTransitionFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise HorizonPhaseTransitionFreezeError(
            "tracked worktree must be clean before phase freeze"
        )
    parent = load_json_object(PARENT_PATH)
    regression = load_json_object(REGRESSION_PROTOCOL_PATH)
    if (
        parent.get("classification")
        != "horizon_consistent_pick_up_regression_smoke_pass"
        or parent.get("smoke_pass") is not True
        or parent.get("lifecycle", {}).get(
            "phase_transition_protocol_freeze_authorized"
        )
        is not True
        or parent.get("lifecycle", {}).get(
            "fresh_clean_efficacy_screen_authorized"
        )
        is not False
    ):
        raise HorizonPhaseTransitionFreezeError(
            "parent regression does not authorize phase protocol freeze"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    bindings = {
        relative: file_sha256(REPO_ROOT / relative)
        for relative in SOURCE_PATHS
    }
    workload = dict(regression["workload"])
    workload["max_steps"] = 100
    gates = dict(regression["gates"])
    gates.update(
        {
            "minimum_online_audit_count": 9,
            "minimum_eligible_online_audit_count": 9,
            "minimum_complete_transaction_count": 9,
            "minimum_dispatch_receipt_count": 90,
            "minimum_effect_allow_count": 9,
            "minimum_complete_move_transaction_count": 1,
            "minimum_move_effect_allow_count": 1,
        }
    )
    return {
        "schema": PROTOCOL_SCHEMA,
        "protocol_id": (
            "proofalign-horizon-consistent-pick-up-"
            "phase-transition-smoke-20260728"
        ),
        "status": "authorized_post_outcome_phase_transition_smoke",
        "created_at": created_at,
        "post_outcome_repair": True,
        "parent_regression_smoke": {
            "path": PARENT_PATH.relative_to(REPO_ROOT).as_posix(),
            "sha256": file_sha256(PARENT_PATH),
            "classification": parent["classification"],
        },
        "execution_authorization": {
            "clean_dual_phase_transition_smoke": True,
            "action_dispatch": True,
            "task_outcome_observation": True,
            "clean_efficacy_rollout": False,
            "attacked_rollout": False,
            "confirmatory_claim": False,
        },
        "workload": workload,
        "design": {
            **regression["design"],
            "parent_holding_observed_on_final_transaction": True,
            "maximum_steps_extended_from": 80,
            "maximum_steps_extended_to": 100,
            "required_next_semantic_phase": "move",
        },
        "gates": gates,
        "victim": regression["victim"],
        "runtime_dependency": regression["runtime_dependency"],
        "resource_gate": regression["resource_gate"],
        "fresh_output_root": (
            "results/proofalign_horizon_consistent_pick_up_"
            "phase_transition_smoke_20260728_fresh1"
        ),
        "source": {
            "repository_commit": bound_commit,
            "repository_tree": _git(
                "rev-parse", f"{bound_commit}^{{tree}}"
            ),
            "sha256": bindings,
        },
        "claim_boundary": (
            "This outcome-conditioned smoke extends the passed regression "
            "pair from 80 to 100 steps solely to verify a closed-loop "
            "pick_up-to-move transition and an allowed move transaction. "
            "It does not estimate clean efficacy, attacked defense, "
            "deployment performance, hardware safety, or a confirmatory "
            "effect."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    source_commit = None
    if args.check and args.output.is_file():
        retained = load_json_object(args.output)
        source_commit = retained.get("source", {}).get(
            "repository_commit"
        )
    text = canonical_text(
        build_protocol(
            created_at=args.created_at,
            source_commit=source_commit,
        )
    )
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise HorizonPhaseTransitionFreezeError(
                f"phase protocol is absent or stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
