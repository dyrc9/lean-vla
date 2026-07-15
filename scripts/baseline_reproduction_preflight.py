#!/usr/bin/env python3
"""Read-only, fail-closed preflight for the deferred SAFE/FIPER reproductions.

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
    require(protocol.get("protocol_status") == "deferred_by_user_before_assets", "SAFE deferment changed")
    require(protocol.get("deferment", {}).get("blocks_phantom_r1_or_scoped_main_experiment") is False, "SAFE cannot block the scoped main experiment")
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


def validate_fiper_protocol(protocol: dict[str, Any]) -> None:
    require(protocol.get("schema") == "proofalign.fiper-r0-protocol.v1", "FIPER schema changed")
    require(protocol.get("protocol_status") == "deferred_by_user_before_assets", "FIPER deferment changed")
    require(protocol.get("deferment", {}).get("blocks_phantom_r1_or_scoped_main_experiment") is False, "FIPER cannot block the scoped main experiment")
    dataset = protocol.get("dataset", {})
    require(
        dataset.get("tasks_in_order") == ["sorting", "stacking", "push_t", "pretzel", "push_chair"],
        "FIPER task order changed",
    )
    require(dataset.get("calibration_rollouts_must_all_be_successful") is True, "FIPER clean calibration gate removed")
    pipeline = protocol.get("official_pipeline", {})
    require(pipeline.get("primary_components") == ["rnd_oe", "entropy"], "FIPER primary components changed")
    require(pipeline.get("random_seeds") == [0, 1, 2, 42, 43], "FIPER seeds changed")
    require(
        pipeline.get("threshold_styles") == ["tvt_quantile", "tvt_cp_band", "ct_quantile"],
        "FIPER threshold styles changed",
    )
    require(pipeline.get("full_default_pipeline_required_for_r0_claim") is True, "FIPER full-pipeline gate removed")
    require(pipeline.get("reduced_smoke_can_satisfy_r0") is False, "FIPER smoke cannot satisfy R0")


def validate_phantom_r1_protocol(protocol: dict[str, Any]) -> None:
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
    require(scope.get("execution_requires_safe_and_fiper_r0_readiness_decision") is False, "deferred baselines cannot block Phantom R1")
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
    blockers: list[str] = []
    checkpoint_record: dict[str, Any] = {"path": str(checkpoint) if checkpoint else None}
    if checkpoint is None or not checkpoint.is_dir():
        blockers.append("SAFE pi0_libero checkpoint directory is not available")
    else:
        checkpoint_record["present"] = True
        checkpoint_record["manifest_frozen"] = bool(
            protocol["rollout_generation"].get("checkpoint_manifest_sha256")
        )
        if not checkpoint_record["manifest_frozen"]:
            blockers.append("SAFE checkpoint manifest digest is not frozen in protocol")

    env_records: list[Path] = []
    policy_records: list[Path] = []
    if rollout_root is None or not rollout_root.is_dir():
        blockers.append("SAFE official pi0-libero_10 rollout root is not available")
    else:
        env_records = pickle_files(rollout_root / "env_records")
        policy_records = sorted((rollout_root / "policy_records").glob("*meta.pkl"))
        expected = protocol["rollout_generation"]["expected_episode_count"]
        if len(env_records) != expected:
            blockers.append(f"SAFE env record count is {len(env_records)}, expected {expected}")
        if not policy_records:
            blockers.append("SAFE policy meta records are absent")
        blockers.append("SAFE trusted-pickle schema/count inspection has not been executed")
        blockers.append("SAFE rollout-tree SHA256 manifest is not frozen")
    return {
        "checkpoint": checkpoint_record,
        "rollout_root": str(rollout_root) if rollout_root else None,
        "env_record_count": len(env_records),
        "policy_record_count": len(policy_records),
        "blockers": blockers,
    }


def check_fiper_assets(protocol: dict[str, Any], *, data_root: Path | None) -> dict[str, Any]:
    blockers: list[str] = []
    counts: dict[str, dict[str, int]] = {}
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
        blockers.append("FIPER trusted-pickle schema/label inspection has not been executed")
        blockers.append("FIPER archive and extracted-tree SHA256 manifests are not frozen")
    return {"data_root": str(data_root) if data_root else None, "counts": counts, "blockers": blockers}


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
    phantom = load_json(workspace / "experiments" / "phantom_menace_r1_protocol.json")
    validate_safe_protocol(safe)
    validate_fiper_protocol(fiper)
    validate_phantom_r1_protocol(phantom)

    safe_git = git_check(workspace / safe["source"]["safe_checkout"], safe["source"]["safe_commit"])
    safe_openpi_git = git_check(
        workspace / safe["source"]["safe_openpi_checkout"], safe["source"]["safe_openpi_commit"]
    )
    fiper_git = git_check(workspace / fiper["source"]["checkout"], fiper["source"]["commit"])
    phantom_git = git_check(workspace / "external" / "Phantom-Menace", phantom["source"]["phantom_patched_runner_commit"])
    libero_git = git_check(workspace / "external" / "LIBERO-Safety", phantom["source"]["libero_safety_commit"])
    openpi_git = git_check(workspace / "external" / "openpi", phantom["source"]["openpi_commit"])

    safe_digests, safe_digest_blockers = digest_check(workspace / "external", safe["source"]["sha256"])
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

    safe_assets = check_safe_assets(
        safe, checkpoint=safe_checkpoint, rollout_root=safe_rollout_root
    )
    fiper_assets = check_fiper_assets(fiper, data_root=fiper_data_root)
    r1_declared_blockers = list(phantom["execution_gate"]["current_blockers"])

    source_blockers = [
        *safe_git["blockers"],
        *safe_openpi_git["blockers"],
        *fiper_git["blockers"],
        *phantom_git["blockers"],
        *libero_git["blockers"],
        *openpi_git["blockers"],
        *safe_digest_blockers,
        *fiper_digest_blockers,
        *submodule_blockers,
    ]
    blockers = [*source_blockers, *safe_assets["blockers"], *fiper_assets["blockers"]]
    return {
        "schema": "proofalign.baseline-reproduction-preflight.v1",
        "workspace": str(workspace),
        "ready": not blockers,
        "source_ready": not source_blockers,
        "gpu_execution_authorized": False,
        "execution_deferred_by_user": True,
        "blocks_phantom_r1_or_scoped_main_experiment": False,
        "protocols": {
            "safe": str(workspace / "experiments" / "safe_r0_protocol.json"),
            "fiper": str(workspace / "experiments" / "fiper_r0_protocol.json"),
            "phantom_r1": str(workspace / "experiments" / "phantom_menace_r1_protocol.json"),
        },
        "git": {
            "safe": safe_git,
            "safe_openpi": safe_openpi_git,
            "fiper": fiper_git,
            "phantom": phantom_git,
            "libero_safety": libero_git,
            "openpi": openpi_git,
        },
        "source_digests": {"safe": safe_digests, "fiper": fiper_digests},
        "safe_assets": safe_assets,
        "fiper_assets": fiper_assets,
        "phantom_r1_declared_blockers": r1_declared_blockers,
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
