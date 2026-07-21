# Current Execution Environment

更新日期：2026-07-21

本文是当前机器运行 CPU/Lean、OpenPI/LIBERO-Safety 和 GPU 实验的唯一环境入口。CLI 具体参数仍以
代码 `--help` 为准。

> **P0b 是唯一例外。** 用户已授权 `saber_threat_replication_p0b_producer_protocol.json` 的 official
> producer，以及其 immutable record gate 通过后新冻结的 P0b victim protocol。两阶段都必须满足 committed
> protocol、clean worktree、fresh absent root 和各自 `<4096 MiB` GPU gate；当前 6 张 GPU 均不满足，所以
> 不执行。其余 OpenPI、MuJoCo、AEGIS 和任何 `--execute` 命令仍暂停。

## 1. 固定路径

```text
workspace        /home/ldx/lean-vla
repo Python      /home/ldx/lean-vla/.venv/bin/python
OpenPI Python    /home/ldx/lean-vla/external/openpi/.venv/bin/python
Lean toolchain   /home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin
LIBERO-Safety    /home/ldx/lean-vla/external/LIBERO-Safety
OpenPI source    /home/ldx/lean-vla/external/openpi
AEGIS source     /home/ldx/lean-vla/external/vlsa-aegis
AEGIS server py  /home/ldx/lean-vla/external/vlsa-aegis/.aegis_venv/bin/python
AEGIS sim py     /home/ldx/lean-vla/external/vlsa-aegis/main/.venv/bin/python
pi0.5 checkpoint /data0/ldx/libero_safety_models/pi05_libero_safety
AEGIS pi0.5      /data0/ldx/saber-cache/openpi/openpi-assets/checkpoints/pi05_libero
AEGIS G-DINO     /data0/ldx/aegis-assets/GroundingDINO
shared uv        /home/ldx/.conda/envs/proofalign-libero/bin/uv
```

不要重新下载模型或创建新环境。优先复用现有 checkout、checkpoint、`.venv` 和 cache。

AEGIS 使用独立环境：官方 source pin 到 commit `57b1aef...`，根目录 Python 3.11 `.aegis_venv` 与
`main/.venv` Python 3.8 已按官方 requirements 建立；标准 `pi05_libero` 与 GroundingDINO 资产位于上列
隔离路径。不得把仓库 OpenPI `.venv` 混作 AEGIS runtime，也不得把 safety-tuned
`pi05_libero_safety` 当作 AEGIS 标准 checkpoint。

## 2. SafeLIBERO/AEGIS 只读 readiness

该检查不构造 simulator、不加载 policy、不调用 `env.step()`，也没有 `--execute`：

```bash
cd /home/ldx/lean-vla
.venv/bin/python scripts/safelibero_aegis_readiness.py \
  --protocol experiments/safelibero_aegis_readiness_protocol.json \
  --source-root external/vlsa-aegis
```

当前预期：`foundation_ready=true`、`aegis_runtime_ready=false`、
`formal_rollout_authorized=false`、`env_step_count=0`。source/data ready 只说明官方 commit/tree/license、
32 scenario、1600 init 和数据 digest 匹配，不说明模型、GPU、场景构造或 AEGIS closed loop 可运行。

static runtime R1 继续核验双环境全部 distribution、源码导入路径、标准 pi0.5/GroundingDINO 身份和
SafeLIBERO 注册；仍不构造 policy/simulator，不监听 socket，也不调用推理或 `env.step()`：

```bash
cd /home/ldx/lean-vla
.venv/bin/python scripts/safelibero_aegis_runtime_preflight.py \
  --protocol experiments/safelibero_aegis_runtime_protocol.json
```

当前预期：`static_runtime_ready=true`、`model_load_probe_authorized=true`、五个 counter 全为 0、
`formal_rollout_authorized=false`。R1 记录了 policy-server 未使用的 `av 14.4.0 -> 14.2.0` 安装兼容覆盖；
不得隐藏或扩大该偏差。

R2/R3 已执行并封存；复核默认 dry-run 不会重新加载模型或构造 scene：

```bash
.venv/bin/python scripts/safelibero_aegis_model_load_probe.py
.venv/bin/python scripts/safelibero_aegis_scene_probe.py
```

终态为 `model_load_ready=true`、`scene_ready=true`、`env_step_count=0`、
`formal_rollout_authorized=false`。执行模式需要各自的冻结 protocol、fresh GPU gate 和显式 `--execute`；
不得仅为复核而重跑。

CTDA v2 full-population state gate 已执行并封存。日常只运行 dry-run（无 simulator）：

```bash
.venv/bin/python scripts/ctda_v2_support_audit.py
.venv/bin/python scripts/ctda_v2_safelibero_state_coverage.py \
  --protocol experiments/ctda_v2_safelibero_state_coverage_protocol_r1.json
```

r1 终态为 32 scenario/1600 init、state key 1600/1600、collision source 1600/1600、`env.step=0`，且
`formal_rollout_authorized=false`。没有新的 protocol/fresh output/GPU 空闲检查时不得加 `--execute`；
r0 的 1250/1600 region-anchor 负结果是保留 artifact，不得覆盖。

## 3. CPU/Lean 开发环境

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

## 4. OpenPI/LIBERO 环境

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

## 5. GPU 规则

GPU 分配是动态的，每次正式启动前都要重新检查：

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
```

永久约束：

- 2026-07-17 16:14 起没有运行中的 ProofAlign/FIPER service；FIPER fresh2 已按用户要求停止；
- 2026-07-17 的旧 ProofAlign/FIPER/Phantom/SABER/SAFE protocol 全部保持暂停，不得 resume；
- 2026-07-20 起只允许按 [`optimization_plan.md`](optimization_plan.md) 和
  [`next_experiment_prompt.md`](next_experiment_prompt.md) 推进 fresh SABER/EDPA producer、unguarded
  VLA-only clean/attacked pair和独立 safety qualification；禁止运行 CTDA/ProofAlign/AEGIS/SAFE/FIPER
  method 或 baseline；
- VLA-only 正式 GPU execution 仍必须先有新 protocol、clean commit、fresh root 和全部 preflight gate；
- 若新 protocol 与交接授权满足全部 gate，必须重新查询 inventory，并选择 prelaunch used memory
  `<4096 MiB` 的 physical GPU；不得沿用历史 GPU 编号；
- E1 runner 的 CUDA、MuJoCo EGL 和 render device 都绑定同一 physical id；
- JAX 在 `CUDA_VISIBLE_DEVICES=<physical id>` 的进程内通常看到 logical device 0，这是正常的；
- 不把无关 GPU process 当成 ProofAlign 任务停止或修改。

只读检查已停止的 FIPER service：

```bash
systemctl --user show proofalign-fiper-r0-fresh2.service \
  --property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
```

预期为 `inactive/dead`。run manifest 仍为 `started`，partial artifact 不能作为结果或 resume 来源；停止
快照见
[`fiper_r0_stop_20260717.json`](../experiments/fiper_r0_stop_20260717.json)。

## 6. 正式实验顺序：仅 VLA-only 攻击复现

本节当前只授权 official attack producer 与 unguarded VLA-only victim。旧 CTDA no-dispatch 命令和结果
继续保留，但不得执行或覆盖。

### A. 攻击 producer 与 runner 验证

```bash
git status --short
ATTACK_ENV_PYTHON ATTACK_PRODUCER_OR_RUNNER.py --help
ATTACK_ENV_PYTHON ATTACK_PRODUCER_OR_RUNNER.py --protocol NEW_PROTOCOL.json --preflight
git diff --check
```

具体命令必须取自当前 official SABER/EDPA runner 的 `--help`，不得凭本文猜参数。禁止运行任何
`ctda_v2_*` audit/probe、Lean method evaluator、AEGIS/SAFE/FIPER runner 或 ProofAlign clean pilot。

### B. 冻结

1. 写 protocol 和 runner；
2. protocol pin runner/source/external commit/checkpoint/file hashes；
3. 只运行 attack producer/record validator/VLA-only runner 的 focused preflight；
4. 提交冻结 commit；
5. 确认 worktree clean。

### C. GPU preflight

新 runner 必须默认只读 preflight，只有显式 `--execute --gpu PHYSICAL_ID` 才能运行。preflight 至少检查：

- selected GPU inventory/memory；
- CUDA/EGL physical-id binding；
- OpenPI real-policy output 可加载和严格序列化；
- `env.step()` 调用次数为 0；
- task/init/manifest/fallback/checkpoint/source hash；
- VLA-only clean/attacked pair 的 shared initial digest 与 first policy chunk binding；
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

不要照抄 `3`；以当次 preflight 选出的可用 physical id 为准。runner 必须是 unguarded VLA-only attack
runner，不得包含 CTDA/ProofAlign/AEGIS/SAFE/FIPER arm。运行必须在提交冻结 protocol 的 clean commit
上启动。

### E. 终态验证

```bash
external/openpi/.venv/bin/python NEW_RUNNER.py \
  --protocol NEW_PROTOCOL.json \
  --output-root results/NEW_FRESH_ROOT \
  --validate-results
```

随后独立重算 ledger/manifest/episode hashes，写 `experiments/*_terminal_summary.json`，同步
`evaluation_results.md` 和 `project_status.md`，再提交 artifacts。正式结果不能只存在于日志或聊天中。
每个 workload terminal 后停止并汇报，不自动进入自研 method 或 attacked+defended comparison。

## 7. 已知环境问题

- `external/fiper/data` 是后台复现所需的用户 symlink，会使 generic source-clean preflight
  `source_ready=false`；不要删除它。新的 ProofAlign 自身 runner 应 pin 自己实际依赖的 source，而不是
  把该无关 symlink 当成 GPU execution blocker。
- 全量 pytest 会把上述 `source_ready=false` 作为预期的 fail-closed 状态验证，而不是要求删除 symlink。
  历史 E0/E1/E3 protocol 继续绑定原始 source blob；当前 checkout 不得直接执行它们，离线测试只读取
  保留 protocol/result 验证分类语义。
- Lean timing 很慢；保留诊断，不把 deadline 作为下一 clean utility pilot 的 gate。
