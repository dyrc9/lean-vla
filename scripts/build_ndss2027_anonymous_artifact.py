#!/usr/bin/env python3
"""Audit and build a deterministic, path-scrubbed NDSS 2027 artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

PROTOCOLS = (
    Path("experiments/saber_confirmatory_preregistration_v1.json"),
    Path("experiments/saber_confirmatory_producer_m2_authorized_protocol.json"),
    Path("experiments/saber_confirmatory_victim_m2_authorized_protocol.json"),
    Path(
        "experiments/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_task_utility_qualification_fresh1_protocol.json"
    ),
    Path(
        "experiments/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_attacked_task_utility_"
        "qualification_fresh1_protocol.json"
    ),
    Path(
        "experiments/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_attacked_task_utility_"
        "qualification_fresh2_protocol.json"
    ),
)

FINAL_RESULT_ROOTS = (
    Path(
        "results/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_task_utility_qualification_20260807_fresh1"
    ),
    Path(
        "results/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_attacked_task_utility_qualification_"
        "20260807_fresh1"
    ),
    Path(
        "results/proofalign_predictive_virtual_brake_v15_14_"
        "unified_force_envelope_attacked_task_utility_qualification_"
        "20260807_fresh2"
    ),
)

M2_RESULT_ROOTS = (
    Path("results/saber_confirmatory_producer_m2_20260727_fresh1"),
    Path("results/saber_confirmatory_victim_m2_20260727_fresh1"),
)

ALWAYS_INCLUDE = (
    Path("README.md"),
    Path("artifact/README.md"),
    Path("docs/current_status_and_roadmap.md"),
    Path("docs/paper/ndss2027_claim_evidence.md"),
    Path("docs/paper/v15_14_final_four_arm_results.md"),
    Path("scripts/audit_ndss2027_paper_claims.py"),
    Path("scripts/build_ndss2027_anonymous_artifact.py"),
)

SOURCE_TREES = (
    Path("lean"),
    Path("docs/paper/overleaf"),
)

EXCLUDED_PARTS = {".git", ".lake", "build", "tmp", "__pycache__"}
TEXT_SUFFIXES = {
    "",
    ".bib",
    ".json",
    ".jsonl",
    ".lean",
    ".md",
    ".py",
    ".rb",
    ".tex",
    ".txt",
    ".yaml",
    ".yml",
}

REPO_PREFIX = re.compile(
    r"/(?:home|Users)/[^/\s\"']+/(?:agent/)?lean-vla"
)
CHECKPOINT_PREFIX = re.compile(
    r"/data\d+/[^/\s\"']+/libero_safety_models/pi05_libero_safety"
)
UNHANDLED_LOCAL_PATH = re.compile(
    r"/(?:home|Users|data\d+)/[^\s\"']+"
)


class ArtifactError(RuntimeError):
    pass


def load_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ArtifactError(f"expected JSON object: {path}")
    return value


def file_sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(raw: str | Path) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise ArtifactError(f"unsafe artifact path: {path}")
    return path


def iter_tree(relative_root: Path) -> Iterable[Path]:
    absolute_root = ROOT / relative_root
    if not absolute_root.is_dir():
        return
    for path in sorted(absolute_root.rglob("*")):
        relative = path.relative_to(ROOT)
        if path.is_file() and not (EXCLUDED_PARTS & set(relative.parts)):
            yield relative


def protocol_paths(protocol_path: Path) -> tuple[set[Path], set[Path]]:
    protocol = load_object(ROOT / protocol_path)
    included: set[Path] = {protocol_path}
    external: set[Path] = set()
    source = protocol.get("source") or {}
    sha_rows = source.get("sha256") or {}
    candidates = list(sha_rows.keys())
    candidates.extend(
        row["path"]
        for row in protocol.get("required_bindings", [])
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    )
    for raw in candidates:
        relative = safe_relative(str(raw))
        if relative.parts and relative.parts[0] == "external":
            external.add(relative)
        else:
            included.add(relative)
    return included, external


def collect_paths(allow_incomplete_m2: bool) -> tuple[list[Path], list[Path], list[Path]]:
    included = set(ALWAYS_INCLUDE)
    external: set[Path] = set()
    missing: set[Path] = set()

    for protocol_path in PROTOCOLS:
        if not (ROOT / protocol_path).is_file():
            missing.add(protocol_path)
            continue
        protocol_included, protocol_external = protocol_paths(protocol_path)
        included.update(protocol_included)
        external.update(protocol_external)

    for tree in SOURCE_TREES:
        included.update(iter_tree(tree))
    for tree in FINAL_RESULT_ROOTS:
        if not (ROOT / tree).is_dir():
            missing.add(tree)
        else:
            included.update(iter_tree(tree))

    for tree in M2_RESULT_ROOTS:
        if not (ROOT / tree).is_dir():
            missing.add(tree)
        else:
            included.update(iter_tree(tree))

    present: list[Path] = []
    for relative in sorted(included):
        absolute = ROOT / relative
        if absolute.is_file():
            present.append(relative)
        elif not (relative.parts and relative.parts[0] == "external"):
            missing.add(relative)

    if missing and not allow_incomplete_m2:
        rendered = "\n".join(f"  - {path}" for path in sorted(missing))
        raise ArtifactError(f"required artifact inputs are missing:\n{rendered}")
    non_m2_missing = [
        path
        for path in missing
        if not any(path == root or root in path.parents for root in M2_RESULT_ROOTS)
    ]
    if non_m2_missing:
        rendered = "\n".join(f"  - {path}" for path in sorted(non_m2_missing))
        raise ArtifactError(f"non-M2 artifact inputs are missing:\n{rendered}")
    return present, sorted(external), sorted(missing)


def redact(relative: Path, data: bytes) -> tuple[bytes, dict[str, int]]:
    if relative.suffix.lower() not in TEXT_SUFFIXES and relative.name not in {
        "SHA256SUMS",
        "lean-toolchain",
    }:
        return data, {}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data, {}
    text, repo_count = REPO_PREFIX.subn("${REPO_ROOT}", text)
    text, checkpoint_count = CHECKPOINT_PREFIX.subn("${PI05_CHECKPOINT}", text)
    unhandled = sorted(set(UNHANDLED_LOCAL_PATH.findall(text)))
    if unhandled:
        sample = ", ".join(unhandled[:3])
        raise ArtifactError(f"unhandled local path in {relative}: {sample}")
    counts = {
        key: value
        for key, value in {
            "repo_prefix": repo_count,
            "checkpoint_prefix": checkpoint_count,
        }.items()
        if value
    }
    return text.encode("utf-8"), counts


def packaged_relative(relative: Path) -> Path:
    if relative.name == "SHA256SUMS" and relative.parts[0] == "results":
        return relative.with_name("SHA256SUMS.frozen")
    return relative


def audit_files(paths: list[Path]) -> tuple[list[dict], int, int]:
    rows: list[dict] = []
    source_bytes = 0
    packaged_bytes = 0
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        transformed, counts = redact(relative, data)
        rows.append(
            {
                "source_path": relative.as_posix(),
                "artifact_path": packaged_relative(relative).as_posix(),
                "source_sha256": file_sha256_bytes(data),
                "artifact_sha256": file_sha256_bytes(transformed),
                "source_bytes": len(data),
                "artifact_bytes": len(transformed),
                "redactions": counts,
            }
        )
        source_bytes += len(data)
        packaged_bytes += len(transformed)
    return rows, source_bytes, packaged_bytes


def write_package(output: Path, paths: list[Path], rows: list[dict], external: list[Path]) -> None:
    if output.exists():
        raise ArtifactError(f"refusing to overwrite existing output: {output}")
    resolved = output.resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        raise ArtifactError("artifact output must be outside the source repository")
    output.mkdir(parents=True)

    by_source = {row["source_path"]: row for row in rows}
    for relative in paths:
        data = (ROOT / relative).read_bytes()
        transformed, _ = redact(relative, data)
        destination = output / packaged_relative(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(transformed)

    map_payload = {
        "schema": "proofalign.ndss2027-anonymous-artifact-redaction-map.v1",
        "redaction_scope": "recognized local path prefixes only",
        "files": rows,
        "external_dependencies_not_redistributed": [path.as_posix() for path in external],
    }
    map_bytes = (json.dumps(map_payload, indent=2, sort_keys=True) + "\n").encode()
    (output / "REDACTION_MAP.json").write_bytes(map_bytes)

    checksum_rows = []
    for path in sorted(p for p in output.rglob("*") if p.is_file()):
        relative = path.relative_to(output)
        if relative == Path("SHA256SUMS"):
            continue
        checksum_rows.append(f"{file_sha256_bytes(path.read_bytes())}  {relative.as_posix()}")
    (output / "SHA256SUMS").write_text("\n".join(checksum_rows) + "\n", encoding="utf-8")

    if len(by_source) != len(paths):
        raise ArtifactError("internal artifact row/path count mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-incomplete-m2", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.check_only and args.output is None:
        parser.error("provide --check-only or --output")
    if args.check_only and args.output is not None:
        parser.error("--check-only and --output are mutually exclusive")
    if args.output is not None and args.allow_incomplete_m2:
        parser.error("a release artifact cannot be built with incomplete M2 inputs")

    paths, external, missing = collect_paths(args.allow_incomplete_m2)
    rows, source_bytes, packaged_bytes = audit_files(paths)
    redacted_files = sum(bool(row["redactions"]) for row in rows)
    redaction_count = sum(sum(row["redactions"].values()) for row in rows)

    if args.output is not None:
        write_package(args.output, paths, rows, external)

    status = "PARTIAL" if missing else "READY"
    print(f"NDSS 2027 anonymous artifact audit: {status}")
    print(f"- files: {len(paths)}")
    print(f"- source bytes: {source_bytes}")
    print(f"- packaged bytes: {packaged_bytes}")
    print(f"- redacted files/occurrences: {redacted_files}/{redaction_count}")
    print(f"- external pinned paths not redistributed: {len(external)}")
    if missing:
        print("- missing M2 inputs:")
        for path in missing:
            print(f"  - {path}")
    if args.output is not None:
        print(f"- output: {args.output.resolve()}")


if __name__ == "__main__":
    try:
        main()
    except ArtifactError as error:
        raise SystemExit(f"artifact audit failed: {error}")
