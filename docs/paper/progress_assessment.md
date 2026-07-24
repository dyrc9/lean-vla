# 论文进展评估

更新日期：2026-07-23

## 总体判断

论文从“完整 CTDA clean utility 失败、attack-defense 尚未评估”推进到了“Execution-only mitigation
拥有强探索性正结果”。这是实质性进展，但还不是可直接投稿的完整 ProofAlign 证据链。

最重要的新事实是：

- clean action-envelope 保留 `22/23 = 95.7%` baseline-eligible strict success；
- attacked+defended 完成 48/48 valid episode；
- 17,828 个 final command 全部满足冻结的 action envelope；
- 15 个 P0b clean-safe→attacked-unsafe signal pair 中，defended LIBERO cost/collision 为 `0/15`；
- 其中 `8/15` 同时恢复 strict task success without cost。

因此论文现在有一个可信的 empirical anchor：**低层执行完整性干预可以在固定攻击 slice 上显著缓解
粗粒度安全失败，并基本保留 clean utility。**

但当前 positive result 只覆盖 Execution-only。若论文仍以“两种 integrity relation + Dual”为核心，
Intent-only unique catch、Dual composition gain、confirmatory attack foundation 和统计复验仍是主缺口。

## 证据就绪矩阵

| 论文命题 | 当前状态 | 现有证据 | 缺口 |
|---|---|---|---|
| exact final-command mediation 能按设计执行 | scoped ready | 48/48 valid；17,828/17,828 action audited；全部在 envelope 内 | 仅固定 simulator slice；无 hardware/real-time |
| Execution-only clean utility 可接受 | exploratory ready | 22/23 retention，超过冻结 0.8 gate | 单个冻结 population；需跨 seed 确认 |
| Execution-only 缓解已识别攻击风险 | strong exploratory | signal subset cost/collision `15/15 -> 0/15`；8/15 strict success | P0b denominator `23 < 26`；无重复/确认性 CI |
| mitigation 恢复完整物理安全 | not supported | signal subset cost/collision 为 0 | 11/15 contact delta，1/15 joint-limit delta；1 个 nonsignal pair unsafe |
| Intent–Plan 与 Plan–Execution 各自必要 | not evaluated | focused unit 覆盖层级差异 | 缺同 trace/closed-loop Intent-only 与 Execution-only causal ablation |
| Dual 比单层更强且保留 utility | not evaluated | 无 | 缺四臂 shared-runner clean/attack matrix |
| Lean spec 对在线 checker 提供 assurance | partial | IntegrityCore 与历史 parity/fault evidence存在 | 缺 fast-checker refinement/equivalence；Lean 非实时 |
| 优于外部 baseline | not evaluated | AEGIS/SAFE/FIPER/EDPA 只有 readiness、partial 或 terminal failure | 至少需要一个公平、terminal、同 endpoint baseline |
| 可推广到总体任务或硬件 | not supported | 无 | 多 seed、多 population、真实系统与连续动力学证据均缺 |

## 对论文故事的影响

### 可以强化的主张

1. **Complete mediation is measurable.** proposal、投影后的 final command、authorization、dispatch 与
   outcome 可以逐 action 审计，而不是只报告 detector accuracy。
2. **Clean-first gate is useful.** Full CTDA v1 的 `0/12` clean retention 与 action-envelope 的
   `22/23` 构成清晰设计教训：fail-closed 不够，必须同时验证 liveness/utility。
3. **A narrow execution guard can be practically useful.** 本轮不是微弱趋势，而是在预定义 signal
   subset 上把 coarse cost/collision 从 15 个降为 0 个。
4. **Safety endpoints must remain plural.** cost/collision 的改善与 contact/joint proxy 的残余风险同时
   存在，正好支持论文坚持 typed multi-channel evidence，而不是单一“safe”标签。

### 不能因为正结果而扩大

1. L2 projection 本身不是足够强的方法 novelty；论文新意仍需来自 mission-rooted authorization、
   exact execution binding、persistent checked completion 与两层因果分解。
2. 不能把 `0/15` 写成 attack-defense efficacy 已确认，因为 P0b qualification denominator 未通过。
3. 不能把“没有 LIBERO cost/collision”写成完整物理安全；contact/joint 指标明确给出反例。
4. 不能让 Execution-only pilot 替代 Intent-only/Dual 主实验，否则论文标题、方法和证据不对齐。

## 当前论文完成度（规划性判断）

以下不是统计量，而是用于排期的 readiness 判断：

| 模块 | 就绪度 | 说明 |
|---|---|---|
| 问题定义与 claim boundary | 高 | 两关系、两不变量、三 transaction 已稳定 |
| 原型与 artifact audit | 高 | minimal core、Lean model、terminal artifacts、hash/validator 链完整 |
| clean utility 叙事 | 中高 | 有 Full CTDA 负结果与 Execution-only 正结果，但 population 不同 |
| attack mitigation 证据 | 中 | 新结果强，但仍是 exploratory/nonconfirmatory |
| 核心四臂因果消融 | 低 | 尚无 shared-runner closed-loop 结果 |
| external baseline | 低 | 没有可比较的 terminal baseline |
| 泛化与统计 | 低 | 单一冻结 population，缺多 seed/confirmatory design |
| 写作组织 | 中高 | 主故事已清楚，本轮结果可以进入 results/discussion |

结论：**足以开始形成完整论文初稿和图表，但不足以冻结最终实验表或提交。**

## 本轮论文产物 checkpoint

结果整理与下一实验设计已经从“建议”推进为可复算 artifact：

- [`action_envelope_results.md`](action_envelope_results.md) 自动生成 validity、outcome、suite、设计迭代
  和 projection modification 表；48 个 raw episode digest 与 ledger 逐一绑定；
- 13,108 个 projected action 的修改 L2 为 median `0.002853`、P95 `0.008507`、max `0.039266`，
  并按四个 suite 分层；
- [`action_envelope_failure_taxonomy.json`](../../experiments/action_envelope_failure_taxonomy.json)
  将 15 个 signal pair 与 1 个 signal 外 coarse unsafe pair 做互斥逐项审计；
- [`confirmatory_preregistration.md`](confirmatory_preregistration.md) 冻结了 60 个新 base pair ×
  2 seed block、cluster bootstrap、confirmatory denominator/transition gate，以及 shared-runner
  四臂 clean/attack 设计。

因此下列原“强烈建议”项已经完成设计/整理层面：projection 幅度分布与 task-family 分层、唯一 unsafe
与 11 个 residual-harm pair taxonomy、从 ledger/raw artifact 独立生成论文表。它们提高了写作和复算
就绪度，但不增加新的 empirical outcome，也不改变下方投稿前实验缺口。

## 推荐论文结构

1. 问题：VLA 的任务授权完整性与执行完整性；
2. 方法：两个关系、两个不变量、三个 transaction；
3. 实现与 TCB：exact final-command authorization、single dispatch、effect update、Lean spec；
4. RQ1 clean utility：Full CTDA v1 负结果与收缩后的 Execution-only clean gate；
5. RQ2 exploratory attack mitigation：本次 48-pair结果；
6. RQ3 causal necessity：未来四臂 shared-runner 结果；
7. RQ4 assurance/robustness：E4 fault matrix、artifact audit、runtime limitation；
8. Discussion：coarse safety improvement 与 contact/joint residual risk、nonconfirmatory attack substrate；
9. Limitations：simulator、single population、no hardware、no real-time、no general defense。

## 投稿前最低证据清单

### 必须

1. 独立、事前冻结的 confirmatory population，满足 attack denominator 或按新 protocol 诚实失败；
2. VLA-only / Intent-only / Execution-only / Dual 四臂共享 runner 的 clean utility；
3. 至少在 qualified attack population 上完成 Execution-only 与 Dual 的 causal comparison；
4. 多 seed 或等价重复设计、事前冻结 confidence method；
5. 同时报 cost/collision、contact、joint limit、force、task success、episode length 与 intervention rate；
6. 保留 Full CTDA v1 的 clean failure，解释为何方法收缩，而不是隐藏负结果。

### 强烈建议

1. 一个 terminal external physical-filter baseline，使用相同 proposal、oracle 与 fallback；
2. fast checker 与 Lean core 的 refinement/equivalence evidence；
3. ~~对 13,108 次 projection 做修改幅度分布和 task-family 分层，而不只给总数；~~ 已完成；
4. ~~对唯一 defended unsafe pair 和 11 个 residual-harm pair 做 failure taxonomy；~~ 已完成
   descriptive、post-outcome taxonomy，未来 confirmatory taxonomy 仍须 outcome 前冻结；
5. ~~独立复算脚本或表格生成器，直接从 ledger 生成论文表，避免手抄数字。~~ 已完成。

## 下一步决策

短期不再重跑相同实验。结果表、descriptive failure taxonomy 和 confirmatory/four-arm preregistration
已经完成；当前仍缺新 producer/runner readiness、fast-checker refinement/equivalence、资源预算和显式
用户执行授权。只有这些 execution-specific binding 另行冻结并获得明确授权后，才可启动下一轮 GPU
execution。
