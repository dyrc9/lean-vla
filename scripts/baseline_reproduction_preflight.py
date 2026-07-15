#!/usr/bin/env python3
"""Read-only, fail-closed preflight for the SAFE and FIPER R0 reproductions.

The preflight intentionally does not unpickle rollout files. Both upstream
pipelines use Python pickle, so schema inspection must only happen after an
official asset digest has been frozen and the operator explicitly trusts it.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SAFE_PROTOCOL = REPO_ROOT / "experiments" / "safe_r0_protocol.json"
FIPER_PROTOCOL = REPO_ROOT / "experiments" / "fiper_r0_protocol.json"
PHANTOM_R1_PROTOCOL = REPO_ROOT / "experiments" / "phantom_menace_r1_protocol.json"
CANONICAL_UV = "/home/ldx/.conda/envs/proofalign-libero/bin/uv"
PHYSICAL_SUITES = (
    "affordance",
    "obstacle_avoidance",
    "human_safety",
    "obstacle_avoidance_human",
)


class ProtocolError(ValueError):
    """Raised when a frozen protocol no longer has its preregistered shape."""


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProtocolError(f"protocol must be a JSON object: {path}")
    return payload


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProtocolError(message)


def validate_safe_protocol(protocol: dict[str, Any]) -> None:
    require(protocol.get("schema") == "proofalign.safe-r0-protocol.v1", "SAFE schema changed")
    scope = protocol.get("scope", {})
    require(scope.get("victim") == "OpenPI pi0", "SAFE R0 must remain on official pi0")
    require(scope.get("pi05_adapter_experiment") is False, "SAFE R0 cannot include pi0.5 adapter work")
    rollout = protocol.get("rollout_generation", {})
    require(rollout.get("suite") == "libero_10", "SAFE suite changed")
    require(rollout.get("task_ids") == list(range(10)), "SAFE task order changed")
    require(rollout.get("num_trials_per_task") == 50, "SAFE trial count changed")
    require(rollout.get("expected_episode_count") == 500, "SAFE episode count changed")
    require(rollout.get("action_samples_per_observation") == 1, "SAFE primary sampling changed")
    detector = protocol.get("detector_reproduction", {})
    require(detector.get("primary_model_family") == "lstm", "SAFE primary model changed")
    require(detector.get("primary_feature") == "pre_velocity", "SAFE feature changed")
    require(detector.get("official_seeds") == [0, 1, 2], "SAFE seed list changed")
    require(detector.get("full_official_multirun_required_for_r0_claim") is True, "SAFE full-matrix gate removed")
    require(detector.get("reduced_smoke_can_satisfy_r0") is False, "SAFE smoke cannot satisfy R0")
    environment = protocol.get("environment", {})
    require(environment.get("uv") == CANONICAL_UV, "SAFE environment manager changed")
    require(
        environment.get("detector_environment") == "/data0/ldx/uv-envs/safe-r0",
        "SAFE isolated environment changed",
    )
    require(
        environment.get("openpi_server_environment") == "/data0/ldx/uv-envs/safe-r0-openpi",
        "SAFE OpenPI server environment changed",
    )
    require(
        environment.get("libero_client_environment") == "/data0/ldx/uv-envs/safe-r0-libero-client",
        "SAFE LIBERO client environment changed",
    )
    require(
        bool(rollout.get("checkpoint_tree_manifest_sha256")),
        "SAFE checkpoint manifest digest is not frozen",
    )


def validate_fiper_protocol(protocol: dict[str, Any]) -> None:
    require(protocol.get("schema") == "proofalign.fiper-r0-protocol.v1", "FIPER schema changed")
    dataset = protocol.get("dataset", {})
    require(
        dataset.get("tasks_in_order") == ["sorting", "stacking", "push_t", "pretzel", "push_chair"],
        "FIPER task order changed",
    )
    require(
        dataset.get("calibration_rollouts_must_all_be_successful") is False,
        "FIPER official mixed calibration semantics changed",
    )
    require(
        dataset.get("threshold_calibration_uses_successful_rollouts_only") is True,
        "FIPER successful threshold subset changed",
    )
    require(
        dataset.get("preprocessing_and_rnd_training_use_full_calibration_subset") is True,
        "FIPER full calibration training subset changed",
    )
    pipeline = protocol.get("official_pipeline", {})
    require(pipeline.get("launcher") == "scripts/run_fiper_compat.py", "FIPER compatibility launcher changed")
    require(
        pipeline.get("compatibility_shim", {}).get("upstream_source_modified") is False,
        "FIPER upstream source must remain unmodified",
    )
    require(pipeline.get("primary_components") == ["rnd_oe", "entropy"], "FIPER primary components changed")
    require(pipeline.get("random_seeds") == [0, 1, 2, 42, 43], "FIPER seeds changed")
    require(
        pipeline.get("threshold_styles") == ["tvt_quantile", "tvt_cp_band", "ct_quantile"],
        "FIPER threshold styles changed",
    )
    require(pipeline.get("full_default_pipeline_required_for_r0_claim") is True, "FIPER full-pipeline gate removed")
    require(pipeline.get("reduced_smoke_can_satisfy_r0") is False, "FIPER smoke cannot satisfy R0")
    environment = protocol.get("environment", {})
    require(environment.get("uv") == CANONICAL_UV, "FIPER environment manager changed")
    require(
        environment.get("isolated_environment") == "/data0/ldx/uv-envs/fiper-r0",
        "FIPER isolated environment changed",
    )
    require(
        dataset.get("artifact_expected_size_bytes") == 5_676_727_608,
        "FIPER official archive size changed",
    )
    require(
        dataset.get("artifact_sha256") == "00922af40e54b23ce4434402858116fbfd485ca06852f09d180ff192868bf191",
        "FIPER official archive digest changed",
    )


def validate_phantom_r1_protocol(protocol: dict[str, Any]) -> None:
    """Retain the independent main-line guard for the frozen Phantom R1 protocol."""

    require(
        protocol.get("schema") == "proofalign.phantom-menace-r1-protocol.v1",
        "Phantom R1 schema changed",
    )
    require(protocol.get("attack_results_observed") is False, "Phantom R1 is no longer outcome-blind")
    require(
        protocol.get("protocol_status") == "preregistered_execution_authorized_after_commit",
        "Phantom R1 execution status changed",
    )
    scope = protocol.get("scope", {})
    require(scope.get("execution_authorized_after_protocol_commit") is True, "Phantom R1 execution is not authorized")
    require(scope.get("execution_requires_safe_and_fiper_r0_readiness_decision") is False, "SAFE/FIPER cannot retroactively block Phantom R1")
    episode = protocol.get("episode_config", {})
    require(episode.get("init_state_id") == 1, "Phantom R1 must remain held out from init 0")
    require(episode.get("camera_attacked") == "agentview", "Phantom R1 camera changed")
    screening = protocol.get("clean_screening", {})
    require(tuple(screening.get("suite_order", ())) == PHYSICAL_SUITES, "Phantom R1 suite order changed")
    require(screening.get("candidate_task_order_per_suite") == [0, 7, 14], "Phantom R1 candidates changed")
    require(screening.get("qualifying_pair_count") == 4, "Phantom R1 qualifying count changed")
    attack = protocol.get("attack", {})
    require(
        (attack.get("family"), attack.get("strength")) == ("laser_blinding", "strong"),
        "Phantom R1 attack cell changed",
    )
    gate = protocol.get("primary_signal_gate", {})
    require(gate.get("task_failure_alone_counts_as_signal") is False, "task failure cannot become the R1 safety signal")
    require(gate.get("minimum_clean_safe_to_attacked_unsafe_pairs") == 2, "Phantom R1 gate changed")
    require(protocol.get("execution_gate", {}).get("no_episode_may_start_while_any_blocker_remains") is True, "R1 fail-closed gate removed")


def digest(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def command(argv: Iterable[str], *, cwd: Path) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            tuple(argv), cwd=cwd, check=False, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def git_check(path: Path, expected_head: str) -> dict[str, Any]:
    blockers: list[str] = []
    if not path.is_dir():
        return {"path": str(path), "head": None, "clean": None, "blockers": [f"checkout missing: {path}"]}
    rc, head, error = command(("git", "rev-parse", "HEAD"), cwd=path)
    if rc != 0:
        blockers.append(f"cannot read Git head for {path}: {error}")
        head = ""
    elif head != expected_head:
        blockers.append(f"Git head mismatch for {path}: {head} != {expected_head}")
    rc, status, error = command(("git", "status", "--porcelain=v1"), cwd=path)
    clean: bool | None = None
    if rc != 0:
        blockers.append(f"cannot read Git status for {path}: {error}")
    else:
        clean = not bool(status)
        if not clean:
            blockers.append(f"checkout is dirty: {path}")
    return {"path": str(path), "head": head or None, "clean": clean, "blockers": blockers}


def digest_check(base: Path, expected: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    blockers: list[str] = []
    for relative, expected_digest in expected.items():
        path = base / relative
        observed = digest(path)
        match = observed == expected_digest
        records.append(
            {
                "path": str(path),
                "expected_sha256": expected_digest,
                "observed_sha256": observed,
                "match": match,
            }
        )
        if not match:
            blockers.append(f"source digest mismatch or missing: {path}")
    return records, blockers


def pickle_files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in {".pkl", ".pickle"})


def check_safe_assets(
    protocol: dict[str, Any],
    *,
    checkpoint: Path | None,
    rollout_root: Path | None,
) -> dict[str, Any]:
    checkpoint_blockers: list[str] = []
    rollout_blockers: list[str] = []
    checkpoint_record: dict[str, Any] = {"path": str(checkpoint) if checkpoint else None}
    if checkpoint is None or not checkpoint.is_dir():
        checkpoint_blockers.append("SAFE pi0_libero checkpoint directory is not available")
    else:
        checkpoint_record["present"] = True
        rollout = protocol["rollout_generation"]
        manifest_path = Path(rollout["checkpoint_tree_manifest"])
        expected_manifest_digest = rollout["checkpoint_tree_manifest_sha256"]
        observed_manifest_digest = digest(manifest_path)
        checkpoint_record.update(
            {
                "manifest": str(manifest_path),
                "expected_manifest_sha256": expected_manifest_digest,
                "observed_manifest_sha256": observed_manifest_digest,
                "manifest_match": observed_manifest_digest == expected_manifest_digest,
            }
        )
        if observed_manifest_digest != expected_manifest_digest:
            checkpoint_blockers.append("SAFE checkpoint tree manifest is missing or its digest changed")
        else:
            manifest = load_json(manifest_path)
            expected_fields = {
                "root": str(checkpoint.resolve()),
                "tree_sha256": rollout["checkpoint_tree_sha256"],
                "file_count": rollout["checkpoint_file_count"],
                "total_file_bytes": rollout["checkpoint_total_file_bytes"],
            }
            for key, expected in expected_fields.items():
                if manifest.get(key) != expected:
                    checkpoint_blockers.append(f"SAFE checkpoint manifest {key} changed")
        tokenizer = Path(rollout["tokenizer_local_path"])
        checkpoint_record["tokenizer"] = {
            "path": str(tokenizer),
            "expected_sha256": rollout["tokenizer_sha256"],
            "observed_sha256": digest(tokenizer),
        }
        if not tokenizer.is_file() or tokenizer.stat().st_size != rollout["tokenizer_size_bytes"]:
            checkpoint_blockers.append("SAFE tokenizer is missing or its size changed")
        elif checkpoint_record["tokenizer"]["observed_sha256"] != rollout["tokenizer_sha256"]:
            checkpoint_blockers.append("SAFE tokenizer digest changed")

    env_records: list[Path] = []
    policy_records: list[Path] = []
    if rollout_root is None or not rollout_root.is_dir():
        rollout_blockers.append("SAFE official pi0-libero_10 rollout root is not available")
    else:
        env_records = pickle_files(rollout_root / "env_records")
        policy_records = sorted((rollout_root / "policy_records").glob("*meta.pkl"))
        expected = protocol["rollout_generation"]["expected_episode_count"]
        if len(env_records) != expected:
            rollout_blockers.append(f"SAFE env record count is {len(env_records)}, expected {expected}")
        if not policy_records:
            rollout_blockers.append("SAFE policy meta records are absent")
        rollout_blockers.append("SAFE trusted-pickle schema/count inspection has not been executed")
        rollout_blockers.append("SAFE rollout-tree SHA256 manifest is not frozen")
    return {
        "checkpoint": checkpoint_record,
        "rollout_root": str(rollout_root) if rollout_root else None,
        "env_record_count": len(env_records),
        "policy_record_count": len(policy_records),
        "checkpoint_ready": not checkpoint_blockers,
        "rollout_ready": not rollout_blockers,
        "checkpoint_blockers": checkpoint_blockers,
        "rollout_blockers": rollout_blockers,
        "blockers": [*checkpoint_blockers, *rollout_blockers],
    }


def check_fiper_assets(protocol: dict[str, Any], *, data_root: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    counts: dict[str, dict[str, int]] = {}
    dataset = protocol["dataset"]
    data_root = data_root or Path(dataset["extracted_data_root"])
    minimum = int(protocol["dataset"]["minimum_files_per_task_split_from_upstream_code"])
    if data_root is None or not data_root.is_dir():
        blockers.append("FIPER official rollout data root is not available")
    else:
        for task in protocol["dataset"]["tasks_in_order"]:
            counts[task] = {}
            for split in ("calibration", "test"):
                count = len(pickle_files(data_root / task / "rollouts" / split))
                counts[task][split] = count
                if count < minimum:
                    blockers.append(
                        f"FIPER {task}/{split} has {count} pickle files, minimum is {minimum}"
                    )

    archive = Path(dataset["artifact_local_path"])
    if not archive.is_file() or archive.stat().st_size != dataset["artifact_expected_size_bytes"]:
        blockers.append("FIPER official archive is missing or its size changed")

    report_specs = (
        ("archive_digest", Path(dataset["artifact_digest_report"]), dataset["artifact_digest_report_sha256"]),
        (
            "tree_manifest",
            Path(dataset["extracted_tree_manifest"]),
            dataset["extracted_tree_manifest_sha256"],
        ),
        (
            "pickle_inspection",
            Path(dataset["trusted_pickle_inspection_report"]),
            dataset["trusted_pickle_inspection_report_sha256"],
        ),
    )
    reports: dict[str, Any] = {}
    for name, path, expected_digest in report_specs:
        observed_digest = digest(path)
        reports[name] = {
            "path": str(path),
            "expected_sha256": expected_digest,
            "observed_sha256": observed_digest,
            "match": observed_digest == expected_digest,
        }
        if observed_digest != expected_digest:
            blockers.append(f"FIPER {name} report is missing or its digest changed")

    if reports["archive_digest"]["match"]:
        archive_report = load_json(Path(dataset["artifact_digest_report"]))
        if archive_report.get("size") != dataset["artifact_expected_size_bytes"]:
            blockers.append("FIPER archive digest report size changed")
        if archive_report.get("sha256") != dataset["artifact_sha256"]:
            blockers.append("FIPER archive digest report SHA256 changed")
    if reports["tree_manifest"]["match"]:
        tree_report = load_json(Path(dataset["extracted_tree_manifest"]))
        for key, expected in {
            "root": str(data_root.resolve()),
            "tree_sha256": dataset["extracted_tree_sha256"],
            "file_count": dataset["extracted_file_count"],
            "total_file_bytes": dataset["extracted_total_file_bytes"],
        }.items():
            if tree_report.get(key) != expected:
                blockers.append(f"FIPER extracted-tree manifest {key} changed")
    if reports["pickle_inspection"]["match"]:
        inspection = load_json(Path(dataset["trusted_pickle_inspection_report"]))
        if inspection.get("valid") is not True:
            blockers.append("FIPER trusted-pickle inspection is not valid")
        for task in dataset["tasks_in_order"]:
            task_report = inspection.get("tasks", {}).get(task, {})
            calibration = task_report.get("calibration", {})
            test = task_report.get("test", {})
            if calibration.get("success_count", 0) < 1:
                blockers.append(f"FIPER {task} lacks successful calibration rollouts")
            if test.get("success_count", 0) < 1 or test.get("failure_count", 0) < 1:
                blockers.append(f"FIPER {task} test labels are not mixed")
            for split, split_report in (("calibration", calibration), ("test", test)):
                if split_report.get("file_count") != counts.get(task, {}).get(split):
                    blockers.append(f"FIPER {task}/{split} count differs from trusted inspection")
    return {
        "data_root": str(data_root) if data_root else None,
        "counts": counts,
        "reports": reports,
        "ready": not blockers,
        "blockers": blockers,
    }


def check_python_environment(
    path: Path,
    *,
    modules: tuple[str, ...],
    pythonpath: tuple[Path, ...] = (),
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    python = path / "bin" / "python"
    blockers: list[str] = []
    if not python.is_file():
        blockers.append(f"environment Python is missing: {python}")
        return {"path": str(path), "python": str(python), "blockers": blockers}
    setup = ["import os, sys"]
    if pythonpath:
        setup.append(f"sys.path[:0] = {[str(item.resolve()) for item in pythonpath]!r}")
    for key, value in (env or {}).items():
        setup.append(f"os.environ[{key!r}] = {value!r}")
    program = "; ".join([*setup, *(f"import {module}" for module in modules), "print(sys.version)"])
    rc, stdout, stderr = command((str(python), "-c", program), cwd=REPO_ROOT)
    if rc != 0:
        blockers.append(f"environment import check failed for {path}: {stderr or stdout}")
    return {
        "path": str(path),
        "python": str(python),
        "modules": list(modules),
        "pythonpath": [str(item.resolve()) for item in pythonpath],
        "version": stdout if rc == 0 else None,
        "blockers": blockers,
    }


def collect_preflight(
    workspace: Path,
    *,
    safe_checkpoint: Path | None = None,
    safe_rollout_root: Path | None = None,
    fiper_data_root: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    safe = load_json(workspace / "experiments" / "safe_r0_protocol.json")
    fiper = load_json(workspace / "experiments" / "fiper_r0_protocol.json")
    validate_safe_protocol(safe)
    validate_fiper_protocol(fiper)

    safe_git = git_check(workspace / safe["source"]["safe_checkout"], safe["source"]["safe_commit"])
    safe_openpi_git = git_check(
        workspace / safe["source"]["safe_openpi_checkout"], safe["source"]["safe_openpi_commit"]
    )
    fiper_git = git_check(workspace / fiper["source"]["checkout"], fiper["source"]["commit"])
    safe_digests, safe_digest_blockers = digest_check(
        workspace / safe["source"]["digest_root"], safe["source"]["sha256"]
    )
    fiper_digests, fiper_digest_blockers = digest_check(
        workspace / fiper["source"]["checkout"], fiper["source"]["sha256"]
    )

    submodule_blockers: list[str] = []
    safe_openpi_root = workspace / safe["source"]["safe_openpi_checkout"]
    rc, submodules, error = command(("git", "submodule", "status"), cwd=safe_openpi_root)
    required_submodules = safe["source"]["required_submodules"]
    if rc != 0:
        submodule_blockers.append(f"cannot inspect SAFE-openpi submodules: {error}")
    else:
        observed_submodules: dict[str, tuple[str, str]] = {}
        for line in submodules.splitlines():
            if not line.strip():
                continue
            marker = line[0]
            parts = line[1:].strip().split()
            if len(parts) >= 2:
                observed_submodules[parts[1]] = (marker, parts[0])
        for path, expected_head in required_submodules.items():
            marker, observed_head = observed_submodules.get(path, ("-", ""))
            if marker == "-":
                submodule_blockers.append(f"SAFE-openpi submodule is not initialized: {path}")
            elif marker in {"+", "U"} or observed_head != expected_head:
                submodule_blockers.append(
                    f"SAFE-openpi submodule mismatch: {path} {observed_head} != {expected_head}"
                )

    safe_checkpoint = safe_checkpoint or Path(safe["rollout_generation"]["checkpoint_local_path"])
    safe_assets = check_safe_assets(safe, checkpoint=safe_checkpoint, rollout_root=safe_rollout_root)
    fiper_assets = check_fiper_assets(fiper, data_root=fiper_data_root)
    environments = {
        "safe_detector": check_python_environment(
            Path(safe["environment"]["detector_environment"]),
            modules=("failure_prob", "torch", "hydra"),
        ),
        "safe_openpi_server": check_python_environment(
            Path(safe["environment"]["openpi_server_environment"]),
            modules=("openpi", "jax", "torch"),
        ),
        "safe_libero_client": check_python_environment(
            Path(safe["environment"]["libero_client_environment"]),
            modules=("openpi_client", "libero.libero", "mujoco", "torch"),
            pythonpath=(workspace / safe["source"]["safe_openpi_checkout"] / "third_party" / "libero",),
            env={
                "LIBERO_CONFIG_PATH": str(
                    workspace / "experiments" / "safe_fiper_r0_env" / "libero_config"
                )
            },
        ),
        "fiper": check_python_environment(
            Path(fiper["environment"]["isolated_environment"]),
            modules=("torch", "hydra", "zarr"),
        ),
    }
    environment_blockers = [
        blocker for record in environments.values() for blocker in record["blockers"]
    ]
    source_blockers = [
        *safe_git["blockers"],
        *safe_openpi_git["blockers"],
        *fiper_git["blockers"],
        *safe_digest_blockers,
        *fiper_digest_blockers,
        *submodule_blockers,
    ]
    blockers = [
        *source_blockers,
        *environment_blockers,
        *safe_assets["blockers"],
        *fiper_assets["blockers"],
    ]
    input_readiness = {
        "safe_rollout": not (
            source_blockers
            or environments["safe_openpi_server"]["blockers"]
            or environments["safe_libero_client"]["blockers"]
            or safe_assets["checkpoint_blockers"]
        ),
        "safe_detector": not (
            source_blockers
            or environments["safe_detector"]["blockers"]
            or safe_assets["blockers"]
        ),
        "fiper": not (
            source_blockers or environments["fiper"]["blockers"] or fiper_assets["blockers"]
        ),
    }
    return {
        "schema": "proofalign.baseline-reproduction-preflight.v1",
        "workspace": str(workspace),
        "ready": not blockers,
        "source_ready": not source_blockers,
        "gpu_execution_authorized": False,
        "protocols": {
            "safe": str(workspace / "experiments" / "safe_r0_protocol.json"),
            "fiper": str(workspace / "experiments" / "fiper_r0_protocol.json"),
        },
        "git": {
            "safe": safe_git,
            "safe_openpi": safe_openpi_git,
            "fiper": fiper_git,
        },
        "source_digests": {"safe": safe_digests, "fiper": fiper_digests},
        "environments": environments,
        "input_readiness": input_readiness,
        "safe_assets": safe_assets,
        "fiper_assets": fiper_assets,
        "blockers": blockers,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=REPO_ROOT)
    parser.add_argument("--safe-checkpoint", type=Path)
    parser.add_argument("--safe-rollout-root", type=Path)
    parser.add_argument("--fiper-data-root", type=Path)
    parser.add_argument("--output", type=Path, help="Optionally write the JSON report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any blocker remains.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = collect_preflight(
            args.workspace,
            safe_checkpoint=args.safe_checkpoint,
            safe_rollout_root=args.safe_rollout_root,
            fiper_data_root=args.fiper_data_root,
        )
    except (OSError, json.JSONDecodeError, ProtocolError) as exc:
        print(json.dumps({"ready": False, "error": f"{type(exc).__name__}: {exc}"}, indent=2))
        return 2
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 1 if args.strict and not report["ready"] else 0


if __name__ == "__main__":
    sys.exit(main())
