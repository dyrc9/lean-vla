# 论文就绪度评估

| 模块 | 就绪度 | 证据/缺口 |
|---|---|---|
| Threat model | 高 | 沿用原始可信 intent + attacked policy view |
| 双层问题定义 | 高 | Intent→ActionBlock 与 ActionBlock→Execution 的 estimand 已稳定 |
| Trusted semantic boundary | 中高 | context/allowlist/prompt binding 已实现；尚无硬件级 trusted tap |
| Semantic selector | 低 | 首轮 pilot 只支持 skill-level 路线；held-out qualification 未完成 |
| Action conditioning | 低 | prompt path 有非零敏感性，但动作差异很小，尚非可靠 control |
| Local ActionBlock checker | 低 | 接口与 pure selection 已有；真实几何 checker/qualification 未完成 |
| ActionBlock runtime schema | 中高 | v3 typed objects 与 digest chain 已有；`Z_t`/prompt 尚未端到端贯通 |
| Action–Execution checker | 中高 | Python tests + Lean core；仍无完整 refinement |
| Four-arm fixed trace | 中高 | shared runner 已重构；需加入 semantic identity 并重新冻结 artifact |
| Observer adequacy | 中低 | cost/collision 较好，contact proxy 仍残留 |
| M2 confirmatory foundation | 设计完成、未授权 | 60 pair × 2 seed × 2 condition |
| Closed-loop Semantic-only/Dual | 未开始 | 必须在 selector/checker、identity、M2 gate 后 |

论文主故事仍是两层对齐，而不是 SemanticSubtask 本身。当前最重要的科学风险集中在 L1：

1. `Z_t` 是否能在 held-out task/object/stage 上稳定选择合法 frontier；
2. `Z_t` 作为显式 policy 输入是否对 ActionBlock 有足够、阶段合理的影响；
3. local checker 能否在 attacked blocks 上控制 false allow，同时保持 clean coverage；
4. 这些组件接入 runtime 后是否因 latency/unknown 导致 deadlock。

如果 selector/checker 支持集太窄，Dual 会 deadlock；如果阈值太松，攻击 block 会 false allow。如果
`Z_t` 对 action head 几乎没有行为影响，它仍可作为 verifier anchor，但不能被表述为有效的 hierarchical
control。

最短可发表路径：

1. 完成 semantic runtime binding 与 K=1 executable-prefix local checker；
2. 冻结并通过 selector、action-conditioning 和 local-checker qualification；
3. 更新 fixed-trace identity artifact、资源预算和 Python↔Lean evidence；
4. 获得 M2 denominator/signal；
5. 运行 fixed-trace、clean、attacked 四臂；
6. 按预注册分别报告 safety、utility、coverage、unknown 和 deadlock，不扩大到 physical safety。

若 selector qualification 或 action conditioning 不通过，论文仍可回退到“双层对齐 + deterministic
task-FSM L1”的窄版本；不能为了保留 SemanticSubtask 学习叙事而放宽 gate。
