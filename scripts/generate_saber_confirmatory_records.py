#!/usr/bin/env python3
"""Produce or validate the 60 outcome-blind confirmatory SABER records.

The committed M1 protocol intentionally has execution authorization disabled.
Dry-run, preflight, and result validation are read-only.  A future execution
protocol must bind this entrypoint and all dependencies at a clean commit, set
the explicit producer authorization bit, and use an absent output root.
"""

from __future__ import annotations

import argparse
import asyncio
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
    ATTACK_RECORD_BUNDLE_SCHEMA,
    ConfirmatoryContractError,
    file_sha256,
    load_json_object,
    producer_pairs,
    validate_attack_record_bundle,
    validate_confirmatory_preregistration,
)
from scripts import saber_io  # noqa: E402
from scripts.generate_saber_threat_records_r2 import (  # noqa: E402
    generate_records as generate_records_with_official_saber,
    write_checksums,
)


PRODUCER_PROTOCOL_SCHEMA = "proofalign.saber-confirmatory-producer-protocol.v1"
DEFAULT_PROTOCOL = (
    REPO_ROOT / "experiments" / "saber_confirmatory_producer_m1_protocol.json"
)
DEFAULT_OUTPUT_ROOT = (
    REPO_ROOT / "results" / "saber_confirmatory_producer_p1_20260724_fresh1"
)


class ProducerProtocolError(RuntimeError):
    """Raised when the producer protocol or environment fails closed."""


def validate_protocol(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
) -> tuple[dict[str, Any], Path]:
    if protocol.get("schema") != PRODUCER_PROTOCOL_SCHEMA:
        raise ProducerProtocolError("unexpected confirmatory producer schema")
    if protocol.get("protocol_status") not in {
        "m1_implementation_frozen_execution_not_authorized",
        "preregistered_producer_execution_authorized",
    }:
        raise ProducerProtocolError("confirmatory producer status is invalid")
    if protocol.get("victim_outcomes_observed") is not False:
        raise ProducerProtocolError("producer protocol is not outcome-blind")
    policy = protocol.get("record_policy")
    if not isinstance(policy, dict):
        raise ProducerProtocolError("record policy is missing")
    expected = {
        "required_record_count": 60,
        "producer_seed": 83,
        "one_generation_per_base_pair": True,
        "best_of_n_selection_allowed": False,
        "regeneration_or_replacement_allowed": False,
        "victim_rollout_visible": False,
        "victim_outcome_visible": False,
    }
    for key, value in expected.items():
        if policy.get(key) != value:
            raise ProducerProtocolError(f"record policy changed: {key}")
    authorization = protocol.get("execution_authorization")
    if not isinstance(authorization, dict):
        raise ProducerProtocolError("execution authorization block is missing")
    if authorization.get("victim_rollout_authorized") is not False:
        raise ProducerProtocolError("producer protocol authorizes victim rollout")
    if authorization.get("defense_rollout_authorized") is not False:
        raise ProducerProtocolError("producer protocol authorizes defense rollout")

    dependency = protocol.get("confirmatory_preregistration")
    if not isinstance(dependency, dict):
        raise ProducerProtocolError("confirmatory dependency is missing")
    preregistration_path = (REPO_ROOT / str(dependency.get("path", ""))).resolve()
    confirmatory = load_json_object(preregistration_path)
    validate_confirmatory_preregistration(confirmatory)
    if dependency.get("protocol_id") != confirmatory.get("protocol_id"):
        raise ProducerProtocolError("confirmatory protocol id differs")
    if dependency.get("sha256") != file_sha256(preregistration_path):
        raise ProducerProtocolError("confirmatory protocol digest differs")
    if len(producer_pairs(confirmatory)) != policy["required_record_count"]:
        raise ProducerProtocolError("producer population does not contain 60 pairs")
    return confirmatory, preregistration_path


def runtime_protocol(
    protocol: dict[str, Any],
    *,
    confirmatory: dict[str, Any],
) -> dict[str, Any]:
    """Adapt the M1 protocol to the already-audited official SABER loop."""

    attack_agent = dict(protocol["attack_agent"])
    attack_agent["producer_seed"] = protocol["record_policy"]["producer_seed"]
    return {
        **protocol,
        "frozen_pairs": producer_pairs(confirmatory),
        "attack_agent": attack_agent,
    }


def _git_report(root: Path, expected_commit: str) -> dict[str, Any]:
    if not root.is_dir():
        return {
            "path": str(root),
            "expected_commit": expected_commit,
            "present": False,
            "observed_commit": None,
            "tracked_clean": False,
        }
    head = saber_io.run_command(("git", "rev-parse", "HEAD"), cwd=root)
    status = saber_io.run_command(
        ("git", "status", "--porcelain=v1", "--untracked-files=no"),
        cwd=root,
    )
    observed = head.stdout.strip() if head.returncode == 0 else None
    return {
        "path": str(root),
        "expected_commit": expected_commit,
        "present": True,
        "observed_commit": observed,
        "commit_matches": observed == expected_commit,
        "tracked_clean": status.returncode == 0 and not status.stdout.strip(),
        "error": (
            None
            if head.returncode == 0 and status.returncode == 0
            else (head.stderr or status.stderr).strip()
        ),
    }


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    output_root: Path,
    attack_gpus: str,
) -> dict[str, Any]:
    confirmatory, preregistration_path = validate_protocol(
        protocol, protocol_path=protocol_path
    )
    blockers: list[str] = []
    source = protocol["source"]
    file_reports: dict[str, dict[str, Any]] = {}
    for relative, expected in source["sha256"].items():
        path = REPO_ROOT / relative
        observed = file_sha256(path) if path.is_file() else None
        file_reports[relative] = {
            "present": path.is_file(),
            "expected_sha256": expected,
            "observed_sha256": observed,
            "matches": observed == expected,
        }
        if observed != expected:
            blockers.append(f"source digest mismatch: {relative}")
    checkout_roots = {
        "saber": REPO_ROOT / "external" / "SABER",
        "libero_safety": REPO_ROOT / "external" / "LIBERO-Safety",
        "openpi": REPO_ROOT / "external" / "openpi",
    }
    checkout_reports = {
        key: _git_report(root, source[f"{key}_commit"])
        for key, root in checkout_roots.items()
    }
    for key, report in checkout_reports.items():
        if not report.get("commit_matches"):
            blockers.append(f"{key} checkout commit mismatch")
        if not report.get("tracked_clean"):
            blockers.append(f"{key} checkout has tracked changes")

    model_root = Path(protocol["attack_agent"]["model_path"])
    model_reports: dict[str, dict[str, Any]] = {}
    for relative, expected in protocol["attack_agent"]["model_sha256"].items():
        path = model_root / relative
        observed = file_sha256(path) if path.is_file() else None
        model_reports[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "matches": observed == expected,
        }
        if observed != expected:
            blockers.append(f"attack model digest mismatch: {relative}")

    status = saber_io.run_command(
        ("git", "status", "--porcelain=v1", "--untracked-files=normal"),
        cwd=REPO_ROOT,
    )
    tracked_status = status.stdout.splitlines() if status.returncode == 0 else []
    if status.returncode != 0 or tracked_status:
        blockers.append("ProofAlign worktree is not clean")
    if output_root.exists():
        blockers.append(f"fresh producer root already exists: {output_root}")
    if not attack_gpus:
        blockers.append("two attack GPUs have not been selected")
        gpu_report: dict[str, Any] = {"selected": None}
    else:
        try:
            selected_ids = [int(item) for item in attack_gpus.split(",")]
            if len(selected_ids) != 2 or len(set(selected_ids)) != 2:
                raise ValueError
            inventory = saber_io.gpu_inventory()
            by_id = {row["index"]: row for row in inventory}
            selected = [by_id[index] for index in selected_ids]
            maximum = int(
                protocol["resource_budget"][
                    "selected_gpu_prelaunch_memory_used_mib_max_exclusive"
                ]
            )
            if any(row["memory_used_mib"] >= maximum for row in selected):
                blockers.append("selected attack GPU violates prelaunch memory gate")
            gpu_report = {"inventory": inventory, "selected": selected}
        except (KeyError, ValueError, saber_io.ProtocolError) as exc:
            blockers.append(f"invalid attack GPU selection: {exc}")
            gpu_report = {"selected": None, "error": str(exc)}
    if (
        protocol["execution_authorization"].get(
            "attack_record_generation_authorized"
        )
        is not True
    ):
        blockers.append("attack-record generation is not authorized by this protocol")
    return {
        "schema": "proofalign.saber-confirmatory-producer-preflight.v1",
        "ready": not blockers,
        "read_only": True,
        "victim_loaded": False,
        "victim_outcomes_observed": False,
        "protocol": {
            "path": str(protocol_path),
            "sha256": file_sha256(protocol_path),
        },
        "confirmatory_preregistration": {
            "path": str(preregistration_path),
            "sha256": file_sha256(preregistration_path),
        },
        "population": {
            "base_pair_count": len(producer_pairs(confirmatory)),
            "sha256": confirmatory["base_population_sha256"],
        },
        "source_files": file_reports,
        "checkouts": checkout_reports,
        "attack_model": {"path": str(model_root), "files": model_reports},
        "gpu": gpu_report,
        "output_root": str(output_root),
        "proofalign_status": tracked_status,
        "blockers": blockers,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    output_root: Path,
    attack_gpus: str,
    server_port: int | None,
) -> dict[str, Any]:
    report = preflight(
        protocol,
        protocol_path=protocol_path,
        output_root=output_root,
        attack_gpus=attack_gpus,
    )
    if not report["ready"]:
        raise ProducerProtocolError(f"producer preflight failed: {report['blockers']}")
    confirmatory, _ = validate_protocol(protocol, protocol_path=protocol_path)
    adapted = runtime_protocol(protocol, confirmatory=confirmatory)
    output_root.mkdir(parents=True)
    (output_root / "runtime").mkdir()
    manifest_path = output_root / protocol["artifact_policy"]["manifest"]
    manifest = {
        "schema": "proofalign.saber-confirmatory-producer-run.v1",
        "status": "generating_records",
        "created_at": saber_io.utc_now(),
        "protocol_sha256": file_sha256(protocol_path),
        "preflight": report,
        "replacement_attempt_count": 0,
        "victim_loaded": False,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        records = asyncio.run(
            generate_records_with_official_saber(
                adapted,
                protocol_path,
                output_root,
                attack_gpus,
                server_port,
            )
        )
        bundle = {
            "schema": ATTACK_RECORD_BUNDLE_SCHEMA,
            "created_at": saber_io.utc_now(),
            "confirmatory_protocol_id": confirmatory["protocol_id"],
            "producer_protocol_sha256": file_sha256(protocol_path),
            "victim_outcomes_observed": False,
            "generation_attempt_count": len(records),
            "replacement_attempt_count": 0,
            "records": records,
        }
        validate_attack_record_bundle(
            bundle,
            confirmatory_protocol=confirmatory,
            producer_protocol_sha256=file_sha256(protocol_path),
        )
        records_path = output_root / protocol["artifact_policy"]["attack_records"]
        saber_io.atomic_json(records_path, bundle)
        summary = {
            "schema": "proofalign.saber-confirmatory-producer-summary.v1",
            "complete": True,
            "record_count": len(records),
            "generation_attempt_count": len(records),
            "replacement_attempt_count": 0,
            "victim_outcomes_observed": False,
            "victim_execution_authorized_by_record_gate": True,
            "defense_execution_authorized": False,
            "attack_records_sha256": file_sha256(records_path),
        }
        saber_io.atomic_json(
            output_root / protocol["artifact_policy"]["summary"], summary
        )
        manifest["status"] = "attack_records_complete"
        manifest["completed_at"] = saber_io.utc_now()
        manifest["attack_records_sha256"] = file_sha256(records_path)
        saber_io.atomic_json(manifest_path, manifest)
        write_checksums(output_root)
        return summary
    except BaseException as exc:
        manifest["status"] = "terminal_failed_no_replacement"
        manifest["completed_at"] = saber_io.utc_now()
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        saber_io.atomic_json(manifest_path, manifest)
        write_checksums(output_root)
        raise


def validate_results(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    confirmatory, _ = validate_protocol(protocol, protocol_path=protocol_path)
    records_path = output_root / protocol["artifact_policy"]["attack_records"]
    bundle = load_json_object(records_path)
    records = validate_attack_record_bundle(
        bundle,
        confirmatory_protocol=confirmatory,
        producer_protocol_sha256=file_sha256(protocol_path),
    )
    manifest = load_json_object(output_root / protocol["artifact_policy"]["manifest"])
    summary = load_json_object(output_root / protocol["artifact_policy"]["summary"])
    if manifest.get("status") != "attack_records_complete":
        raise ProducerProtocolError("producer manifest is not terminal-complete")
    if summary.get("complete") is not True or summary.get("record_count") != 60:
        raise ProducerProtocolError("producer summary did not pass the record gate")
    if summary.get("attack_records_sha256") != file_sha256(records_path):
        raise ProducerProtocolError("producer summary record digest differs")
    return {
        "ok": True,
        "record_count": len(records),
        "replacement_attempt_count": bundle["replacement_attempt_count"],
        "victim_outcomes_observed": bundle["victim_outcomes_observed"],
        "attack_records_sha256": file_sha256(records_path),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--validate-results", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--attack-gpus", default="")
    parser.add_argument("--attack-server-port", type=int)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        protocol_path = args.protocol.resolve()
        output_root = args.output_root.resolve()
        protocol = load_json_object(protocol_path)
        confirmatory, _ = validate_protocol(protocol, protocol_path=protocol_path)
        if args.dry_run:
            payload = {
                "mode": "dry_run",
                "record_count": len(producer_pairs(confirmatory)),
                "victim_loaded": False,
                "victim_outcomes_observed": False,
                "generation_authorized": protocol["execution_authorization"][
                    "attack_record_generation_authorized"
                ],
                "pairs": producer_pairs(confirmatory),
            }
        elif args.preflight:
            payload = preflight(
                protocol,
                protocol_path=protocol_path,
                output_root=output_root,
                attack_gpus=args.attack_gpus,
            )
        elif args.validate_results:
            payload = validate_results(
                protocol,
                protocol_path=protocol_path,
                output_root=output_root,
            )
        else:
            payload = execute(
                protocol,
                protocol_path=protocol_path,
                output_root=output_root,
                attack_gpus=args.attack_gpus,
                server_port=args.attack_server_port,
            )
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (
        ConfirmatoryContractError,
        KeyError,
        OSError,
        ProducerProtocolError,
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
