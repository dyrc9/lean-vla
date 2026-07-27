#!/usr/bin/env python3
"""Validate and analyze a future terminal v4 four-arm ledger."""

from __future__ import annotations

import argparse
from pathlib import Path
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
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    ANALYSIS_SCHEMA,
    ARM_ORDER,
    LATENCY_FIELDS,
    LEDGER_ROW_SCHEMA,
    RISK_FIELDS,
    build_terminal_analysis,
    canonical_text,
    read_ledger,
    validate_successor_protocol,
    verify_episode_artifacts,
)


DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_successor_protocol.json"
)
DEFAULT_CONTRACT = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_analysis_contract.json"
)


class FourArmV4AnalysisError(RuntimeError):
    """Raised when terminal four-arm analysis must stop fail-closed."""


def build_contract_evidence(
    protocol_path: Path = DEFAULT_PROTOCOL,
) -> dict[str, Any]:
    protocol = load_json_object(protocol_path)
    validate_successor_protocol(
        protocol,
        repo_root=REPO_ROOT,
    )
    return {
        "schema": "proofalign.four-arm-v4-analysis-contract.v1",
        "protocol_id": protocol["protocol_id"],
        "protocol_path": protocol_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "protocol_sha256": file_sha256(protocol_path),
        "terminal_output_schema": ANALYSIS_SCHEMA,
        "ledger_row_schema": LEDGER_ROW_SCHEMA,
        "expected_closed_loop_episode_count_per_stage": 480,
        "expected_unit_count": 120,
        "expected_base_pair_cluster_count": 60,
        "arms": list(ARM_ORDER),
        "risk_fields": list(RISK_FIELDS),
        "latency_fields": list(LATENCY_FIELDS),
        "clean_gate": protocol["clean_gate"],
        "attacked_endpoints": protocol["attacked_endpoints"],
        "analysis": protocol["analysis"],
        "conservative_missing_rule": (
            "missing_or_invalid_arm_is_task_failure_unsafe_deadlock_unknown"
        ),
        "clean_ledger_required_for_attacked_analysis": True,
        "outcomes_observed": False,
        "policy_loaded": False,
        "simulator_created": False,
        "actions_dispatched": False,
        "execution_authorized": False,
        "claim_boundary": (
            "This artifact freezes terminal schemas and statistical methods "
            "only. It contains no experimental row or outcome and authorizes "
            "no execution."
        ),
    }


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FourArmV4AnalysisError(
            f"refusing to overwrite existing analysis output: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol", type=Path, default=DEFAULT_PROTOCOL
    )
    parser.add_argument(
        "--contract", type=Path, default=DEFAULT_CONTRACT
    )
    parser.add_argument("--freeze-contract", action="store_true")
    parser.add_argument("--check-contract", action="store_true")
    parser.add_argument(
        "--stage",
        choices=(
            "B_clean_closed_loop",
            "C_attacked_closed_loop",
        ),
    )
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--clean-ledger", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--terminal", action="store_true")
    args = parser.parse_args(argv)

    protocol_path = args.protocol.resolve()
    contract = build_contract_evidence(protocol_path)
    if args.freeze_contract:
        args.contract.parent.mkdir(parents=True, exist_ok=True)
        args.contract.write_text(
            canonical_text(contract),
            encoding="utf-8",
        )
        print(args.contract)
        return 0
    if args.check_contract:
        if not args.contract.is_file():
            raise FourArmV4AnalysisError(
                f"analysis contract is absent: {args.contract}"
            )
        if args.contract.read_text(
            encoding="utf-8"
        ) != canonical_text(contract):
            raise FourArmV4AnalysisError(
                f"analysis contract is stale: {args.contract}"
            )
        print(f"current: {args.contract}")
        return 0

    if args.stage is None or args.ledger is None or args.output is None:
        parser.error(
            "terminal analysis requires --stage, --ledger, and --output"
        )
    protocol = load_json_object(protocol_path)
    confirmatory = validate_successor_protocol(
        protocol,
        repo_root=REPO_ROOT,
    )
    rows = read_ledger(args.ledger)
    verify_episode_artifacts(
        rows,
        artifact_root=args.ledger.resolve().parent,
    )
    clean_rows = None
    if args.stage == "C_attacked_closed_loop":
        if args.clean_ledger is None:
            parser.error(
                "attacked analysis requires --clean-ledger"
            )
        clean_rows = read_ledger(args.clean_ledger)
        verify_episode_artifacts(
            clean_rows,
            artifact_root=args.clean_ledger.resolve().parent,
        )
    analysis = build_terminal_analysis(
        protocol,
        confirmatory=confirmatory,
        stage=args.stage,
        rows=rows,
        clean_rows=clean_rows,
        terminal=args.terminal,
        episode_artifacts_verified=True,
        clean_episode_artifacts_verified=(
            args.stage == "C_attacked_closed_loop"
        ),
    )
    _write_new(args.output, canonical_text(analysis))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
