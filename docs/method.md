# 方法定义

## 问题设定

我们考虑一个离散决策、连续执行的 VLA 机器人系统。VLA 在每个时间步或 action chunk 边界接收自然语言任务、视觉观测和历史上下文，输出候选动作。外部感知、规划和仿真模块将连续世界压缩成符号状态和 safety certificate。Lean 不直接处理原始图像、点云或轨迹优化，而是检查这些抽象和 certificate 是否满足形式化 specification。

## 符号

设：

- `I`：human instruction，自然语言任务指令。
- `o_t`：observation at time `t`，可包含 RGB-D、proprioception、force/torque、人手检测、物体检测等原始或中间观测。
- `s_t`：state abstraction，由 perception / state observer 从 `o_t` 生成的符号状态。
- `a_t`：VLA action chunk，VLA 在时间 `t` 提出的候选动作片段。
- `e_t`：predicted effect，动作 `a_t` 声称会产生的抽象效果或 postcondition。
- `s_{t+1}`：observed next state，执行 `a_t` 后由 state observer 生成的下一符号状态。
- `Σ`：safety specification，包含任务意图、对象类型、区域约束、安全不变量、动作 precondition / postcondition、abort condition 和 domain axioms。

更具体地：

```text
I          : NaturalLanguageInstruction
o_t        : RawObservation
s_t        : WorldState
a_t        : ActionChunk
e_t        : PredictedEffect
s_{t+1}    : WorldState
Σ          : SafetySpec
```

VLA 本身可以输出连续控制、末端执行器位姿序列、语言化动作、或低层 primitive 序列。本文将其统一称为 `a_t`，并要求系统提供一个 symbolic action abstraction：

```text
α(a_t, o_t) = â_t
```

其中 `â_t` 是 Lean 可检查的动作表示，例如：

- `Pick(object=cup, grasp_part=handle)`
- `Place(object=cup, region=coaster)`
- `MoveThrough(path_id=p, avoid={human_hand, knife})`
- `Open(object=drawer, handle=drawer_handle)`
- `Stop(reason=unsafe_precondition)`

为简洁起见，后文仍用 `a_t` 表示抽象后的候选动作。

## Safety Specification `Σ`

`Σ` 是运行时检查的规范集合，至少包含：

1. **Task intent**：由 `I` 编译得到的目标、允许对象、禁止对象、优先级和完成条件。
2. **World typing**：对象类别、部件、affordance、区域、危险属性。
3. **Invariants**：执行中必须始终保持的安全性质。
4. **Preconditions**：每个动作类型在当前状态下允许执行的条件。
5. **Postconditions**：每个动作执行后应满足的效果。
6. **Frame conditions**：除动作允许影响的对象外，其他关键对象应保持不变。
7. **Abort conditions**：一旦检测到必须中止、safe stop 或 replan 的条件。
8. **Certificate schemas**：外部模块提交 certificate 时需要满足的结构。

示例 invariant：

```text
NoCollision(robot, protected_objects)
HumanHandClearance(robot, min_distance)
DoNotMove(forbidden_objects)
OnlyManipulate(target_objects)
SharpPartAwayFromHuman(sharp_objects)
ObjectStableAfterPlace(target_objects)
```

## Intent-Action Alignment

Intent-Action Alignment 是执行前检查：

```text
IntentAlign(I, s_t, a_t, Σ) : Prop
```

直观含义：候选动作 `a_t` 在当前抽象状态 `s_t` 下，是对初始指令 `I` 的忠实、安全、相关的执行步骤。

我们将其展开为若干子条件：

```text
IntentAlign(I, s_t, a_t, Σ) :=
  TaskRelevant(I, s_t, a_t, Σ)
  ∧ TargetConsistent(I, s_t, a_t, Σ)
  ∧ AffordanceValid(s_t, a_t, Σ)
  ∧ SatisfiesPreconditions(s_t, a_t, Σ)
  ∧ PreservesInvariantsBeforeExecution(s_t, a_t, Σ)
  ∧ NotForbiddenByIntent(I, s_t, a_t, Σ)
  ∧ CertificateValid_Pre(s_t, a_t, Σ)
```

### TaskRelevant

`TaskRelevant` 检查动作是否推动任务目标，而不是无关探索或危险捷径。例如，指令要求把杯子放到杯垫上，抓取杯子或移动到杯垫附近是相关动作，抓取刀具通常不是相关动作。

### TargetConsistent

`TargetConsistent` 检查动作对象、目标区域和关系是否与任务意图一致。它防止抓错物体、把对象放到错误容器、把“near”误解为“inside”等问题。

### AffordanceValid

`AffordanceValid` 检查动作是否使用正确的物体部件和 affordance。例如抓杯子应优先抓 handle 或安全区域；抓刀应抓 handle 而不是 blade；打开抽屉应作用于 handle。

### SatisfiesPreconditions

`SatisfiesPreconditions` 检查动作类型的前置条件。例如 pick 要求目标可见、可达、未被人手占用、grasp part 可用；place 要求目标区域空闲、稳定、允许该对象。

### PreservesInvariantsBeforeExecution

该条件检查在执行动作计划或 action chunk 前，外部 certificate 是否证明动作不会违反已知 invariant，例如路径不穿过禁区、机器人与人手保持距离。

### NotForbiddenByIntent

有些指令带有显式或隐式禁止条件，例如“不要碰红色碗”“不要移动刀”“把杯子放远离笔记本”。该条件使禁止约束优先于普通任务目标。

### CertificateValid_Pre

外部模块可能提交：

- collision-free path certificate
- reachability certificate
- grasp stability certificate
- distance clearance certificate
- object identity confidence certificate
- affordance detection certificate

Lean 检查 certificate 的离散结构、引用对象和边界条件是否与 `s_t`、`a_t`、`Σ` 一致。连续几何计算由外部模块完成。

## Action-Effect Alignment

Action-Effect Alignment 是执行后检查：

```text
EffectAlign(s_t, a_t, s_{t+1}, Σ) : Prop
```

直观含义：执行动作 `a_t` 后，观察到的状态变化 `s_t -> s_{t+1}` 与动作承诺的效果一致，并且没有违反安全规范。

展开为：

```text
EffectAlign(s_t, a_t, s_{t+1}, Σ) :=
  ExpectedEffectHolds(s_t, a_t, s_{t+1}, Σ)
  ∧ FrameConditionHolds(s_t, a_t, s_{t+1}, Σ)
  ∧ InvariantsHoldAfterExecution(s_{t+1}, Σ)
  ∧ NoUnexpectedHazardIntroduced(s_t, a_t, s_{t+1}, Σ)
  ∧ CertificateValid_Post(s_t, a_t, s_{t+1}, Σ)
```

### ExpectedEffectHolds

检查动作声称的效果是否出现。例如：

- `Pick(cup)` 后 cup 应被 robot held。
- `Place(cup, coaster)` 后 cup 应位于 coaster region 且不再被 gripper held。
- `MoveTo(pregrasp_pose)` 后 gripper 应位于目标邻域。
- `Open(drawer)` 后 drawer relation 应从 closed 变为 open。

### FrameConditionHolds

只允许动作影响指定对象和允许的关系。若执行 `Pick(cup)` 后 knife 被移动，或者人手附近对象发生危险位移，应视为 violation。

### InvariantsHoldAfterExecution

后继状态必须继续满足安全不变量。例如没有碰撞、没有 forbidden object 被移动、人手仍在安全距离外、危险物体未朝向人。

### NoUnexpectedHazardIntroduced

捕捉“虽然 expected effect 成立，但引入了新危险”的情况。例如杯子成功放在目标区域，但压住了人手附近的物体；或放置后对象不稳定、可能倾倒。

### CertificateValid_Post

外部 observer / simulator 可以提交执行日志、接触事件摘要、最小距离、对象位移、状态估计置信度等 post-execution certificate。Lean 检查这些 certificate 是否足以推出 postcondition。

## 执行许可规则

一个动作只有同时通过两层检查才被系统视为安全执行的一部分：

```text
AllowExecute(I, s_t, a_t, Σ) :=
  IntentAlign(I, s_t, a_t, Σ)
```

执行后：

```text
AcceptTransition(s_t, a_t, s_{t+1}, Σ) :=
  EffectAlign(s_t, a_t, s_{t+1}, Σ)
```

完整 step-level rule：

```text
SafeStep(I, s_t, a_t, s_{t+1}, Σ) :=
  IntentAlign(I, s_t, a_t, Σ)
  ∧ Execute(a_t)
  ∧ EffectAlign(s_t, a_t, s_{t+1}, Σ)
```

如果 `IntentAlign` 不成立，动作不得执行，系统进入 reject / repair / replan。若 `IntentAlign` 成立但执行后 `EffectAlign` 不成立，系统进入 recovery / safe stop / re-observe / replan。

## Runtime Algorithm

```text
Input: instruction I, safety spec Σ, current observation o_t
Output: execute, reject, repair, safe_stop, or replan

1. s_t <- StateObserver(o_t)
2. a_t <- VLA(I, o_t, history)
3. â_t, e_t, cert_pre <- ActionAbstractor(a_t, s_t, Σ)
4. if not LeanCheck(IntentAlign(I, s_t, â_t, Σ), cert_pre):
       return RejectOrRepair(â_t)
5. execute monitored action chunk a_t
6. o_{t+1} <- Observe()
7. s_{t+1}, cert_post <- StateObserver(o_{t+1})
8. if not LeanCheck(EffectAlign(s_t, â_t, s_{t+1}, Σ), cert_post):
       return RecoverOrSafeStop(s_t, â_t, s_{t+1})
9. update history and continue
```

## 设计原则

1. **Lean checks contracts, not pixels.** 原始感知由外部模块处理，Lean 检查抽象状态和证据。
2. **Safety is stepwise and cumulative.** 每个 action chunk 都需要检查；episode-level success 不替代过程级安全。
3. **Intent is persistent.** 初始人类意图在整个执行过程中保持约束力，防止中途语义漂移。
4. **Effects are audited.** 机器人不能只承诺动作安全，还必须在执行后证明状态变化符合承诺。
5. **Rejection is a valid outcome.** 在危险或不确定条件下拒绝执行应被视为安全行为，而不是简单失败。

