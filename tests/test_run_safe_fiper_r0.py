from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_safe_fiper_r0 import (
    LaunchError,
    fiper_plan,
    main,
    parse_args,
    safe_detector_plan,
    safe_rollout_plan,
)


ROOT = Path(__file__).resolve().parents[1]


def args(target: str, tmp_path: Path):
    values = [
        "--target",
        target,
        "--dry-run",
        "--run-dir",
        str(tmp_path / target),
        "--policy-gpu",
        "3",
        "--egl-gpu",
        "5",
    ]
    return parse_args(values)


def test_safe_rollout_plan_is_the_frozen_500_episode_pi0_run(tmp_path: Path) -> None:
    plan = safe_rollout_plan(args("safe-rollout", tmp_path))
    server, client = plan

    assert "pi0_libero" in server.argv
    assert "pi05_libero" not in server.argv
    assert server.env["CUDA_VISIBLE_DEVICES"] == "3"
    assert server.env["UV_PROJECT_ENVIRONMENT"] == "/data0/ldx/uv-envs/safe-r0-openpi"
    assert client.env["CUDA_VISIBLE_DEVICES"] == "5"
    assert client.env["MUJOCO_EGL_DEVICE_ID"] == "5"
    assert client.argv[0] == "/data0/ldx/uv-envs/safe-r0-libero-client/bin/python"
    assert client.argv[client.argv.index("--args.num_trials_per_task") + 1] == "50"
    assert client.argv[client.argv.index("--args.start_task_id") + 1] == "0"
    assert client.argv[client.argv.index("--args.end_task_id") + 1] == "9"


def test_detector_and_fiper_plans_use_isolated_uv_environments(tmp_path: Path) -> None:
    safe = safe_detector_plan(args("safe-detector", tmp_path))[0]
    fiper = fiper_plan(args("fiper", tmp_path))[0]

    assert safe.env["PATH"].startswith("/data0/ldx/uv-envs/safe-r0/bin:")
    assert safe.env["WANDB_MODE"] == "offline"
    assert fiper.argv[0] == "/data0/ldx/uv-envs/fiper-r0/bin/python"
    assert fiper.argv[1].endswith("/scripts/run_fiper_compat.py")
    assert fiper.env["UV_CACHE_DIR"] == "/data0/ldx/uv-cache"


def test_safe_rollout_refuses_implicit_or_shared_gpu(tmp_path: Path) -> None:
    base = [
        "--target",
        "safe-rollout",
        "--dry-run",
        "--run-dir",
        str(tmp_path / "run"),
    ]
    with pytest.raises(LaunchError, match="policy-gpu"):
        main(base)
    with pytest.raises(LaunchError, match="distinct"):
        main(base + ["--policy-gpu", "3", "--egl-gpu", "3"])
