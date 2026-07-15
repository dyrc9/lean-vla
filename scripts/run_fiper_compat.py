#!/usr/bin/env python3
"""Run frozen FIPER with the NumPy alias expected by its unpinned environment.

FIPER commit 13d79c5 references ``np.bool``, which NumPy removed in 1.24.
The upstream environment.yml leaves NumPy unpinned.  Restoring that alias to
the identical scalar type keeps the upstream checkout clean and does not alter
the detector's numerical computation.
"""

from __future__ import annotations

import os
import runpy
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIPER_ROOT = REPO_ROOT / "external" / "fiper"


def main() -> None:
    if "bool" not in np.__dict__:
        np.bool = np.bool_  # type: ignore[attr-defined]
    fiper_root = Path(os.environ.get("PROOFALIGN_FIPER_ROOT", DEFAULT_FIPER_ROOT)).resolve()
    entrypoint = fiper_root / "scripts" / "run_fiper.py"
    if not entrypoint.is_file():
        raise FileNotFoundError(f"frozen FIPER entrypoint is missing: {entrypoint}")
    runpy.run_path(str(entrypoint), run_name="__main__")


if __name__ == "__main__":
    main()
