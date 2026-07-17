# Current Execution Environment

更新日期：2026-07-17

本文是当前机器运行 CPU/Lean、OpenPI/LIBERO-Safety 和 GPU 实验的唯一环境入口。CLI 具体参数仍以
代码 `--help` 为准。

## 1. 固定路径

```text
workspace        /home/ldx/lean-vla
repo Python      /home/ldx/lean-vla/.venv/bin/python
OpenPI Python    /home/ldx/lean-vla/external/openpi/.venv/bin/python
Lean toolchain   /home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin
LIBERO-Safety    /home/ldx/lean-vla/external/LIBERO-Safety
OpenPI source    /home/ldx/lean-vla/external/openpi
pi0.5 checkpoint /data0/ldx/libero_safety_models/pi05_libero_safety
shared uv        /home/ldx/.conda/envs/proofalign-libero/bin/uv
```

不要重新下载模型或创建新环境。优先复用现有 checkout、checkpoint、`.venv` 和 cache。

## 2. CPU/Lean 开发环境

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/python --version
lean --version
lake --version
.venv/bin/pytest -q
(cd lean && lake build ProofAlign)
git diff --check
```

如果 shell 没有仓库 Lean PATH，测试会因 `lean`/`lake` not found 失败；这不是 evaluator verdict。

## 3. OpenPI/LIBERO 环境

```bash
cd /home/ldx/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH="$PWD/src:$PWD:$PWD/experiments/libero_safety_import_overlay:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

external/openpi/.venv/bin/python --version
test -d external/LIBERO-Safety
test -d external/openpi
test -d /data0/ldx/libero_safety_models/pi05_libero_safety
```

E1-style paired runner 使用 `external/openpi/.venv/bin/python`。通用 OpenPI runner 需要 uv project 时使用：

```bash
"$PROOFALIGN_UV" --project external/openpi run python SCRIPT.py --help
```

不要混用仓库 `.venv`、OpenPI `.venv` 和历史裸 conda 命令。

## 4. GPU 规则

GPU 分配是动态的，每次正式启动前都要重新检查：

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
```

永久约束：

- **GPU 1 禁止使用**：它属于后台 `proofalign-fiper-r0-fresh2.service`；
- 2026-07-17 检查时 GPU 3 空闲，适合作为下一实验候选，但启动时必须重查；
- 选择非 1 的 physical GPU，prelaunch used memory 目标 `<4096 MiB`；
- E1 runner 的 CUDA、MuJoCo EGL 和 render device 都绑定同一 physical id；
- JAX 在 `CUDA_VISIBLE_DEVICES=<physical id>` 的进程内通常看到 logical device 0，这是正常的；
- 不停止、kill、renice 或修改 FIPER service/process。

只读检查 FIPER：

```bash
systemctl --user show proofalign-fiper-r0-fresh2.service \
  --property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
```

## 5. 正式实验顺序

### A. 修改与验证

```bash
git status --short
.venv/bin/pytest -q TESTS...
(cd lean && lake build ProofAlign)
git diff --check
```

### B. 冻结

1. 写 protocol 和 runner；
2. protocol pin runner/source/external commit/checkpoint/file hashes；
3. 只运行不产生 rollout outcome 的 unit/fake-env/no-dispatch probe；
4. 提交冻结 commit；
5. 确认 worktree clean。

### C. GPU preflight

新 runner 必须默认只读 preflight，只有显式 `--execute --gpu PHYSICAL_ID` 才能运行。preflight 至少检查：

- selected GPU inventory/memory；
- CUDA/EGL physical-id binding；
- OpenPI real-policy output 可加载和严格序列化；
- `env.step()` 调用次数为 0；
- task/init/manifest/fallback/checkpoint/source hash；
- 双臂 shared-observer initial digest；
- output root 尚不存在。

### D. 正式运行

命令形态应为：

```bash
external/openpi/.venv/bin/python NEW_RUNNER.py \
  --protocol NEW_PROTOCOL.json \
  --output-root results/NEW_FRESH_ROOT \
  --gpu 3 \
  --execute
```

不要照抄 `3`；以当次 preflight 选出的非 GPU 1 physical id 为准。运行必须在提交冻结 protocol 的
clean commit 上启动。

### E. 终态验证

```bash
external/openpi/.venv/bin/python NEW_RUNNER.py \
  --protocol NEW_PROTOCOL.json \
  --output-root results/NEW_FRESH_ROOT \
  --validate-results
```

随后独立重算 ledger/manifest/episode hashes，写 `experiments/*_terminal_summary.json`，同步
`evaluation_results.md` 和 `project_status.md`，再提交 artifacts。正式结果不能只存在于日志或聊天中。

## 6. 已知环境问题

- `external/fiper/data` 是后台复现所需的用户 symlink，会使 generic source-clean preflight
  `source_ready=false`；不要删除它。新的 ProofAlign 自身 runner 应 pin 自己实际依赖的 source，而不是
  把该无关 symlink 当成 GPU execution blocker。
- 全量 pytest 当前预期为 `345 passed / 1 failed / 1 skipped`；唯一失败是上述 generic baseline
  preflight 的 source-ready 断言。相关 CTDA/E4 focused suite 为通过状态。
- Lean timing 很慢；保留诊断，不把 deadline 作为下一 clean utility pilot 的 gate。
