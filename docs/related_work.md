# Related Work：双层执行完整性的定位

> 本文只用于研究定位，不是实现状态、CLI 或执行计划的事实来源。当前方法和 claim 以
> [`method.md`](method.md) 为准。

## 定位原则

ProofAlign 不以“首次将形式化方法用于机器人”“首次做运行时监控”或“首次用 Lean 检查
VLA”为新意。已有工作分别覆盖了安全任务 gate、时序 monitor、proof-carrying planning、
runtime assurance、连续 safety filter、软件/轨迹 attestation 和 VLA attack。

CTDA 的候选新意是把这些问题收束成 VLA 控制链上的两个不可互相推出的完整性关系：

```text
Mission Authorization Integrity:
  trusted, locally frozen mission + active phase
    -> persistent semantic macro-contract

Execution / Effect Realization Integrity:
  contract -> proposal -> authorized command -> executed command -> observed trace
```

它关注的是从自然语言授权根到连续动作前缀的端到端绑定、complete mediation 和跨 action
chunk 的时序连续性。Lean 是实现离散 checker 的手段，不单独构成 novelty。

## 1. VLA safety benchmark 与攻击

LIBERO-Safety、HazardArena、ForesightSafety-VLA 等工作说明 task success 无法覆盖碰撞、危险
affordance、语义约束和过程级风险。SABER 进一步把 instruction channel 作为攻击面，目标包括
task failure、action inflation 和 constraint violation。

这些工作为 CTDA 提供 threat workload，但不自动给出 runtime authorization mechanism。
ProofAlign 的攻击线独立生成并保存 attack artifact；防御线使用同一 task/init/seed/proposal
做 paired replay 和 online evaluation。攻击成功率是威胁证据，不等于防御效果。

CTDA 与 training-time safety alignment 的区别是：它不要求重新训练或验证 VLA，而把 VLA
视为非可信 proposal producer。即使攻击后的 prompt 和 proposal 内部一致，它们仍必须对齐
冻结的 mission root。

## 2. Semantic gate、task contract 与 temporal monitor

[SafeGate / Task Safety Contracts](https://arxiv.org/abs/2604.05427) 在 LLM-controlled robot
systems 中结合 pre-execution gate、invariants、guards、abort conditions 和运行时 contract。
RoboGuard、SafePlan、Plug in the Safety Chip、Code-as-Monitor、VASO 和 SafeManip 等方向分别
探索了神经/符号 guard、formal task planning、LTL/时序约束、generated monitor 和 skill
contract。

这些工作使以下主张不再成立：

- “首次在机器人任务执行前做语义安全检查”；
- “首次在执行中和完成时使用 temporal monitor”；
- “首次把任务表示成 formal contract”。

CTDA 必须通过更窄的区别成立：

1. policy-facing prompt 与 trusted mission root 分离；
2. semantic contract 跨多个 VLA action chunks 持续存在；
3. 第一层只决定合同是否被任务授权，不把物理可行性偷渡成语义结论；
4. 第二层绑定 proposal、filter 后命令、actuator receipt 和 trace；
5. 未取得 completion witness 时不得推进 task phase。

因此 SafeGate/semantic monitor 是第一层和共享 monitor substrate 的强 baseline，而不是应被
弱化的 strawman。

## 3. Runtime assurance 与连续控制安全

[SOTER](https://doi.org/10.1109/DSN.2019.00027) 将 uncertified advanced controller、
certified baseline controller 和 safety specification 组成 runtime-assurance module，并研究
安全切换与模块组合。Simplex/RTA、ModelPlex、VeriPhy、CBF、predictive safety filter 和
reachability 方法进一步覆盖 dynamics model、reachable set、barrier condition、sampling 与
fallback。

这些工作比当前 CTDA prototype 的 simulator zero-hold 和 Boolean tube 声明提供更强的连续
安全基础。CTDA 不应声称替代它们；第二层应把它们的 consumer-checkable witness 作为
`PrefixPreCertified` 和 observed-prefix conformance 的证据。

CTDA 的区别是把 continuous/RTA evidence 绑定到 VLA 的 semantic macro-contract 和任务阶段。
即使一条 trajectory 对局部 dynamics 是安全的，如果它没有被 frozen mission 授权，第一层
仍应拒绝；即使合同语义合法，如果 tube、command 或 trace 不一致，第二层仍应拒绝。

## 4. Proof-carrying plan 与 machine-checkable contract

Proof-Carrying Plans、formal planning、resource logic 和 proof-producing solver 已经说明 plan
可以携带 pre/post-condition proof，而不是只携带动作序列。CTDA 将对象从离散完整 plan 扩展
为闭环 VLA proposal 与短 action prefix，并增加实际执行回执和 observed-trace audit。

这里必须区分三种 evidence：

- `binding metadata`：digest、id、version、timestamp，只证明对象身份和关联；
- `trusted attestation`：由声明 TCB/密钥/隔离边界保证 producer 身份与软件状态；
- `consumer-checkable witness`：checker 可以独立复核的 proof、tube、barrier 或 trace artifact。

当前不少 CTDA evidence 仍属于前两类，不能统一写成 physical proof。更准确的当前表述是
contract/evidence-carrying runtime；只有可复核 witness 覆盖相应 claim 后，才使用更强的
proof-carrying 表述。

## 5. Autonomous-system execution integrity 与 attestation

安全领域已有与 CTDA 非常接近的执行完整性工作：

- [ARI, USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/wang-jinwen)
  定义 Real-time Mission Execution Integrity，关注自主 CPS 任务的正确、及时执行及其 attestation；
- [DIAT, NDSS 2019](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/)
  关注自主系统中数据生成、处理和传输链的完整性证明；
- [TAT, USENIX Security 2026](https://www.usenix.org/conference/usenixsecurity26/presentation/yao)
  定义工业机械臂 trajectory integrity，并对实际运动轨迹做 attestation。

这些工作要求 ProofAlign 不能只把 digest equality 写成 security mechanism。若 threat model
包含恶意 host、IPC、observer 或 actuator，必须引入签名/密钥、可信计数器、隔离 reference
monitor 和 sensor/actuator attestation。

CTDA 相对这一方向最有潜力的区别是：现有 mission/trajectory attestation 主要从程序或预定
轨迹出发，而 VLA 的授权根来自自然语言任务，proposal 在闭环中不断变化。CTDA 试图连接：

```text
authenticated natural-language/BDDL mission semantics
  -> semantic phase authorization
  -> exact low-level prefix authorization
  -> executed command and observed effect integrity
```

要使这一差异成为安全贡献，论文必须明确定义攻击者、认证机制、TCB 和端到端安全属性，不能
只依赖 `authenticated = true` 或可由攻击者重算的普通 hash。

## 6. 最接近工作的差异矩阵

| 方向 | 已有能力 | CTDA 需要证明的增量 |
|---|---|---|
| SafeGate / semantic guard | unsafe command gate、task contracts、runtime constraints | prompt 与 frozen authority 分离；VLA prefix 与任务 phase 的持续绑定 |
| Code-as-Monitor / SafeManip | execution/completion temporal monitoring | monitor artifact 不直接成为信任根；跨 proposal 的 persistent residual state |
| VASO / formal skill contract | formal/planner-facing skill abstraction | proposal、authorized、executed、observed 四对象绑定 |
| SOTER / Simplex RTA | uncertified/verified controller 切换与安全保证 | RTA witness 与 semantic contract、任务 phase 组合 |
| CBF / predictive filter / reachability | 连续 prefix safety 或 recoverability | 局部物理安全不能替代 mission authorization |
| ARI / DIAT / TAT | mission、data 或 trajectory integrity attestation | 从认证自然语言语义到动态 VLA proposal/effect 的端到端连接 |
| Proof-carrying planning | plan 的 machine-checkable pre/post proof | 闭环 prefix、实际 receipt、observed trace 和 partial completion |

## 7. Novelty 与 claim 边界

当前最稳健的 novelty statement 是：

> CTDA formulates VLA execution as two coupled integrity relations: every
> persistent semantic contract must refine a trusted, locally frozen mission, and
> every proposed, authorized, executed, and observed action prefix must remain
> bound to that contract until a checked completion witness advances the task.

论文不能把以下单独列为新意：双 checker、使用 Lean、执行前 gate、执行后 monitor、temporal
logic 或 fallback。新意必须来自双层安全属性、端到端对象绑定、跨 chunk complete mediation，
以及它们在攻击 workload 下的可验证增益。

最终保证分三层报告：

1. **协议保证**：没有两层授权不 dispatch，没有 completion witness 不推进 phase；
2. **离散形式保证**：checker 的 `proven` 推出 typed proposition；
3. **条件物理保证**：仅在 observer、dynamics、timing、actuator、abstraction 和 fallback
   assumptions 成立时推出 prefix invariant preservation。

三者不能在摘要或实验表中合并成无条件“robot safety proof”。
