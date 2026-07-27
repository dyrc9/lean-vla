#!/usr/bin/env python3
"""Export or validate dispatch-free typed proposal traces for Stage A.

This exporter never loads a simulator or policy and never dispatches a command.
It accepts only a complete typed-proposal source whose proposal adapter file and
digest are bound by the four-arm M1 protocol.  The current M1 protocol leaves
that adapter binding empty, so export fails closed while dry-run and validation
remain available.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    FIXED_TRACE_BUNDLE_SCHEMA,
    ConfirmatoryContractError,
    file_sha256,
    load_json_object,
    validate_confirmatory_preregistration,
    validate_fixed_trace_bundle,
    validate_fixed_trace_results,
    validate_four_arm_preregistration,
)
from scripts import saber_io  # noqa: E402


FOUR_ARM_EXECUTION_SCHEMA = "proofalign.four-arm-execution-protocol.v1"
TYPED_TRACE_SOURCE_SCHEMA = "proofalign.typed-action-assessment-traces.v3"
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_four_arm_m1_protocol.json"
DEFAULT_OUTPUT = (
    REPO_ROOT / "results" / "proofalign_fixed_trace_p1_20260724_fresh1.json"
)


class FixedTraceExportError(RuntimeError):
    """Raised when fixed-trace export cannot preserve its frozen bindings."""


def validate_protocol(
    protocol: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if protocol.get("schema") != FOUR_ARM_EXECUTION_SCHEMA:
        raise FixedTraceExportError("unexpected four-arm execution schema")
    if protocol.get("protocol_status") != (
        "m1_implementation_frozen_execution_not_authorized"
    ):
        raise FixedTraceExportError("four-arm M1 protocol status changed")
    dependencies = protocol.get("preregistrations")
    if not isinstance(dependencies, dict):
        raise FixedTraceExportError("four-arm preregistration bindings are missing")
    confirm_path = REPO_ROOT / dependencies["confirmatory"]["path"]
    four_arm_path = REPO_ROOT / dependencies["four_arm"]["path"]
    confirmatory = load_json_object(confirm_path)
    four_arm = load_json_object(four_arm_path)
    validate_confirmatory_preregistration(confirmatory)
    if file_sha256(confirm_path) != dependencies["confirmatory"]["sha256"]:
        raise FixedTraceExportError("confirmatory preregistration digest differs")
    if file_sha256(four_arm_path) != dependencies["four_arm"]["sha256"]:
        raise FixedTraceExportError("four-arm preregistration digest differs")
    validate_four_arm_preregistration(
        four_arm,
        confirmatory_protocol=confirmatory,
        confirmatory_sha256=dependencies["confirmatory"]["sha256"],
    )
    if protocol.get("dispatch") is not False:
        raise FixedTraceExportError("fixed-trace protocol permits dispatch")
    return confirmatory, four_arm


def _adapter_binding(protocol: dict[str, Any]) -> tuple[Path, str, str]:
    adapter = protocol.get("proposal_adapter")
    if not isinstance(adapter, dict):
        raise FixedTraceExportError("proposal adapter binding is missing")
    missing = [
        key for key in ("id", "path", "sha256") if not adapter.get(key)
    ]
    if missing:
        raise FixedTraceExportError(
            f"proposal adapter is not frozen: {missing}"
        )
    path = REPO_ROOT / adapter["path"]
    if not path.is_file() or file_sha256(path) != adapter["sha256"]:
        raise FixedTraceExportError("proposal adapter digest differs")
    return path, adapter["id"], adapter["sha256"]


def export_bundle(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    source_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    confirmatory, four_arm = validate_protocol(protocol)
    _, adapter_id, adapter_sha256 = _adapter_binding(protocol)
    if protocol["execution_authorization"].get("fixed_trace_export_authorized") is not True:
        raise FixedTraceExportError("fixed-trace export is not authorized")
    if output_path.exists():
        raise FixedTraceExportError(f"fresh fixed-trace output exists: {output_path}")
    source = load_json_object(source_path)
    if source.get("schema") != TYPED_TRACE_SOURCE_SCHEMA:
        raise FixedTraceExportError("unexpected typed-trace source schema")
    if source.get("dispatch_attempt_count") != 0:
        raise FixedTraceExportError("typed-trace source contains dispatch")
    if source.get("proposal_adapter") != {
        "id": adapter_id,
        "sha256": adapter_sha256,
    }:
        raise FixedTraceExportError("typed-trace source adapter binding differs")
    if source.get("condition") != protocol.get("trace_source_condition"):
        raise FixedTraceExportError("typed-trace source condition differs")
    traces = source.get("traces")
    if not isinstance(traces, list):
        raise FixedTraceExportError("typed-trace source traces are missing")
    bundle = {
        "schema": FIXED_TRACE_BUNDLE_SCHEMA,
        "created_at": saber_io.utc_now(),
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": file_sha256(protocol_path),
        "source_path": str(source_path),
        "source_sha256": file_sha256(source_path),
        "condition": protocol["trace_source_condition"],
        "dispatch": False,
        "proposal_adapter_frozen": True,
        "proposal_adapter": {
            "id": adapter_id,
            "sha256": adapter_sha256,
        },
        "traces": traces,
    }
    validate_fixed_trace_bundle(
        bundle,
        confirmatory_protocol=confirmatory,
        four_arm_protocol=four_arm,
    )
    saber_io.atomic_json(output_path, bundle)
    return {
        "ok": True,
        "trace_count": len(traces),
        "dispatch": False,
        "output": str(output_path),
        "sha256": file_sha256(output_path),
    }


def preflight(
    protocol: dict[str, Any],
    *,
    output_path: Path,
) -> dict[str, Any]:
    confirmatory, _ = validate_protocol(protocol)
    blockers: list[str] = []
    try:
        path, adapter_id, adapter_sha = _adapter_binding(protocol)
        adapter: dict[str, Any] = {
            "frozen": True,
            "path": str(path),
            "id": adapter_id,
            "sha256": adapter_sha,
        }
    except FixedTraceExportError as exc:
        blockers.append(str(exc))
        adapter = {"frozen": False, "error": str(exc)}
    if protocol.get("trace_source_condition") not in ("clean", "attacked"):
        blockers.append("fixed-trace source condition is not frozen")
    if output_path.exists():
        blockers.append(f"fresh fixed-trace output exists: {output_path}")
    if protocol["dependencies"].get("confirmatory_gate_pass_bound") is not True:
        blockers.append("confirmatory M2 gate pass is not bound")
    if protocol["resource_budget"].get("authorized_smoke_measurement_bound") is not True:
        blockers.append("authorized checker-latency smoke is not bound")
    if protocol["execution_authorization"].get("fixed_trace_export_authorized") is not True:
        blockers.append("fixed-trace export is not authorized")
    return {
        "schema": "proofalign.four-arm-fixed-trace-preflight.v1",
        "ready": not blockers,
        "read_only": True,
        "dispatch": False,
        "unit_count": len(confirmatory["frozen_base_pairs"]) * 2,
        "proposal_adapter": adapter,
        "output_path": str(output_path),
        "blockers": blockers,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--export", action="store_true")
    mode.add_argument("--validate-bundle", type=Path)
    mode.add_argument("--validate-results", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--trace-bundle", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        protocol_path = args.protocol.resolve()
        protocol = load_json_object(protocol_path)
        confirmatory, four_arm = validate_protocol(protocol)
        if args.dry_run:
            report: dict[str, Any] = {
                "mode": "dry_run",
                "unit_count": 120,
                "dispatch": False,
                "proposal_adapter_frozen": all(
                    protocol.get("proposal_adapter", {}).get(key)
                    for key in ("id", "path", "sha256")
                ),
                "trace_source_condition": protocol.get("trace_source_condition"),
                "export_authorized": protocol["execution_authorization"][
                    "fixed_trace_export_authorized"
                ],
            }
        elif args.preflight:
            report = preflight(protocol, output_path=args.output.resolve())
        elif args.export:
            if args.source is None:
                raise FixedTraceExportError("--export requires --source")
            report = export_bundle(
                protocol,
                protocol_path=protocol_path,
                source_path=args.source.resolve(),
                output_path=args.output.resolve(),
            )
        elif args.validate_bundle:
            bundle = load_json_object(args.validate_bundle.resolve())
            validate_fixed_trace_bundle(
                bundle,
                confirmatory_protocol=confirmatory,
                four_arm_protocol=four_arm,
            )
            report = {"ok": True, "trace_count": len(bundle["traces"])}
        else:
            if args.trace_bundle is None:
                raise FixedTraceExportError(
                    "--validate-results requires --trace-bundle"
                )
            results = load_json_object(args.validate_results.resolve())
            bundle = load_json_object(args.trace_bundle.resolve())
            validate_fixed_trace_results(results, trace_bundle=bundle)
            report = {"ok": True, "row_count": len(results["rows"])}
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (
        ConfirmatoryContractError,
        FixedTraceExportError,
        KeyError,
        OSError,
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
