# ProofAlign 文档导航

更新日期：2026-07-10

本页是仓库文档入口。当前主方法是 **ProofAlign 2.0: Contract-Carrying
Temporal Dual Alignment（CTDA）**。旧的 `IntentAligned / EffectAligned`
Boolean checker 仍作为兼容路径和实验基线保留，不代表完整 CTDA 在线授权路径。

## 建议阅读顺序

1. [`method.md`](method.md)：当前方法定义、形式判断、运行时协议和保证边界。
2. [`system_architecture.md`](system_architecture.md)：模块职责、数据流、信任边界和
   LIBERO 在线接入状态。
3. [`lean_spec_design.md`](lean_spec_design.md)：Lean 类型和旧版双层 specification 的
   设计背景。
4. [`lean_method_upgrade_20260710.md`](lean_method_upgrade_20260710.md)：CTDA 的相关工作、
   设计推导、迁移方案和截至 2026-07-10 的详细实现审计。
5. [`implementation_notes.md`](implementation_notes.md)：本地/GPU 环境、验证命令和
   工程约束。
6. [`experiments.md`](experiments.md) 与
   [`main_experiment_plan.md`](main_experiment_plan.md)：实验协议、baseline 和指标。
7. [`roadmap.md`](roadmap.md)：已完成能力、当前阻塞和下一阶段优先级。

攻击生成与防御方法当前双轨推进。GPU 攻击线固定 runner/protocol 并产出版本化 attack
artifact；method 线独立优化 CTDA，再以相同 task/init/seed/proposal 做配对。攻击跑通不能直接
解释为防御有效。

## 当前实现口径

| 能力 | 当前状态 | 可以声称什么 |
|---|---|---|
| Legacy 双层 checker | 已实现并接入真实 Lean | 对具体离散 Boolean claim 进行 Lean kernel 检查 |
| Typed CTDA 数据模型 | 已实现 | mission、contract、proposal、authorization、receipt 和 trace 有不可变结构与 digest 绑定 |
| Python CTDA reference checker | 已实现并接入 LIBERO | fail-closed 地执行 semantic、prefix-pre、observed-prefix 和 monitor 检查 |
| Lean CTDA checker 与定理 | 已实现、可编译 | checker 对 Lean 中定义的离散 proposition 具有 soundness/reflection 定理 |
| 跨-prefix monitor history | reference 版已实现 | Lean 在累计 accepted trace 上求值；Python 将 accepted events/nonce 纳入 monitor digest |
| Lean CTDA 在线 evaluator | 未接入 | 不能声称每个 LIBERO prefix 当前由 Lean CTDA 判定 |
| 连续动力学安全证明 | 未实现 | 当前仅有带显式假设的 simulator/运动学证据，不能声称真实机器人连续安全 |
| Verified fallback / 硬件 attestation | 未实现 | 当前 hold fallback、软件 receipt 和 simulator 证据只适用于测试 TCB |

## 文档口径规则

- “双层”指两类 alignment：`SemanticTemporalRefines` 与
  `PhysicalEffectConforms`。第二层在运行时分为执行前授权、执行中逐 prefix 监控和
  执行后完成审计。
- “Lean-backed legacy”不等于“Lean CTDA online”。前者通过临时 Lean 文件检查
  `Bool = true`；后者需要在线调用 `ProofAlign/CTDA.lean` 中的分阶段 evaluator，当前
  尚未完成接线。
- `safe_pending` 只表示已检查前缀尚未发现 violation 且合同仍有未决义务，不是整个未来
  trajectory 的安全证明。
- digest 只提供完整性和对象绑定；producer、感知、动力学或 fallback 的可信性必须由独立
  verifier/witness 支撑。
- Lean 不处理像素、点云、VLA inference、轨迹优化或真实硬件动力学。

若文档之间出现冲突，以 [`method.md`](method.md) 的方法定义和
[`lean_method_upgrade_20260710.md`](lean_method_upgrade_20260710.md) 最后的“实现状态与
剩余边界”为准；命令行行为以代码和 `--help` 为准。
