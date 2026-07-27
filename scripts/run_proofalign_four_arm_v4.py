#!/usr/bin/env python3
"""Build the outcome-blind v4 four-arm closed-loop execution plan.

The committed successor protocol authorizes no execution.  This entry point
therefore supports protocol checking and dry-run schedule construction only;
a later clean-commit authorization successor must supply the actual GPU
runner.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
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
    ARM_ORDER,
    DRY_RUN_SCHEMA,
    STAGE_CONDITIONS,
    build_schedule,
    canonical_text,
    schedule_digest,
    validate_successor_protocol,
)


DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_successor_protocol.json"
)
DEFAULT_EVIDENCE = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_orchestration_dry_run.json"
)


class FourArmV4OrchestrationError(RuntimeError):
    """Raised when the four-arm orchestrator must stop fail-closed."""


def _stage_root_key(stage: str) -> str:
    return {
        "A_fixed_trace_shadow": "stage_a",
        "B_clean_closed_loop": "stage_b",
        "C_attacked_closed_loop": "stage_c",
    }[stage]


def stage_dry_run(
    protocol: dict[str, Any],
    *,
    confirmatory: dict[str, Any],
    stage: str,
) -> dict[str, Any]:
    specs = build_schedule(confirmatory, protocol, stage=stage)
    root_relative = protocol["fresh_roots"][_stage_root_key(stage)]
    output_root = REPO_ROOT / root_relative
    arm_counts = Counter(spec.arm for spec in specs)
    position_counts = {
        arm: [0, 0, 0, 0] for arm in ARM_ORDER
    }
    by_unit: dict[str, list[Any]] = {}
    for spec in specs:
        by_unit.setdefault(spec.unit.unit_id, []).append(spec)
    for unit_specs in by_unit.values():
        for position, spec in enumerate(unit_specs):
            position_counts[spec.arm][position] += 1
    expected_authorization_key = {
        "A_fixed_trace_shadow": "stage_a_shadow",
        "B_clean_closed_loop": "stage_b_clean_rollout",
        "C_attacked_closed_loop": "stage_c_attacked_rollout",
    }[stage]
    m2_summary = (
        REPO_ROOT
        / protocol["dependencies"]["m2_victim_protocol"][
            "terminal_summary_path"
        ]
    )
    blockers = []
    if not m2_summary.is_file():
        blockers.append("m2_terminal_summary_absent")
    if (
        protocol["execution_authorization"][
            expected_authorization_key
        ]
        is not True
    ):
        blockers.append("stage_execution_not_authorized")
    if output_root.exists():
        blockers.append("fresh_output_root_occupied")
    if stage == "C_attacked_closed_loop":
        blockers.append("clean_gate_terminal_pass_not_bound")
    return {
        "stage": stage,
        "condition": STAGE_CONDITIONS[stage],
        "dispatch_planned": stage != "A_fixed_trace_shadow",
        "unit_count": len(by_unit),
        "arm_count": len(ARM_ORDER),
        "row_or_episode_count": len(specs),
        "arm_counts": dict(sorted(arm_counts.items())),
        "arm_position_counts": position_counts,
        "schedule_sha256": schedule_digest(specs),
        "first_episode_id": specs[0].episode_id,
        "last_episode_id": specs[-1].episode_id,
        "fresh_output_root": root_relative,
        "fresh_output_root_absent": not output_root.exists(),
        "ledger_path": f"{root_relative}/episodes_ledger.jsonl",
        "execution_authorization_key": expected_authorization_key,
        "execution_authorized": False,
        "execution_ready": False,
        "blockers": blockers,
    }


def build_dry_run_evidence(
    protocol_path: Path = DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    protocol = load_json_object(protocol_path)
    confirmatory = validate_successor_protocol(
        protocol,
        repo_root=REPO_ROOT,
    )
    stages = [
        stage_dry_run(
            protocol,
            confirmatory=confirmatory,
            stage=stage,
        )
        for stage in STAGE_CONDITIONS
    ]
    return {
        "schema": DRY_RUN_SCHEMA,
        "protocol_id": protocol["protocol_id"],
        "protocol_path": protocol_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "protocol_sha256": file_sha256(protocol_path),
        "classification": (
            "four_arm_v4_schedule_frozen_execution_not_authorized"
        ),
        "complete": all(
            row["unit_count"] == 120
            and row["arm_count"] == 4
            and row["row_or_episode_count"] == 480
            and row["arm_counts"]
            == {arm: 120 for arm in ARM_ORDER}
            and all(
                count == 30
                for counts in row["arm_position_counts"].values()
                for count in counts
            )
            for row in stages
        ),
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "outcomes_observed": False,
        "stages": stages,
        "identity_contract": protocol["identity_contract"],
        "ledger_contract": protocol["ledger_contract"],
        "claim_boundary": (
            "This dry run proves deterministic 120-unit by four-arm "
            "scheduling, Latin-square balance, fresh-root naming, and ledger "
            "identity only. It authorizes no execution and observes no "
            "outcome."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", type=Path, default=DEFAULT_PROTOCOL
    )
    parser.add_argument(
        "--evidence", type=Path, default=DEFAULT_EVIDENCE
    )
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--stage",
        choices=tuple(STAGE_CONDITIONS),
    )
    args = parser.parse_args(argv)
    evidence = build_dry_run_evidence(args.protocol.resolve())
    if args.freeze:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            canonical_text(evidence),
            encoding="utf-8",
        )
        print(args.evidence)
        return 0
    if args.check:
        if not args.evidence.is_file():
            raise FourArmV4OrchestrationError(
                f"four-arm dry-run evidence is absent: {args.evidence}"
            )
        if args.evidence.read_text(
            encoding="utf-8"
        ) != canonical_text(evidence):
            raise FourArmV4OrchestrationError(
                f"four-arm dry-run evidence is stale: {args.evidence}"
            )
        print(f"current: {args.evidence}")
        return 0
    if args.dry_run:
        if args.stage is None:
            print(json.dumps(evidence, indent=2))
        else:
            selected = next(
                row
                for row in evidence["stages"]
                if row["stage"] == args.stage
            )
            print(json.dumps(selected, indent=2))
        return 0
    raise FourArmV4OrchestrationError(
        "the frozen v4 successor authorizes no execution; use --dry-run "
        "or --check"
    )


if __name__ == "__main__":
    raise SystemExit(main())
