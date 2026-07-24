# 文档导航

主线阅读顺序：

1. [`method.md`](method.md)：两层定义、threat model、四臂和 Lean claim boundary；
2. [`action_block_assessment.md`](action_block_assessment.md)：L1 assessor 设计、资格化和泄漏控制；
3. [`experiments.md`](experiments.md)：M1/M2/fixed-trace/closed-loop gate；
4. [`paper/related_work.md`](paper/related_work.md)：与 VLA、world model、shielding、formal methods 的关系；
5. [`experiment_reuse.md`](experiment_reuse.md)：P0b/R9 的逐项复用、迁移步骤与禁止边界；
6. [`progress_and_plan.md`](progress_and_plan.md)：当前 blocker、历史复用和下一步；
7. [`remote_execution.md`](remote_execution.md)：执行授权与远程运行规则。

论文组织：

- [`paper/paper_story.md`](paper/paper_story.md)
- [`paper/progress_assessment.md`](paper/progress_assessment.md)
- [`paper/confirmatory_preregistration.md`](paper/confirmatory_preregistration.md)

审计原则：

- 旧 CTDA/PlanWitness/P0b/R9 文件不等于当前方法证据；
- frozen legacy protocol 可以保留旧字段名，但新 v3 runtime/result 使用
  `Intent–ActionBlock` / `ActionBlock–Execution`；
- 没有用户明确授权时，任何 protocol 都不授权新 outcome rollout。
