#!/usr/bin/env python3
"""Execute a frozen v2 L1 collection through the audited v1 collector."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from scripts import run_l1_task_conditioned_experiment as collector  # noqa: E402
from scripts.run_l1_task_conditioned_successor_v2 import (  # noqa: E402
    annotate_payload,
    patched_task_conditioned_l1_v2_runtime,
)


def execute(
    protocol_path: Path, policy_gpu: int, egl_gpu: int
) -> dict[str, Any]:
    original_runtime = collector.patched_task_conditioned_l1_runtime
    original_annotate = collector.annotate_payload
    collector.patched_task_conditioned_l1_runtime = (
        patched_task_conditioned_l1_v2_runtime
    )
    collector.annotate_payload = annotate_payload
    try:
        return collector.execute(protocol_path, policy_gpu, egl_gpu)
    finally:
        collector.patched_task_conditioned_l1_runtime = original_runtime
        collector.annotate_payload = original_annotate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--policy-gpu", type=int, required=True)
    parser.add_argument("--egl-gpu", type=int, required=True)
    args = parser.parse_args()
    value = execute(args.protocol.resolve(), args.policy_gpu, args.egl_gpu)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

