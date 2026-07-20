# ProofAlign 文档入口

更新日期：2026-07-20

## 当前事实来源

建议按顺序阅读：

1. [`project_status.md`](project_status.md)：当前状态、可写/不可写结论和唯一主任务。
2. [`evaluation_results.md`](evaluation_results.md)：E0--E4 统一结果与机器 artifact 入口。
3. [`method.md`](method.md)：normative 方法、威胁模型和 claim boundary。
4. [`system_architecture.md`](system_architecture.md)：实现模块和信任边界。
5. [`roadmap.md`](roadmap.md)：当前 research pause、attack foundation gate 与后续顺序。
6. [`experiments.md`](experiments.md)：实验冻结、配对、指标和失败规则。
7. [`remote_execution.md`](remote_execution.md)：当前 Python/Lean/OpenPI/GPU 环境和运行顺序。
8. [`implementation_notes.md`](implementation_notes.md)：代码入口、不变量和已完成 observer 配对修复。
9. [`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)：Phantom/SABER/SAFE/FIPER
   证据审计与“0 qualified attack”判定。

外部线：

- [`reproduction_plan.md`](reproduction_plan.md)：Phantom/SABER/SAFE/FIPER 状态、EDPA R0 asset gate 与 E5 gate。
- [`safe_fiper_r0_runbook.md`](safe_fiper_r0_runbook.md)：已停止 SAFE/FIPER partial 的审计与历史 runbook。

[`next_experiment_prompt.md`](next_experiment_prompt.md) 已完成并 superseded，不是当前执行授权。

论文材料：

- [`paper/paper_story.md`](paper/paper_story.md)
- [`paper/related_work.md`](paper/related_work.md)

## Archive

已终止阶段的长结果文档、旧 handoff 和旧命令位于 [`archive/`](archive/README.md)。它们保留用于
审计，但不是当前方法、CLI、状态或计划的事实来源。机器 JSON 和已提交 `results/` 才是正式实验记录。

## 冲突规则

1. 方法以 `method.md` 为准；
2. 当前结果以 `evaluation_results.md` 和机器 JSON 为准；
3. 当前优先级以 `roadmap.md` 为准；
4. CLI 以代码 `--help` 为准；
5. 环境以 `remote_execution.md` 为准；
6. archive 不覆盖 canonical 文档。

## 维护规则

- 不再新增日期型 status、handoff 或每阶段一份长报告；
- 新结果更新统一结果文档并保存 protocol/ledger/manifest/terminal summary；
- 已终止 protocol/result 不覆盖、不重标；
- 运行环境变化只更新 `remote_execution.md`；
- 详细历史通过 Git 和 archive 追溯。
