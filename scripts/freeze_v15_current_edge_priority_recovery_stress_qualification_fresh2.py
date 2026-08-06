#!/usr/bin/env python3
"""Freeze compatibility-only fresh2 recovery stress qualification."""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    file_sha256,
    load_json_object,
)
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_v15_current_edge_priority_recovery_stress_qualification_fresh2 as runner  # noqa: E402


FRESH1_PROTOCOL_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_protocol.json"
)
FRESH1_ABORT_PATH = (
    REPO_ROOT
    / "experiments"
    / "proofalign_predictive_virtual_brake_v15_current_edge_priority_"
    "recovery_stress_qualification_fresh1_abort.json"
)
OUTPUT_PATH = runner.DEFAULT_PROTOCOL
SELF_PATH = (
    REPO_ROOT
    / "scripts"
    / "freeze_v15_current_edge_priority_recovery_stress_qualification_fresh2.py"
)
SOURCE_PATHS = (
    "scripts/run_v15_current_edge_priority_recovery_stress_calibration.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_qualification.py",
    "scripts/run_v15_current_edge_priority_recovery_stress_qualification_fresh2.py",
    "scripts/freeze_v15_current_edge_priority_recovery_stress_qualification_fresh2.py",
    "tests/test_v15_current_edge_priority_recovery_stress_qualification_fresh1_abort.py",
    "tests/test_v15_current_edge_priority_recovery_stress_qualification_fresh2.py",
    "experiments/proofalign_predictive_virtual_brake_v15_current_edge_priority_recovery_stress_qualification_fresh1_abort.json",
)
PROTOCOL_ID = (
    "proofalign-predictive-virtual-brake-v15-2-current-edge-priority-"
    "recovery-stress-qualification-20260731-fresh2"
)
CREATED_AT = "2026-07-31T21:02:58+08:00"


class V15RecoveryStressQualificationFresh2FreezeError(RuntimeError):
    """Raised when the fresh2 retry cannot be frozen exactly."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise V15RecoveryStressQualificationFresh2FreezeError(
            completed.stderr.strip() or "git command failed"
        )
    return completed.stdout.strip()


def _binding(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise V15RecoveryStressQualificationFresh2FreezeError(
            f"fresh2 predecessor is absent: {path}"
        )
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": file_sha256(path),
    }


def build_protocol(
    *,
    created_at: str = CREATED_AT,
    source_commit: str | None = None,
) -> dict[str, Any]:
    if _git("status", "--porcelain=v1", "--untracked-files=normal"):
        raise V15RecoveryStressQualificationFresh2FreezeError(
            "worktree must be clean before fresh2 freeze"
        )
    source = load_json_object(FRESH1_PROTOCOL_PATH)
    abort = load_json_object(FRESH1_ABORT_PATH)
    fresh1_root = REPO_ROOT / str(source["fresh_output_root"])
    if (
        source.get("schema")
        != runner.predecessor.PROTOCOL_SCHEMA
        or abort.get("abort_classification")
        != (
            "v15_2_recovery_stress_qualification_fresh1_"
            "pre_evidence_analysis_abort"
        )
        or abort.get("integrity", {}).get(
            "qualification_metrics_observed"
        )
        is not False
        or abort.get("repair_scope_authorized", {}).get(
            "analysis_compatibility_aliases_only"
        )
        is not True
        or fresh1_root.exists()
    ):
        raise V15RecoveryStressQualificationFresh2FreezeError(
            "fresh1 abort differs from compatibility-only retry"
        )
    bound_commit = source_commit or _git("rev-parse", "HEAD")
    _git("merge-base", "--is-ancestor", bound_commit, "HEAD")
    protocol = deepcopy(source)
    protocol.update(
        {
            "schema": runner.PROTOCOL_SCHEMA,
            "protocol_id": PROTOCOL_ID,
            "status": runner.AUTHORIZED_STATUS,
            "created_at": created_at,
            "stage": (
                "held_out_outcome_blind_recovery_stress_"
                "qualification_fresh2_compatibility_retry"
            ),
            "fresh_output_root": (
                "results/proofalign_predictive_virtual_brake_v15_2_"
                "recovery_stress_qualification_20260731_fresh2"
            ),
            "required_bindings": [
                _binding(FRESH1_PROTOCOL_PATH),
                _binding(FRESH1_ABORT_PATH),
            ],
            "selection": {
                **source["selection"],
                "fresh1_aborted_before_evidence": True,
                "fresh1_qualification_metrics_observed": False,
                "population_reused_exactly": True,
                "random_seed_reused_exactly": True,
            },
            "design": {
                **source["design"],
                "fresh2_change": (
                    "supply the legacy selected-floor and 50-ms control-"
                    "period aliases required by the reused calibration "
                    "analysis layer"
                ),
                "mechanism_parameters_changed": False,
                "registered_gates_changed": False,
                "registered_thresholds_changed": False,
            },
            "fresh1_abort": {
                "path": FRESH1_ABORT_PATH.relative_to(
                    REPO_ROOT
                ).as_posix(),
                "sha256": file_sha256(FRESH1_ABORT_PATH),
                "analysis_compatibility_aliases_only": True,
                "qualification_metrics_observed": False,
            },
            "source": {
                "repository_commit": bound_commit,
                "repository_tree": _git(
                    "rev-parse", f"{bound_commit}^{{tree}}"
                ),
                "sha256": {
                    relative: file_sha256(REPO_ROOT / relative)
                    for relative in SOURCE_PATHS
                },
                "freezer": SELF_PATH.relative_to(REPO_ROOT).as_posix(),
                "freezer_sha256": file_sha256(SELF_PATH),
            },
            "claim_boundary": (
                source["claim_boundary"]
                + " Fresh1 created no evidence and exposed no qualification "
                "metric. Fresh2 changes only two internal analysis aliases; "
                "the population, seed, mechanism, registered gates, and "
                "thresholds are byte-identical to fresh1."
            ),
        }
    )
    if (
        protocol["environments"] != source["environments"]
        or protocol["gates"] != source["gates"]
        or protocol["execution_authorization"]
        != source["execution_authorization"]
    ):
        raise V15RecoveryStressQualificationFresh2FreezeError(
            "fresh2 changed population, gates, or authorization"
        )
    return protocol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--created-at", default=CREATED_AT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    retained = (
        load_json_object(args.output)
        if args.check and args.output.is_file()
        else None
    )
    protocol = build_protocol(
        created_at=(
            str(retained["created_at"])
            if retained is not None
            else args.created_at
        ),
        source_commit=(
            str(retained["source"]["repository_commit"])
            if retained is not None
            else None
        ),
    )
    text = canonical_text(protocol)
    if args.check:
        if (
            not args.output.is_file()
            or args.output.read_text(encoding="utf-8") != text
        ):
            raise V15RecoveryStressQualificationFresh2FreezeError(
                f"fresh2 protocol is stale: {args.output}"
            )
        print(f"current: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
