#!/usr/bin/env python3
"""Read-only retained-E1 and SafeLIBERO exact-unit CTDA v2 support audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.safelibero_ctda_support import (  # noqa: E402
    build_ctda_v2_support_audit,
    dump_support_json,
)
from proofalign.benchmark.aegis_runtime import sha256_file  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse retained E1 JSON and official SafeLIBERO BDDL/init inventory without "
            "constructing a model/simulator, running policy inference, or calling env.step()."
        )
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "experiments" / "ctda_v2_no_dispatch_protocol.json",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "external" / "vlsa-aegis",
    )
    parser.add_argument(
        "--retained-root",
        type=Path,
        default=ROOT / "results" / "proofalign_e1_clean_utility_seed1_20260717",
    )
    parser.add_argument(
        "--state-coverage-summary",
        type=Path,
        default=ROOT / "experiments" / "ctda_v2_safelibero_state_coverage_summary_r1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional fresh output path; existing files are never overwritten.",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Print all exact-unit rows instead of the compact gate summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    report = build_ctda_v2_support_audit(
        protocol,
        source_root=args.source_root,
        retained_root=args.retained_root,
        state_coverage_summary=args.state_coverage_summary,
    )
    report["protocol_path"] = str(args.protocol.resolve())
    report["protocol_sha256"] = sha256_file(args.protocol.resolve())
    report["recorded_at_ns"] = time.time_ns()
    encoded = dump_support_json(report)
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite CTDA v2 support audit: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    stdout = report if args.full_report else {
        "schema": report["schema"],
        "status": report["status"],
        "checks": report["checks"],
        "structural_audit_ready": report["structural_audit_ready"],
        "executable_support_ready": report["executable_support_ready"],
        "retained_e1": {
            "episode_count": report["retained_e1"]["episode_count"],
            "block_reason_counts": report["retained_e1"]["block_reason_counts"],
            "accepted_prefixes": report["retained_e1"]["accepted_prefixes"],
            "v2_replay_ready_count": report["retained_e1"]["v2_replay_ready_count"],
        },
        "safelibero": {
            "scenario_count": report["safelibero"]["scenario_count"],
            "candidate_episode_count": report["safelibero"]["candidate_episode_count"],
            "goal_manifest_parse_supported_scenarios": report["safelibero"][
                "goal_manifest_parse_supported_scenarios"
            ],
            "semantic_template_supported_scenarios": report["safelibero"][
                "semantic_template_supported_scenarios"
            ],
            "current_runtime_skill_set_supported_scenarios": report["safelibero"][
                "current_runtime_skill_set_supported_scenarios"
            ],
            "state_adapter_schema_supported_scenarios": report["safelibero"][
                "state_adapter_schema_supported_scenarios"
            ],
            "progress_adapter_supported_scenarios": report["safelibero"][
                "progress_adapter_supported_scenarios"
            ],
            "exact_unit_executable_support_scenarios": report["safelibero"][
                "exact_unit_executable_support_scenarios"
            ],
            "exact_unit_executable_support_episodes": report["safelibero"][
                "exact_unit_executable_support_episodes"
            ],
        },
        "safelibero_state_coverage": report["safelibero_state_coverage"],
        "counters": report["counters"],
        "formal_rollout_authorized": report["formal_rollout_authorized"],
        "next_gate": report["next_gate"],
    }
    print(dump_support_json(stdout), end="")
    return 0 if report["structural_audit_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
