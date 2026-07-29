#!/usr/bin/env python3
"""Extract outcome-blind exact executed prefixes from frozen v11 traces."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


from proofalign.integrity_v4_models import command_digest  # noqa: E402


CORPUS_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_fixed_policy_prefix_v12_corpus.json"
)
FRESH15_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_fresh15_protocol.json"
)
SCALE45_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_joint_limit_containment_v11_clean_scale45_protocol.json"
)
SCHEMA = "proofalign.fixed-policy-prefix-v12-corpus.v1"


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(
        payload, indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def _trace_path(
    protocol: dict[str, Any],
    workload: dict[str, Any],
    *,
    tag: str,
) -> Path:
    root = REPO_ROOT / protocol["fresh_output_root"]
    run_id = (
        f"joint_limit_containment_v11_clean_{tag}_vla_only_"
        f"{workload['base_pair_id']}_"
        f"env{workload['environment_seed']}_"
        f"policy{workload['policy_seed']}"
    )
    return (
        root
        / run_id
        / "episodes"
        / (
            f"{workload['suite']}_task{workload['task_id']}_"
            f"init{workload['init_state_id']}.json"
        )
    )


def _extract(
    protocol: dict[str, Any],
    workload: dict[str, Any],
    *,
    tag: str,
) -> dict[str, Any]:
    path = _trace_path(protocol, workload, tag=tag)
    payload = _load(path)
    metadata = payload["metadata"]
    trace = payload["trace"]
    first_index = next(
        (
            index
            for index, row in enumerate(trace)
            if row.get("phase") == "policy"
            and isinstance(row.get("policy_call"), dict)
            and row["policy_call"].get("policy_call_index") == 0
        ),
        None,
    )
    if first_index is None:
        raise RuntimeError(f"trace lacks first policy call: {path}")
    rows = trace[first_index : first_index + 10]
    if (
        len(rows) != 10
        or any(row.get("phase") != "policy" for row in rows)
        or any(
            row.get("policy_call") is not None
            for row in rows[1:]
        )
    ):
        raise RuntimeError(
            f"trace lacks one contiguous executed prefix: {path}"
        )
    prefix = np.asarray(
        [row["action"] for row in rows], dtype=np.float64
    )
    if prefix.shape != (10, 7) or not np.isfinite(prefix).all():
        raise RuntimeError(f"trace prefix is malformed: {path}")
    if (
        metadata["benchmark_name"] != workload["suite"]
        or int(metadata["task_id"]) != int(workload["task_id"])
        or int(metadata["init_state_id"])
        != int(workload["init_state_id"])
        or int(metadata["seed"])
        != int(workload["environment_seed"])
        or int(metadata["policy_seed"])
        != int(workload["policy_seed"])
    ):
        raise RuntimeError(f"trace metadata binding differs: {path}")
    first_call = rows[0]["policy_call"]
    return {
        "base_pair_id": workload["base_pair_id"],
        "suite": workload["suite"],
        "task_id": int(workload["task_id"]),
        "init_state_id": int(workload["init_state_id"]),
        "trusted_instruction": workload["trusted_instruction"],
        "bddl_path": metadata["canonical_bddl_file"],
        "environment_seed": int(workload["environment_seed"]),
        "policy_seed": int(workload["policy_seed"]),
        "source_trace_path": str(path.relative_to(REPO_ROOT)),
        "source_trace_sha256": _sha256(path),
        "source_initial_state_sha256": metadata[
            "initial_state_sha256"
        ],
        "source_policy_chunk_sha256": first_call[
            "policy_action_chunk_sha256"
        ],
        "source_policy_chunk_shape": first_call[
            "policy_action_chunk_shape"
        ],
        "source_policy_chunk_dtype": first_call[
            "policy_action_chunk_dtype"
        ],
        "executed_prefix": prefix.tolist(),
        "executed_prefix_digest": command_digest(
            tuple(float(value) for value in prefix.reshape(-1))
        ),
        "executed_prefix_shape": [10, 7],
        "extraction_rule": (
            "Take the first ten contiguous phase=policy rows beginning at "
            "policy_call_index=0 and bind the exact recorded env.step "
            "action, not raw_action, reward, done, task_success, cost, or "
            "collision."
        ),
    }


def build_corpus() -> dict[str, Any]:
    fresh = _load(FRESH15_PROTOCOL)
    scale = _load(SCALE45_PROTOCOL)
    formal = [
        _extract(fresh, workload, tag="fresh15")
        for workload in fresh["workloads"]
    ]
    pilot_workloads = [
        next(
            workload
            for workload in scale["workloads"]
            if workload["suite"] == suite
        )
        for suite in (
            "obstacle_avoidance",
            "human_safety",
            "obstacle_avoidance_human",
        )
    ]
    pilot = [
        _extract(scale, workload, tag="scale45")
        for workload in pilot_workloads
    ]
    formal_ids = {row["base_pair_id"] for row in formal}
    if formal_ids & {row["base_pair_id"] for row in pilot}:
        raise RuntimeError("fixed-prefix pilot overlaps formal corpus")
    return {
        "schema": SCHEMA,
        "created_at": "2026-07-29T22:00:00+08:00",
        "source_protocols": {
            "formal": {
                "path": str(FRESH15_PROTOCOL.relative_to(REPO_ROOT)),
                "sha256": _sha256(FRESH15_PROTOCOL),
            },
            "pilot": {
                "path": str(SCALE45_PROTOCOL.relative_to(REPO_ROOT)),
                "sha256": _sha256(SCALE45_PROTOCOL),
            },
        },
        "formal_prefix_count": len(formal),
        "pilot_prefix_count": len(pilot),
        "formal_prefixes": formal,
        "pilot_prefixes": pilot,
        "outcome_fields_used_for_selection_or_extraction": [],
        "outcome_known_population": True,
        "claim_boundary": (
            "This corpus mechanically extracts exact actions that were "
            "already passed to env.step in frozen clean VLA-only traces. "
            "The source episode files contain outcomes, but extraction and "
            "population selection do not read reward, done, task_success, "
            "cost, collision, or terminal classification. The corpus is "
            "therefore suitable only for controller-shadow mechanics, not "
            "fresh policy inference, clean utility, or efficacy."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = _canonical(build_corpus())
    if args.check:
        if not CORPUS_PATH.is_file():
            raise SystemExit(f"missing: {CORPUS_PATH}")
        if CORPUS_PATH.read_text() != expected:
            raise SystemExit(f"stale: {CORPUS_PATH}")
        print(f"current: {CORPUS_PATH}")
        return 0
    if CORPUS_PATH.exists():
        raise SystemExit(f"refusing to overwrite corpus: {CORPUS_PATH}")
    CORPUS_PATH.write_text(expected)
    print(f"wrote: {CORPUS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
