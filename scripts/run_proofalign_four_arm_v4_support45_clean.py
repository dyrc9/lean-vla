#!/usr/bin/env python3
"""Run or validate the authorized support45 exploratory clean stage."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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
from proofalign.benchmark.four_arm_v4 import (  # noqa: E402
    canonical_text,
    ledger_row_from_episode_payload,
    read_ledger,
    verify_episode_artifacts,
)
from proofalign.benchmark.four_arm_v4_support import (  # noqa: E402
    FourArmV4SupportError,
    build_support_clean_analysis,
    build_support_schedule,
    validate_support_ledger_rows,
    validate_support_successor,
)
from scripts import run_saber_threat_validation_r5 as p0b_runner  # noqa: E402
from scripts import saber_io  # noqa: E402
from scripts.run_proofalign_four_arm_v4_clean import (  # noqa: E402
    _assert_external_checkout,
    _episode_args,
    _execute_episode,
    _tree_size_bytes,
)


DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_support45_successor.json"
)


class Support45CleanError(RuntimeError):
    """Raised when the support45 clean stage must fail closed."""


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _output_root(protocol: dict[str, Any]) -> Path:
    return REPO_ROOT / protocol["fresh_roots"]["stage_b_clean"]


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int | None,
    egl_gpu: int | None,
) -> dict[str, Any]:
    design, confirmatory, supported_ids = validate_support_successor(
        protocol,
        repo_root=REPO_ROOT,
    )
    blockers: list[str] = []
    output_root = _output_root(protocol)
    if output_root.exists():
        blockers.append(f"fresh2 clean root exists: {output_root}")
    if protocol["execution_authorization"][
        "stage_b_clean_rollout"
    ] is not True:
        blockers.append("support45 clean rollout is not authorized")
    status = _git(
        "status", "--porcelain=v1", "--untracked-files=no"
    )
    tracked_clean = status.returncode == 0 and not status.stdout.strip()
    if not tracked_clean:
        blockers.append("ProofAlign tracked worktree is not clean")
    source = protocol["source"]
    ancestor = _git(
        "merge-base",
        "--is-ancestor",
        source["repository_commit"],
        "HEAD",
    )
    tree = _git("rev-parse", f"{source['repository_commit']}^{{tree}}")
    repository_bound = (
        ancestor.returncode == 0
        and tree.returncode == 0
        and tree.stdout.strip() == source["repository_tree"]
    )
    if not repository_bound:
        blockers.append("bound ProofAlign source commit/tree is invalid")

    checkout_roots = {
        "libero_safety": REPO_ROOT / "external" / "LIBERO-Safety",
        "openpi": REPO_ROOT / "external" / "openpi",
        "saber": REPO_ROOT / "external" / "SABER",
    }
    checkouts = {}
    for label, expected in protocol["runtime_dependency"][
        "external_checkout_commits"
    ].items():
        try:
            checkouts[label] = _assert_external_checkout(
                checkout_roots[label],
                expected_commit=expected,
                label=label,
            )
        except (RuntimeError, KeyError) as exc:
            blockers.append(str(exc))

    disk_free_gib = shutil.disk_usage(REPO_ROOT).free / (1024**3)
    disk_ready = disk_free_gib >= float(
        protocol["resource_budget"]["minimum_free_disk_gib_at_launch"]
    )
    if not disk_ready:
        blockers.append(
            f"free disk is below launch gate: {disk_free_gib:.2f} GiB"
        )
    if policy_gpu is None or egl_gpu is None:
        blockers.append("policy and EGL GPUs have not been selected")
        selected_gpu: Any = None
    else:
        try:
            selected_gpu = p0b_runner.validate_gpu_selection(
                {
                    "execution_gate": {
                        "selected_gpu_memory_used_mib_max_exclusive": (
                            protocol["resource_budget"][
                                "selected_gpu_prelaunch_memory_used_mib_"
                                "max_exclusive"
                            ]
                        )
                    }
                },
                saber_io.gpu_inventory(),
                policy_gpu,
                egl_gpu,
            )
        except Exception as exc:
            selected_gpu = None
            blockers.append(f"invalid GPU selection: {exc}")

    checkpoint = Path(protocol["victim"]["checkpoint"])
    checkpoint_files = {}
    for relative, expected in protocol["victim"][
        "checkpoint_sha256"
    ].items():
        path = checkpoint / relative
        observed = file_sha256(path) if path.is_file() else None
        checkpoint_files[relative] = {
            "expected": expected,
            "observed": observed,
            "matches": observed == expected,
        }
        if observed != expected:
            blockers.append(
                f"victim checkpoint digest differs: {relative}"
            )
    specs = build_support_schedule(
        confirmatory,
        design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported_ids,
    )
    if (
        len(specs) != 360
        or len({spec.unit.unit_id for spec in specs}) != 90
    ):
        blockers.append("support45 schedule is not 90 units / 360 rows")
    return {
        "schema": "proofalign.four-arm-v4-support45-clean-preflight.v1",
        "ready": not blockers,
        "read_only": True,
        "support_conditioned": True,
        "exploratory": True,
        "confirmatory_claim_authorized": False,
        "protocol_path": protocol_path.relative_to(
            REPO_ROOT
        ).as_posix(),
        "protocol_sha256": file_sha256(protocol_path),
        "base_pair_count": len(supported_ids),
        "unit_count": len({spec.unit.unit_id for spec in specs}),
        "episode_count": len(specs),
        "output_root": output_root.relative_to(REPO_ROOT).as_posix(),
        "output_root_absent": not output_root.exists(),
        "tracked_worktree_clean": tracked_clean,
        "repository_bound": repository_bound,
        "external_checkouts": checkouts,
        "disk_free_gib": disk_free_gib,
        "disk_ready": disk_ready,
        "selected_gpu": selected_gpu,
        "checkpoint": checkpoint_files,
        "blockers": blockers,
    }


def execute(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    policy_gpu: int,
    egl_gpu: int,
) -> dict[str, Any]:
    report = preflight(
        protocol,
        protocol_path=protocol_path,
        policy_gpu=policy_gpu,
        egl_gpu=egl_gpu,
    )
    if not report["ready"]:
        raise Support45CleanError(
            f"support45 clean preflight failed: {report['blockers']}"
        )
    design, confirmatory, supported_ids = validate_support_successor(
        protocol,
        repo_root=REPO_ROOT,
    )
    output_root = _output_root(protocol)
    output_root.mkdir(parents=True)
    runtime_config = p0b_runner.ensure_libero_runtime_config(
        output_root
    )
    p0b_runner.configure_environment(
        policy_gpu,
        egl_gpu,
        "proofalign-four-arm-v4-support45-clean-fresh2",
    )
    os.environ["LIBERO_CONFIG_PATH"] = runtime_config["directory"]
    specs = build_support_schedule(
        confirmatory,
        design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported_ids,
    )
    first_args = _episode_args(
        protocol,
        spec=specs[0],
        output_dir=output_root,
        egl_gpu=egl_gpu,
    )
    manifest_path = output_root / "run_manifest.json"
    ledger_path = output_root / "episodes_ledger.jsonl"
    manifest = {
        "schema": "proofalign.four-arm-v4-support45-clean-run.v1",
        "status": "loading_policy",
        "created_at": saber_io.utc_now(),
        "protocol_id": protocol["protocol_id"],
        "protocol_sha256": file_sha256(protocol_path),
        "support_conditioned": True,
        "exploratory": True,
        "confirmatory_claim_authorized": False,
        "preflight": report,
        "runtime_config": runtime_config,
    }
    saber_io.atomic_json(manifest_path, manifest)
    try:
        policy_protocol = {
            **protocol,
            "episode_config": protocol["episode_constants"],
        }
        policy, jax, image_tools, _ = p0b_runner.load_policy(
            policy_protocol,
            first_args,
        )
        extractor = p0b_runner.make_constraint_extractor()
        manifest["status"] = "running_support45_clean_four_arm"
        saber_io.atomic_json(manifest_path, manifest)
        for spec in specs:
            _execute_episode(
                protocol,
                design,
                spec=spec,
                output_root=output_root,
                ledger_path=ledger_path,
                policy=policy,
                jax=jax,
                image_tools=image_tools,
                egl_gpu=egl_gpu,
                extractor=extractor,
            )
            output_gib = _tree_size_bytes(output_root) / (1024**3)
            if output_gib > float(
                protocol["resource_budget"][
                    "output_disk_cap_gib_per_closed_loop_stage"
                ]
            ):
                raise Support45CleanError(
                    "support45 clean output exceeded the disk cap: "
                    f"{output_gib:.3f} GiB"
                )
        rows = read_ledger(ledger_path)
        validate_support_ledger_rows(
            rows,
            confirmatory=confirmatory,
            design=design,
            stage="B_clean_closed_loop",
            supported_base_pair_ids=supported_ids,
        )
        verify_episode_artifacts(rows, artifact_root=output_root)
        analysis = build_support_clean_analysis(
            protocol,
            design=design,
            confirmatory=confirmatory,
            rows=rows,
            terminal=True,
            episode_artifacts_verified=True,
        )
        saber_io.atomic_json(output_root / "analysis.json", analysis)
        manifest["status"] = "complete"
        manifest["classification"] = analysis["classification"]
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        p0b_runner.write_checksums(output_root)
        return analysis
    except BaseException as exc:
        manifest["status"] = "terminal_failed_closed"
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest["completed_at"] = saber_io.utc_now()
        saber_io.atomic_json(manifest_path, manifest)
        p0b_runner.write_checksums(output_root)
        raise


def validate_results(protocol: dict[str, Any]) -> dict[str, Any]:
    design, confirmatory, supported_ids = validate_support_successor(
        protocol,
        repo_root=REPO_ROOT,
    )
    output_root = _output_root(protocol)
    p0b_runner.read_checksums(output_root)
    manifest = load_json_object(output_root / "run_manifest.json")
    if manifest.get("status") != "complete":
        raise Support45CleanError(
            "support45 clean run manifest is not terminal-complete"
        )
    rows = read_ledger(output_root / "episodes_ledger.jsonl")
    validate_support_ledger_rows(
        rows,
        confirmatory=confirmatory,
        design=design,
        stage="B_clean_closed_loop",
        supported_base_pair_ids=supported_ids,
    )
    verify_episode_artifacts(rows, artifact_root=output_root)
    recomputed = build_support_clean_analysis(
        protocol,
        design=design,
        confirmatory=confirmatory,
        rows=rows,
        terminal=True,
        episode_artifacts_verified=True,
    )
    retained = load_json_object(output_root / "analysis.json")
    if retained != recomputed:
        raise Support45CleanError(
            "retained support45 analysis differs from recomputation"
        )
    return recomputed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--policy-gpu", type=int)
    parser.add_argument("--egl-gpu", type=int)
    args = parser.parse_args(argv)
    if sum(
        (args.preflight, args.validate_results, args.execute)
    ) != 1:
        parser.error(
            "choose exactly one of --preflight, --validate-results, "
            "or --execute"
        )
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    try:
        if args.preflight:
            payload = preflight(
                protocol,
                protocol_path=protocol_path,
                policy_gpu=args.policy_gpu,
                egl_gpu=args.egl_gpu,
            )
        elif args.validate_results:
            payload = validate_results(protocol)
        else:
            if args.policy_gpu is None or args.egl_gpu is None:
                parser.error(
                    "--execute requires --policy-gpu and --egl-gpu"
                )
            payload = execute(
                protocol,
                protocol_path=protocol_path,
                policy_gpu=args.policy_gpu,
                egl_gpu=args.egl_gpu,
            )
        print(canonical_text(payload), end="")
        return 0
    except (
        FourArmV4SupportError,
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
