# ProofAlign 文档入口

更新日期：2026-07-24

当前文档已经收敛为一个主线：

1. [`progress_and_plan.md`](progress_and_plan.md)：当前结果、证据边界、下一实验和 M0–M6 规划；
2. [`method.md`](method.md)：两层关系、两个不变量、三个 transaction 和四臂语义；
3. [`experiments.md`](experiments.md)：实验冻结、gate、统计和停止规则；
4. [`remote_execution.md`](remote_execution.md)：本地/远程环境、资源隔离和执行前检查；
5. [`paper/action_envelope_results.md`](paper/action_envelope_results.md)：由 R9 terminal evidence
   生成的论文表、projection 分布和 failure taxonomy；
6. [`paper/confirmatory_preregistration.md`](paper/confirmatory_preregistration.md)：独立确认性
   attack foundation 与后续四臂设计；
7. [`paper/paper_story.md`](paper/paper_story.md)：论文叙事；
8. [`paper/progress_assessment.md`](paper/progress_assessment.md)：论文就绪度和缺口；
9. [`paper/related_work.md`](paper/related_work.md)：相关工作与 novelty 边界。

结果数字以机器 JSON 为准：

- [`saber_integrity_action_envelope_terminal_summary.json`](../experiments/saber_integrity_action_envelope_terminal_summary.json)
- [`action_envelope_paper_tables.json`](../experiments/action_envelope_paper_tables.json)
- [`action_envelope_failure_taxonomy.json`](../experiments/action_envelope_failure_taxonomy.json)
- [`saber_confirmatory_preregistration_v1.json`](../experiments/saber_confirmatory_preregistration_v1.json)
- [`proofalign_four_arm_preregistration_v1.json`](../experiments/proofalign_four_arm_preregistration_v1.json)

旧架构、失败方案、阶段 handoff 和重复状态文档已从工作树删除，通过 Git 历史追溯。冻结的 R0–R9
协议/状态链仍留在 `experiments/`，因为 terminal R9 的审计绑定需要它们；它们不是可继续执行的并行
方案。

完整 R9 raw episode 只保留在实验机本地，不上传远端。
