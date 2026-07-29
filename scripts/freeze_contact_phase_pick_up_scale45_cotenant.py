#!/usr/bin/env python3
"""Freeze a co-tenant resource successor for the v8 scale45 run."""

from __future__ import annotations

import argparse
from copy import deepcopy
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
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
)


PREDECESSOR_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_four_arm_protocol.json"
)
OUTPUT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_contact_phase_pick_up_scale45_cotenant_protocol.json"
)
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_contact_phase_pick_up_scale45_cotenant.py"
)
SOURCE_PATHS = (
    "src/proofalign/contact_phase_pick_up.py",
    "scripts/run_l2_execution_attack_eval_v8.py",
    "scripts/run_contact_phase_pick_up_clean_pilot.py",
    "scripts/freeze_contact_phase_pick_up_scale45_cotenant.py",
    "tests/test_contact_phase_pick_up_scale45_cotenant.py",
)
PROTOCOL_ID = (
    "proofalign-contact-phase-pick-up-scale45-cotenant-20260729"
)
CREATED_AT = "2026-07-29T10:05:00+08:00"
MEMORY_USED_LIMIT_MIB = 43_000


class ContactPhaseScale45CotenantFreezeError(RuntimeError):
    """Raised when the co-tenant scale45 successor cannot be frozen."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ContactPhaseScale45CotenantFreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=no"):
        raise ContactPhaseScale45CotenantFreezeError(
            "tracked worktree must be clean before co-tenant freeze"
        )
    predecessor = load_json_object(PREDECESSOR_PATH)
    if (
        predecessor.get("protocol_id")
        != "proofalign-contact-phase-pick-up-scale45-four-arm-20260729"
        or predecessor.get("design", {}).get("episode_count") != 180
        or predecessor.get("outcomes_observed_for_selection") is not False
    ):
        raise ContactPhaseScale45CotenantFreezeError(
            "scale45 predecessor identity differs"
        )
    protocol = deepcopy(predecessor)
    protocol.update(
        {
            "protocol_id": PROTOCOL_ID,
            "created_at": created_at,
            "co_tenant_resource_exception": {
                "active": True,
                "reason": (
                    "no two GPUs remained below the exclusive 1024 MiB "
                    "launch gate; all observed GPU utilization was zero"
                ),
                "explicit_user_continuation_date": "2026-07-29",
                "method_changed": False,
                "schedule_changed": False,
                "outcome_or_safety_gate_changed": False,
                "timing_or_throughput_claim_authorized": False,
                "result_scope": "exploratory_clean_task_outcomes_only",
                "selected_gpu_memory_used_mib_max_exclusive": (
                    MEMORY_USED_LIMIT_MIB
                ),
            },
            "fresh_output_root": (
                "results/proofalign_contact_phase_pick_up_"
                "scale45_cotenant_20260729_fresh1"
            ),
            "complete_classification": (
                "contact_phase_pick_up_scale45_cotenant_complete"
            ),
            "incomplete_classification": (
                "contact_phase_pick_up_scale45_cotenant_incomplete"
            ),
            "claim_boundary": (
                "This outcome-blind clean exploratory experiment retains "
                "the frozen 45-task, 180-episode schedule and all method, "
                "outcome, and safety gates. It relaxes only prelaunch GPU "
                "isolation and therefore supports no timing, throughput, "
                "exclusive-resource, attacked-defense, confirmatory, "
                "deployment, or hardware-safety claim."
            ),
        }
    )
    protocol["resource_gate"][
        "selected_gpu_memory_used_mib_max_exclusive"
    ] = MEMORY_USED_LIMIT_MIB
    protocol["required_bindings"] = [
        {
            "path": PREDECESSOR_PATH.relative_to(
                REPO_ROOT
            ).as_posix(),
            "sha256": file_sha256(PREDECESSOR_PATH),
        },
        *protocol["required_bindings"],
    ]
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol["source"] = {
        "repository_commit": bound_commit,
        "repository_tree": _git(
            "rev-parse", f"{bound_commit}^{{tree}}"
        ),
        "sha256": {
            relative: file_sha256(REPO_ROOT / relative)
            for relative in SOURCE_PATHS
        },
        "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
        "freezer_sha256": file_sha256(SELF_PATH),
    }
    return protocol


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
            raise ContactPhaseScale45CotenantFreezeError(
                f"co-tenant scale45 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
