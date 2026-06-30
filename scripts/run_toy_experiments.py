from __future__ import annotations

from pathlib import Path

from proofalign.baselines import BaselineMode
from proofalign.experiments import run_directory


if __name__ == "__main__":
    run_directory(
        Path("examples/tasks"),
        Path("results/toy"),
        [
            BaselineMode.VLA_ONLY,
            BaselineMode.COLLISION_ONLY,
            BaselineMode.INTENT_ONLY,
            BaselineMode.EFFECT_ONLY,
            BaselineMode.DUAL,
        ],
    )
