from __future__ import annotations

import argparse
import ast
from collections import Counter
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTOCOL = REPO_ROOT / "experiments" / "proofalign_e0_protocol.json"


class E0AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceTask:
    suite: str
    task_id: int
    level: int
    level_id: int
    task_name: str
    instruction: str
    bddl_file: str
    bddl_sha256: str
    init_file: str | None


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def _task_map(path: Path) -> dict[str, dict[int, list[str]]]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if "vla_safety_task_map" not in names:
            continue
        value = ast.literal_eval(node.value)
        return {
            str(suite): {
                int(level): [str(task) for task in tasks]
                for level, tasks in levels.items()
            }
            for suite, levels in value.items()
        }
    raise E0AuditError(f"vla_safety_task_map is absent from {path}")


def _match_task_file(directory: Path, task_name: str, suffix: str) -> Path | None:
    exact = directory / f"{task_name}{suffix}"
    if exact.is_file():
        return exact
    matches = [
        item
        for item in sorted(directory.glob(f"*{suffix}"))
        if task_name.startswith(item.stem) or item.stem.startswith(task_name)
    ]
    return matches[0] if len(matches) == 1 else None


def _bddl_instruction(text: str) -> str:
    import re

    match = re.search(r"\(:language\s+([^)]+)\)", text)
    if match is None:
        raise E0AuditError("BDDL task has no :language field")
    return " ".join(match.group(1).split())


def source_tasks(benchmark_root: Path, suites: tuple[str, ...]) -> list[SourceTask]:
    source_root = benchmark_root / "libero" / "libero"
    map_path = source_root / "benchmark" / "vla_safety_task_map.py"
    task_map = _task_map(map_path)
    records: list[SourceTask] = []
    for suite in suites:
        if suite not in task_map:
            raise E0AuditError(f"suite {suite!r} is absent from the pinned task map")
        task_id = 0
        for level in sorted(task_map[suite]):
            for level_id, task_name in enumerate(task_map[suite][level]):
                bddl = _match_task_file(
                    source_root / "bddl_files" / suite / f"L{level}",
                    task_name,
                    ".bddl",
                )
                if bddl is None:
                    raise E0AuditError(
                        f"could not resolve one BDDL file for {suite}/{task_id}: {task_name}"
                    )
                init_file = _match_task_file(
                    source_root / "init_files" / suite / f"L{level}",
                    task_name,
                    ".pruned_init",
                )
                text = bddl.read_text(encoding="utf-8")
                records.append(
                    SourceTask(
                        suite=suite,
                        task_id=task_id,
                        level=level,
                        level_id=level_id,
                        task_name=task_name,
                        instruction=_bddl_instruction(text),
                        bddl_file=str(bddl.relative_to(benchmark_root)),
                        bddl_sha256=_sha256(bddl),
                        init_file=(
                            str(init_file.relative_to(benchmark_root))
                            if init_file is not None
                            else None
                        ),
                    )
                )
                task_id += 1
    return records


def _expand_groups(groups: dict[str, list[int]], suites: tuple[str, ...]) -> set[tuple[str, int]]:
    unknown_suites = sorted(set(groups) - set(suites))
    if unknown_suites:
        raise E0AuditError(f"classification contains unknown suites: {unknown_suites}")
    return {
        (suite, int(task_id))
        for suite, task_ids in groups.items()
        for task_id in task_ids
    }


def validate_protocol_structure(protocol: dict[str, Any]) -> dict[str, set[tuple[str, int]]]:
    if protocol.get("schema") not in {
        "proofalign.e0.protocol.v1",
        "proofalign.e0.protocol.v2-candidate",
    }:
        raise E0AuditError("unsupported E0 protocol schema")
    benchmark = protocol.get("benchmark") or {}
    suites = tuple(str(item) for item in benchmark.get("suites", []))
    task_ids = tuple(int(item) for item in benchmark.get("task_ids", []))
    if not suites or not task_ids:
        raise E0AuditError("benchmark suites and task ids must be non-empty")
    universe = {(suite, task_id) for suite in suites for task_id in task_ids}
    classification = protocol.get("classification") or {}
    expanded = {
        name: _expand_groups(classification.get(name) or {}, suites)
        for name in ("supported", "ambiguous", "unsupported")
    }
    for name, values in expanded.items():
        outside = sorted(values - universe)
        if outside:
            raise E0AuditError(f"{name} classification is outside the task universe: {outside}")
    overlap = (
        (expanded["supported"] & expanded["ambiguous"])
        | (expanded["supported"] & expanded["unsupported"])
        | (expanded["ambiguous"] & expanded["unsupported"])
    )
    if overlap:
        raise E0AuditError(f"task classification overlaps: {sorted(overlap)}")
    covered = set().union(*expanded.values())
    if covered != universe:
        raise E0AuditError(
            f"task classification does not cover the universe; missing={sorted(universe - covered)}"
        )
    structural = _expand_groups(
        protocol.get("live_init_audit", {}).get("structurally_compiled") or {},
        suites,
    )
    expected_structural = expanded["supported"] | expanded["ambiguous"] | _expand_groups(
        protocol.get("classification", {}).get("unsupported_but_structurally_compiled") or {},
        suites,
    )
    if structural != expected_structural:
        raise E0AuditError(
            "structural compiler list differs from the classified structural candidates"
        )
    frozen_units = {
        (str(item["suite"]), int(item["task_id"]))
        for item in protocol.get("e1", {}).get("pilot_units", [])
    }
    if frozen_units != expanded["supported"]:
        raise E0AuditError("E1 pilot units must equal the complete frozen supported set")
    return {**expanded, "universe": universe, "structural": structural}


def _validate_pins(protocol: dict[str, Any], benchmark_root: Path) -> list[str]:
    issues: list[str] = []
    pins = protocol.get("method_pins") or {}
    if _git_commit(REPO_ROOT) != pins.get("base_commit"):
        # Documentation/audit commits after the method freeze are expected. File
        # digests below are the normative method pin.
        issues.append("repository HEAD differs from method base_commit (informational)")
    for relative, expected in (pins.get("files") or {}).items():
        path = REPO_ROOT / relative
        actual = _sha256(path) if path.is_file() else None
        if actual != expected:
            raise E0AuditError(f"method pin mismatch for {relative}: {actual} != {expected}")
    benchmark = protocol["benchmark"]
    actual_commit = _git_commit(benchmark_root)
    if actual_commit != benchmark.get("commit"):
        raise E0AuditError(
            f"LIBERO-Safety commit mismatch: {actual_commit} != {benchmark.get('commit')}"
        )
    map_path = benchmark_root / "libero" / "libero" / "benchmark" / "vla_safety_task_map.py"
    actual_map_digest = _sha256(map_path) if map_path.is_file() else None
    if actual_map_digest != benchmark.get("task_map_sha256"):
        raise E0AuditError("LIBERO-Safety task-map digest mismatch")
    for item in protocol.get("fallback_artifacts", []):
        path = REPO_ROOT / str(item["path"])
        actual = _sha256(path) if path.is_file() else None
        if actual != item.get("sha256"):
            raise E0AuditError(f"fallback artifact digest mismatch for {path}")
    return issues


def _live_probe(
    protocol: dict[str, Any],
    task: SourceTask,
    benchmark_root: Path,
) -> dict[str, Any]:
    # Importing the benchmark is intentionally delayed so source-only audit has
    # no MuJoCo/PyTorch dependency. This path performs reset/set_init_state and
    # symbolic compilation only: it never loads a policy or calls env.step().
    from proofalign.benchmark.libero_online_runner import (
        build_safety_spec,
        create_initialized_env,
        load_libero_task_runtime,
        parse_args as parse_episode_args,
    )
    from proofalign.benchmark.libero_online_wrapper import LiberoStateObserver
    from proofalign.benchmark.libero_task_manifest import (
        LiberoTaskManifestError,
        compile_libero_task_manifest,
        load_libero_task_manifest,
    )
    from proofalign.ctda import AuthorityEnvelope, TimeBase, digest_text, mission_from_legacy
    from proofalign.intent_parser import parse_intent

    execution = protocol["execution"]
    task_manifest = None
    manifest_error = None
    registry_value = protocol.get("task_manifest_registry")
    if registry_value:
        try:
            task_manifest = load_libero_task_manifest(
                REPO_ROOT / str(registry_value),
                suite=task.suite,
                task_id=task.task_id,
                bddl_path=benchmark_root / task.bddl_file,
            )
        except LiberoTaskManifestError as exc:
            manifest_error = f"{type(exc).__name__}: {exc}"
    args = parse_episode_args(
        [
            "--benchmark",
            task.suite,
            "--task-id",
            str(task.task_id),
            "--init-state-id",
            str(execution["init_state_ids"][0]),
            "--warmup-steps",
            "0",
            "--camera-height",
            str(execution["camera_height"]),
            "--camera-width",
            str(execution["camera_width"]),
            "--camera-names",
            ",".join(execution["camera_names"]),
            "--render-gpu-device-id",
            str(execution.get("audit_render_gpu_device_id", -1)),
            "--control-freq",
            str(execution["control_freq_hz"]),
            "--horizon",
            str(execution["environment_horizon"]),
            "--seed",
            str(execution["env_seeds"][0]),
        ]
    )
    runtime = load_libero_task_runtime(
        benchmark_name=task.suite,
        task_id=task.task_id,
        init_state_id=int(execution["init_state_ids"][0]),
        bddl_file=str(benchmark_root / task.bddl_file),
    )
    # Load runtime before build_safety_spec: the legacy adapter adds an import
    # path that can shadow LIBERO's namespace-package layout if used first.
    spec = build_safety_spec(args)
    env = create_initialized_env(runtime, args)
    try:
        observation = getattr(env, "_proofalign_initialized_observation", None)
        observer = LiberoStateObserver(
            contact_part_queries=(task_manifest.contact_query,) if task_manifest else ()
        )
        state = observer.observe(env, observation)
        result: dict[str, Any] = {
            "registered_init_present": runtime.init_state is not None,
            "selected_init_state_applied": bool(
                getattr(env, "_proofalign_selected_init_state_applied", False)
            ),
            "initialized_observation_source": getattr(
                env, "_proofalign_initialized_observation_source", "unknown"
            ),
            "compiler_status": "rejected",
            "compiler_reason": None,
            "mission_goal": None,
            "phases": [],
            "unknown_observations": sorted(
                note
                for note in state.notes
                if note.startswith("ctda_unknown_observation:")
            ),
        }
        try:
            authority = AuthorityEnvelope(
                "proofalign-e0-audit",
                "libero-safety-live-init",
                "v2-candidate" if registry_value else "v1",
                digest_text("proofalign-e0-audit"),
                authenticated=False,
            )
            time_base = TimeBase(
                "e0-audit-clock", 20_000_000, 1_000_000, 1_000_000, 2_000_000
            )
            compiler_args = {
                "spec_id": f"{task.suite}:{task.task_id}:{execution['init_state_ids'][0]}",
                "episode_nonce": "e0-live-init-audit-no-rollout",
            }
            if registry_value:
                if manifest_error is not None or task_manifest is None:
                    raise LiberoTaskManifestError(
                        manifest_error or "task has no source-bound manifest"
                    )
                mission = compile_libero_task_manifest(
                    task_manifest,
                    state,
                    spec,
                    authority,
                    time_base,
                    **compiler_args,
                )
            else:
                mission = mission_from_legacy(
                    parse_intent(runtime.instruction),
                    state,
                    spec,
                    authority,
                    time_base,
                    **compiler_args,
                )
        except Exception as exc:
            result["compiler_reason"] = f"{type(exc).__name__}: {exc}"
        else:
            result.update(
                {
                    "compiler_status": "compiled",
                    "mission_goal": mission.goal,
                    "mission_goal_atoms": list(mission.goal_atoms),
                    "phases": list(mission.phases),
                }
            )
        return result
    finally:
        if hasattr(env, "close"):
            env.close()


def audit(
    protocol_path: Path,
    benchmark_root: Path,
    *,
    live_init: bool,
) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expanded = validate_protocol_structure(protocol)
    notes = _validate_pins(protocol, benchmark_root)
    suites = tuple(protocol["benchmark"]["suites"])
    tasks = source_tasks(benchmark_root, suites)
    actual_universe = {(task.suite, task.task_id) for task in tasks}
    if actual_universe != expanded["universe"]:
        raise E0AuditError("pinned source task universe differs from the frozen protocol")
    records: list[dict[str, Any]] = []
    observed_structural: set[tuple[str, int]] = set()
    config_context = tempfile.TemporaryDirectory(
        prefix="proofalign-libero-safety-config-"
    ) if live_init else nullcontext(None)
    previous_config = os.environ.get("LIBERO_CONFIG_PATH")
    try:
        with config_context as config_dir:
            if config_dir is not None:
                _write_libero_config(Path(config_dir), benchmark_root)
                os.environ["LIBERO_CONFIG_PATH"] = str(config_dir)
            for task in tasks:
                key = (task.suite, task.task_id)
                status = next(
                    name
                    for name in ("supported", "ambiguous", "unsupported")
                    if key in expanded[name]
                )
                record = asdict(task) | {
                    "classification": status,
                    "e1_eligible": key in expanded["supported"],
                }
                if live_init:
                    record["live_init"] = _live_probe(protocol, task, benchmark_root)
                    if record["live_init"]["compiler_status"] == "compiled":
                        observed_structural.add(key)
                records.append(record)
    finally:
        if previous_config is None:
            os.environ.pop("LIBERO_CONFIG_PATH", None)
        else:
            os.environ["LIBERO_CONFIG_PATH"] = previous_config
    if live_init and observed_structural != expanded["structural"]:
        raise E0AuditError(
            "live structural compiler result changed; "
            f"added={sorted(observed_structural - expanded['structural'])}, "
            f"removed={sorted(expanded['structural'] - observed_structural)}"
        )
    counts = Counter(record["classification"] for record in records)
    protocol_schema = str(protocol.get("schema"))
    report = {
        "schema": (
            "proofalign.e0.audit.v2-candidate"
            if protocol_schema.endswith("v2-candidate")
            else "proofalign.e0.audit.v1"
        ),
        "protocol": str(protocol_path),
        "benchmark_root": str(benchmark_root),
        "benchmark_commit": _git_commit(benchmark_root),
        "outcome_blind": True,
        "policy_loaded": False,
        "env_step_called": False,
        "live_init_checked": live_init,
        "counts": {
            "task_total": len(records),
            "supported": counts["supported"],
            "ambiguous": counts["ambiguous"],
            "unsupported": counts["unsupported"],
            "structurally_compiled": (
                len(observed_structural) if live_init else len(expanded["structural"])
            ),
            "e1_pilot_units": len(protocol["e1"]["pilot_units"]),
        },
        "notes": notes,
        "tasks": records,
    }
    return report


def _write_libero_config(config_dir: Path, benchmark_root: Path) -> None:
    source_root = (benchmark_root / "libero" / "libero").resolve()
    payload = {
        "benchmark_root": str(source_root),
        "bddl_files": str(source_root / "bddl_files"),
        "init_states": str(source_root / "init_files"),
        "datasets": str((benchmark_root / "libero" / "datasets").resolve()),
        "assets": str(source_root / "assets"),
    }
    config_dir.mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML and avoids importing benchmark dependencies here.
    (config_dir / "config.yaml").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the outcome-blind ProofAlign E0 scope freeze."
    )
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument(
        "--benchmark-root",
        type=Path,
        default=Path(os.environ.get("LIBERO_SAFETY_ROOT", REPO_ROOT / "external" / "LIBERO-Safety")),
    )
    parser.add_argument(
        "--live-init",
        action="store_true",
        help="Also reset/apply init and compile the observed registry; never loads policy or steps env.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = audit(
            args.protocol.expanduser().resolve(),
            args.benchmark_root.expanduser().resolve(),
            live_init=bool(args.live_init),
        )
    except (E0AuditError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(json.dumps({"ready": False, "error": str(exc)}, indent=2))
        return 1
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
