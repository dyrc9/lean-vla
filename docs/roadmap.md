# ProofAlign Roadmap

更新日期：2026-07-17

## 目标

完成一个诚实、有限、可复核的 VLA runtime safety evaluation：同时报告安全收益和正常任务完成度
trade-off，不追求绝对安全或通用证明。

## 已完成

1. **方法闭环**：trusted mission、persistent contract、consumer-side raw binder、canonical wire、
   Lean kernel evaluator、observed trace monitor。
2. **E0 support**：固定 12 个 affordance/init0 supported unit。
3. **E3 safety**：clean 12/12 safety preserved；独立 post-dispatch challenge 原始行为和 primary unknown
   均已封存。
4. **E4 robustness**：35/35 frozen fault case fail closed；timing 负结果保留。
5. **外部 workload gates**：Phantom held-out 和 SABER record gate 按冻结停止条件关闭。
6. **E1 clean utility**：新 policy-seed 1 pilot 12/12 valid pair；VLA-only 8/12、Full CTDA 0/12
   task/safe success，retention 0，completion loss 原样封存。

## 已完成阶段：clean utility trade-off

在相同 clean task、init、实际 policy seed 下，Full CTDA 相比 VLA-only 的任务完成度和 safe
success 损失已经得到有效 pilot 答案：12/12 valid pair，VLA-only 8/12、Full CTDA 0/12，两种
retention 都为 0；两臂 collision/cost coverage 100%、observed unsafe 0，Full CTDA 为 12 block/
deadlock、0 phase completion、0 Lean parity mismatch。

执行顺序：

```text
shared-observer fix + tests
  -> outcome-blind no-dispatch init/policy probe
  -> freeze new protocol on policy_seed=1
  -> clean commit
  -> GPU/EGL/model/Lean preflight
  -> fresh paired execution
  -> retained artifact validation
  -> scoped utility/safety report
```

本轮停止条件全部按冻结执行：

- 两臂 initial-state digest 或 first policy chunk digest 不同：不 dispatch 正式 pair；
- protocol/source/checkpoint/hash/preflight 任一不一致：不创建正式 output root；
- 已进入 episode 后发生异常：保留为 invalid/unknown，不替换该 unit；
- 0 valid pair：终态为 not evaluated，不计算 retention；
- 不因结果调整支持 task、policy seed、horizon 或 classifier。

所有 12 pair 均 valid，未触发 0-pair `not_evaluated`；大 completion loss 没有触发重跑或 gate 放宽。

## 当前阶段：retained-trace utility failure analysis

先做不产生新 rollout 的离线归因：

1. 统计 12 个 Full CTDA episode 的 binder verdict、no-progress budget、unknown provenance 和最终
   approach phase；
2. 保持 closed-loop block 为 intervention label；没有独立 action counterfactual 时不计算 false
   positive；
3. 若需要修改 binder/monitor 或补 fixed-trace counterfactual，必须新方法版本、新 protocol、新 seed/
   unit 授权和 fresh root；不得 resume 或覆盖本轮；
4. 在解释 retention 0 前，不扩大 task slice 或对总体 utility 作外推。

## 后续阶段

### 独立 containment challenge

clean utility 结果已经形成；若考虑新的 post-dispatch challenge，仍必须使用新的实验单位或新 fault，
事前冻结与当前 typed receipt schema 一致的 validator；旧 12 条不得重跑或升级。

### E5 external comparison

只有 baseline terminal readiness 和独立 workload safety signal 同时满足时才执行。当前 SAFE 未复现、
FIPER fresh2 仍在 GPU 1 后台、Phantom/SABER 的条件式主实验已关闭，因此 E5 暂不启动。

## 永久 claim boundary

即使后续全部通过，也只声称指定 simulator/task/workload 上的 safety/utility trade-off；不声称绝对
安全、硬件安全、verified recovery、通用攻击防御或实时控制。
