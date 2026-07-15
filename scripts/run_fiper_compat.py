#!/usr/bin/env python3
"""Run frozen FIPER with the NumPy alias expected by its unpinned environment.

FIPER commit 13d79c5 references ``np.bool``, which NumPy removed in 1.24.
The upstream environment.yml leaves NumPy unpinned.  Restoring that alias to
the identical scalar type keeps the upstream checkout clean and does not alter
the detector's numerical computation.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_ENTRYPOINT = REPO_ROOT / "upstream" / "fiper" / "scripts" / "run_fiper.py"


def main() -> None:
    if "bool" not in np.__dict__:
        np.bool = np.bool_  # type: ignore[attr-defined]
    runpy.run_path(str(UPSTREAM_ENTRYPOINT), run_name="__main__")


if __name__ == "__main__":
    main()
