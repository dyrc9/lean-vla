#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.phantom_menace_plugin import (
    ATTACK_PARAMETERS,
    DEFAULT_PHANTOM_ROOT,
    PhantomMenaceConfig,
    PhantomMenaceObservationTransform,
    upstream_manifest,
)


def _fixture() -> np.ndarray:
    y, x = np.mgrid[0:64, 0:64]
    return np.stack(((x * 4) % 256, (y * 4) % 256, ((x + y) * 2) % 256), axis=-1).astype(np.uint8)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic CPU smoke tests for frozen Phantom Menace transforms.")
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_PHANTOM_ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    image = _fixture()
    records = []
    for attack_type in sorted(ATTACK_PARAMETERS):
        for strength in ("weak", "medium", "strong"):
            transform = PhantomMenaceObservationTransform(
                PhantomMenaceConfig(
                    attack_type=attack_type,
                    attack_strength=strength,
                    repo_root=args.repo_root,
                )
            )
            attacked_first, record_first = transform(image)
            attacked_second, record_second = transform(image)
            if not np.array_equal(attacked_first, attacked_second) or record_first != record_second:
                raise RuntimeError(f"Nondeterministic transform: {attack_type}/{strength}")
            if not record_first["changed"]:
                raise RuntimeError(f"Transform did not alter fixture: {attack_type}/{strength}")
            record_first["deterministic_repeat"] = True
            records.append(record_first)

    payload = {
        "schema": "proofalign.phantom-menace-cpu-smoke.v1",
        "status": "passed",
        "upstream": upstream_manifest(args.repo_root),
        "fixture": {"shape": list(image.shape), "dtype": str(image.dtype)},
        "records": records,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
