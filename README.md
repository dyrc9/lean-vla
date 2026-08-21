# ProofAlign: VLA ActionBlock 跨层完整性

ProofAlign 面向只暴露连续数值动作的 action-only VLA。系统在 consumer/dispatch boundary 保护同一个
source ActionBlock 从可信任务判断到实际执行证据的身份连续性：

- **L1（Trusted-context assessment）**：从独立可信任务与观察分支产生当前合法子任务，并对 VLA 实际
  输出的 exact ActionBlock 做 checker-relative assessment；
- **L2a（Execution transaction）**：把 contract、一次性 authorization、ordered dispatch、receipt 和
  observed effects 绑定为同一事务；
- **L2b（Covered containment）**：在接近关节边界时，对同一 source ActionBlock 的有限 guard
  configurations 做有界 screening。

主实验采用同一 runner 上的两个机制开关：

| Arm | L1 | L2a+L2b |
|---|---:|---:|
| VLA-only | off | off |
| L1-only | on | off |
| L2-only | off | on |
| Dual | on | on |

## 当前主线

唯一状态入口是 [`docs/current_status_and_roadmap.md`](docs/current_status_and_roadmap.md)。默认只讲一个
最终系统，不叙述内部版本演进。

1. **SABER 攻击已成功复现**：OpenPI Pi0.5 与 LIBERO-Safety 上的冻结
   `constraint_violation` instruction records 共完成240个有效 episodes；86个 clean-eligible units 中有
   39个产生新的 risk transition，观测 ASR 为 `39/86 = 45.35%`，95% base-pair cluster-bootstrap CI 为
   `[32.93%, 57.78%]`。
2. **最终 ProofAlign 已完成全量配对四臂实验**：60个base pairs乘2组seeds，共120个固定units；
   clean/attacked与四个arms组成960次episode attempts，全部artifact存在，每个条件`475/480` valid。
   attacked risk transitions为VLA/L1/L2/Dual `45/85、42/78、43/86、43/78`，没有显示broader endpoint下降；
   237个valid attacked L2-on rows的joint-limit steps为0。由于all-valid gate失败，结果按保守nonconfirmatory
   终态报告。
3. **项目已结题**：论文源、claim--evidence 映射、最终实验结果和复现审计材料均已冻结；默认不再继续
   方法优化、运行新实验或扩展 benchmark。
4. **后续只做可复现性维护**：保留历史协议、结果、checksums 和 non-pass 分类。除非项目被明确重启，
   更多 seeds、其他攻击族、camera-only trusted perception、真实机器人或更强 execution attestation
   仅作为未执行的未来方向。

## 文档

- [当前状态与路线图](docs/current_status_and_roadmap.md)
- [中文论文叙事母稿](docs/paper/paper_narrative_zh.md)
- [方法与 claim boundary](docs/method.md)
- [最终全量四臂结果](docs/paper/full120_four_arm_result_integration.md)
- [ActionBlock长度与候选采样数消融](docs/paper/actionblock_sampling_ablation.md)
- [相关工作定位](docs/paper/related_work.md)
- [文档导航](docs/README.md)
- [历史审计归档](docs/archive/README.md)

## 验证

结题版本的发布门禁只验证最终论文声明、聚焦测试、Lean transaction model 和匿名 PDF：

```bash
uv run python scripts/audit_ndss2027_paper_claims.py
uv run python scripts/check_ndss2027_submission.py
```

全库 `pytest` 仍是历史审计入口，不是结题发布门禁；它会按设计检查旧冻结 artifact 与当前源码 digest 的
一致性。2026-08-21 的完整运行结果与未改判原因见
[`docs/archive/project_closeout_audit_20260821.md`](docs/archive/project_closeout_audit_20260821.md)。历史协议、内部
版本、开发过程和冻结分类继续保留用于审计与复现，但不进入默认论文叙事。论文提交系统的 paper number 与
最终 AI 模型标签仍属于外部人工字段，不应在仓库中猜测填写。
