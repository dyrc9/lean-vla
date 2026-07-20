#!/usr/bin/env python3
"""Run the frozen, read-only AEGIS runtime R1 gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proofalign.benchmark.aegis_runtime import (  # noqa: E402
    build_runtime_preflight,
    dump_json,
    load_json,
    sha256_file,
)


DEFAULT_PROTOCOL = ROOT / "experiments" / "safelibero_aegis_runtime_protocol.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify pinned AEGIS runtimes and assets without constructing a "
            "policy, binding a server, constructing a simulator, or stepping it."
        )
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a fresh full report; existing files are never overwritten.",
    )
    parser.add_argument(
        "--full-report",
        action="store_true",
        help="Print the full report instead of the compact gate result.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol_path = args.protocol.resolve()
    protocol = load_json(protocol_path)
    report = build_runtime_preflight(protocol, project_root=ROOT)
    report["protocol_path"] = str(protocol_path)
    report["protocol_sha256"] = sha256_file(protocol_path)

    if args.output:
        output = args.output.resolve()
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing report: {output}")
        dump_json(output, report)

    if args.full_report:
        printable = report
    else:
        printable = {
            "schema": report["schema"],
            "protocol_id": report["protocol_id"],
            "protocol_sha256": report["protocol_sha256"],
            "checks": report["checks"],
            "counters": report["counters"],
            "static_runtime_ready": report["static_runtime_ready"],
            "model_load_probe_authorized": report["model_load_probe_authorized"],
            "formal_rollout_authorized": report["formal_rollout_authorized"],
            "status": report["status"],
        }
    print(json.dumps(printable, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if report["static_runtime_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
