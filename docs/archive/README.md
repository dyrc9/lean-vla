# Documentation Archive

本目录保存历史设计、阶段性结果、旧命令和外部 patch，仅用于追溯。

**这些文件不是当前方法、claim、CLI、实验协议或执行优先级的事实来源。** Agent 默认不得
加载 archive；只有明确的历史复现、结果审计或外部 patch 恢复任务才可以读取。

## 目录

- `pre_scope_freeze_20260710/`：2026-07-10 scope freeze 前的完整文档快照，包括 legacy Dual
  Lean、过宽的 CTDA upgrade memo、旧 GPU handoff、旧实验计划和日期型结果记录。
- `evaluations/`：已终止 E0/E1/E3/E4 阶段的详细叙述报告；当前数字已合并到
  [`../evaluation_results.md`](../evaluation_results.md)。
- `handoffs/`：已经执行或过期的 GPU/agent 交接 prompt。
- `artifacts/saber_patches/`：先前成功运行 SABER LoRA eval 所使用的外部仓库 patch。它们依赖
  对应 upstream commit；没有 commit 匹配时不得直接应用。

## 当前入口

返回 [`../README.md`](../README.md) 查看 canonical 文档列表。当前 CLI 以代码和 `--help` 为准，
环境配置以 [`../remote_execution.md`](../remote_execution.md) 为准。

## 归档原则

- 归档材料保留原文，不持续修正其中的过期结论或断链。
- 新实验不能只增加一份日期型 Markdown；必须保存 raw artifact、配置和可重建 summary。
- 新设计不能在 archive 中悄悄成为当前方法；必须更新 canonical `method.md` 与 `roadmap.md`。
