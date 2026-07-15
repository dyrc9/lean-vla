#!/usr/bin/env python3
"""Freeze and inspect official SAFE/FIPER reproduction assets.

Pickle is executable.  The inspection commands refuse to unpickle anything
unless ``--trust-pickle`` is supplied explicitly.  Only use that switch for
artifacts downloaded from the frozen upstream locations in the protocols.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import pickle
import re
import sys
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SAFE_PROTOCOL = REPO_ROOT / "experiments" / "safe_r0_protocol.json"
FIPER_PROTOCOL = REPO_ROOT / "experiments" / "fiper_r0_protocol.json"


class AssetError(ValueError):
    """Raised when an asset does not satisfy the frozen protocol."""


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssetError(f"expected JSON object: {path}")
    return payload


def file_sha256(path: Path, *, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def tree_manifest(root: Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise AssetError(f"tree root is not a directory: {root}")
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append({"path": relative, "kind": "symlink", "target": os.readlink(path)})
        elif path.is_file():
            entries.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size": path.stat().st_size,
                    "sha256": file_sha256(path),
                }
            )
    frozen = {"schema": "proofalign.tree-manifest.v1", "root": str(root), "entries": entries}
    frozen["tree_sha256"] = canonical_digest(entries)
    frozen["file_count"] = sum(item["kind"] == "file" for item in entries)
    frozen["total_file_bytes"] = sum(item.get("size", 0) for item in entries)
    return frozen


def verify_tree_manifest(path: Path) -> dict[str, Any]:
    expected = load_json(path)
    if expected.get("schema") != "proofalign.tree-manifest.v1":
        raise AssetError(f"unsupported tree manifest schema: {path}")
    observed = tree_manifest(Path(expected["root"]))
    if observed["entries"] != expected.get("entries"):
        raise AssetError(f"tree differs from frozen manifest: {path}")
    return observed


def pickle_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".pkl", ".pickle"})


def trusted_pickle_load(path: Path, *, trust_pickle: bool) -> Any:
    if not trust_pickle:
        raise AssetError(
            "refusing to load executable pickle data; verify the official download and pass --trust-pickle"
        )
    with path.open("rb") as handle:
        return pickle.load(handle)  # noqa: S301 - guarded by the explicit trust boundary above.


def shape_of(value: Any) -> list[int] | None:
    shape = getattr(value, "shape", None)
    if shape is not None:
        try:
            return [int(item) for item in shape]
        except (TypeError, ValueError):
            return None
    if isinstance(value, (list, tuple)):
        if not value:
            return [0]
        child_shapes = {tuple(item) for child in value if (item := shape_of(child)) is not None}
        if len(child_shapes) == 1:
            return [len(value), *next(iter(child_shapes))]
    return None


def inspect_safe_rollouts(
    rollout_root: Path,
    *,
    trust_pickle: bool,
    expected_episodes: int | None = None,
) -> dict[str, Any]:
    rollout_root = rollout_root.expanduser().resolve()
    env_paths = pickle_files(rollout_root / "env_records")
    policy_paths = sorted((rollout_root / "policy_records").glob("*meta.pkl"))
    required_env = {
        "task_suite_name",
        "task_id",
        "task_description",
        "episode_idx",
        "episode_success",
        "model_infer_times",
        "replan_steps",
    }
    episode_records: list[dict[str, Any]] = []
    total_policy_calls = 0
    successes = 0
    failures = 0
    for path in env_paths:
        payload = trusted_pickle_load(path, trust_pickle=trust_pickle)
        if not isinstance(payload, dict):
            raise AssetError(f"SAFE env record is not a dict: {path}")
        missing = sorted(required_env - payload.keys())
        if missing:
            raise AssetError(f"SAFE env record missing {missing}: {path}")
        calls = payload["model_infer_times"]
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise AssetError(f"invalid model_infer_times in {path}: {calls!r}")
        success = bool(payload["episode_success"])
        successes += int(success)
        failures += int(not success)
        total_policy_calls += calls
        episode_records.append(
            {
                "path": path.name,
                "task_id": int(payload["task_id"]),
                "episode_idx": int(payload["episode_idx"]),
                "success": success,
                "policy_calls": calls,
                "replan_steps": int(payload["replan_steps"]),
            }
        )
    if expected_episodes is not None and len(env_paths) != expected_episodes:
        raise AssetError(f"SAFE has {len(env_paths)} env records; expected {expected_episodes}")
    if len(policy_paths) != total_policy_calls:
        raise AssetError(
            f"SAFE has {len(policy_paths)} policy records but env records declare {total_policy_calls} calls"
        )
    feature_shapes: set[tuple[int, ...]] = set()
    action_shapes: set[tuple[int, ...]] = set()
    for path in policy_paths:
        payload = trusted_pickle_load(path, trust_pickle=trust_pickle)
        if not isinstance(payload, dict) or not {"pre_velocity", "actions"} <= payload.keys():
            raise AssetError(f"SAFE policy record lacks pre_velocity/actions: {path}")
        feature_shape = shape_of(payload["pre_velocity"])
        action_shape = shape_of(payload["actions"])
        if feature_shape is None or len(feature_shape) != 3:
            raise AssetError(f"SAFE pre_velocity is not rank 3: {path} shape={feature_shape}")
        if action_shape is None or len(action_shape) != 2:
            raise AssetError(f"SAFE actions is not rank 2: {path} shape={action_shape}")
        feature_shapes.add(tuple(feature_shape))
        action_shapes.add(tuple(action_shape))
    if env_paths and (successes == 0 or failures == 0):
        raise AssetError("SAFE detector data must contain both successful and failed rollouts")
    return {
        "schema": "proofalign.safe-rollout-inspection.v1",
        "root": str(rollout_root),
        "trusted_pickle": trust_pickle,
        "valid": True,
        "env_record_count": len(env_paths),
        "policy_record_count": len(policy_paths),
        "declared_policy_call_count": total_policy_calls,
        "success_count": successes,
        "failure_count": failures,
        "pre_velocity_shapes": [list(item) for item in sorted(feature_shapes)],
        "action_shapes": [list(item) for item in sorted(action_shapes)],
        "episodes": episode_records,
    }


def _filename_success(path: Path) -> bool:
    name = path.name.lower()
    if "success" in name or "_s_" in name:
        return True
    if "failure" in name or "_f_" in name:
        return False
    # This mirrors FIPER's upstream fallback for filenames without a label.
    return True


def _fiper_rollout(payload: Any, path: Path, split: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # Match TaskManager._convert_raw_rollouts: filename labels are the fallback,
    # and embedded metadata overrides them when present.
    metadata: dict[str, Any] = {
        "successful": _filename_success(path),
        "rollout_subtype": "id" if split == "calibration" else "ood",
    }
    if isinstance(payload, dict):
        if not isinstance(payload.get("metadata", {}), dict) or not isinstance(payload.get("rollout"), list):
            raise AssetError(f"invalid FIPER dict rollout: {path}")
        metadata.update(payload.get("metadata", {}))
        rollout = payload["rollout"]
    elif isinstance(payload, list) and payload and isinstance(payload[0], dict):
        rollout = payload
        if payload[0].get("metadata"):
            embedded = payload[0]["metadata"]
            if isinstance(embedded, dict):
                metadata.update(embedded)
            else:
                metadata.update(payload[0])
            rollout = payload[1:]
    else:
        raise AssetError(f"invalid FIPER top-level rollout: {path}")
    if not rollout or not all(isinstance(step, dict) for step in rollout):
        raise AssetError(f"empty or invalid FIPER step sequence: {path}")
    return metadata, rollout


def inspect_fiper_rollouts(
    data_root: Path,
    *,
    tasks: Iterable[str],
    trust_pickle: bool,
    minimum_files: int = 5,
) -> dict[str, Any]:
    data_root = data_root.expanduser().resolve()
    task_records: dict[str, Any] = {}
    for task in tasks:
        split_records: dict[str, Any] = {}
        for split in ("calibration", "test"):
            paths = pickle_files(data_root / task / "rollouts" / split)
            if len(paths) < minimum_files:
                raise AssetError(f"FIPER {task}/{split} has {len(paths)} files; expected at least {minimum_files}")
            successes = 0
            failures = 0
            subtype_counts: dict[str, int] = {}
            step_key_sets: set[tuple[str, ...]] = set()
            obs_shapes: set[tuple[int, ...]] = set()
            action_shapes: set[tuple[int, ...]] = set()
            for path in paths:
                payload = trusted_pickle_load(path, trust_pickle=trust_pickle)
                metadata, rollout = _fiper_rollout(payload, path, split)
                success = bool(metadata["successful"])
                successes += int(success)
                failures += int(not success)
                subtype = str(metadata["rollout_subtype"])
                subtype_counts[subtype] = subtype_counts.get(subtype, 0) + 1
                for step in rollout:
                    missing = {"obs_embedding", "action_pred"} - step.keys()
                    if missing:
                        raise AssetError(f"FIPER step missing {sorted(missing)}: {path}")
                    step_key_sets.add(tuple(sorted(step.keys())))
                    obs_shape = shape_of(step["obs_embedding"])
                    action_shape = shape_of(step["action_pred"])
                    if obs_shape is not None:
                        obs_shapes.add(tuple(obs_shape))
                    if action_shape is not None:
                        action_shapes.add(tuple(action_shape))
            if split == "calibration" and not successes:
                raise AssetError(f"FIPER {task} calibration has no successful rollouts for threshold fitting")
            if split == "test" and (not successes or not failures):
                raise AssetError(f"FIPER {task} test must contain success and failure labels")
            split_records[split] = {
                "file_count": len(paths),
                "success_count": successes,
                "failure_count": failures,
                "threshold_eligible_success_count": successes if split == "calibration" else None,
                "rollout_subtypes": subtype_counts,
                "step_key_sets": [list(item) for item in sorted(step_key_sets)],
                "obs_embedding_shapes": [list(item) for item in sorted(obs_shapes)],
                "action_pred_shapes": [list(item) for item in sorted(action_shapes)],
            }
        task_records[task] = split_records
    return {
        "schema": "proofalign.fiper-rollout-inspection.v1",
        "root": str(data_root),
        "trusted_pickle": trust_pickle,
        "valid": True,
        "tasks": task_records,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest = subparsers.add_parser("manifest", help="Hash every file below a directory.")
    manifest.add_argument("root", type=Path)
    manifest.add_argument("--output", type=Path, required=True)

    verify = subparsers.add_parser("verify-manifest", help="Re-hash a frozen tree manifest.")
    verify.add_argument("manifest", type=Path)

    safe = subparsers.add_parser("inspect-safe", help="Validate official SAFE rollout pickles.")
    safe.add_argument("rollout_root", type=Path)
    safe.add_argument("--protocol", type=Path, default=SAFE_PROTOCOL)
    safe.add_argument("--trust-pickle", action="store_true")
    safe.add_argument("--output", type=Path, required=True)

    fiper = subparsers.add_parser("inspect-fiper", help="Validate official FIPER rollout pickles.")
    fiper.add_argument("data_root", type=Path)
    fiper.add_argument("--protocol", type=Path, default=FIPER_PROTOCOL)
    fiper.add_argument("--trust-pickle", action="store_true")
    fiper.add_argument("--output", type=Path, required=True)

    archive = subparsers.add_parser("archive-digest", help="Hash a downloaded upstream archive.")
    archive.add_argument("archive", type=Path)
    archive.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "manifest":
            report = tree_manifest(args.root)
            write_json(args.output, report)
        elif args.command == "verify-manifest":
            report = verify_tree_manifest(args.manifest)
        elif args.command == "inspect-safe":
            protocol = load_json(args.protocol)
            report = inspect_safe_rollouts(
                args.rollout_root,
                trust_pickle=args.trust_pickle,
                expected_episodes=int(protocol["rollout_generation"]["expected_episode_count"]),
            )
            write_json(args.output, report)
        elif args.command == "inspect-fiper":
            protocol = load_json(args.protocol)
            report = inspect_fiper_rollouts(
                args.data_root,
                tasks=protocol["dataset"]["tasks_in_order"],
                trust_pickle=args.trust_pickle,
                minimum_files=int(protocol["dataset"]["minimum_files_per_task_split_from_upstream_code"]),
            )
            write_json(args.output, report)
        else:
            archive = args.archive.expanduser().resolve()
            if not archive.is_file():
                raise AssetError(f"archive not found: {archive}")
            report = {
                "schema": "proofalign.archive-digest.v1",
                "path": str(archive),
                "size": archive.stat().st_size,
                "sha256": file_sha256(archive),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            write_json(args.output, report)
    except (AssetError, OSError, json.JSONDecodeError, pickle.UnpicklingError) as exc:
        print(json.dumps({"valid": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
