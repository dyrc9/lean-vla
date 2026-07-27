#!/usr/bin/env python3
"""Audit semantic v4 C5 closure without loading a policy or simulator."""

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

from proofalign.benchmark.confirmatory import file_sha256  # noqa: E402
from scripts.generate_semantic_v4_equivalence_evidence import (  # noqa: E402
    OUTPUT_PATH as EQUIVALENCE_PATH,
    THEOREM_NAMES,
    build_evidence as build_equivalence_evidence,
    canonical_text as equivalence_canonical_text,
)
from scripts.run_semantic_v4_fixed_trace_gate import (  # noqa: E402
    EVIDENCE_PATH as FIXED_TRACE_PATH,
    FUTURE_FRESH_ROOTS,
    PROTOCOL_PATH,
    build_evidence as build_fixed_trace_evidence,
    build_protocol,
    canonical_text as fixed_trace_canonical_text,
    validate_protocol,
)


DEFAULT_PACKET = (
    REPO_ROOT
    / "experiments"
    / "proofalign_semantic_v4_c5_readiness_packet_v1.json"
)
READINESS_SOURCE_PATHS = (
    "scripts/validate_semantic_v4_c5_readiness.py",
    "tests/test_semantic_v4_c5.py",
    "Makefile",
    "scripts/check_all.sh",
)
MAKEFILE_REQUIRED_FRAGMENTS = (
    "semantic-v4-c5-check:",
    "scripts/run_semantic_v4_fixed_trace_gate.py --check",
    "scripts/generate_semantic_v4_equivalence_evidence.py --check",
    "scripts/validate_semantic_v4_c5_readiness.py --check",
)
CHECK_ALL_REQUIRED_FRAGMENTS = (
    "scripts/run_semantic_v4_fixed_trace_gate.py --check",
    "scripts/generate_semantic_v4_equivalence_evidence.py --check",
    "scripts/validate_semantic_v4_c5_readiness.py --check",
)


class C5ReadinessError(RuntimeError):
    """Raised when semantic v4 C5 readiness evidence is invalid or stale."""


def _root_report(paths: dict[str, str]) -> dict[str, Any]:
    return {
        name: {
            "path": relative,
            "absolute_path": str(REPO_ROOT / relative),
            "absent": not (REPO_ROOT / relative).exists(),
        }
        for name, relative in paths.items()
    }


def _wiring_report() -> dict[str, Any]:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    check_all = (REPO_ROOT / "scripts" / "check_all.sh").read_text(
        encoding="utf-8"
    )
    makefile_fragments = {
        fragment: fragment in makefile
        for fragment in MAKEFILE_REQUIRED_FRAGMENTS
    }
    check_all_fragments = {
        fragment: fragment in check_all
        for fragment in CHECK_ALL_REQUIRED_FRAGMENTS
    }
    return {
        "complete": (
            all(makefile_fragments.values())
            and all(check_all_fragments.values())
        ),
        "makefile_fragments": makefile_fragments,
        "check_all_fragments": check_all_fragments,
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise C5ReadinessError(f"expected a JSON object: {path}")
    return value


def build_report() -> dict[str, Any]:
    protocol = _read_json(PROTOCOL_PATH)
    validate_protocol(protocol)
    expected_protocol = fixed_trace_canonical_text(build_protocol())
    protocol_current = (
        PROTOCOL_PATH.read_text(encoding="utf-8") == expected_protocol
    )

    fixed_trace = build_fixed_trace_evidence(protocol)
    expected_fixed_trace = fixed_trace_canonical_text(fixed_trace)
    fixed_trace_current = (
        FIXED_TRACE_PATH.is_file()
        and FIXED_TRACE_PATH.read_text(encoding="utf-8")
        == expected_fixed_trace
    )

    equivalence = build_equivalence_evidence()
    expected_equivalence = equivalence_canonical_text(equivalence)
    equivalence_current = (
        EQUIVALENCE_PATH.is_file()
        and EQUIVALENCE_PATH.read_text(encoding="utf-8")
        == expected_equivalence
    )

    roots = _root_report(protocol["future_fresh_roots"])
    wiring = _wiring_report()
    zero_dispatch = (
        fixed_trace["dispatch_attempt_count"] == 0
        and fixed_trace["simulator_created"] is False
        and fixed_trace["sink_created"] is False
        and fixed_trace["policy_loaded"] is False
        and fixed_trace["outcomes_observed"] is False
    )
    identity_complete = (
        fixed_trace["identity_pass"] is True
        and fixed_trace["case_count"] == 8
        and fixed_trace["row_count"] == 32
    )
    equivalence_complete = (
        equivalence_current
        and equivalence["all_scoped_cases_match"] is True
        and equivalence["lean_build_required"] is True
        and len(equivalence["bindings"]["lean_source"]["theorems"])
        == len(THEOREM_NAMES)
        == 14
        and equivalence["scope"][
            "machine_checked_full_refinement_complete"
        ]
        is False
    )
    fresh_roots_complete = all(
        row["absent"] for row in roots.values()
    )
    source_bindings = {
        relative: file_sha256(REPO_ROOT / relative)
        for relative in READINESS_SOURCE_PATHS
    }
    legacy_bindings_complete = all(
        file_sha256(REPO_ROOT / relative) == expected
        for relative, expected in protocol["legacy_v3_artifacts"].items()
    )

    components = {
        "canonical_protocol": {
            "complete": protocol_current,
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
        },
        "fixed_trace_identity": {
            "complete": fixed_trace_current and identity_complete,
            "path": str(FIXED_TRACE_PATH.relative_to(REPO_ROOT)),
            "sha256": (
                file_sha256(FIXED_TRACE_PATH)
                if FIXED_TRACE_PATH.is_file()
                else None
            ),
            "case_count": fixed_trace["case_count"],
            "row_count": fixed_trace["row_count"],
            "identity_pass": fixed_trace["identity_pass"],
        },
        "zero_dispatch_boundary": {
            "complete": zero_dispatch,
            "dispatch_attempt_count": fixed_trace[
                "dispatch_attempt_count"
            ],
            "simulator_created": fixed_trace["simulator_created"],
            "sink_created": fixed_trace["sink_created"],
            "policy_loaded": fixed_trace["policy_loaded"],
            "outcomes_observed": fixed_trace["outcomes_observed"],
        },
        "semantic_v4_lean_scoped_evidence": {
            "complete": equivalence_complete,
            "path": str(EQUIVALENCE_PATH.relative_to(REPO_ROOT)),
            "sha256": (
                file_sha256(EQUIVALENCE_PATH)
                if EQUIVALENCE_PATH.is_file()
                else None
            ),
            "theorem_anchor_count": len(THEOREM_NAMES),
            "machine_checked_full_refinement_complete": False,
        },
        "legacy_v3_artifacts_unchanged": {
            "complete": legacy_bindings_complete,
            "bindings": protocol["legacy_v3_artifacts"],
        },
        "top_level_check_wiring": wiring,
        "future_fresh_roots": {
            "complete": fresh_roots_complete,
            "roots": roots,
        },
    }
    c5_complete = all(
        component["complete"]
        for name, component in components.items()
        if name != "future_fresh_roots"
    )
    next_stage_ready = c5_complete and fresh_roots_complete

    dependencies = protocol["qualification_dependencies"]
    blockers: list[str] = []
    if not c5_complete:
        blockers.append(
            "semantic v4 C5 component closure is incomplete or stale"
        )
    if not dependencies["selector_qualification_complete"]:
        blockers.append("E1 selector qualification is incomplete")
    if not dependencies["action_conditioning_qualification_complete"]:
        blockers.append("E2 action-conditioning qualification is incomplete")
    if not dependencies["local_checker_qualification_complete"]:
        blockers.append("E3 local-checker qualification is incomplete")
    if not dependencies["semantic_effect_observer_qualified"]:
        blockers.append("semantic effect observer is not qualified")
    if not fresh_roots_complete:
        blockers.append(
            "at least one planned semantic qualification output root exists"
        )
    blockers.extend(
        (
            "authorized latency/resource smoke is incomplete",
            "semantic v4 implementation is not bound to a clean commit",
            "efficacy rollout remains explicitly unauthorized",
        )
    )

    return {
        "schema": "proofalign.semantic-v4-c5-readiness.v1",
        "packet_id": "proofalign-semantic-v4-c5-readiness-20260725-v1",
        "outcomes_observed_or_generated": False,
        "policy_loaded": False,
        "simulator_steps": 0,
        "gpu_runtime_queried": False,
        "c5_component_closure_complete": c5_complete,
        "next_qualification_stage_ready": next_stage_ready,
        "efficacy_rollout_ready": False,
        "efficacy_rollout_authorized": False,
        "components": components,
        "current_blockers": blockers,
        "protocol_binding": {
            "path": str(PROTOCOL_PATH.relative_to(REPO_ROOT)),
            "sha256": file_sha256(PROTOCOL_PATH),
            "protocol_id": protocol["protocol_id"],
        },
        "readiness_source_bindings": source_bindings,
        "claim_boundary": (
            "This packet proves only semantic v4 C5 no-dispatch component "
            "closure and freshness. It contains no selector/checker efficacy "
            "result, victim outcome, simulator rollout, or physical-safety "
            "evidence, and it authorizes no execution."
        ),
    }


def canonical_report(value: Any) -> str:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report()
        text = canonical_report(report)
        if args.check:
            if args.packet.read_text(encoding="utf-8") != text:
                raise C5ReadinessError(
                    f"C5 readiness packet is stale: {args.packet}"
                )
            print(f"C5 readiness packet is current: {args.packet}")
        else:
            args.packet.parent.mkdir(parents=True, exist_ok=True)
            args.packet.write_text(text, encoding="utf-8")
            print(args.packet)
        return 0
    except (
        C5ReadinessError,
        KeyError,
        OSError,
        RuntimeError,
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
