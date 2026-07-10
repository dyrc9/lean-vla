# 论文核心故事

> 状态说明（2026-07-10）：当前论文方法名为 **ProofAlign 2.0: Contract-Carrying
> Temporal Dual Alignment (CTDA)**。本文保留了早期 Intent-Action / Action-Effect 的
> 动机表述；正式方法、在线实现状态和不可声称边界以 [`method.md`](method.md) 为准。

## 背景

Vision-Language-Action (VLA) 模型正在把自然语言指令、视觉观测和机器人动作连接到同一个策略中。它们的优势是端到端泛化、语义理解和动作生成能力；风险也来自同一个地方：模型可能在语言、视觉、动作之间产生难以解释的错配。一个机器人可以完成看似正确的动作，却抓错对象、忽略人手、越过禁区、执行危险子目标，或者在动作执行后造成与任务意图相反的环境变化。

传统评测常用 task success rate 衡量 VLA 是否完成任务。但对安全执行而言，成功率不是充分指标。一个 episode 可以在最终状态上成功，同时中途撞到障碍物、擦过人手、推动危险物体、使用错误 affordance，或违反“不要移动某物”的约束。相反，一个安全系统可能主动拒绝或中止危险动作，导致任务未完成，但这是正确行为。因此，安全 VLA 需要过程级、语义级和效果级的检查，而不只是最终任务完成情况。

## 现有 VLA 安全方法的问题

当前 VLA 安全方法大致有几类：

1. 训练时加入更多安全数据或偏好数据。
2. 执行前用 LLM / VLM verifier 进行自然语言审查。
3. 使用 collision checker 或 motion planner 做几何安全过滤。
4. 在 planner 层加入约束、规则、temporal logic 或 contract。
5. 以仿真评测或 post-hoc safety metrics 识别失败模式。

这些方向都重要，但仍留下三个缺口。

第一，语义意图与动作之间缺少可信检查。VLA 的 action chunk 可能在多步执行中从最初指令漂移出去。例如用户说“把干净杯子放到杯垫上”，模型可能转而抓杯垫、移动刀具、或把杯子放到不稳定区域。几何上可行的动作不一定忠实于原始意图。

第二，动作承诺与实际效果之间缺少可信检查。即使候选动作在执行前看起来安全，真实环境可能因为动力学误差、抓取滑移、感知延迟、人手进入、障碍物移动而产生不同效果。只检查计划不检查执行后状态，会漏掉 runtime deviation。

第三，很多 verifier 本身仍是神经模型或启发式规则。LLM verifier 可以解释，但不适合作为 trusted boundary；collision checker 可以排除部分几何碰撞，但无法表达“不要抓刀刃”“不要把热杯子递给人”“只移动目标物体”“动作后危险物体仍应远离人手”等语义条件。

## 为什么只看任务成功率不够

安全不是任务成功率的子集。至少有四种情况会被成功率掩盖：

- Unsafe success：任务完成了，但执行过程中发生碰撞、越界、危险接触或对象误操作。
- Fortuitous success：模型做了错误动作，但环境偶然恢复到成功状态。
- Semantic violation：最终状态满足粗粒度目标，但违反了用户的隐含约束或安全规范。
- Intervention-dependent success：执行依赖人类干预、对象碰撞或外力修正，不能算作可靠自主执行。

LIBERO-Safety 这类 benchmark 的价值正在于把 VLA 从“完成任务了吗”推进到“在严格安全约束下完成了吗”。我们的框架进一步把这种评测思想转化为运行时执行机制：每个 action chunk 都必须带着可检查的 contract，而不是只在 episode 结束后统计失败。

## 为什么只做 collision checker 不够

Collision checker 解决的是一类重要但有限的问题：轨迹与几何体是否相交，或者机器人是否进入禁区。它通常不直接理解：

- 指令意图：机器人应该移动哪个对象，不应该移动哪个对象。
- 物体部件语义：杯柄、刀柄、刀刃、按钮、盖子、容器开口等。
- 关系约束：物体应保持在某区域内、某对象应远离人手、某容器不能倾倒。
- 动作承诺：抓取后目标对象应被持有，放置后对象应位于目标区域。
- 动态干扰：人手出现后动作是否仍满足安全 precondition。
- 语义安全：不能把清洁剂放到食物旁，不能把尖锐物朝向人。

因此，collision checker 应该是 certificate 生成者或低层安全模块之一，而不是完整安全框架。我们的设计把几何检查、仿真器、感知模块和 motion planner 的结果抽象成 Lean 可检查的 predicates / certificates，再与任务意图和安全规范结合。

## 为什么需要时序双层对齐

我们提出两个互补检查：

### 1. Semantic-Temporal Alignment

这一层检查 semantic macro-contract 是否仍然忠实于冻结的任务根、当前 task phase 和
residual obligations。它发生在第一次 prefix authorization 前，核心问题是：

> Given frozen mission `M`, active phase `q`, current abstract state `s_t`, and
> semantic contract `κ`, is `κ` a legal, non-blocking temporal refinement of `M`?

它防止的问题包括语义漂移、目标误解、抓错物体、错误 affordance、危险指令执行、无关动作插入，以及“为了完成任务而违反约束”的捷径。

### 2. Physical-Effect Alignment

这一层把 policy proposal、过滤后授权命令、实际执行回执和 realized trace 绑定到合同。
它分为执行前 prefix authorization、执行中逐 prefix conformance 和执行后 completion audit：

> Given contract `κ`, authorization `A`, execution receipt `R`, and realized trace
> `τ`, does every checked prefix conform to the authorized physical-effect contract?

它防止的问题包括物理执行偏差、动态障碍、人手干扰、碰撞风险、状态估计错误、抓取失败、误推动邻近物体，以及动作效果与 certificate 不一致。

这两层对应不同 failure modes：第一层处理“合同是否应被当前任务授权”，第二层处理“具体
命令和实际 trace 是否实现该合同”。只做 semantic refinement 会漏掉执行偏差；只做 physical
monitor 会允许任务无关但局部稳定的动作进入系统。

## 为什么 Lean 适合作为 proof checker

Lean 的角色不是生成动作，也不是求解轨迹。它适合作为小而可信的 proof checking core，原因是：

- Lean 可以表达 typed symbolic world model、任务意图、安全不变量、precondition、postcondition 和关系约束。
- Lean 的 kernel 检查证明项，trusted computing base 比把 LLM/VLM 当 verifier 更小。
- 外部模块可以自由使用神经模型、优化器、仿真器和 motion planner，只要输出可检查 certificate。
- 对离散抽象层面的 contract，Lean 可以给出可复核的拒绝或接受依据。
- Proof checking 与 action generation 解耦，使得系统可以替换 VLA、perception 或 planner，而保持相同 safety spec。

我们不声称 Lean 能直接解决机器人安全。Lean 不证明连续动力学的完整真实世界正确性，不保证感知一定正确，也不替代硬件级安全控制。本文主张的是更窄也更可执行的观点：在 VLA 执行链路中，安全关键的 symbolic contract 应由 trusted proof checker 检查，而不是完全依赖神经判断或隐式策略行为。

## 论文一句话

Safe VLA execution should be treated as contract-carrying temporal dual
alignment: every semantic macro-contract must refine an authenticated frozen
mission, and every authorized and realized action prefix must remain bound to
that contract and its checkable evidence.

## 主张边界

本项目是 prototype / research proposal。我们不声称：

- 完全解决真实机器人安全。
- 证明端到端 VLA policy 正确。
- 证明连续控制、接触动力学或视觉识别的物理真值。
- 取代 motion planning、collision checking、control barrier functions 或硬件急停。

我们主张：

- 对 VLA 的高层动作、对象语义、区域关系、安全不变量和状态转移效果，可以建立 machine-checkable contract。
- Lean 可以作为这些 contract 的 trusted checker。
- CTDA 把冻结任务 refinement 与 proposal/authorized/executed/observed evidence chain 组合成
  两类 machine-checkable alignment。
- 当前 Lean 中已经有 CTDA specification 与 checker theorem，Python reference runtime 已接入
  LIBERO；但在线 prefix 尚未调用 Lean CTDA evaluator，因此不能把当前结果写成完整 Lean
  online proof。
