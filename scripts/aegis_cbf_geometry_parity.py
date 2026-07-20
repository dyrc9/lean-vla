#!/usr/bin/env python3
"""Cross-check typed AEGIS geometry coefficients against pinned source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AEGIS_MAIN = ROOT / "external" / "vlsa-aegis" / "main"
AEGIS_PYTHON = AEGIS_MAIN / ".venv" / "bin" / "python"
SCHEMA = "proofalign.aegis-cbf-geometry-parity-v1"
JSON_MARKER = "__PROOFALIGN_GEOMETRY_JSON__"

IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
ROTATE_Z_90 = (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
ROTATE_Y_90 = (0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0)

CASES: tuple[dict[str, Any], ...] = (
    {
        "name": "identity_axis",
        "robot_center": (0.0, 0.0, 0.0),
        "robot_shape": (0.06, 0.12, 0.11),
        "robot_rotation": IDENTITY,
        "obstacle_center": (0.3, 0.1, 0.05),
        "obstacle_shape": (0.08, 0.15, 0.2),
        "obstacle_rotation": IDENTITY,
        "direction_z": (1.0, 0.0, 0.0),
    },
    {
        "name": "rotated_robot",
        "robot_center": (-0.05, 0.1, 0.8),
        "robot_shape": (0.06, 0.12, 0.2),
        "robot_rotation": ROTATE_Z_90,
        "obstacle_center": (0.2, -0.15, 0.95),
        "obstacle_shape": (0.1, 0.18, 0.14),
        "obstacle_rotation": IDENTITY,
        "direction_z": (0.4, -0.2, 0.9),
    },
    {
        "name": "both_rotated_nonunit_direction",
        "robot_center": (0.1, -0.2, 0.7),
        "robot_shape": (0.09, 0.07, 0.16),
        "robot_rotation": ROTATE_Y_90,
        "obstacle_center": (-0.2, 0.25, 1.1),
        "obstacle_shape": (0.2, 0.11, 0.08),
        "obstacle_rotation": ROTATE_Z_90,
        "direction_z": (-3.0, 2.0, 1.0),
    },
    {
        "name": "near_axis_dense",
        "robot_center": (0.02, 0.03, -0.04),
        "robot_shape": (0.051, 0.123, 0.097),
        "robot_rotation": IDENTITY,
        "obstacle_center": (0.021, -0.13, 0.22),
        "obstacle_shape": (0.077, 0.131, 0.203),
        "obstacle_rotation": ROTATE_Y_90,
        "direction_z": (0.001, 0.7, -0.4),
    },
)


def _source_reference(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import numpy as np
    if str(AEGIS_MAIN) not in sys.path:
        sys.path.insert(0, str(AEGIS_MAIN))
    import utils

    records = []
    for case in cases:
        values = utils.compute_h_coeffs_3d(
            np.asarray(case["robot_center"], dtype=float),
            np.asarray(case["robot_shape"], dtype=float),
            np.asarray(case["robot_rotation"], dtype=float).reshape(3, 3),
            np.asarray(case["obstacle_center"], dtype=float),
            np.asarray(case["obstacle_shape"], dtype=float),
            np.asarray(case["obstacle_rotation"], dtype=float).reshape(3, 3),
            np.asarray(case["direction_z"], dtype=float),
        )
        records.append(
            {
                "name": case["name"],
                "a_v": np.asarray(values[0]).tolist(),
                "a_omega": np.asarray(values[1]).tolist(),
                "a_uz": np.asarray(values[2]).tolist(),
                "h": float(values[3]),
                "mu_row": np.asarray(values[4]).tolist(),
            }
        )
    return records


def _maximum_error(actual: tuple[float, ...], expected: list[float]) -> float:
    return max(abs(left - right) for left, right in zip(actual, expected))


def _audit() -> dict[str, Any]:
    if not AEGIS_PYTHON.is_file():
        raise RuntimeError(f"pinned AEGIS Python is missing: {AEGIS_PYTHON}")
    reference = subprocess.run(
        [str(AEGIS_PYTHON), str(Path(__file__).resolve()), "--source-reference"],
        cwd=AEGIS_MAIN,
        input=json.dumps(CASES),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if reference.returncode != 0 or JSON_MARKER not in reference.stdout:
        raise RuntimeError(
            f"official AEGIS geometry reference failed ({reference.returncode}): "
            f"{reference.stdout[-2000:]} {reference.stderr[-2000:]}"
        )
    expected_records = json.loads(reference.stdout.rsplit(JSON_MARKER, 1)[1])

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from proofalign.benchmark.aegis_cbf_filter import AegisCBFSourceIdentityV2
    from proofalign.benchmark.aegis_cbf_geometry import (
        AegisGeometryObservationV2,
        _compute_coefficients,
    )
    from proofalign.ctda import digest_text

    source = AegisCBFSourceIdentityV2(
        source_commit="57b1aef306f212aea3574b0a3b64aa1a3d8f5e4b",
        source_tree="1b55f9d97f0ae57b97e68fcb1177e524b096d13b",
        file_sha256=(
            ("controller", digest_text("parity-controller")),
            ("geometry", digest_text("parity-geometry")),
        ),
    )
    maxima = {"a_v": 0.0, "a_omega": 0.0, "a_uz": 0.0, "h": 0.0, "mu_row": 0.0}
    records = []
    for case, expected in zip(CASES, expected_records):
        observation = AegisGeometryObservationV2(
            source_identity_digest=source.source_identity_digest,
            state_snapshot_digest=digest_text("geometry-parity-state"),
            safety_bundle_digest=digest_text("geometry-parity-safety"),
            observed_at_ns=0,
            robot_center=tuple(case["robot_center"]),
            robot_shape_diagonal=tuple(case["robot_shape"]),
            robot_rotation=tuple(case["robot_rotation"]),
            obstacle_center=tuple(case["obstacle_center"]),
            obstacle_shape_diagonal=tuple(case["obstacle_shape"]),
            obstacle_rotation=tuple(case["obstacle_rotation"]),
            direction_z=tuple(case["direction_z"]),
            raw_provenance_digest=digest_text(f"geometry-parity:{case['name']}"),
        )
        actual = _compute_coefficients(observation)
        errors = {
            "a_v": _maximum_error(actual[0], expected["a_v"]),
            "a_omega": _maximum_error(actual[1], expected["a_omega"]),
            "a_uz": _maximum_error(actual[2], expected["a_uz"]),
            "h": abs(actual[3] - expected["h"]),
            "mu_row": _maximum_error(actual[4], expected["mu_row"]),
        }
        for name, error in errors.items():
            maxima[name] = max(maxima[name], error)
        records.append(
            {
                "name": case["name"],
                "errors": errors,
                "parity": all(error <= 1e-9 for error in errors.values()),
            }
        )
    if not all(record["parity"] for record in records):
        raise RuntimeError(f"AEGIS geometry parity tolerance exceeded: {records}")
    return {
        "schema": SCHEMA,
        "status": "parity_passed",
        "case_count": len(records),
        "tolerance": 1e-9,
        "maximum_absolute_errors": maxima,
        "records": records,
        "source_stdout_sha256": __import__("hashlib").sha256(reference.stdout.encode()).hexdigest(),
        "source_stderr_sha256": __import__("hashlib").sha256(reference.stderr.encode()).hexdigest(),
        "counters": {
            "simulator_construction_count": 0,
            "env_step_count": 0,
            "model_construction_count": 0,
            "policy_inference_count": 0,
            "socket_bind_count": 0,
            "dispatch_count": 0,
        },
        "formal_rollout_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-reference", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.source_reference:
        cases = json.load(sys.stdin)
        print(JSON_MARKER + json.dumps(_source_reference(cases), sort_keys=True))
        return 0
    print(json.dumps(_audit(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
