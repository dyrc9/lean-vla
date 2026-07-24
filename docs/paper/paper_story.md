# Paper story

## 一句话

> ProofAlign 在不要求 VLA 输出高层规划的条件下，将可信意图到具体 ActionBlock 的后果对齐，与获准
> ActionBlock 到 observed execution/effects 的事务完整性分离，并用四臂共享 runner 估计两层的独立和
> 联合作用。

## 动机

Instruction/observation attack 的危险不在于 VLA 是否“承认”恶意计划，而在于可信任务仍是 `T` 时，
模型可能输出实际效果偏离 `T` 的数值 action chunk。多数实际 VLA 接口只给动作，因此把显式 plan
设为前提会把核心问题绕开。

## 方法

L1 用冻结 consumer assessor 预测 concrete block 的 skill/target/effects/violations，并与 trusted intent
比较。L2 用 consumer-generated contract、exact dispatch receipt 和 observed effects 检查执行没有
substitution/drift。Lean 只约束 L2 的有限绑定和 phase transition。

## 经验问题

1. 攻击是否稳定地产生 intent-divergent ActionBlocks？
2. L1 在可接受 clean retention 下能否降低 attacked-block false allow？
3. L2 是否能捕获 command/effect drift，并保留 task utility？
4. Dual 是否互补，还是增加 unknown/deadlock？

## 贡献边界

可能的贡献：

- action-only VLA 上可观测的双层完整性定义；
- trusted-intent/action-consequence assessment 的 qualification protocol；
- action/authorization/receipt/effect/phase 的 Lean-specified transaction；
- byte-identical four-arm causal runner；
- instruction/observation attack 下的 confirmatory benchmark evidence。

不作为贡献：

- 首次 high-level planning；
- 首次 world model、shield 或 action filter；
- Lean 证明物理安全；
- 从动作唯一恢复模型 latent intent。

## 证据叙事

P0b 与 R9 是问题存在性和 Execution-only 的探索性证据；新的论文主结果必须来自 M2 gate 后的四臂。
`23 < 26`、residual contact proxy 和 incomplete strict-success recovery 都必须保留，不能被“强正结果”
掩盖。
