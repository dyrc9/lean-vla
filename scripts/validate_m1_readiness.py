#!/usr/bin/env python3
"""Audit M1 without loading a policy, simulator, attacker, or GPU runtime."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import (  # noqa: E402
    build_units,
    file_sha256,
    load_json_object,
    validate_confirmatory_preregistration,
    validate_four_arm_preregistration,
    victim_episode_specs,
)
from scripts import saber_io  # noqa: E402
from scripts.export_proofalign_fixed_trace import (  # noqa: E402
    validate_protocol as validate_four_arm_execution_protocol,
)
from scripts.generate_checker_equivalence_evidence import (  # noqa: E402
    build_evidence,
    canonical_text,
)
from scripts.generate_saber_confirmatory_records import (  # noqa: E402
    validate_protocol as validate_producer_protocol,
)
from scripts.run_saber_confirmatory_victim import (  # noqa: E402
    validate_protocol as validate_victim_protocol,
)


PRODUCER_PROTOCOL = (
    REPO_ROOT / "experiments" / "saber_confirmatory_producer_m1_protocol.json"
)
VICTIM_PROTOCOL = (
    REPO_ROOT / "experiments" / "saber_confirmatory_victim_m1_protocol.json"
)
FOUR_ARM_PROTOCOL = (
    REPO_ROOT / "experiments" / "proofalign_four_arm_m1_protocol.json"
)
CONFIRMATORY_PREREGISTRATION = (
    REPO_ROOT / "experiments" / "saber_confirmatory_preregistration_v1.json"
)
FOUR_ARM_PREREGISTRATION = (
    REPO_ROOT / "experiments" / "proofalign_four_arm_preregistration_v1.json"
)
EQUIVALENCE_EVIDENCE = (
    REPO_ROOT / "experiments" / "proofalign_fast_lean_equivalence_m1.json"
)
DEFAULT_PACKET = (
    REPO_ROOT / "experiments" / "proofalign_m1_readiness_packet_v1.json"
)


class ReadinessError(RuntimeError):
    """Raised when a supposedly frozen M1 binding is internally invalid."""


def _source_binding_report(protocol: dict[str, Any]) -> dict[str, Any]:
    reports: dict[str, Any] = {}
    for relative, expected in protocol["source"]["sha256"].items():
        path = REPO_ROOT / relative
        observed = file_sha256(path) if path.is_file() else None
        reports[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "matches": observed == expected,
        }
    return {
        "complete": bool(reports)
        and all(row["matches"] for row in reports.values()),
        "files": reports,
    }


def _root_report(paths: dict[str, str]) -> dict[str, Any]:
    return {
        name: {
            "path": relative,
            "absolute_path": str(REPO_ROOT / relative),
            "absent": not (REPO_ROOT / relative).exists(),
        }
        for name, relative in paths.items()
    }


def _committed_source_report(
    commit: str | None,
    protocols: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    if not commit:
        return {
            "complete": False,
            "commit": None,
            "commit_exists": False,
            "files": {},
        }
    resolved = saber_io.run_command(
        ("git", "rev-parse", "--verify", f"{commit}^{{commit}}"),
        cwd=REPO_ROOT,
    )
    if resolved.returncode != 0:
        return {
            "complete": False,
            "commit": commit,
            "commit_exists": False,
            "files": {},
        }
    resolved_commit = resolved.stdout.strip()
    expected_by_path: dict[str, str] = {}
    for protocol in protocols:
        for relative, expected in protocol["source"]["sha256"].items():
            previous = expected_by_path.setdefault(relative, expected)
            if previous != expected:
                raise ReadinessError(
                    f"protocol source digests disagree for {relative}"
                )
    files: dict[str, Any] = {}
    for relative, expected in expected_by_path.items():
        observed = subprocess.run(
            ("git", "show", f"{resolved_commit}:{relative}"),
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            timeout=120,
        )
        digest = (
            sha256(observed.stdout).hexdigest()
            if observed.returncode == 0
            else None
        )
        binding_kind = "git_commit"
        if digest is None and relative.startswith("external/"):
            dependency_path = REPO_ROOT / relative
            digest = (
                file_sha256(dependency_path)
                if dependency_path.is_file()
                else None
            )
            binding_kind = "external_content_sha256"
        files[relative] = {
            "expected_sha256": expected,
            "observed_sha256": digest,
            "matches": digest == expected,
            "binding_kind": binding_kind,
        }
    return {
        "complete": bool(files)
        and all(row["matches"] for row in files.values()),
        "commit": resolved_commit,
        "commit_exists": True,
        "files": files,
    }


def build_report() -> dict[str, Any]:
    confirmatory = load_json_object(CONFIRMATORY_PREREGISTRATION)
    four_arm_design = load_json_object(FOUR_ARM_PREREGISTRATION)
    producer = load_json_object(PRODUCER_PROTOCOL)
    victim = load_json_object(VICTIM_PROTOCOL)
    four_arm = load_json_object(FOUR_ARM_PROTOCOL)
    validate_confirmatory_preregistration(confirmatory)
    validate_four_arm_preregistration(
        four_arm_design,
        confirmatory_protocol=confirmatory,
        confirmatory_sha256=file_sha256(CONFIRMATORY_PREREGISTRATION),
    )
    validate_producer_protocol(producer, protocol_path=PRODUCER_PROTOCOL)
    validate_victim_protocol(victim, protocol_path=VICTIM_PROTOCOL)
    validate_four_arm_execution_protocol(four_arm)

    producer_sources = _source_binding_report(producer)
    victim_sources = _source_binding_report(victim)
    four_arm_sources = _source_binding_report(four_arm)
    expected_evidence = canonical_text(build_evidence())
    evidence_current = (
        EQUIVALENCE_EVIDENCE.is_file()
        and EQUIVALENCE_EVIDENCE.read_text(encoding="utf-8") == expected_evidence
    )
    proposal_adapter = four_arm["proposal_adapter"]
    proposal_adapter_frozen = all(
        proposal_adapter.get(key) for key in ("id", "path", "sha256")
    )
    assessor = four_arm.get("intent_action_assessor")
    assessor_frozen = isinstance(assessor, dict) and all(
        assessor.get(key)
        for key in (
            "id",
            "implementation_path",
            "implementation_sha256",
            "checkpoint_or_rules_digest",
            "qualification_protocol_path",
            "qualification_protocol_sha256",
        )
    ) and assessor.get("thresholds_frozen") is True
    trace_condition_frozen = four_arm.get("trace_source_condition") in {
        "clean",
        "attacked",
    }
    roots = _root_report(
        {
            "producer": producer["fresh_root"],
            "confirmatory_victim": victim["fresh_root"],
            "fixed_trace": four_arm["fixed_trace_artifacts"]["fresh_output"],
            "four_arm_clean": four_arm["closed_loop_fresh_roots"]["clean"],
            "four_arm_attacked": four_arm["closed_loop_fresh_roots"]["attacked"],
        }
    )
    committed_sources = _committed_source_report(
        four_arm.get("implementation_commit"),
        (producer, victim, four_arm),
    )
    resource_budget_complete = bool(
        victim["resource_budget"]["authorized_smoke_measurement_bound"]
        and four_arm["resource_budget"]["authorized_smoke_measurement_bound"]
        and victim["resource_budget"]["gpu_hours_cap"] is not None
        and victim["resource_budget"]["wall_clock_hours_cap"] is not None
        and victim["resource_budget"]["cpu_core_cap"] is not None
        and victim["resource_budget"]["ram_gib_cap"] is not None
        and four_arm["resource_budget"]["checker_latency_cap_ns"] is not None
    )
    components = {
        "population_and_order_contract": {
            "complete": True,
            "base_pair_count": 60,
            "unit_count": len(build_units(confirmatory)),
            "victim_episode_count": len(victim_episode_specs(confirmatory)),
        },
        "confirmatory_producer_and_record_validator": {
            "complete": producer_sources["complete"],
            "source_digest_count": len(producer_sources["files"]),
            "generation_authorized": producer["execution_authorization"][
                "attack_record_generation_authorized"
            ],
        },
        "confirmatory_vla_only_victim_and_artifact_validator": {
            "complete": victim_sources["complete"],
            "source_digest_count": len(victim_sources["files"]),
            "producer_bundle_bound": all(
                victim["producer"].get(key)
                for key in (
                    "protocol_path",
                    "protocol_sha256",
                    "output_root",
                    "attack_records_path",
                    "attack_records_sha256",
                    "checksums_sha256",
                )
            ),
        },
        "shared_four_arm_shadow_runner": {
            "complete": four_arm_sources["complete"],
            "source_digest_count": len(four_arm_sources["files"]),
            "dispatch_in_stage_a": False,
        },
        "fixed_trace_exporter": {
            "complete": (
                four_arm_sources["complete"]
                and proposal_adapter_frozen
                and trace_condition_frozen
            ),
            "proposal_adapter_frozen": proposal_adapter_frozen,
            "trace_source_condition_frozen": trace_condition_frozen,
        },
        "intent_action_assessor": {
            "complete": assessor_frozen,
            "implementation_and_checkpoint_frozen": assessor_frozen,
            "thresholds_frozen": (
                assessor.get("thresholds_frozen")
                if isinstance(assessor, dict)
                else False
            ),
            "victim_outcome_visible_during_qualification": (
                assessor.get("victim_outcome_visible_during_qualification")
                if isinstance(assessor, dict)
                else None
            ),
        },
        "fast_checker_lean_scoped_evidence": {
            "complete": evidence_current,
            "path": str(EQUIVALENCE_EVIDENCE.relative_to(REPO_ROOT)),
            "sha256": (
                file_sha256(EQUIVALENCE_EVIDENCE)
                if EQUIVALENCE_EVIDENCE.is_file()
                else None
            ),
            "machine_checked_full_refinement_complete": False,
        },
        "resource_budget": {
            "complete": resource_budget_complete,
            "episode_and_disk_caps_frozen": True,
            "cpu_and_ram_caps_frozen": True,
            "authorized_smoke_measurement_bound": False,
        },
        "fresh_roots": {
            "complete": all(row["absent"] for row in roots.values()),
            "roots": roots,
        },
        "clean_commit": {
            "complete": committed_sources["complete"],
            "implementation_commit": committed_sources["commit"],
            "commit_exists": committed_sources["commit_exists"],
            "source_digest_count": len(committed_sources["files"]),
            "all_bound_sources_match_commit": committed_sources["complete"],
        },
    }
    blockers: list[str] = []
    if not producer_sources["complete"]:
        blockers.append("producer source digest bindings are incomplete")
    if not victim_sources["complete"]:
        blockers.append("victim source digest bindings are incomplete")
    if not four_arm_sources["complete"]:
        blockers.append("four-arm source digest bindings are incomplete")
    if not proposal_adapter_frozen:
        blockers.append("typed VLA ActionBlock trace adapter is not frozen")
    if not assessor_frozen:
        blockers.append(
            "Intent-ActionBlock assessor and outcome-blind qualification "
            "thresholds are not designed and frozen"
        )
    if not trace_condition_frozen:
        blockers.append(
            "Stage A clean/attacked fixed-trace source condition is not frozen"
        )
    if not evidence_current:
        blockers.append("scoped fast-checker/Lean evidence is stale")
    if not resource_budget_complete:
        blockers.append(
            "GPU/CPU/RAM/wall-clock/storage throughput and checker-latency "
            "budgets lack an authorized smoke measurement"
        )
    if not all(row["absent"] for row in roots.values()):
        blockers.append("at least one planned fresh output root already exists")
    if not committed_sources["complete"]:
        blockers.append(
            "M1 implementation sources are not bound to a verified Git commit"
        )
    implementation_complete = all(
        component["complete"] for component in components.values()
    )
    return {
        "schema": "proofalign.m1-no-outcome-readiness.v1",
        "packet_id": "proofalign-m1-readiness-20260724-v1",
        "outcomes_observed_or_generated": False,
        "policy_or_attacker_loaded": False,
        "simulator_steps": 0,
        "gpu_runtime_queried": False,
        "components": components,
        "implementation_readiness_complete": implementation_complete,
        "m2_rollout_ready": False,
        "m2_rollout_authorized": False,
        "current_blockers": blockers,
        "protocol_bindings": {
            str(path.relative_to(REPO_ROOT)): file_sha256(path)
            for path in (
                CONFIRMATORY_PREREGISTRATION,
                FOUR_ARM_PREREGISTRATION,
                PRODUCER_PROTOCOL,
                VICTIM_PROTOCOL,
                FOUR_ARM_PROTOCOL,
            )
        },
        "claim_boundary": (
            "This packet audits implementation readiness only. It contains no new "
            "victim or defense outcome and does not authorize attack-record generation, "
            "M2 victim rollout, or any four-arm stage."
        ),
    }


def canonical_report(value: Any) -> str:
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


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
            observed = args.packet.read_text(encoding="utf-8")
            if observed != text:
                raise ReadinessError(f"M1 readiness packet is stale: {args.packet}")
            print(f"M1 readiness packet is current: {args.packet}")
        else:
            args.packet.parent.mkdir(parents=True, exist_ok=True)
            args.packet.write_text(text, encoding="utf-8")
            print(args.packet)
        return 0
    except (
        KeyError,
        OSError,
        ReadinessError,
        RuntimeError,
        subprocess.TimeoutExpired,
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
