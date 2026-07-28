#!/usr/bin/env python3
"""Run the L1 qualification with fail-closed interpreter/EGL selection."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
for root in (REPO_ROOT / "src", REPO_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

from proofalign.benchmark.confirmatory import load_json_object  # noqa: E402
from proofalign.benchmark.four_arm_v4 import canonical_text  # noqa: E402
from scripts import run_four_arm_v4_l1_repair_qualification as v1  # noqa: E402


DEFAULT_PROTOCOL = (
    REPO_ROOT
    / "experiments"
    / "proofalign_four_arm_v4_l1_repair_qualification_fresh3_protocol.json"
)
REQUIRED_INTERPRETER = (
    REPO_ROOT / "external" / "openpi" / ".venv" / "bin" / "python"
)
_BASE_PREFLIGHT = v1.preflight
_BASE_ARGS = v1._args
_DEVICE_STATE: dict[str, Any] | None = None


class RepairQualificationV2Error(RuntimeError):
    """Raised when the corrected qualification launch must fail closed."""


def _runtime_device_state(gpu: int) -> dict[str, Any]:
    if Path(sys.executable).resolve() != REQUIRED_INTERPRETER.resolve():
        raise RepairQualificationV2Error(
            "qualification must use external/openpi/.venv/bin/python"
        )
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
    os.environ["MUJOCO_GL"] = "egl"
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    from scripts.run_saber_integrity_action_envelope_r3 import (
        _egl_cuda_device_mapping,
    )

    mapping = _egl_cuda_device_mapping()
    ordinals = [
        int(row["egl_device_ordinal"])
        for row in mapping
        if int(row["cuda_physical_index"]) == gpu
    ]
    if len(ordinals) != 1:
        raise RepairQualificationV2Error(
            f"GPU {gpu} has no unique EGL ordinal: {mapping}"
        )
    egl_ordinal = ordinals[0]
    if egl_ordinal != gpu:
        raise RepairQualificationV2Error(
            "the single-GPU qualification requires physical CUDA index "
            f"{gpu} to equal its EGL ordinal, observed {egl_ordinal}"
        )
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(egl_ordinal)
    import jax

    jax.config.update("jax_cuda_visible_devices", "0")
    return {
        "mapping_source": "EGL_NV_device_cuda",
        "mapping": mapping,
        "selected_cuda_physical_index": gpu,
        "selected_egl_device_ordinal": egl_ordinal,
        "cuda_visible_devices": str(gpu),
        "jax_cuda_visible_devices": "0",
        "interpreter": str(Path(sys.executable).resolve()),
        "jax_version": str(jax.__version__),
    }


def _configure_single_gpu(gpu: int) -> None:
    global _DEVICE_STATE
    _DEVICE_STATE = _runtime_device_state(gpu)
    os.environ["MUJOCO_EGL_DEVICE_ID"] = str(
        _DEVICE_STATE["selected_egl_device_ordinal"]
    )
    os.environ["MUJOCO_GL"] = "egl"
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    os.environ["JAX_COMPILATION_CACHE_DIR"] = (
        "/data0/ldx/jax-cache/proofalign-l1-repair-qualification"
    )
    os.environ["XLA_PYTHON_CLIENT_PREALLOCATE"] = "false"
    os.environ["LIBERO_SAFETY_ROOT"] = str(
        REPO_ROOT / "external" / "LIBERO-Safety"
    )


def _args(
    protocol: dict[str, Any],
    *,
    output_root: Path,
) -> SimpleNamespace:
    if _DEVICE_STATE is None:
        raise RepairQualificationV2Error(
            "device mapping was not established before argument construction"
        )
    args = _BASE_ARGS(protocol, output_root=output_root)
    args.render_gpu_device_id = int(
        _DEVICE_STATE["selected_egl_device_ordinal"]
    )
    return args


def preflight(
    protocol: dict[str, Any],
    *,
    protocol_path: Path,
    gpu: int | None,
) -> dict[str, Any]:
    report = _BASE_PREFLIGHT(
        protocol,
        protocol_path=protocol_path,
        gpu=gpu,
    )
    blockers = list(report["blockers"])
    device_state = None
    if gpu is not None:
        try:
            device_state = _runtime_device_state(gpu)
        except BaseException as exc:
            blockers.append(
                f"runtime device preflight failed: {type(exc).__name__}: {exc}"
            )
    return {
        **report,
        "schema": "proofalign.four-arm-v4-l1-repair-preflight.v2",
        "ready": not blockers,
        "blockers": blockers,
        "runtime_device": device_state,
    }


def _install_v2_launch() -> None:
    v1.preflight = preflight
    v1._configure_single_gpu = _configure_single_gpu
    v1._args = _args


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--validate-results", action="store_true")
    parser.add_argument("--gpu", type=int)
    args = parser.parse_args(argv)
    if sum(
        (args.preflight, args.execute, args.validate_results)
    ) != 1:
        parser.error(
            "choose exactly one of --preflight, --execute, "
            "or --validate-results"
        )
    protocol_path = args.protocol.resolve()
    protocol = load_json_object(protocol_path)
    _install_v2_launch()
    if args.preflight:
        payload = preflight(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    elif args.execute:
        if args.gpu is None:
            parser.error("--execute requires --gpu")
        payload = v1.execute(
            protocol,
            protocol_path=protocol_path,
            gpu=args.gpu,
        )
    else:
        payload = v1.validate_results(
            protocol,
            protocol_path=protocol_path,
        )
    print(canonical_text(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
