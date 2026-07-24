# 论文就绪度评估

| 模块 | 就绪度 | 证据/缺口 |
|---|---|---|
| Threat model | 高 | 沿用原始可信 intent + attacked policy view |
| ActionBlock runtime schema | 高 | v3 typed objects 与 digest chain |
| Action–Execution checker | 中高 | Python tests + Lean core；仍无完整 refinement |
| Four-arm fixed trace | 中高 | shared runner 已重构；需更新/冻结 artifact |
| L1 assessor | 低 | 只有接口与 synthetic fixtures，真实资格化未完成 |
| Observer adequacy | 中低 | cost/collision 较好，contact proxy 仍残留 |
| M2 confirmatory foundation | 设计完成、未授权 | 60 pair × 2 seed × 2 condition |
| Closed-loop Dual | 未开始 | 必须在 M2 和 assessor gate 后 |

当前最重要的科学风险不是“π0.5 没有输出 plan”，而是 ActionBlock consequence assessor 的可识别性与
校准：如果支持集太窄，Dual 会 deadlock；如果阈值太松，攻击 block 会 false allow。

最短可发表路径：

1. 完成 M1 no-outcome artifacts；
2. 冻结并通过 assessor qualification；
3. 获得 M2 denominator/signal；
4. 运行 fixed-trace、clean、attacked 四臂；
5. 按预注册报告 safety/utility/coverage/deadlock，不扩大到 physical safety。
