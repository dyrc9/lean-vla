# ProofAlign 文档入口

更新日期：2026-07-20

## 当前事实来源

建议按顺序阅读：

1. [`project_status.md`](project_status.md)：实验暂停状态、minimal prototype 和下一实验优先级。
2. [`evaluation_results.md`](evaluation_results.md)：E0--E4 统一结果与机器 artifact 入口。
3. [`optimization_plan.md`](optimization_plan.md)：本地 no-action prototype 状态、实验暂停边界，以及
   恢复后的 VLA-only 攻击复现顺序。
4. [`roadmap.md`](roadmap.md)：minimal prototype checkpoint、下一实验优先级与永久边界。
5. [`method.md`](method.md)：两关系、两不变量、三 transaction 的 normative 方法与 claim boundary。
6. [`system_architecture.md`](system_architecture.md)：当前实现、五组件目标架构、plumbing/intervention
   边界和后续迁移顺序。
7. [`experiments.md`](experiments.md)：实验冻结、配对、指标和失败规则。
8. [`remote_execution.md`](remote_execution.md)：当前 Python/Lean/OpenPI/GPU 环境和运行顺序。
9. [`implementation_notes.md`](implementation_notes.md)：minimal/v1/v2 代码入口、不变量和验证命令。
10. [`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)：Phantom/SABER/SAFE/FIPER
   证据审计与“0 qualified attack”判定。

外部线：

- [`reproduction_plan.md`](reproduction_plan.md)：旧 Phantom/SABER/SAFE/FIPER 状态，以及新的
  SafeLIBERO/AEGIS、SABER constraint-violation、EDPA 与 E5 gate。
- [`safe_fiper_r0_runbook.md`](safe_fiper_r0_runbook.md)：已停止 SAFE/FIPER partial 的审计与历史 runbook。

[`next_experiment_prompt.md`](next_experiment_prompt.md) 是暂停中的下一实验交接 prompt；当前不得执行。

论文材料：

- [`paper/paper_story.md`](paper/paper_story.md)：最小论文叙事、贡献和四臂因果评估。
- [`paper/related_work.md`](paper/related_work.md)：SafeGate/RoboGuard、temporal monitor、proof-carrying
  planning、RTA/filter 与 mission/trajectory integrity 的 novelty 审计。

## Archive

已终止阶段的长结果文档、旧 handoff 和旧命令位于 [`archive/`](archive/README.md)。它们保留用于
审计，但不是当前方法、CLI、状态或计划的事实来源。机器 JSON 和已提交 `results/` 才是正式实验记录。

## 冲突规则

1. 方法以 `method.md` 为准；
2. 当前结果以 `evaluation_results.md` 和机器 JSON 为准；
3. 当前执行顺序以 `optimization_plan.md` 为准，摘要优先级以 `roadmap.md` 为准；
4. CLI 以代码 `--help` 为准；
5. 环境以 `remote_execution.md` 为准；
6. archive 不覆盖 canonical 文档。

## 维护规则

- 不再新增日期型 status、handoff 或每阶段一份长报告；
- 新结果更新统一结果文档并保存 protocol/ledger/manifest/terminal summary；
- 已终止 protocol/result 不覆盖、不重标；
- 运行环境变化只更新 `remote_execution.md`；
- 详细历史通过 Git 和 archive 追溯。
