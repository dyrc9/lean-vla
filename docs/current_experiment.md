# Current Experiment Priority

更新日期：2026-07-23

## 决策

当前唯一实验优先级是 **SABER P0b attacked+defended action-envelope successor**。它评估
`proofalign-integrity-v2` 的 Execution-only L2 action envelope、exact final-command reauthorization 与
non-finite zero brake。它不是 Full CTDA、Dual arm、通用语义防御或物理安全证明。

2026-07-23 的 R3 fresh1 已按用户要求停止并封存。下一次执行必须先修复资源隔离、冻结 successor
protocol，并使用 fresh absent root；不得续跑或覆盖 R3。

## 已建立的直接前序证据

1. P0b fresh2 producer 生成 48 条 immutable record，victim 完成 96/96 valid clean/attacked episode；
2. P0b 只有 23 个 clean-eligible pair，低于冻结的 26-pair gate，因此正式分类仍是
   `p0b_blocked_insufficient_clean_baseline`；15/23 pair 有 typed transition，rate 为 `0.6522`，但不能把
   denominator failure 后验改成 qualification pass；
3. clean action-envelope R1 完成 48/48 valid episode，在 23 个 baseline-eligible pair 上保留
   `22/23 = 0.9565` strict success，超过冻结的 `0.8` clean utility gate；
4. attacked+defended R2 在任何新 `env.step` 前遇到 non-finite policy command，形成 terminal invalid；
5. R3 冻结 deterministic zero brake，使 non-finite source command 不进入 `ActionProposal`，zero command
   仍须经过 exact reauthorization。

## R3 fresh1 终态

R3 于 11:33 启动，static preflight `ready=true`，冻结 population 为 48 个 attacked+defended episode。
runner 在正式 episode 前执行 96 个 clean/attacked zero-step binding probe，并只在整个 probe 完成后写回
manifest。运行超过三小时后：

- manifest 仍没有 `real_policy_probe`；
- retained binding、episode、ledger、summary 和 efficacy outcome 均为 0；
- 进程持续约 100% 单核 CPU、无文件 I/O；
- 实验实际同时在 GPU 3/5 各保留约 8.6 GiB，GPU 5 上后来出现约 30 GiB 的外部 compute process，
  总利用率达到 99%；
- `pmon` 另观察到 GPU 4 graphics context，实际 device mapping 未满足预期的 policy 3 / EGL 5 隔离。

用户于 14:54 前后要求停止。PID `2978322` 已退出，GPU 3 回落到 3 MiB；GPU 5 仍由外部任务占用。
机器状态见
[`saber_integrity_action_envelope_r3_status.json`](../experiments/saber_integrity_action_envelope_r3_status.json)。

## Successor 执行 gate

下一次执行按以下顺序进行：

1. 保持 R3 root 和 terminal manifest 不变；
2. 修复并测试 JAX policy device 与 MuJoCo EGL device 的实际隔离，不能只检查 CLI 参数；
3. 增加 launch 后 runtime device observation；若实际 compute/graphics device 与冻结角色不一致，probe 前
   fail closed；
4. 冻结新的 successor protocol、source hash 和 fresh absent output root；
5. 只在两张不同物理 GPU 同时满足 `<4096 MiB`、无 compute process，并稳定至少五分钟时启动；
6. probe 期间持续检查外部 compute process；资源 gate 被破坏时 terminal stop，不进入 episode；
7. 完成 48/48 attacked+defended episode、ledger、summary、checksums 和独立 validator 后才报告结果。

当前不并行启动 EDPA、Full CTDA、AEGIS、SAFE、FIPER 或新的 clean pilot。

## Claim boundary

R1 只支持该冻结 slice 上的 exploratory clean utility。R2/R3 都没有产生 attacked+defended outcome。
P0b 的 denominator gate 仍未通过，因此即使 successor 完成，也只能作为该冻结 P0b setting 的探索性
measurement，不能建立已确认攻击复现、Full CTDA efficacy、通用 defense efficacy、real-time enforcement
或物理安全。
