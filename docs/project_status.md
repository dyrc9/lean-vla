# Project Status

更新日期：2026-07-20

## 当前状态

| 工作线 | 状态 | 当前结论 | 下一步 |
|---|---|---|---|
| CTDA 方法 | v1 frozen; revision required | 协议/实现/Lean parity 在冻结语义内有效，但 clean operational utility 不合格，当前方法不具备可接受的 runtime viability | 保留 v1 历史；按 `optimization_plan.md` 推进 v2 离线设计、fixed-trace/shadow 与 no-dispatch gate |
| E0 support | complete | 12 个 affordance/init0 non-real-time supported unit | 新实验不得越过支持范围，除非先做新 support audit |
| E1 utility | scoped pilot complete | policy-seed 1 的新 pilot 为 12/12 valid pair；VLA-only 8/12、Full CTDA 0/12 task/safe success，retention 0 | 负结果和归因已保存；不扩写总体结论或重跑旧 unit |
| E3 safety | scoped evidence complete | clean 12/12 preserved；post-dispatch 行为 fail closed，但正式 primary 12 unknown | 不改写旧分类；新的独立 challenge 才能增加 containment 证据 |
| E4 robustness | complete | 35/35 frozen fault case fail closed | 只保留 scoped component claim |
| timing | negative/deferred | Lean 0.9--1.3 s/stage，不满足实时控制 | 不优化，不恢复 real-time claim |
| attack foundation | not established | Phantom held-out 仅 1/4 independent safety transition；正式 SABER exact-task R1 为 0 record/0 victim episode | 与 v2 离线开发隔离并行；新 official SABER constraint-violation/EDPA workload 只能从 producer gate 开始 |
| external baselines | rebuild planned | SAFE partial、FIPER stopped；当前缺低层闭环 safety-filter baseline | P0 做 SafeLIBERO/AEGIS readiness；旧 partial 只作审计，不 resume、不发布指标 |

完整数字见 [`evaluation_results.md`](evaluation_results.md)。

## 方法 validity 判定

“实验有效”和“方法可用”必须分开：

- 新 E1 paired experiment 是有效的，12/12 pair 配对与 artifact validation 均通过；
- 2640/2640 Lean proof/parity 通过，说明实现执行了冻结的离散 spec，但不验证阈值、state abstraction
  或 utility 本身；
- 当前 CTDA v1 的 clean operational utility 判定为 **fail on the evaluated slice/seed**：baseline 的
  8 个 safe completion 一个也未保留，Full CTDA 0 phase completion；
- 该 clean pilot 两臂 observed unsafe 都是 0，因而没有显示可补偿 completion loss 的 clean safety
  benefit；两种距离 provenance 又在 24/24 episode 缺失；
- 总判定是 **v1 不具备 operational claim readiness，必须修改**，而不是把有效负结果改称
  terminal-invalid，也不是声称 CTDA 在所有分布上都无效。

机器可读判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

## 当前可以写

- 在固定 simulator task slice 上，Full CTDA clean safety observation 为 12/12 preserved；
- 在固定 CPU/Lean fault matrix 上，35/35 fault case fail closed；
- Lean unavailable/timeout、关键 binding tamper 和 typed fallback evidence 不足时，当前实现不会静默
  回退到 Python 授权；
- 当前系统是 slow-interlock/offline prototype。
- 在固定 12-task/init0/env7/policy-seed1 simulator slice 上，VLA-only 为 8/12 task/safe
  success，Full CTDA 为 0/12，task/safe-success retention 都是 0；两臂 collision/cost
  coverage 为 100%、observed unsafe 为 0。

## 当前不能写

- 该 12-task/policy-seed1 结果可推广到总体 task distribution 或其他 policy seed；
- post-dispatch containment 已正式建立；
- 对发布攻击有总体 defense efficacy；
- physical/hardware/continuous-dynamics safety；
- verified recovery、availability 或 real-time enforcement。
- 当前已经复现了足以支持 ProofAlign defense claim 的发布攻击。

## 已完成 clean utility 主任务

新 clean paired utility pilot 已完成并封存：

1. 24/24 episode、12/12 pair valid，双臂 initial digest、first policy chunk、checkpoint/config/camera/
   init/seed binding 匹配；
2. VLA-only 仍为 `UnguardedObservationChecker`，trace 中无 CTDA record；Full CTDA 使用
   `ctda-lean-kernel` 与 `slow-interlock-diagnostic-v1`；
3. VLA-only 8/12 task/safe success，Full CTDA 0/12；8 个 pair 构成 method-attributable utility
   loss；
4. Full CTDA 为 12 block、12 deadlock、0 phase completion；没有独立 action counterfactual，故不称
   false positive；
5. 两臂均为 12/12 episode unknown，因为 human/obstacle distance provenance 缺失；这与冻结的
   task/safe-success 标签正交，不改写为 invalid；
6. retained trace 归因完成：9/12 因 40 秒 semantic contract wall-clock window 无法再覆盖一个
   prefix，3/12 因 persistent bounded-stutter no-progress limit 在 3 个 prefix 后耗尽；12/12 都在
   approach 阶段 pre-dispatch refuted；
7. 下一步是 CTDA v2 设计 gate：重定义/实现 contract lifetime 与 proof latency 的关系、校准 binder
   liveness、补全 observation provenance，并事前冻结可接受 retention 与独立 safety endpoint。任何
   修订或新 rollout 必须新 method version/protocol/seed 或 unit/new root，不重跑本轮。

机器结果见
[`proofalign_e1_clean_utility_terminal_summary.json`](../experiments/proofalign_e1_clean_utility_terminal_summary.json)，
后续边界见 [`roadmap.md`](roadmap.md)。

## 当前主任务：CTDA v2 与安全实验基础双线重建

完整执行规划见 [`optimization_plan.md`](optimization_plan.md)。当前顺序不再是 attack-first 单线程：

- 工作线 A 允许先推进 CTDA v2 设计、代码、fixed-trace/shadow 和 no-dispatch preflight；
- 工作线 B 独立推进 SafeLIBERO/AEGIS readiness 和 VLA-only threat qualification；
- 两线汇合前不执行 attacked+defended 正式 rollout，不让 attack outcome 参与 v2 threshold 校准，也不让
  CTDA verdict 参与 attack ground truth。

攻击证据审计的正式结论仍是 `0` 条 workload 通过完整 qualification：

1. Phantom 固定 R0 的 medium laser 确实改变 20/20 policy frame，但 clean/attack 都成功；
2. R0b discovery 只有 strong laser 产生 3/3 task failure，held-out LIBERO-Safety R1 最终只有 1/4
   clean-safe → attacked-unsafe，低于 2/4 gate；
3. 早期 SABER-style 记录是 `saber_style_manual`；clean 7/12、attacked 8/12 task success，只有 1/12
   attacked unsafe，不能当作官方 SABER attack efficacy；
4. 正式 SABER exact-task R1 在第一条 record 的 chat-model 初始化阶段失败，0 valid record、0 victim
   rollout；
5. SAFE/FIPER 都是 defense baseline 而不是 attack；SAFE partial，FIPER fresh2 于
   2026-07-17 16:14:05 停止，terminal gate 未通过；
6. 在新的 VLA-only threat-validation protocol 通过前，不启动 attacked+defended rollout、不声称
   attack-defense benefit；这不阻止 outcome-blind 的 CTDA v2 离线优化和 clean/no-dispatch gate。

完整叙述见 [`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)，机器记录见
[`attack_reproduction_evidence_audit_20260717.json`](../experiments/attack_reproduction_evidence_audit_20260717.json)。

## 仓库状态规则

- 已终止的 protocol/result 不 resume、不覆盖、不重新分类；
- 所有正式执行必须先在 clean commit 冻结 protocol，再使用 fresh absent output root；
- timing 保留原始记录但不是下一实验 gate；
- raw artifact、ledger、manifest 和 terminal summary 必须一起保存；
- archive 只用于历史追溯，不作为当前方法或 CLI 来源。
- 新工作顺序、里程碑、停止条件和工作机交接以 [`optimization_plan.md`](optimization_plan.md) 与
  [`next_experiment_prompt.md`](next_experiment_prompt.md) 为准。
