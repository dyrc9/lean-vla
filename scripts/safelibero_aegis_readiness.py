#!/usr/bin/env python3
"""Read-only SafeLIBERO/AEGIS source, data, and environment preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (SRC, ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from proofalign.benchmark.safelibero_foundation import (  # noqa: E402
    build_readiness_report,
    dump_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Outcome-blind SafeLIBERO/AEGIS inventory preflight. This command has no "
            "execution mode and never constructs a simulator or calls env.step()."
        )
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=ROOT / "experiments" / "safelibero_aegis_readiness_protocol.json",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=ROOT / "external" / "vlsa-aegis",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional fresh path for the complete read-only readiness report.",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Emit the complete file/scenario manifest on stdout instead of a compact summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    report = build_readiness_report(protocol, args.source_root)
    encoded = dump_json(report)
    if args.output is not None:
        if args.output.exists():
            raise FileExistsError(f"refusing to overwrite readiness report: {args.output}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    stdout_value = report if args.full_report else {
        "schema": report["schema"],
        "protocol_id": report["protocol_id"],
        "status": report["status"],
        "checks": report["checks"],
        "source": {
            "commit": report["source"]["commit"],
            "git_tree": report["source"]["git_tree"],
            "git_clean": report["source"]["git_clean"],
            "license": report["source"]["license"],
        },
        "dataset": {
            "dataset_digest": report["dataset"]["dataset_digest"],
            "suite_count": report["dataset"]["suite_count"],
            "scenario_count": report["dataset"]["scenario_count"],
            "candidate_episode_count": report["dataset"]["candidate_episode_count"],
        },
        "foundation_ready": report["foundation_ready"],
        "aegis_runtime_ready": report["aegis_runtime_ready"],
        "formal_rollout_authorized": report["formal_rollout_authorized"],
        "env_step_count": report["env_step_count"],
    }
    print(dump_json(stdout_value), end="")
    return 0 if report["foundation_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
