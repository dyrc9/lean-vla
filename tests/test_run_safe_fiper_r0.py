from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_safe_fiper_r0 import (
    LaunchError,
    fiper_plan,
    main,
    manifest,
    parse_args,
    prepare_fiper_runtime_data,
    remove_fiper_data_link,
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
    assert fiper.argv[2].startswith("hydra.run.dir=")
    assert fiper.env["UV_CACHE_DIR"] == "/data0/ldx/uv-cache"
    assert fiper.env["PROOFALIGN_FIPER_ROOT"].endswith("/external/fiper")


def test_manifest_records_root_and_gpu_process_provenance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[tuple[str, ...], Path]] = []

    def fake_command_output(argv, *, cwd):
        calls.append((tuple(argv), cwd))
        return {"argv": list(argv), "returncode": 0, "stdout": "ok", "stderr": ""}

    monkeypatch.setattr("scripts.run_safe_fiper_r0.command_output", fake_command_output)
    launch_args = args("fiper", tmp_path)
    report = manifest(launch_args, fiper_plan(launch_args))

    assert report["versions"]["proofalign"]["returncode"] == 0
    assert report["versions"]["proofalign_status"]["returncode"] == 0
    assert report["versions"]["gpu"]["returncode"] == 0
    assert report["versions"]["gpu_compute_apps"]["returncode"] == 0
    queried = {argv for argv, _cwd in calls}
    assert ("git", "rev-parse", "HEAD") in queried
    assert ("git", "status", "--porcelain=v1") in queried
    assert (
        "nvidia-smi",
        "--query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu",
        "--format=csv,noheader",
    ) in queried
    assert (
        "nvidia-smi",
        "--query-compute-apps=gpu_uuid,pid,process_name,used_memory",
        "--format=csv,noheader",
    ) in queried


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


def test_fiper_runtime_data_is_fresh_and_source_link_is_temporary(tmp_path: Path) -> None:
    source = tmp_path / "official"
    for task in ("sorting", "push_t"):
        (source / task / "rollouts").mkdir(parents=True)
    protocol = tmp_path / "fiper_protocol.json"
    protocol.write_text(
        json.dumps(
            {
                "dataset": {
                    "extracted_data_root": str(source),
                    "tasks_in_order": ["sorting", "push_t"],
                }
            }
        ),
        encoding="utf-8",
    )
    fiper_root = tmp_path / "fiper"
    run_dir = tmp_path / "run"
    fiper_root.mkdir()
    run_dir.mkdir()
    launch_args = SimpleNamespace(
        fiper_protocol=protocol,
        fiper_root=fiper_root,
        run_dir=run_dir,
    )

    data_link, runtime_root = prepare_fiper_runtime_data(launch_args)

    assert data_link.is_symlink()
    assert data_link.resolve() == runtime_root
    assert (runtime_root / "sorting" / "rollouts").resolve() == source / "sorting" / "rollouts"
    assert (runtime_root / "push_t" / "rollouts").resolve() == source / "push_t" / "rollouts"

    remove_fiper_data_link(data_link, runtime_root)
    assert not data_link.exists()
    assert runtime_root.is_dir()
