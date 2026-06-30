# Related Work

## 位置概述

本项目位于 VLA 安全执行、LLM/VLM 机器人规划、形式化方法、proof-carrying planning 与运行时监控的交叉处。我们的 novelty 不是“第一个把 formal methods 用到机器人安全”，也不是“第一个检查机器人计划安全”。更准确地说，我们提出：

> 将 safe VLA execution 表述为双层 machine-checkable alignment：动作执行前必须对齐初始人类意图，动作执行后必须对齐其承诺的实际效果。

这一定位使我们与计划级验证、collision checking、LLM verifier、training-time safety alignment 和 proof-carrying plans 区分开。

## SENTINEL: multi-level formal safety evaluation

SENTINEL 提出面向 LLM-based embodied agents 的多层形式化安全评测框架，覆盖 semantic、plan 和 trajectory levels，并用 temporal logic 表达安全需求。它的重要启发是：机器人安全不应只靠启发式规则或 LLM 自我判断，而应将自然语言安全需求落到形式语义和可验证结构上。

与 SENTINEL 的区别：

- SENTINEL 更偏 evaluation framework，关注多层安全评估。
- 我们关注 VLA runtime execution，每个 action chunk 都经过执行前和执行后 checking。
- SENTINEL 的多层结构是 semantic / plan / trajectory；我们的核心结构是 intent-action / action-effect 两种 alignment relation。
- 我们使用 Lean 作为 proof checker，强调 proof-carrying contract 和 trusted checking boundary。

## SafeGate / Task Safety Contracts

SafeGate 与 Task Safety Contracts 关注 LLM-controlled robot systems 的 pre-execution safety gate 和运行时 contract。它们将自然语言任务转化为 invariants、guards 和 abort conditions，并可使用 SMT solver 执行约束检查。

与 SafeGate 的区别：

- SafeGate 重点是阻止 unsafe / defective commands 进入执行，并通过 task safety contracts 约束状态转移。
- 我们的入口不是只有 task command，而是 VLA 在闭环中不断生成的 action chunk。
- 我们显式区分 `IntentAlign` 和 `EffectAlign`：前者防止语义漂移和错误 affordance，后者审计实际执行效果。
- 我们选择 Lean proof checking，而不是把约束主要表达为 SMT 问题；Lean 更适合表达 rich typed symbolic domains、证明结构和可组合规格。

## SafePlan

SafePlan 将 formal logic 与 chain-of-thought reasoners 结合，用于提高 LLM-based robotic task planning 的安全性，检查 task prompts、plans 和 allocations 中的安全问题。

与 SafePlan 的区别：

- SafePlan 的核心对象是 LLM task planning 与 reasoning pipeline。
- 我们面向 VLA execution，其中动作直接来自视觉-语言-动作策略，可能是 action chunk 而非离散自然语言计划。
- SafePlan 使用 reasoner 辅助安全判断；我们把最终安全边界放在 Lean checker 上。
- 我们强调执行后效果检查，因为 VLA 的物理执行可能偏离计划。

## Plug in the Safety Chip

Plug in the Safety Chip 提出为 LLM-driven robot agents 加入基于 temporal constraints 的安全模块，能够编码 prohibited actions、解释 violation，并进行 unsafe action pruning。

与该工作的区别：

- Safety Chip 强调 LTL 约束和 action pruning。
- 我们将 pruning 扩展成双层 contract：动作能否执行，以及执行后状态转移是否可接受。
- 我们更关注 VLA 的语义-物理错配，例如抓错物体、错误 affordance、postcondition failure。
- 我们把 collision / planner / perception 的输出作为 certificate，由 Lean 检查其与任务规范的一致性。

## FEARL

FEARL (Foundation-Enabled Assured Robot Learning) 通过模块化架构把大模型 controller 与小型 safety module 分离，使形式化验证集中在低维 safety module 上，而不是验证完整 foundation model。

与 FEARL 的区别：

- FEARL 的重点是将可验证性放到小型 safety module，保留 foundation model 的表达能力。
- 我们不验证一个 learned safety policy，而是验证每个 VLA action chunk 的 symbolic contract。
- FEARL 更接近 policy architecture decomposition；我们更接近 runtime proof-carrying execution architecture。
- 二者互补：FEARL 的 safety module 可以作为 certificate 生成者之一，Lean checker 则检查其输出是否满足任务级 contract。

## Proof-Carrying Plans

Proof-Carrying Plans 将 AI plans 与证明结合，使用资源逻辑、Curry-Howard 风格和 proof-carrying structure 来验证计划的 pre/post conditions。它说明计划可以携带可检查证明，而不是只携带动作序列。

与 Proof-Carrying Plans 的区别：

- Proof-Carrying Plans 主要面向 classical planning / AI plans。
- 我们面向 VLA 的闭环 action chunks，动作可能来自神经策略且执行环境动态变化。
- 我们不仅要求 plan/action 携带 proof，还要求 execution result 被检查。
- 我们的 EffectAlign 是对 proof-carrying planning 的运行时扩展：证明不只在执行前成立，还要与观察到的状态转移一致。

## SayCan

SayCan 将语言模型的 high-level knowledge 与机器人 affordance value functions 结合，强调“do as I can, not as I say”。它通过可执行技能的 affordance 分数 grounding LLM 计划。

与 SayCan 的区别：

- SayCan 解决语言计划与机器人能力之间的 grounding。
- 我们解决 VLA 动作与安全规范、初始意图、实际效果之间的 formal alignment。
- SayCan 的 affordance score 是选择动作的依据；我们的 affordance condition 是可检查的 safety obligation。
- SayCan 不提供 machine-checked proof boundary；我们的 Lean checker 是 trusted runtime component。

## Inner Monologue

Inner Monologue 研究 LLM 在 embodied planning 中如何利用环境反馈、成功检测、场景描述和人类交互形成闭环语言推理。

与 Inner Monologue 的区别：

- Inner Monologue 强调语言反馈提升闭环规划。
- 我们强调形式化反馈约束执行安全。
- Inner Monologue 的反馈可帮助重新规划；我们的 EffectAlign 会把执行后偏差转化为 formal violation report。
- 两者可结合：violation report 可以成为 VLA / LLM planner 的 structured feedback。

## Code as Policies

Code as Policies 使用 LLM 生成机器人 policy code，通过程序结构组合 perception APIs、控制 primitives 和空间几何计算。

与 Code as Policies 的区别：

- Code as Policies 把语言转化为可执行代码。
- 我们把 VLA 动作转化为可检查 contract。
- 生成的代码或 policy 可以成为动作生成器，但仍需要 IntentAlign 与 EffectAlign 检查其安全性。
- 我们不依赖代码生成模型本身作为安全证明来源。

## ProgPrompt

ProgPrompt 用程序化 prompt 结构生成 situated robot task plans，使 LLM 输出更受 available actions、objects 和 executable programs 约束。

与 ProgPrompt 的区别：

- ProgPrompt 通过 prompt 结构改善计划生成。
- 我们通过 Lean proof checking 验证 action chunk 是否满足 task intent 和 safety specification。
- ProgPrompt 的约束主要影响生成分布；我们的约束是运行时 gate。
- 对于 VLA，动作往往不是显式程序文本，因此我们需要 symbolic action abstraction。

## 其他相关方向

### Collision checking and motion planning

运动规划与 collision checking 是机器人安全的基础。它们可以保证特定轨迹在给定几何模型下避开障碍物。然而它们通常不表达高层任务意图、语义危险、对象部件 affordance、禁止对象和 postcondition frame conditions。因此我们将其作为 certificate generator，而不是完整 verifier。

### Runtime monitoring

运行时监控可以检测人手进入、接触异常、力阈值、tracking loss 等事件。我们的 Execution Monitor 与 Lean checker 互补：monitor 提供事件和证据，Lean 检查这些事件是否导致 contract violation。

### Safety benchmarks for VLA

LIBERO-Safety、HazardArena 和 ForesightSafety-VLA 等 benchmark 说明 VLA 安全不能用单一 task success 捕捉。它们推动了对 physical safety、semantic safety、process-level risk 和 failure taxonomy 的关注。本项目使用 LIBERO-Safety 作为主要评测，并把 benchmark 中的安全约束转化为 Lean-checkable specification。

## Novelty Summary

已有工作已经探索了形式化评测、SMT/LTL safety gate、proof-carrying planning、LLM-based robot planning、affordance grounding 和 runtime monitoring。我们的新意在于组合方式和问题表述：

1. **Dual alignment formulation**：safe VLA execution 被定义为 `IntentAlign ∧ EffectAlign`，分别约束动作生成前的语义忠实性和动作执行后的物理/语义效果。
2. **Machine-checkable runtime contracts**：每个 action chunk 需要携带或引用 Lean 可检查的 contract，而不是只在 episode 结束后评测。
3. **Persistent human intent**：初始指令被编译成持续约束，不允许 VLA 在闭环中语义漂移。
4. **Effect auditing**：执行后的状态转移必须与动作承诺匹配，防止物理偏差和动态干扰被忽略。
5. **Lean as trusted proof checker**：神经模型、planner、simulator 和 perception 可以生成候选与 certificate，但最终 contract checking 由 Lean 完成。

## References

- SENTINEL: A Multi-Level Formal Framework for Safety Evaluation of LLM-based Embodied Agents. https://arxiv.org/abs/2510.12985
- LIBERO-Safety: A Comprehensive Benchmark for Physical and Semantic Safety in Vision-Language-Action Models. https://arxiv.org/abs/2606.23686
- Pre-Execution Safety Gate & Task Safety Contracts for LLM-Controlled Robot Systems. https://arxiv.org/abs/2604.05427
- SafePlan: Leveraging Formal Logic and Chain-of-Thought Reasoning for Enhanced Safety in LLM-based Robotic Task Planning. https://arxiv.org/abs/2503.06892
- Plug in the Safety Chip: Enforcing Constraints for LLM-driven Robot Agents. https://arxiv.org/abs/2309.09919
- FEARL / Verifiable Foundation Models for Robot Safety. https://arxiv.org/abs/2606.23754
- Proof-Carrying Plans: a Resource Logic for AI Planning. https://arxiv.org/abs/2008.04165
- SayCan / Do As I Can, Not As I Say: Grounding Language in Robotic Affordances. https://arxiv.org/abs/2204.01691
- Inner Monologue: Embodied Reasoning through Planning with Language Models. https://arxiv.org/abs/2207.05608
- Code as Policies: Language Model Programs for Embodied Control. https://arxiv.org/abs/2209.07753
- ProgPrompt: Generating Situated Robot Task Plans using Large Language Models. https://arxiv.org/abs/2209.11302

