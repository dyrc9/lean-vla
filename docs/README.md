# ProofAlign 文档入口

本目录只把少量文档定义为当前事实来源。历史实验记录、旧设计、旧命令和阶段性 handoff
已经移到 [`archive/`](archive/README.md)。除非任务明确要求历史追溯，agent 不应读取或引用
archive 中的内容。

## Canonical 文档

建议按以下顺序阅读：

1. [`project_status.md`](project_status.md)：当前真实进展、已验证资产和 P0 阻塞。
2. [`method.md`](method.md)：唯一 normative 方法定义、威胁模型和 claim boundary。
3. [`system_architecture.md`](system_architecture.md)：当前实现与目标闭环的模块对应。
4. [`roadmap.md`](roadmap.md)：唯一执行优先级、阶段 gate 和停止条件。
5. [`experiments.md`](experiments.md)：最小配对实验、指标和 artifact 规则。
6. [`reproduction_plan.md`](reproduction_plan.md)：发布攻击、现有防御与 CTDA 的复现证据链。
7. [`implementation_notes.md`](implementation_notes.md)：本地 CPU/Lean 开发与验证约定。
8. [`remote_execution.md`](remote_execution.md)：迁移到远程 GPU 后的环境、路径和运行协议。
9. [`paper_story.md`](paper_story.md)：收缩后的论文叙事和可写贡献。
10. [`related_work.md`](related_work.md)：研究定位；不作为实现状态或 CLI 来源。

## 当前方法口径

当前核心是一个有限范围的 **mission-rooted persistent dual monitor**：

- `MissionRefinementGate`：合同必须来自 trusted, locally frozen benchmark mission、当前
  phase 和 residual obligation；policy-facing prompt 无权重写任务根。
- `TraceConformanceGate`：raw proposal、实际 dispatch 和累计 observed trace 必须绑定同一
  合同；没有 completion witness 不得推进 phase。

当前 runner 可选择 `ctda-python-reference`、`ctda-lean-kernel` 和 `ctda-shadow`。有限 Pick/Place
paper path 已改为 mission-rooted contract 与 independent raw binder；`ctda-lean-kernel` 的四个
stage 确实生成并检查 replay artifact，golden parity 为零 mismatch。当前 Lean p99 仍远超 control
period，因此只能表述为 slow interlock/offline audit，仍不能把系统表述为完整 proof-carrying VLA、
real-time safety monitor 或 physical safety proof。

## 冲突处理

当文档、代码和历史记录不一致时：

1. 方法与 claim 以 [`method.md`](method.md) 为准；
2. 当前优先级以 [`roadmap.md`](roadmap.md) 为准；
3. CLI、schema 和默认值以当前代码、测试和 `--help` 为准；
4. 远程机器路径与迁移清单以 [`remote_execution.md`](remote_execution.md) 为准；
5. `archive/` 永远不是当前事实来源。

## 文档维护规则

- 不再新增日期型状态文档；状态统一更新 `project_status.md`。
- 不再新增并行 roadmap；任务统一进入 `roadmap.md`。
- 远程环境和成功命令只更新 `remote_execution.md`。
- 实验完成后保存原始 artifact 和机器可重建 summary；不要只写一份结果叙述。
- 方法字段、Lean semantics、Python evaluator 和实验标签必须同步更新。
