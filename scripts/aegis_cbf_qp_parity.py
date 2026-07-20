#!/usr/bin/env python3
"""Cross-check the source-bound AEGIS analytical QP against CVXPY/OSQP.

The default mode runs the ProofAlign producer in the project environment and
asks the pinned AEGIS Python environment to solve the same frozen numeric
fixtures with the controller's CVXPY formulation.  Neither mode constructs a
simulator, loads a model, queries a policy, opens a socket, or dispatches an
action.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AEGIS_ROOT = ROOT / "external" / "vlsa-aegis"
AEGIS_PYTHON = AEGIS_ROOT / "main" / ".venv" / "bin" / "python"
SOURCE_COMMIT = "57b1aef306f212aea3574b0a3b64aa1a3d8f5e4b"
SOURCE_TREE = "1b55f9d97f0ae57b97e68fcb1177e524b096d13b"
SCHEMA = "proofalign.aegis-cbf-qp-parity-v1"


CASES: tuple[dict[str, Any], ...] = (
    {
        "name": "admissible_identity",
        "command": (0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        "rotation": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        "direction_z": (0.0, 0.0, 1.0),
        "a_v": (1.0, 0.0, 0.0),
        "a_omega": (0.0, 0.0, 0.0),
        "a_uz": (0.0, 0.0, 0.0),
        "h": 0.0,
        "mu_row": (0.0, 0.0, 0.0),
    },
    {
        "name": "active_translation_boundary",
        "command": (-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        "rotation": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        "direction_z": (0.0, 0.0, 1.0),
        "a_v": (1.0, 0.0, 0.0),
        "a_omega": (0.0, 0.0, 0.0),
        "a_uz": (0.0, 0.0, 0.0),
        "h": 0.0,
        "mu_row": (0.0, 0.0, 0.0),
    },
    {
        "name": "active_rotated_mixed_constraint",
        "command": (0.2, -0.1, 0.05, 0.1, -0.2, 0.05, 1.0),
        "rotation": (0.0, -1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0),
        "direction_z": (0.0, 0.0, 1.0),
        "a_v": (0.7, -0.3, 0.2),
        "a_omega": (0.1, 0.4, -0.2),
        "a_uz": (0.2, -0.1, 0.3),
        "h": -0.2,
        "mu_row": (0.4, -0.2, 0.1),
    },
    {
        "name": "active_direction_update",
        "command": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        "rotation": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        "direction_z": (0.0, 0.0, 1.0),
        "a_v": (0.0, 0.0, 0.0),
        "a_omega": (0.0, 0.0, 0.0),
        "a_uz": (1.0, -0.5, 0.0),
        "h": -0.3,
        "mu_row": (0.1, 0.2, 0.0),
    },
    {
        "name": "infeasible_degenerate_normal",
        "command": (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0),
        "rotation": (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0),
        "direction_z": (0.0, 0.0, 1.0),
        "a_v": (0.0, 0.0, 0.0),
        "a_omega": (0.0, 0.0, 0.0),
        "a_uz": (0.0, 0.0, 0.0),
        "h": -0.1,
        "mu_row": (0.0, 0.0, 0.0),
    },
)


def _cvxpy_reference(cases: list[dict[str, Any]]) -> dict[str, Any]:
    import cvxpy as cp
    import numpy as np

    records = []
    weight = np.diag([1.0 / 25.0] * 6 + [1.0] * 3)
    for case in cases:
        command = np.asarray(case["command"], dtype=float)
        rotation = np.asarray(case["rotation"], dtype=float).reshape(3, 3)
        mu_row = np.asarray(case["mu_row"], dtype=float)
        latent_nominal = np.hstack(
            [5.0 * rotation.T @ command[:3], 5.0 * command[3:6], 10.0 * mu_row]
        )
        coefficients = np.hstack(
            [
                0.2 * np.asarray(case["a_v"], dtype=float),
                0.2 * np.asarray(case["a_omega"], dtype=float),
                np.asarray(case["a_uz"], dtype=float),
            ]
        )
        latent = cp.Variable(9)
        problem = cp.Problem(
            cp.Minimize(cp.quad_form(latent - latent_nominal, weight)),
            [coefficients @ latent + 10.0 * float(case["h"]) >= 0],
        )
        problem.solve(solver=cp.OSQP)
        record: dict[str, Any] = {
            "name": case["name"],
            "status": problem.status,
            "nominal_residual": float(coefficients @ latent_nominal + 10.0 * case["h"]),
        }
        if latent.value is not None:
            solution = np.asarray(latent.value, dtype=float)
            world_velocity = rotation @ solution[:3]
            adjusted = np.hstack(
                [0.2 * world_velocity, 0.2 * solution[3:6], command[6]]
            )
            z = np.asarray(case["direction_z"], dtype=float)
            dz = (np.eye(3) - np.outer(z, z)) @ solution[6:9]
            next_z = z + 0.05 * dz
            next_z = next_z / np.linalg.norm(next_z)
            record.update(
                {
                    "latent_solution": solution.tolist(),
                    "adjusted_command": adjusted.tolist(),
                    "adjusted_residual": float(
                        coefficients @ solution + 10.0 * float(case["h"])
                    ),
                    "next_direction_z": next_z.tolist(),
                }
            )
        records.append(record)
    return {
        "cvxpy_version": cp.__version__,
        "numpy_version": np.__version__,
        "records": records,
    }


def _max_error(left: tuple[float, ...], right: list[float]) -> float:
    return max(abs(a - b) for a, b in zip(left, right))


def _audit() -> dict[str, Any]:
    if not AEGIS_PYTHON.is_file():
        raise RuntimeError(f"pinned AEGIS Python is missing: {AEGIS_PYTHON}")
    reference = subprocess.run(
        [str(AEGIS_PYTHON), str(Path(__file__).resolve()), "--cvxpy-reference"],
        input=json.dumps(CASES),
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )
    if reference.returncode != 0:
        raise RuntimeError(
            f"CVXPY reference failed ({reference.returncode}): {reference.stderr[-4000:]}"
        )
    cvxpy_result = json.loads(reference.stdout)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from proofalign.benchmark.aegis_cbf_filter import (
        AEGIS_FILTER_ID,
        AEGIS_FILTER_VERSION,
        AegisCBFConstraintV2,
        AegisCBFNoActionFilterV2,
        audit_aegis_cbf_source,
    )
    from proofalign.benchmark.safelibero_ctda_v2_no_dispatch import SafeLiberoCommandV2
    from proofalign.ctda import digest_text
    from proofalign.evidence_crypto import Ed25519EvidenceIssuer

    source = audit_aegis_cbf_source(
        AEGIS_ROOT,
        source_commit=SOURCE_COMMIT,
        source_tree=SOURCE_TREE,
    )
    signer = Ed25519EvidenceIssuer.generate_for_testing(AEGIS_FILTER_ID, AEGIS_FILTER_VERSION)
    runtime = AegisCBFNoActionFilterV2(source, signer, 10, 20)
    records = []
    maxima = {
        "latent_solution": 0.0,
        "adjusted_command": 0.0,
        "adjusted_residual": 0.0,
        "next_direction_z": 0.0,
    }
    for case, expected in zip(CASES, cvxpy_result["records"]):
        constraint = AegisCBFConstraintV2(
            source_identity_digest=source.source_identity_digest,
            state_snapshot_digest=digest_text("qp-parity-state"),
            safety_bundle_digest=digest_text("qp-parity-safety"),
            observed_at_ns=99,
            rotation_world_from_eef=tuple(case["rotation"]),
            direction_z=tuple(case["direction_z"]),
            a_v=tuple(case["a_v"]),
            a_omega=tuple(case["a_omega"]),
            a_uz=tuple(case["a_uz"]),
            h=case["h"],
            mu_row=tuple(case["mu_row"]),
            provenance_digest=digest_text(f"qp-parity:{case['name']}"),
        )
        actual = runtime.produce(
            SafeLiberoCommandV2(tuple(case["command"])), constraint, now_ns=100
        ).result
        if expected["name"] != case["name"]:
            raise RuntimeError("CVXPY parity case ordering changed")
        if expected["status"] in {"infeasible", "infeasible_inaccurate"}:
            if actual.solver_status != "infeasible_degenerate":
                raise RuntimeError(f"{case['name']}: infeasibility parity failed")
            records.append(
                {
                    "name": case["name"],
                    "cvxpy_status": expected["status"],
                    "analytical_status": actual.solver_status,
                    "parity": True,
                }
            )
            continue
        if expected["status"] not in {"optimal", "optimal_inaccurate"}:
            raise RuntimeError(f"{case['name']}: unexpected CVXPY status {expected['status']}")
        errors = {
            "latent_solution": _max_error(actual.latent_solution, expected["latent_solution"]),
            "adjusted_command": _max_error(actual.adjusted_command.values, expected["adjusted_command"]),
            "adjusted_residual": abs(
                actual.adjusted_constraint_residual - expected["adjusted_residual"]
            ),
            "next_direction_z": _max_error(
                actual.next_direction_z, expected["next_direction_z"]
            ),
        }
        for name, error in errors.items():
            maxima[name] = max(maxima[name], error)
        records.append(
            {
                "name": case["name"],
                "cvxpy_status": expected["status"],
                "analytical_status": actual.solver_status,
                "projection_active": actual.projection_active,
                "errors": errors,
                "parity": all(error <= 1e-5 for error in errors.values()),
            }
        )
    if not all(record["parity"] for record in records):
        raise RuntimeError(f"AEGIS QP parity tolerance exceeded: {records}")
    return {
        "schema": SCHEMA,
        "status": "parity_passed",
        "source_commit": SOURCE_COMMIT,
        "source_tree": SOURCE_TREE,
        "source_identity_digest": source.source_identity_digest,
        "cvxpy_version": cvxpy_result["cvxpy_version"],
        "numpy_version": cvxpy_result["numpy_version"],
        "solver": "OSQP",
        "case_count": len(records),
        "tolerance": 1e-5,
        "maximum_absolute_errors": maxima,
        "records": records,
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
    parser.add_argument("--cvxpy-reference", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.cvxpy_reference:
        cases = json.load(sys.stdin)
        print(json.dumps(_cvxpy_reference(cases), sort_keys=True))
        return 0
    print(json.dumps(_audit(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
