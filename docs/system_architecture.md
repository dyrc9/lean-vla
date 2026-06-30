# 系统架构

## 总览

系统由 VLA policy、感知与状态抽象、动作抽象、Lean checker、执行监控和恢复机制组成。核心思想是把 VLA 的候选动作放在两个 formal gates 之间：

1. 执行前经过 Intent-Action checker。
2. 执行后经过 Action-Effect checker。

```text
Natural Language Instruction
        |
        v
Task Spec Compiler --------------+
        |                         |
        v                         |
   SafetySpec Σ                   |
        |                         |
        v                         |
Observation o_t ---> State Observer ---> WorldState s_t
        |                         |
        v                         |
      VLA Policy ---> Action Chunk a_t
                            |
                            v
              Symbolic Action Abstractor
                            |
                            v
              Intent-Action Lean Checker
                            |
              accept / reject / repair
                            |
                            v
              Monitored Execution
                            |
                            v
Observation o_{t+1} -> State Observer -> WorldState s_{t+1}
                            |
                            v
              Action-Effect Lean Checker
                            |
       accept / recover / safe stop / replan
```

## 从自然语言指令到 Lean task spec

输入 `I` 是自然语言，例如：

```text
"Pick up the mug by its handle and place it on the coaster without touching the knife."
```

Task Spec Compiler 负责生成：

- 目标对象：`mug`
- 目标部件：`mug.handle`
- 目标区域：`coaster.region`
- 禁止对象：`knife`
- 禁止接触关系：`Contacting(robot, knife)`
- 动作偏好：`Pick(mug, mug.handle)` before `Place(mug, coaster.region)`
- 完成条件：`InRegion(mug, coaster.region) ∧ Stable(mug)`

该 compiler 可以由 LLM、规则系统或人工标注辅助，但输出必须变成 Lean 可检查的 `TaskIntent` 和 `SafetySpec`。在 prototype 中，可以先使用模板化 parser 或 benchmark annotation，避免把自然语言解析本身作为主要贡献。

## 从 VLA action chunk 到 symbolic action abstraction

VLA 可能输出：

- end-effector delta actions
- waypoint sequence
- gripper command
- language-like skill command
- low-level primitive chunk

Symbolic Action Abstractor 将其映射到 `Action`：

```text
raw chunk:
  move gripper toward cup handle, close gripper

symbolic abstraction:
  Pick(object=cup, part=cup_handle)

predicted effect:
  Holding(robot, cup)
```

抽象器需要引用 perception 结果、planner metadata 和 VLA action intent。若无法可靠抽象，系统应返回 `unknown`，触发 re-observe 或 ask-for-clarification，而不是直接执行。

## Intent-Action Checker

Intent-Action checker 调用 Lean 检查：

```text
IntentAlign(I, s_t, a_t, Σ)
```

输入：

- `TaskIntent`
- `WorldState s_t`
- `Action a_t`
- pre-execution certificates
- `SafetySpec Σ`

输出：

- `accepted(theorem_ref)`
- `rejected(violation_report)`
- `unknown(missing_certificate)`

典型检查：

- 动作目标是否为 intent 中允许对象。
- 动作是否使用安全 affordance。
- 动作 precondition 是否满足。
- 禁止对象是否保持 untouched。
- 外部 motion planner 是否提供了足够 clearance certificate。
- 人手、禁区、障碍物约束是否覆盖 action chunk。

## Execution Monitor

Execution Monitor 在动作执行期间运行。它不替代 Lean，而是负责实时收集和触发：

- action chunk start / stop
- force threshold events
- emergency stop events
- human hand intrusion
- object slip
- unexpected contact
- tracking loss
- timeout

对于短 action chunk，可以在 chunk 结束后统一检查 EffectAlign。对于长动作或高风险任务，应在中间 checkpoint 执行 partial EffectAlign 或 invariant check。

## State Observer

State Observer 从 `o_t` 生成 `s_t`，从 `o_{t+1}` 生成 `s_{t+1}`。它整合：

- object detection / segmentation
- pose estimation
- part detection
- human hand tracking
- region occupancy
- contact event detection
- robot proprioception
- planner and controller logs

State Observer 还生成 certificate：

- object identity certificate
- pose-to-region certificate
- hand clearance certificate
- object displacement certificate
- contact event certificate
- state confidence certificate

Lean 只接受满足 schema 的 certificate；低置信度、过期或引用错误的 certificate 会导致 `unknown` 或 `rejected`。

## Action-Effect Checker

Action-Effect checker 调用 Lean 检查：

```text
EffectAlign(s_t, a_t, s_{t+1}, Σ)
```

输入：

- 执行前状态 `s_t`
- 已执行动作 `a_t`
- 执行后状态 `s_{t+1}`
- post-execution certificates
- `SafetySpec Σ`

典型检查：

- `Pick(obj)` 后是否 `Holding(robot, obj)`。
- `Place(obj, region)` 后是否 `InRegion(obj, region)` 且 `Stable(obj)`。
- 非目标对象是否保持 frame condition。
- 是否发生不允许接触。
- 人手是否始终远离危险区域。
- forbidden object 是否被移动。
- 若 action 声称避开障碍，执行日志中是否出现越界或碰撞事件。

## Reject / Repair / Safe Stop / Replan

### Reject

当 IntentAlign 明确失败时，系统拒绝动作。示例：

- 抓取了错误对象。
- 试图接触禁止对象。
- 使用危险部件。
- 缺少必需 precondition。

Reject 应产生可读原因，供 VLA 或上层 planner 修正。

### Repair

当动作接近合法但存在可修复错误时，系统尝试局部修正：

- 将 `Pick(knife, blade)` 修正为 `Pick(knife, handle)`。
- 将目标区域从 unsafe region 改为允许区域。
- 要求 planner 重新生成避障路径。
- 要求 VLA 重选对象 referent。

Repair 后必须重新通过 IntentAlign，不能直接绕过 Lean checker。

### Safe Stop

当执行中出现不确定或危险状态时，系统进入 safe stop：

- 人手突然进入 guarded region。
- 物体 tracking loss。
- force/torque 超过阈值。
- 发生未知接触。
- EffectAlign 返回严重 violation。

Safe stop 的目标是降低风险，而不是完成任务。它可以包括停止运动、释放或保持物体、撤退到安全 pose、等待人类确认。

### Replan

当动作失败但任务仍可安全继续时，系统 replan：

- 重新观察状态。
- 更新 `s_t`。
- 保持原始 `TaskIntent`。
- 要求 VLA 或 planner 生成新的 action chunk。
- 再次执行 IntentAlign。

Replan 不允许改变原始安全约束，除非有新的明确人类指令。

## 模块接口

### VLA Policy Interface

```text
Input:
  instruction I
  observation o_t
  execution history H_t
  optional rejection report R_{t-1}

Output:
  action chunk a_t
  optional natural-language rationale
  optional predicted effect e_t
```

VLA rationale 不能作为安全证明，只能辅助 action abstraction 或 debugging。

### Lean Checker Interface

```text
Input:
  check_type: IntentAlign | EffectAlign
  world_state_before
  action
  world_state_after optional
  safety_spec
  certificates

Output:
  ProofResult
```

### Runtime Policy

```text
if IntentAlign = accepted:
    execute under monitor
else if repairable:
    repair and re-check
else:
    reject / replan

if EffectAlign = accepted:
    continue
else if recoverable:
    recover and re-check
else:
    safe stop
```

## 安全边界

本架构把安全责任分层：

- VLA：提出任务相关动作。
- Perception：提供对象、部件、区域和状态估计。
- Planner / simulator：提供连续几何和动力学 certificate。
- Lean：检查 symbolic contract。
- Controller：执行低层动作并维护硬件约束。
- Monitor：检测运行时异常。
- Human / supervisor：处理无法自动恢复的不确定场景。

这种设计不会把所有安全责任压到 Lean 上。Lean 的价值是让每个 action chunk 的关键安全假设显式化、可检查、可复现。

