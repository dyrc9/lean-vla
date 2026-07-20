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
9. **EDPA R0 离线设计**：已完成 official-source-pinned 双相机 patch adapter、outcome-blind
   protocol、预检和终态 validator；当前只是 asset-gated draft，未生成 patch，未授权 victim
   rollout。

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

## 当前阶段：research pause / attack foundation gate

ProofAlign 当前只测到了 clean defense cost，没有有效攻击分母，也没有 measured defense benefit。
在讨论 CTDA v2 前先完成以下决策与 gate：

1. 是否仍把 published-attack defense 作为核心研究主张；
2. 若保留，只允许先冻结 VLA-only threat-validation-only protocol；
3. workload 必须忠实生成并实际作用于 victim，harm 来自独立 simulator safety endpoint；
4. 使用 disjoint held-out task/seed，不复用已关闭的 Phantom/SABER unit，不按结果调攻击；
5. 若没有攻击通过，删除或改变 attack-defense claim，而不是继续调参制造正结果。

已选择 EDPA fixed adversarial patch 作为一次新的 published-workload attempt，而不重跑已关闭的
Phantom/SABER unit。下一步顺序固定为：

```text
official training-data inventory + manifest
  -> generate primary/wrist patches with frozen EDPA defaults
  -> freeze asset SHA-256 and commit an execution amendment
  -> fresh GPU/EGL/model/no-dispatch preflight and explicit rollout authorization
  -> at most 12 clean screening episodes
  -> at most 4 attacked episodes
  -> terminal validator and 2/4 independent safety-transition decision
```

当前停在第一步：`modified_libero_rlds` 及三个需固定资产均缺失。草案中 task failure 单独不是
安全信号，不按 victim outcome 调 patch、换 task 或替换 unit。

正式审计见 [`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)。当前没有
运行中的 ProofAlign、EDPA victim、Phantom、SABER、SAFE 或 FIPER 实验。

## 后续阶段：CTDA v2 revision gate

不直接对 v1 threshold 做结果驱动的放宽。按以下顺序推进：

1. 明确 contract lifetime 的时基：physical wall clock 或 plant/control logical time；前者意味着当前
   slow Lean 不能在线授权，后者必须增加 proof 后 state freshness re-observe/rebind；
2. 在与 E1 outcome 隔离的 trace/unit 上校准 binder progress 与 bounded stutter，并同时验证 nominal
   approach-to-contact liveness 和 adversarial rejection；
3. 为 human-hand/obstacle distance 增加 typed provenance，或从安全 claim 中明确移除；
4. 事前冻结最低可接受 task/safe-success retention 和独立 safety endpoint；仅 fail closed 不再足以
   通过 method gate；
5. fake-env/no-dispatch/fixed-trace gates 全部通过后，才允许冻结 CTDA v2、新 paired protocol、新 seed
   或 unit 和 fresh root。

v1 冻结判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

## 后续阶段

### 独立 containment challenge

clean utility 结果已经形成；若考虑新的 post-dispatch challenge，仍必须使用新的实验单位或新 fault，
事前冻结与当前 typed receipt schema 一致的 validator；旧 12 条不得重跑或升级。

### E5 external comparison

只有 baseline terminal readiness 和独立 workload safety signal 同时满足时才执行。当前 SAFE 未复现、
FIPER fresh2 已停止且未通过 terminal gate、Phantom/SABER 的条件式主实验已关闭，因此 E5 暂不启动。

## 永久 claim boundary

即使后续全部通过，也只声称指定 simulator/task/workload 上的 safety/utility trade-off；不声称绝对
安全、硬件安全、verified recovery、通用攻击防御或实时控制。
