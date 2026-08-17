# 文档导航

当前文档只围绕一个最终 ProofAlign 原型组织：

1. [`current_status_and_roadmap.md`](current_status_and_roadmap.md)：唯一当前状态与写作路线入口；
2. [`paper/paper_narrative_zh.md`](paper/paper_narrative_zh.md)：中文论文叙事母稿；
3. [`method.md`](method.md)：最终系统定义、L1/L2a/L2b 机制和 claim boundary；
4. [`paper/final_four_arm_results.md`](paper/final_four_arm_results.md)：最终 clean/attacked 配对四臂结果；
5. [`paper/actionblock_sampling_ablation.md`](paper/actionblock_sampling_ablation.md)：已冻结的 ActionBlock
   长度 `H=2/5/10` 与候选采样数 `K=1/2/4` 消融；
6. [`paper/related_work.md`](paper/related_work.md)：攻击、防御与 closest-work 定位；
7. [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)：可信任务/观察与不可信 policy view 的边界；
8. [`action_block_assessment.md`](action_block_assessment.md)：ActionBlock assessment 契约；
9. [`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)：结构化子任务与 task frontier。

默认叙事顺序为：

```text
SABER攻击成功复现
  -> action-only VLA的authorization/realization gaps
  -> 最终ProofAlign系统
  -> 最终配对四臂证据
  -> 论文初版
  -> 由初稿缺口驱动的补充实验
```

内部版本、优化过程、失败分析、旧协议和 checkpoint 统一保留在
[`archive/`](archive/README.md)及冻结实验目录中，仅用于历史审计与复现，不进入默认论文故事。
