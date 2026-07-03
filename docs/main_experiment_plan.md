# ProofAlign 主实验计划

目标是准备可报告的 LIBERO-Safety 主实验，而不是继续证明 VLA/LIBERO 链路能跑通。所有结果必须区分 task success、安全指标、ProofAlign decision 和 runner failure。

## 实验分层

### A. pi0.5 Safety Baseline Reproduction

用途：作为 LIBERO-Safety 官方 Safety-tuned policy 的高成功率参考。

模型和脚本：

- model：`/data0/ldx/libero_safety_models/pi05_libero_safety`
- OpenPI config：`pi05_libero`
- script：`scripts/run_liberosafety_pi05_openpi_eval.py`

当前已有结果：

- `results/liberosafety_pi05_openpi_physical60_init0_20260702/`
- 60 episodes，75.0% task success，0.0% cost/collision

下一步可选扩展：

```bash
source scripts/env_vla.sh
export LIBERO_SAFETY_ROOT=$PWD/external/LIBERO-Safety
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

CUDA_VISIBLE_DEVICES=4,5 \
MUJOCO_EGL_DEVICE_ID=5 \
conda run -n proofalign-libero python scripts/run_liberosafety_pi05_openpi_eval.py \
  --checkpoint-dir /data0/ldx/libero_safety_models/pi05_libero_safety \
  --openpi-config pi05_libero \
  --suites affordance,obstacle_avoidance,human_safety,obstacle_avoidance_human \
  --task-ids 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14 \
  --init-state-ids 0,1,2,3,4 \
  --max-steps 600 \
  --num-steps-wait 10 \
  --env-img-res 256 \
  --resize-size 224 \
  --replan-steps 5 \
  --sample-steps 10 \
  --render-gpu-device-id 5 \
  --continue-on-error \
  --output-dir results/liberosafety_pi05_openpi_physical300_init0-4
```

判定标准：

- runner failures 必须单独报告。
- task success 和 strict success without cost/collision 必须同时报告。
- 如果多 init state 明显低于 50%，先检查 init-state protocol 是否和官方一致，不直接调参。

### B. OpenVLA-OFT Diagnostic Baseline

用途：说明 standard LIBERO-Spatial OpenVLA-OFT checkpoint 不是 50%+ LIBERO-Safety baseline。

当前已有诊断结论：

- official-processing-aligned VLA-only sample：2 / 15 = 13.3% task success
- cost/collision：9 / 15 = 60.0%

该 baseline 在论文里只能作为 domain mismatch 或 unsafe baseline 诊断，不应被写成官方 LIBERO-Safety reproduction。

### C. ProofAlign Main Table

目标方法：

- pi0.5/OpenPI only
- pi0.5/OpenPI + collision checker
- pi0.5/OpenPI + Intent only
- pi0.5/OpenPI + Effect only
- pi0.5/OpenPI + Dual Lean Alignment

主表必须使用 `pi05_libero_safety` / OpenPI policy，和 A 节 baseline reproduction 对齐。OpenVLA-OFT 只保留为 B 节 diagnostic，不进入主 baseline 对照表。

第一阶段规模：

- suites：`affordance`, `obstacle_avoidance`, `human_safety`, `obstacle_avoidance_human`, `reasoning_safety`
- tasks：`0-14`
- init states：先跑 `0`
- max steps：和 baseline 对齐用 `600`；只允许 smoke/debug 使用更短 horizon
- chunk execution：`--max-chunk-steps 5`
- replan semantics：主实验使用 `--continue-on-replan`，把 ProofAlign replan 作为 trace-level safety signal，不直接终止 episode
- 输出：`results/main_<method>_5x15_init0_YYYYMMDD/`

第二阶段规模：

- 同样 suites 和 tasks
- init states：`0-4`
- 输出：`results/main_<method>_5x15_init0-4_YYYYMMDD/`

Dual Lean pi0.5/OpenPI smoke / sample 命令：

```bash
source scripts/env_vla.sh
unset VIRTUAL_ENV
export LIBERO_SAFETY_ROOT=$PWD/external/LIBERO-Safety
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

CUDA_VISIBLE_DEVICES=4,5 \
MUJOCO_EGL_DEVICE_ID=5 \
"$PROOFALIGN_UV" --project external/openpi run python scripts/run_libero_online_batch.py \
  --suites affordance obstacle_avoidance human_safety obstacle_avoidance_human \
  --task-ids 0,7,14 \
  --init-state-ids 0 \
  --max-steps 600 \
  --max-chunk-steps 5 \
  --continue-on-replan \
  --warmup-steps 10 \
  --warmup-gripper -1 \
  --camera-height 256 \
  --camera-width 256 \
  --output-dir results/main_pi05_openpi_dual_lean_physical12_init0_raw600_20260703 \
  --method-name pi05_openpi_dual_lean \
  --summary results/main_pi05_openpi_dual_lean_physical12_init0_raw600_20260703/summary_pi05_openpi_dual_lean.json \
  --failure-jsonl results/main_pi05_openpi_dual_lean_physical12_init0_raw600_20260703/failures_pi05_openpi_dual_lean.jsonl \
  --render-gpu-device-id 5 \
  --policy experiments.libero_openpi_plugin:create_policy \
  --abstractor experiments.libero_vla_plugin:create_abstractor
```

多 init state 扩展命令：

```bash
source scripts/env_vla.sh
unset VIRTUAL_ENV
export LIBERO_SAFETY_ROOT=$PWD/external/LIBERO-Safety
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

CUDA_VISIBLE_DEVICES=4,5 \
MUJOCO_EGL_DEVICE_ID=5 \
"$PROOFALIGN_UV" --project external/openpi run python scripts/run_libero_online_batch.py \
  --suites affordance obstacle_avoidance human_safety obstacle_avoidance_human reasoning_safety \
  --task-ids 0-14 \
  --init-state-ids 0-4 \
  --max-steps 600 \
  --max-chunk-steps 5 \
  --continue-on-replan \
  --warmup-steps 10 \
  --warmup-gripper -1 \
  --camera-height 256 \
  --camera-width 256 \
  --output-dir results/main_pi05_openpi_dual_lean_5x15_init0-4_20260703 \
  --method-name pi05_openpi_dual_lean \
  --summary results/main_pi05_openpi_dual_lean_5x15_init0-4_20260703/summary_pi05_openpi_dual_lean.json \
  --failure-jsonl results/main_pi05_openpi_dual_lean_5x15_init0-4_20260703/failures_pi05_openpi_dual_lean.jsonl \
  --skip-existing \
  --render-gpu-device-id 5 \
  --policy experiments.libero_openpi_plugin:create_policy \
  --abstractor experiments.libero_vla_plugin:create_abstractor
```

## 指标

每个方法都必须输出：

- task success rate
- strict success rate without cost/collision
- cost/collision rate
- final decision counts
- trace-level decision counts
- episode rejection rate
- step rejection / violation rate
- violation attribution by layer and type
- average policy step time
- average env step time
- average ProofAlign check time
- runner failure count

ProofAlign 方法额外输出：

- Lean mode counts：`lean` 和 `mock`
- intent violation count
- effect violation count
- unsafe action rejection rate，如果有 oracle unsafe labels
- false rejection rate，如果能从 replay 或 annotations 确认 safe actions

## 运行顺序

1. 先跑 pi0.5/OpenPI + Dual Lean 的 physical 4 suites × tasks `0,7,14` × init0，`max_steps=600`。
2. 用 summary 检查 runner failures、Lean mode、trace schema 和 rejection attribution。
3. 如果 schema 稳定，再跑完整 5 suites × 15 tasks × init0。
4. 同一 split 上补 pi0.5/OpenPI only 和 ablations。
5. 如果 ablations 都稳定，再扩到 init states `0-4`。
6. 只在协议固定后再考虑调 action abstraction threshold。

## 结果验收

一次主实验结果只有同时满足以下条件才进入论文表格：

- episode 输出文件数等于 expected total，或者 failure jsonl 中解释全部缺失项。
- 每个 ProofAlign trace 的 `intent.lean_mode` 为 `lean`，不存在未解释的 `mock`。
- summary 和 per-episode JSON 的 task success / cost / decision 能互相对上。
- 所有方法使用相同 suites、task ids、init state ids、camera settings、seed 和 max steps。
- 所有 runner warnings 和 environment caveats 写入实验 notes。

## 近期工程 TODO

- 给 VLA only / Intent only / Effect only 增加显式 method switch，而不是复制脚本。
- 给 summary 增加 violation attribution 自动汇总。
- 给 result directory 自动写入 git commit。

## 2026-07-03 准备改动

- `run_libero_online_batch.py` 已支持 `--init-state-ids`，可使用 `0-4` 或 `0,1,2`。
- `run_libero_online_batch.py` 已写出 `run_config.json`，包含 command args、task plan 和关键环境变量。
- `run_libero_online_batch.py` 的 summary 已增加 `per_init_state_breakdown`。
- `LeanBridge` 已增加同一进程内 boolean claim 缓存，减少重复 Lean expression 的进程启动开销。
- 已新增 `experiments/libero_openpi_plugin.py`，支持通过 OpenPI 加载 `pi05_libero_safety`，并复用 baseline reproduction 的 image rotation、resize/pad、state concat 和 action chunk 设置。
- 已完成 pi0.5/OpenPI + Dual Lean physical4 smoke：`results/main_pi05_openpi_dual_lean_physical4_smoke_20260703/`，4/4 completed，runner failures 0，task success 1/4，cost/collision 0/4，trace decisions 为 allow 321、replan 44。三个失败 episode 使用 `max_steps=100`，不能和 baseline 600-step 结果直接比较。
- 已修正 `ProofAlignLiberoWrapper.run_episode()` 的 `max_steps` 语义：现在按累计 raw `env.step` 数停止，而不是按 policy/chunk 调用次数停止。`max_steps=600` 因此与 pi0.5 baseline 的 600-step horizon 对齐。
- 已完成 pi0.5/OpenPI + Dual Lean physical12 raw600 小样本：`results/main_pi05_openpi_dual_lean_physical12_init0_raw600_20260703/`，12/12 completed，runner failures 0，task success 5/12，cost/collision 1/12，final decisions allow 7、replan 3、reject 1、safe_stop 1，Lean checks 全部为 `lean`。
- `results/main_pi05_openpi_dual_lean_physical12_init0_20260703/` 是修正 `max_steps` 前中断的 partial run，不能作为结果引用。
