"""Small LIBERO runtime boundary used by the active experiment mainline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class LiberoRuntimeError(RuntimeError):
    """Raised when the external LIBERO runtime cannot be loaded or normalized."""


@dataclass(frozen=True)
class LiberoTaskRuntime:
    benchmark: Any
    task: Any
    task_id: int
    task_name: str
    instruction: str
    bddl_file: Path
    init_state: Any | None
    init_state_id: int
    metadata: dict[str, Any] = field(default_factory=dict)


def load_libero_task_runtime(
    *,
    benchmark_name: str,
    task_id: int,
    init_state_id: int,
    bddl_file: str | None = None,
) -> LiberoTaskRuntime:
    try:
        from libero.libero import get_libero_path
        from libero.libero.benchmark import get_benchmark
    except Exception as exc:  # pragma: no cover - requires the external checkout.
        raise LiberoRuntimeError(
            "Could not import LIBERO/LIBERO-Safety; restore the pinned external checkout"
        ) from exc

    benchmark = get_benchmark(benchmark_name)()
    task = benchmark.get_task(task_id)
    task_name = str(getattr(task, "name", f"{benchmark_name}_{task_id}"))
    instruction = str(getattr(task, "language", "") or task_name.replace("_", " "))
    canonical_bddl_path = _resolve_task_bddl_path(
        get_libero_path("bddl_files"), task
    ).resolve()
    bddl_path = (
        Path(bddl_file).expanduser().resolve()
        if bddl_file
        else canonical_bddl_path
    )
    init_state = _load_init_state(benchmark, task, task_id, init_state_id)
    return LiberoTaskRuntime(
        benchmark=benchmark,
        task=task,
        task_id=task_id,
        task_name=task_name,
        instruction=instruction,
        bddl_file=bddl_path,
        init_state=init_state,
        init_state_id=init_state_id,
        metadata={
            "benchmark_name": benchmark_name,
            "task_id": task_id,
            "task_name": task_name,
            "init_state_id": init_state_id,
            "bddl_file": str(bddl_path),
            "canonical_bddl_file": str(canonical_bddl_path),
        },
    )


def make_libero_offscreen_env(bddl_file_name: str, **kwargs: Any) -> Any:
    try:
        from libero.libero.envs import OffScreenRenderEnv
    except Exception as exc:  # pragma: no cover - requires the external checkout.
        raise LiberoRuntimeError(
            "Could not import LIBERO-Safety OffScreenRenderEnv"
        ) from exc
    return OffScreenRenderEnv(bddl_file_name=bddl_file_name, **kwargs)


def normalize_env_step(result: Any) -> tuple[Any, float, bool, dict[str, Any]]:
    if not isinstance(result, tuple):
        raise LiberoRuntimeError(
            f"LIBERO env.step returned unsupported value: {type(result).__name__}"
        )
    if len(result) == 4:
        observation, reward, done, info = result
        return observation, float(reward), bool(done), dict(info or {})
    if len(result) == 5:
        observation, reward, terminated, truncated, info = result
        return (
            observation,
            float(reward),
            bool(terminated or truncated),
            dict(info or {}),
        )
    raise LiberoRuntimeError(
        f"LIBERO env.step returned tuple of length {len(result)}"
    )


def _resolve_task_bddl_path(bddl_root: str, task: Any) -> Path:
    root = Path(bddl_root)
    problem_folder = str(getattr(task, "problem_folder", ""))
    bddl_file = str(getattr(task, "bddl_file"))
    direct = root / problem_folder / bddl_file
    if direct.exists():
        return direct
    level = getattr(task, "level", None)
    if level is not None:
        level_dir = root / problem_folder / f"L{int(level)}"
        leveled = level_dir / bddl_file
        if leveled.exists():
            return leveled
        matched = _match_bddl_stem(level_dir, bddl_file)
        if matched is not None:
            return matched
    matched = _match_bddl_stem(root / problem_folder, bddl_file)
    return matched if matched is not None else direct


def _match_bddl_stem(directory: Path, bddl_file: str) -> Path | None:
    if not directory.exists():
        return None
    requested = Path(bddl_file).stem
    matches = [
        candidate
        for candidate in sorted(directory.glob("*.bddl"))
        if requested.startswith(candidate.stem) or candidate.stem.startswith(requested)
    ]
    return matches[0] if len(matches) == 1 else None


def _load_init_state(
    benchmark: Any, task: Any, task_id: int, init_state_id: int
) -> Any | None:
    for method_name, call_args in (
        ("get_task_init_states", (task_id,)),
        (
            "get_task_init_states_by_level_id",
            (getattr(task, "level", 0), getattr(task, "level_id", task_id)),
        ),
    ):
        method = getattr(benchmark, method_name, None)
        if not callable(method):
            continue
        try:
            return _select_init_state(method(*call_args), init_state_id)
        except Exception:
            continue
    init_file = getattr(task, "init_states_file", None)
    problem_folder = getattr(task, "problem_folder", None)
    if init_file and problem_folder:
        try:
            from libero.libero import get_libero_path
            import torch

            path = (
                Path(get_libero_path("init_states"))
                / str(problem_folder)
                / str(init_file)
            )
            return _select_init_state(torch.load(path), init_state_id)
        except Exception:
            return None
    return None


def _select_init_state(init_states: Any, init_state_id: int) -> Any:
    if init_states is None:
        return None
    try:
        return init_states[init_state_id]
    except Exception:
        return init_states


__all__ = [
    "LiberoRuntimeError",
    "LiberoTaskRuntime",
    "load_libero_task_runtime",
    "make_libero_offscreen_env",
    "normalize_env_step",
]
