#!/usr/bin/env python3
"""Analyze the frozen full-120 LLM-template successor without touching paper."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import analyze_remote_full120_experiment as original  # noqa: E402


original.UMBRELLA_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_successor_protocol_20260818.json"
original.CLEAN_PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_clean_protocol_20260818.json"
original.ATTACKED_PROTOCOL_PATH = REPO_ROOT / "experiments/proofalign_remote_full120_llm_attacked_protocol_20260818.json"
original.CLEAN_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_clean_20260818_fresh1"
original.ATTACKED_ROOT = REPO_ROOT / "results/proofalign_remote_full120_llm_attacked_20260818_fresh1"
original.HANDOFF_PATH = REPO_ROOT / "docs/paper/remote_full120_llm_result_handoff.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("clean", "attacked"), required=True)
    args = parser.parse_args()
    print(canonical_text(original.analyze(args.stage)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
