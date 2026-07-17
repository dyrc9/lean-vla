# 下一实验执行 Prompt

把下面整段交给下一位 agent：

---

你正在 `/home/ldx/lean-vla` 继续 ProofAlign 项目。请完成一个新的 clean paired utility pilot，正常
评估安全性与任务完成度 trade-off，不追求绝对安全。不要只写计划；在安全、冻结和环境 gate 允许的
范围内持续推进到 terminal result、artifact validation、文档和提交。

## 先读取的当前事实来源

只先读这些 canonical 文档，不要默认加载 `docs/archive/`：

1. `docs/project_status.md`
2. `docs/evaluation_results.md`
3. `docs/roadmap.md`
4. `docs/experiments.md`
5. `docs/remote_execution.md`
6. `docs/implementation_notes.md`
7. `docs/method.md`

当前关键事实：

- E0-v2 支持 12 个 `affordance` task：`0,1,2,3,5,6,7,8,10,11,12,13`，init 0；
- E1-v1/v2/v3 都是 terminal-invalid，没有有效 utility 结论；
- E1-v3 的 blocker 已定位：Full CTDA 初态 observer 安装了 task-bound contact query，VLA-only 没有，
  因而 paired initial-state digest schema 不同；
- E1-v3 的 `policy_seed=0` pair 已执行，不得覆盖、resume 或当作相同实验重跑；
- E3 clean 12/12 safety preserved；post-dispatch formal primary 为 12 unknown；
- E4 v2 为 1/1 control + 35/35 fault fail closed；
- timing 很慢但按用户要求不是下一实验 gate，仍禁止 real-time claim；
- GPU 1 正在运行 FIPER fresh2，严禁使用或干扰。

## 本轮目标

建立一套新的、有效的 clean paired pilot：

- unit：上述 12 个 task、`init_state_id=0`、`env_seed=7`、新的 `policy_seed=1`、clean workload；
- arms：真正 unguarded 的 VLA-only 与 Full CTDA；
- 两臂在第一次 state digest 前必须使用完全相同的 task-manifest contact query 和 observation schema；
- 两臂 checkpoint/config/camera/init/policy seed/first policy chunk 必须精确配对；
- Full CTDA 继续使用 `ctda-lean-kernel` 和 `slow-interlock-diagnostic-v1`；
- primary 输出 valid pairs、两臂 task success、safe success、retention、collision/cost coverage、
  block/unknown/deadlock/phase completion、method-attributable utility loss、Lean parity；
- closed-loop block 没有独立 action counterfactual label，不能自动写成 false positive。

## 环境使用方法

### CPU/Lean

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/python --version
lean --version
.venv/bin/pytest -q \
  tests/test_ctda_evaluator.py \
  tests/test_ctda_runtime.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py
(cd lean && lake build ProofAlign)
```

必须显式加入仓库 Lean PATH，否则测试会因为找不到 `lean`/`lake` 失败。
全量 suite 当前有一个已知失败：`external/fiper/data` symlink 使 generic baseline preflight 的
`source_ready` 断言为 false。不要为了绿色测试删除或改动该 FIPER 数据绑定；记录 focused suite 与
全量 suite 的真实结果即可。

### OpenPI/LIBERO-Safety

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

E1 runner 使用 `external/openpi/.venv/bin/python`，不要换成仓库 `.venv` 或历史裸 conda 命令。模型、
checkout、cache 已存在，不要重新下载或创建环境。

### GPU

启动前只读检查：

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
systemctl --user show proofalign-fiper-r0-fresh2.service \
  --property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
```

GPU 1 永久排除。2026-07-17 最后检查时 GPU 3 空闲，但正式启动时必须重查。选择非 1、used memory
低于 4096 MiB 的 physical GPU；CUDA、MuJoCo EGL 和 render device 都绑定同一个 physical id。不要
停止、kill、renice 或修改任何 FIPER process/service。若 sandbox 阻止 `nvidia-smi`、systemd 或正式 GPU
执行，按环境规则申请必要授权，不要绕过。

## 必须完成的实现

1. 检查 `src/proofalign/benchmark/libero_e1_runner.py` 和
   `src/proofalign/benchmark/libero_online_runner.py` 的初始化顺序。
2. 让 VLA-only runner 接收 frozen task manifest，并在第一次
   `state_observer.observe()` 前执行与 Full CTDA 相同的：

   ```python
   wrapper.state_observer.contact_part_queries = (task_manifest.contact_query,)
   ```

3. 不得给 baseline 添加 CTDA 或 legacy action gate；`UnguardedObservationChecker` 仍只记录并允许。
4. 增加测试，至少证明：
   - 同 task/init/observation 的双臂 initial-state digest 一致；
   - manifest/query 不同会在 preflight fail closed；
   - VLA-only trace 没有 CTDA record，动作不受 ProofAlign gate；
   - Full CTDA 初态 digest 仍匹配 E0 frozen digest；
   - real-policy output probe 严格序列化成功且 `env.step_count=0`。
5. 新建独立 runner/protocol，不要修改旧 E1-v1/v2/v3 protocol/result。可以复用旧 runner 的通用逻辑，
   但必须有新的 schema、source hashes、policy seed 和 fresh root。

## 冻结与执行顺序

严格按下面顺序：

1. 先只做代码、unit/fake-env test、read-only/no-dispatch probe；不要产生正式 rollout outcome。
2. 新 protocol 固定 12 units、`policy_seed=1`、arm order、checkpoint/config、horizon、labels、failure
   policy、required hashes、selected GPU rule和 fresh output root。
3. classifier 只让两侧都 valid 的 pair 进入 retention/inference；0 valid pair 输出 `not_evaluated`。
4. protocol 和 runner 完成后先提交冻结 commit，确认 `git status --short` 为空。
5. 正式 preflight 默认 read-only；必须验证：
   - source/checkpoint/manifest/fallback hash；
   - selected physical GPU 和 EGL binding；
   - real OpenPI load/output audit；
   - no-dispatch shared-observer initial digest；
   - first policy chunk pairing；
   - output root 不存在。
6. 只有 preflight `ready=true` 才运行一次 fresh execution。命令形态：

   ```bash
   external/openpi/.venv/bin/python NEW_RUNNER.py \
     --protocol experiments/NEW_PROTOCOL.json \
     --output-root results/NEW_FRESH_ROOT \
     --gpu 3 \
     --execute
   ```

   `3` 只是候选，必须替换为当次 preflight 选中的非 GPU 1 physical id。
7. 已创建 episode/可能 dispatch 后的异常一律保留为 invalid/unknown，不替换 unit、不改变 seed/horizon。
8. 运行后使用 runner 的 `--validate-results`，再独立重算 manifest/ledger/episode hashes。
9. 写 `experiments/*_terminal_summary.json`，更新 `docs/evaluation_results.md`、
   `docs/project_status.md` 和必要的 roadmap；不要再新建日期型 handoff 或阶段长文。
10. 提交 terminal artifacts 和文档，确认 worktree clean，并只读确认 FIPER 仍正常。

## 结果解释

如果有效完成，这轮可以证明固定 12-task simulator slice 和新 policy seed 上的 clean safety/utility
trade-off。它不能证明绝对安全、总体 task distribution、物理安全、verified recovery、attack defense、
availability 或 real-time enforcement。负结果、0 valid pairs 或较大 completion loss 都必须原样报告。

---
