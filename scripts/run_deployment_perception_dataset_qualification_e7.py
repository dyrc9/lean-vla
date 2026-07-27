#!/usr/bin/env python3
"""Qualify a frozen E7 outcome-blind perception dataset and its assets."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Iterator

import numpy as np
from PIL import Image, UnidentifiedImageError


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from prepare_deployment_perception_dataset_e7 import (  # noqa: E402
    SCHEMA_PATH,
    PerceptionDatasetError,
    build_schema,
    canonical_text,
    file_sha256,
    validate_manifest,
    validate_schema,
)


SCRIPT_PATH = Path(__file__).resolve()
EVIDENCE_NAME = "qualification.json"
CHECKSUMS_NAME = "SHA256SUMS"


class PerceptionQualificationError(RuntimeError):
    """Raised when E7 dataset qualification evidence is invalid."""


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PerceptionQualificationError(
            f"expected a JSON object: {path}"
        )
    return value


def _asset_records(
    snapshots: list[dict[str, Any]],
) -> Iterator[tuple[str, dict[str, Any], str]]:
    for index, snapshot in enumerate(snapshots):
        yield (
            f"snapshots[{index}].main_image",
            snapshot["main_image"],
            "rgb",
        )
        yield (
            f"snapshots[{index}].wrist_image",
            snapshot["wrist_image"],
            "rgb",
        )
        yield (
            f"snapshots[{index}].target.instance_mask",
            snapshot["target"]["instance_mask"],
            "mask",
        )
        yield (
            f"snapshots[{index}].destination.instance_mask",
            snapshot["destination"]["instance_mask"],
            "mask",
        )


def _resolve_asset(
    asset_root: Path,
    path_text: str,
    *,
    context: str,
) -> Path:
    relative = Path(path_text)
    if relative.is_absolute() or ".." in relative.parts:
        raise PerceptionQualificationError(
            f"{context} path must be relative and traversal-free"
        )
    root = asset_root.resolve()
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise PerceptionQualificationError(
            f"{context} path escapes the asset root"
        ) from exc
    if not resolved.is_file():
        raise PerceptionQualificationError(
            f"{context} asset is absent: {resolved}"
        )
    return resolved


def _decode_asset(
    path: Path,
    record: dict[str, Any],
    *,
    role: str,
    context: str,
) -> tuple[list[int], str]:
    try:
        with Image.open(path) as image:
            image.load()
            array = np.asarray(image)
    except (OSError, UnidentifiedImageError) as exc:
        raise PerceptionQualificationError(
            f"{context} is not a decodable image asset: {path}"
        ) from exc
    expected_shape = list(record["shape"])
    actual_shape = list(array.shape)
    actual_dtype = str(array.dtype)
    if actual_shape != expected_shape:
        raise PerceptionQualificationError(
            f"{context} shape mismatch: "
            f"declared={expected_shape}, actual={actual_shape}"
        )
    if actual_dtype != str(record["dtype"]):
        raise PerceptionQualificationError(
            f"{context} dtype mismatch: "
            f"declared={record['dtype']}, actual={actual_dtype}"
        )
    if role == "rgb" and (
        len(actual_shape) != 3
        or actual_shape[2] != 3
        or actual_dtype != "uint8"
    ):
        raise PerceptionQualificationError(
            f"{context} must decode as HxWx3 uint8 RGB"
        )
    if role == "mask" and (
        len(actual_shape) != 2 or actual_dtype != "bool"
    ):
        raise PerceptionQualificationError(
            f"{context} must decode as HxW bool mask"
        )
    return actual_shape, actual_dtype


def audit_assets(
    manifest: dict[str, Any],
    asset_root: Path,
) -> dict[str, Any]:
    if not asset_root.is_dir():
        raise PerceptionQualificationError(
            f"E7 asset root is absent: {asset_root}"
        )
    cache: dict[
        tuple[str, str, tuple[int, ...], str, str],
        dict[str, Any],
    ] = {}
    role_reference_counts = {"rgb": 0, "mask": 0}
    for context, record, role in _asset_records(
        manifest["snapshots"]
    ):
        role_reference_counts[role] += 1
        resolved = _resolve_asset(
            asset_root,
            str(record["path"]),
            context=context,
        )
        key = (
            str(resolved),
            str(record["sha256"]),
            tuple(record["shape"]),
            str(record["dtype"]),
            role,
        )
        if key in cache:
            continue
        actual_sha256 = file_sha256(resolved)
        if actual_sha256 != record["sha256"]:
            raise PerceptionQualificationError(
                f"{context} digest mismatch: {resolved}"
            )
        shape, dtype = _decode_asset(
            resolved,
            record,
            role=role,
            context=context,
        )
        cache[key] = {
            "path": str(resolved.relative_to(asset_root.resolve())),
            "sha256": actual_sha256,
            "shape": shape,
            "dtype": dtype,
            "role": role,
            "bytes": resolved.stat().st_size,
        }
    assets = sorted(
        cache.values(),
        key=lambda row: (
            row["path"],
            row["role"],
            row["sha256"],
        ),
    )
    return {
        "asset_root": str(asset_root.resolve()),
        "asset_reference_count": sum(role_reference_counts.values()),
        "role_reference_counts": role_reference_counts,
        "unique_asset_count": len(assets),
        "unique_asset_bytes": sum(row["bytes"] for row in assets),
        "all_paths_contained": True,
        "all_digests_match": True,
        "all_assets_decode": True,
        "all_shapes_and_dtypes_match": True,
        "assets": assets,
    }


def _identity_digest(
    snapshots: list[dict[str, Any]],
    *,
    split: str,
    field: str,
) -> str:
    values = sorted(
        {
            str(row[field])
            for row in snapshots
            if row["split"] == split
        }
    )
    return sha256(canonical_text(values).encode("utf-8")).hexdigest()


def build_evidence(
    manifest_path: Path,
    asset_root: Path,
) -> dict[str, Any]:
    schema = _read_object(SCHEMA_PATH)
    validate_schema(schema)
    if SCHEMA_PATH.read_text(
        encoding="utf-8"
    ) != canonical_text(build_schema()):
        raise PerceptionQualificationError(
            "E7 supervision contract is stale"
        )
    manifest = _read_object(manifest_path)
    if not str(manifest.get("dataset_id", "")).strip():
        raise PerceptionQualificationError(
            "E7 manifest dataset_id is empty"
        )
    validation = validate_manifest(
        manifest,
        schema,
        enforce_population=True,
        check_assets=False,
    )
    asset_audit = audit_assets(manifest, asset_root)
    snapshots = manifest["snapshots"]
    split_bindings = {
        split: {
            "case_ids_sha256": _identity_digest(
                snapshots,
                split=split,
                field="case_id",
            ),
            "trajectory_ids_sha256": _identity_digest(
                snapshots,
                split=split,
                field="trajectory_id",
            ),
            "scene_ids_sha256": _identity_digest(
                snapshots,
                split=split,
                field="scene_id",
            ),
            "snapshot_count": sum(
                row["split"] == split for row in snapshots
            ),
        }
        for split in schema["allowed_splits"]
    }
    return {
        "schema": (
            "proofalign.deployment-perception-dataset-"
            "qualification-e7.v1"
        ),
        "dataset_id": manifest["dataset_id"],
        "classification": (
            "deployment_perception_dataset_contract_qualified"
        ),
        "dataset_contract_qualified": True,
        "perception_model_qualified": False,
        "training_performed": False,
        "model_selected": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "outcomes_read": False,
        "schema_binding": {
            "path": str(SCHEMA_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(SCHEMA_PATH),
            "schema_id": schema["schema_id"],
        },
        "manifest_binding": {
            "path": str(manifest_path.resolve()),
            "sha256": file_sha256(manifest_path),
        },
        "runner_binding": {
            "path": str(SCRIPT_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(SCRIPT_PATH),
        },
        "validation": validation,
        "asset_audit": asset_audit,
        "split_bindings": split_bindings,
        "claim_boundary": (
            "This evidence qualifies only the frozen E7 dataset contract, "
            "asset bindings, population, and split isolation. It does not "
            "train or qualify a perception model, load a policy, create a "
            "simulator, dispatch actions, read outcomes, measure efficacy, "
            "or establish physical safety."
        ),
    }


def _evidence_paths(output_root: Path) -> tuple[Path, Path]:
    return (
        output_root / EVIDENCE_NAME,
        output_root / CHECKSUMS_NAME,
    )


def validate_evidence(
    manifest_path: Path,
    asset_root: Path,
    output_root: Path,
) -> None:
    evidence_path, checksums_path = _evidence_paths(output_root)
    expected = canonical_text(
        build_evidence(manifest_path, asset_root)
    )
    if evidence_path.read_text(encoding="utf-8") != expected:
        raise PerceptionQualificationError(
            f"E7 dataset qualification evidence is stale: {evidence_path}"
        )
    expected_checksum = (
        f"{file_sha256(evidence_path)}  {evidence_path.name}\n"
    )
    if checksums_path.read_text(
        encoding="utf-8"
    ) != expected_checksum:
        raise PerceptionQualificationError(
            "E7 dataset qualification checksum is stale"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-contract", action="store_true")
    mode.add_argument("--audit", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--asset-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.check_contract:
            schema = _read_object(SCHEMA_PATH)
            validate_schema(schema)
            if SCHEMA_PATH.read_text(
                encoding="utf-8"
            ) != canonical_text(build_schema()):
                raise PerceptionQualificationError(
                    "E7 supervision contract is stale"
                )
            print(
                "E7 dataset qualification runner is ready for a "
                "conforming manifest"
            )
            return 0
        if args.manifest is None or args.asset_root is None:
            raise PerceptionQualificationError(
                "--manifest and --asset-root are required"
            )
        if (args.write or args.check) and args.output_root is None:
            raise PerceptionQualificationError(
                "--output-root is required for --write/--check"
            )
        if args.check:
            validate_evidence(
                args.manifest,
                args.asset_root,
                args.output_root,
            )
            print(
                "E7 dataset qualification evidence is current: "
                f"{args.output_root / EVIDENCE_NAME}"
            )
            return 0
        evidence = build_evidence(
            args.manifest,
            args.asset_root,
        )
        if args.audit:
            print(
                json.dumps(
                    {
                        "classification": evidence["classification"],
                        "dataset_id": evidence["dataset_id"],
                        "validation": evidence["validation"],
                        "asset_audit": {
                            key: value
                            for key, value in evidence[
                                "asset_audit"
                            ].items()
                            if key != "assets"
                        },
                        "outcomes_read": False,
                    },
                    indent=2,
                )
            )
            return 0
        output_root = args.output_root
        if output_root.exists():
            raise PerceptionQualificationError(
                f"refusing to replace E7 output root: {output_root}"
            )
        evidence_path, checksums_path = _evidence_paths(
            output_root
        )
        output_root.mkdir(parents=True)
        evidence_path.write_text(
            canonical_text(evidence),
            encoding="utf-8",
        )
        checksums_path.write_text(
            f"{file_sha256(evidence_path)}  {evidence_path.name}\n",
            encoding="utf-8",
        )
        print(evidence_path)
        return 0
    except (
        KeyError,
        OSError,
        PerceptionDatasetError,
        PerceptionQualificationError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
