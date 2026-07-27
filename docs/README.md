# 文档导航

主线阅读顺序：

1. [`method.md`](method.md)：两层定义、threat model、四臂和 Lean claim boundary；
2. [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)：可信 `Z_t` 的 TCB、双视图和注入覆盖边界；
3. [`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)：零训练 `Z_t`、task graph、绑定和 probe；
4. [`semantic_subtask_pilot.md`](semantic_subtask_pilot.md)：冻结 checkpoint 的首轮 GPU probe 与限制；
5. [`action_block_assessment.md`](action_block_assessment.md)：`Z_t -> ActionBlock` 局部评估和资格化；
6. [`experiments.md`](experiments.md)：M1/M2/fixed-trace/closed-loop gate；
7. [`implementation_and_experiment_readiness.md`](implementation_and_experiment_readiness.md)：下一批代码接口、
   测试、artifact 与实验停止条件；
8. [`paper/paper_story.md`](paper/paper_story.md)：以双层对齐为主线的完整论文叙事；
9. [`paper/related_work.md`](paper/related_work.md)：与 VLA hierarchy、world model、shielding、benchmark 和
   formal methods 的逐层关系；
10. [`experiment_reuse.md`](experiment_reuse.md)：P0b/R9 的逐项复用、迁移步骤与禁止边界；
11. [`progress_and_plan.md`](progress_and_plan.md)：当前 blocker、历史复用和下一步；
12. [`remote_execution.md`](remote_execution.md)：执行授权与远程运行规则。

论文组织：

- [`paper/paper_story.md`](paper/paper_story.md)
- [`paper/progress_assessment.md`](paper/progress_assessment.md)
- [`paper/confirmatory_preregistration.md`](paper/confirmatory_preregistration.md)

审计原则：

- 旧 CTDA/PlanWitness/P0b/R9 文件不等于当前方法证据；
- frozen legacy protocol 和现有 v3 runtime 可以保留 `intent_only` / `intent_action_enabled` 兼容值；
  论文名称统一为 `Semantic-only` 和 `Intent–SemanticSubtask–ActionBlock`，semantic-bound successor
  推荐使用新 v4 schema，不静默改变 v3 digest；
- 顶层贡献始终是 Intent→ActionBlock 与 ActionBlock→Execution 双层对齐；`Z_t` 是 L1 机制，Lean 是
  L2 的核心形式化方法组件；
- 没有用户明确授权时，任何 protocol 都不授权新 outcome rollout。
