# ProofAlign Roadmap

更新日期：2026-07-20

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
7. **v1 validity decision**：实验/internal parity 有效，但 clean operational utility 不合格；当前 v1
   判定为 revision required，不再扩大 rollout 或 runtime claim。
8. **attack evidence audit**：Phantom held-out 为 1/4（gate 2/4）；正式 SABER exact-task 为 0
   record/0 victim；SAFE/FIPER 均未 terminal reproduced。qualified attack count 为 0，所有实验暂停。
9. **EDPA R0 历史草案**：保留 official-source-pinned 双相机 patch adapter、protocol、预检和
   validator 作参考；它已被当前 v2 规划取代，不是 EDPA + SafeLIBERO P1 protocol，不生成
   patch，不运行 victim。

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

## 已完成阶段：retained-trace utility failure analysis

离线归因没有产生新 rollout，也没有改写旧结果：

1. 12/12 Full episode 最终都是 approach-phase pre-dispatch `refuted`，0 phase completion；
2. 9/12 在 12 个 dispatch 后耗尽 40 秒 semantic contract wall-clock coverage；
3. 3/12 pour task 在 3 个 dispatch 后耗尽 persistent bounded-stutter no-progress limit；
4. 24/24 episode 缺 human/obstacle distance provenance；collision/cost coverage 完整但不能替代这些
   safety dimensions；
5. closed-loop block 继续只标 intervention；没有独立 action counterfactual 时不计算 false positive。

## 当前阶段：CTDA v2 与实验基础双线重建

详细架构、里程碑、实验矩阵和停止条件以 [`optimization_plan.md`](optimization_plan.md) 为准。
当前没有运行中的 ProofAlign、Phantom、SABER、SAFE 或 FIPER 正式实验。

### 工作线 A：CTDA v2 outcome-blind 优化

1. 冻结 contract epoch、proof/state freshness、分级 intervention、post-filter authorization、bounded
   recovery 和 typed provenance；
2. 选择 Lean-proven long-lived certificate + fast checker，或可证明 freshness 的 pipelined Lean；
3. 保留 v1 replay，新建 v2 method/wire/schema；
4. 先过 unit/fake-env、retained fixed-trace/shadow 和 no-dispatch gate；
5. 事前冻结 utility/safety gate 后才运行新的 clean v2 pilot。

### 工作线 B：安全土壤与 VLA-only threat qualification

1. P0 建立 SafeLIBERO/AEGIS pinned readiness、outcome-blind candidate/classifier 和 exact-unit support
   audit；
2. P0 从全新的 official SABER constraint-violation producer gate 开始，不续接旧 R1；
3. P1 使用原始 EDPA patch 叠加 SafeLIBERO，task failure 与独立 safety harm 分开；
4. workload 必须通过 immutable artifact、unguarded victim、independent safety transition、disjoint
   held-out gate、terminal artifact 和 population overlap；
5. 若仍无攻击通过，删除或收窄 attack-defense claim，而不是 outcome-driven 调攻击。

### 汇合 gate

只有 CTDA v2 clean utility 合格、至少一个 workload threat-valid、独立 safety oracle 完整且 attack 与
CTDA support population 完全重合，才执行 attacked+defended 正式比较。

两线汇合前，attack outcome 不参与 v2 threshold/binder 调整，CTDA verdict 不参与 attack reward 或
ground truth。

v1 冻结判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

## 后续阶段

### 独立 containment challenge

clean utility 结果已经形成；若考虑新的 post-dispatch challenge，仍必须使用新的实验单位或新 fault，
事前冻结与当前 typed receipt schema 一致的 validator；旧 12 条不得重跑或升级。

### E5 external comparison

只有 baseline terminal readiness、CTDA v2 clean utility、独立 workload safety signal 和 population
overlap 同时满足时才执行。P0 低层闭环 baseline 改为已公开的 AEGIS；SAFE/FIPER 只在新的 terminal
reproduction ready 后作为 detector baseline，旧 partial 不 resume。

## 永久 claim boundary

即使后续全部通过，也只声称指定 simulator/task/workload 上的 safety/utility trade-off；不声称绝对
安全、硬件安全、verified recovery、通用攻击防御或实时控制。
