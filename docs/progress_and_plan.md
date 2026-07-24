# 当前进展与执行计划

## 1. 2026-07-24 对齐结论

主线已从 `TrustedIntent -> explicit PlanWitness -> Action` 改为：

```text
TrustedIntent -> concrete ActionBlock consequence assessment
ActionBlock -> exact dispatch/receipt/observed effects
```

显式高层规划不再是接口要求、denominator 或 blocker。第一关键 blocker 变成：

> 能否构建一个独立于被攻击 policy view、对 ActionBlock 后果有足够 coverage 且 false-allow 可控的
> consumer-side assessor？

这是更直接、也更困难的 challenge：VLA 的数值输出不自带可验证语义，外部系统必须在有限观测和模型误差
下预测它实际会做什么。

## 2. 已完成

- ActionProposal 已成为原生 ActionBlock，不再含 `plan_digest`；
- 新增 `ActionBlockAssessment` 和 `BlockExecutionContract`；
- authorization、dispatch receipt、execution evidence 已绑定 block/assessment/contract digests；
- shared four-arm runner 改为 Intent–Action / Action–Execution 两个开关；
- Lean core 改为 action-block execution transaction semantics；
- L2 支持 exact command、one-use authorization、freshness、expected/forbidden effects、phase gating；
- P0b/R9 历史结果及冻结协议仍保留审计边界。

## 3. 历史实验怎么复用

完整的逐字段映射、post-hoc replay 规则和 confirmatory 禁止项见
[`experiment_reuse.md`](experiment_reuse.md)。

### P0b

可直接复用：

- 原始攻击机制和 threat model；
- clean/attacked pairing；
- valid episode 与 clean-eligible denominator 逻辑；
- transition signal 和缺失/替换规则。

不可复用：

- 新 L1 assessment；
- 四臂 causal effect；
- confirmatory denominator（`23 < 26`）。

### R9 Execution-only

可直接复用：

- action envelope/intervention；
- exact dispatch 和 episode ledger；
- cost/collision、strict success、contact proxy；
- clean retention 和 attacked recovery 的 exploratory baseline。

需要迁移：

- 将旧 transport/audit 映射为 ActionBlock/contract/receipt v3；
- 不把旧 effect verdict 当作完整物理安全；
- 不把 R9 称为 Dual。

## 4. 当前 blocker 排序

1. **Assessor qualification design**：标签、support、false-allow、coverage、calibration、OOD；
2. **资源预算**：assessor 与四臂 latency/GPU memory；
3. **observer adequacy**：contact/collision/task-effect atoms 的可观测性；
4. **clean commit binding**；
5. **M2 execution authorization**。

M1 producer/victim、shared runner、fixed-trace exporter、validator 和 outcome-blind ActionBlock prefix adapter
已经完成；adapter 只读取 policy-call audit 与实际消费的 raw actions，不读取 reward/success/cost/collision，
也不伪造未执行的 chunk tail。

## 5. 下一里程碑

### M1A：component closure

- 全部 Python/Lean tests 通过；
- 新 ActionBlock fixed-trace smoke artifact 当前；
- M1 readiness validator 不再引用 PlanWitness；
- frozen legacy protocol 明确标注 audit-only，新 v3 schema 不改写历史结果。

### M1B：assessor no-outcome qualification protocol

- 冻结训练/qualification split；
- 冻结 finite atom vocabulary；
- 冻结 threshold、abstention 和 worst-group；
- 只允许 offline transition label，不看 M2 victim outcome。

### M2：240 episode

仅在用户/项目负责人明确授权 GPU rollout 后运行。先完成 VLA-only attack foundation，gate 通过后再跑
fixed-trace 和 480+480 四臂。

## 6. 当前可声称与不可声称

可声称：

- 双层问题已定义在 action-only VLA 可观察接口上；
- L2 的有限 transaction semantics 已由 Lean 检查；
- P0b/R9 给出强探索性攻击/Execution-only 信号；
- component runner 可验证两层开关和 digest identity。

不可声称：

- L1 assessor 已对真实 π0.5 资格化；
- 一般防御有效；
- Dual 已验证；
- 完整物理安全；
- Lean 证明 learned predictions 或真实世界。
