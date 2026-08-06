# 文档导航

## 默认阅读

1. [`current_status_and_roadmap.md`](current_status_and_roadmap.md)：唯一项目进度入口；
2. [`method.md`](method.md)：L1/L2方法、四臂设计和Lean claim boundary；
3. [`paper/paper_story.md`](paper/paper_story.md)：论文完整叙事；
4. [`paper/v15_14_final_four_arm_results.md`](paper/v15_14_final_four_arm_results.md)：最终clean与
   SABER-attacked四臂主表；
5. [`paper/final_results_figures.md`](paper/final_results_figures.md)：历史论文表格、图和冻结结果入口。

以后回答“项目进展如何”，默认只读取第1项，并按以下顺序汇报：

```text
复现了什么攻击、攻击成功率是多少
  -> 原方法四臂实验结果
  -> 新方法优化结果
  -> 最终还缺哪些实验
```

## 方法与实现参考

- [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)：可信输入和攻击边界；
- [`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)：L1 semantic hierarchy；
- [`action_block_assessment.md`](action_block_assessment.md)：ActionBlock checker；
- [`experiments.md`](experiments.md)：实验协议；
- [`implementation_and_experiment_readiness.md`](implementation_and_experiment_readiness.md)：代码与执行准备；
- [`remote_execution.md`](remote_execution.md)：远程执行和授权规则。

## 历史归档：非默认读取

- [`progress_and_plan.md`](progress_and_plan.md)：完整实验时间线；
- [`failure_lessons.md`](failure_lessons.md)：失败原因和停止规则；
- [`experiment_reuse.md`](experiment_reuse.md)：历史实验复用边界；
- [`v11_terminal_checkpoint.md`](v11_terminal_checkpoint.md)：v11终局；
- [`v12_simulator_integrated_recovery_checkpoint.md`](v12_simulator_integrated_recovery_checkpoint.md)：
  v12.6–v12.38完整优化过程；
- 其他 `v12_*_checkpoint.md`：v12中间机制证据。

历史non-pass不会被删除或改判，但不再用于日常进度复述。只有在审计特定结论、解释方法来源或编写论文
消融部分时才读取这些归档。
