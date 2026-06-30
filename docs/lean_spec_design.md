# Lean 规格设计

## 设计目标

Lean 在本项目中是 trusted proof checker。它的职责是检查符号状态、任务意图、安全规范和外部 certificate 之间的逻辑关系，而不是生成动作、识别物体、规划轨迹或仿真连续动力学。

Lean 层应满足四个目标：

1. **Typed symbolic interface**：所有对象、区域、动作、关系和任务意图都有明确类型。
2. **Small trusted core**：安全判断最终落到 Lean kernel 可检查的定理或证明项。
3. **Certificate-friendly**：外部模块可以提交结构化 certificate，Lean 检查其是否足以推出目标 property。
4. **Runtime usable**：检查粒度面向 action chunk，而不是只用于离线验证完整任务。

## 核心数据结构

以下是规格设计草图，不是当前项目中的可运行 Lean 实现。

### Object

`Object` 表示环境中的实体。每个对象应包含稳定 ID、类别、属性和可选部件。

```lean
structure Object where
  id        : ObjectId
  category  : ObjectCategory
  parts     : List ObjectPart
  attrs     : ObjectAttributes
```

关键属性包括：

- 是否为任务目标。
- 是否危险，如 sharp、hot、fragile、toxic。
- 是否禁止移动。
- 是否可抓取、可打开、可倒入、可堆叠。
- 与用户指令中的 referent 是否绑定。

### ObjectPart

`ObjectPart` 表示物体的语义部件，例如 handle、blade、rim、lid、button。

```lean
structure ObjectPart where
  parent    : ObjectId
  partType  : PartType
  affordances : List Affordance
  isSafeContact : Bool
```

示例：

- `cup.handle` 支持 safe grasp。
- `knife.handle` 支持 safe grasp。
- `knife.blade` 通常不支持 grasp。
- `drawer.handle` 支持 pull。

### Region

`Region` 是离散或半离散空间区域。它可以来自桌面分区、禁区、人手附近区域、目标放置区域或 planner 生成的 symbolic cell。

```lean
structure Region where
  id          : RegionId
  kind        : RegionKind
  allowedFor  : List ObjectCategory
  forbiddenFor: List ObjectCategory
```

Region 不直接保存连续几何网格；连续边界、距离和碰撞计算由外部模块计算并生成 certificate。Lean 只检查 region-level predicates，例如 `Inside obj region`、`Disjoint r1 r2`、`Clear region`。

### Pose

`Pose` 在 Lean 中应采用抽象表示，而不是完整连续 SE(3) 证明对象。

```lean
structure Pose where
  frame       : FrameId
  region      : Option RegionId
  orientation : Option OrientationClass
```

Lean 可检查的 pose 信息包括：

- 对象属于哪个 region。
- 姿态是否满足稳定性类别，如 upright、tilted、unknown。
- 危险部件方向类别，如 blade_away_from_human。

连续 pose 数值可以留在 certificate payload 中，由外部模块证明其落在某个离散类别。

### Relation

`Relation` 描述对象、部件和区域之间的符号关系。

```lean
inductive Relation where
  | InRegion      : ObjectId -> RegionId -> Relation
  | On            : ObjectId -> ObjectId -> Relation
  | Inside        : ObjectId -> ObjectId -> Relation
  | Near          : ObjectId -> ObjectId -> Relation
  | FarFrom       : ObjectId -> ObjectId -> Relation
  | Holding       : AgentId -> ObjectId -> Relation
  | Contacting    : ObjectId -> ObjectId -> Relation
  | Occluding     : ObjectId -> ObjectId -> Relation
  | Open          : ObjectId -> Relation
  | Closed        : ObjectId -> Relation
  | PartFacing    : ObjectPartRef -> AgentOrRegion -> DirectionClass -> Relation
```

Relation 是 IntentAlign 和 EffectAlign 的主要逻辑对象。

### WorldState

`WorldState` 是 Lean 检查的当前抽象世界。

```lean
structure WorldState where
  objects      : List Object
  regions      : List Region
  relations    : List Relation
  robot        : RobotAbstractState
  humans       : List HumanAbstractState
  certs        : List CertificateRef
  time         : TimeIndex
```

WorldState 的可信度来自 state observer 与 certificate。Lean 可以检查 state well-formedness：

- Object ID 唯一。
- Relation 引用的对象存在。
- 同一对象不同时处于互斥状态，如 `Open drawer` 与 `Closed drawer`。
- Region relation 与 forbidden region 不冲突。

### Action

`Action` 是从 VLA action chunk 抽象出的符号动作。

```lean
inductive Action where
  | Pick       : ObjectId -> ObjectPartRef -> Action
  | Place      : ObjectId -> RegionId -> Action
  | MoveTo     : Pose -> Action
  | MoveThrough: PathId -> List RegionId -> Action
  | Open       : ObjectId -> ObjectPartRef -> Action
  | Close      : ObjectId -> ObjectPartRef -> Action
  | Push       : ObjectId -> DirectionClass -> Action
  | HandOver   : ObjectId -> HumanId -> Action
  | Wait       : Reason -> Action
  | Stop       : Reason -> Action
```

每个 Action 类型关联：

- required preconditions
- expected effects
- frame conditions
- safety-relevant certificates
- repair hints

### TaskIntent

`TaskIntent` 是从自然语言 `I` 编译出的规范对象。

```lean
structure TaskIntent where
  instructionId    : InstructionId
  goal             : GoalSpec
  targetObjects    : List ObjectId
  targetRegions    : List RegionId
  allowedActions   : List ActionSchema
  forbiddenObjects : List ObjectId
  forbiddenActions : List ActionSchema
  preferences      : List Preference
```

TaskIntent 需要保留初始人类意图，而不是每步重新由 VLA 自由解释。后续 replan 只能在 TaskIntent 允许的空间内修改动作序列。

### SafetySpec

`SafetySpec` 聚合任务和领域安全规则。

```lean
structure SafetySpec where
  intent          : TaskIntent
  invariants      : List Invariant
  preconditions   : Action -> List Predicate
  postconditions  : Action -> List Predicate
  frameConditions : Action -> List FrameCondition
  abortConditions : List Predicate
  certSchemas     : List CertificateSchema
```

示例 invariant：

- Protected objects must not be contacted.
- Human hand must remain outside guarded zone.
- Forbidden objects must not change region.
- Sharp parts must not face human during handover.
- Object placed on target region must be stable.

### ProofResult

Lean 检查返回结构化结果，供 runtime monitor 决策。

```lean
inductive ProofResult where
  | accepted : TheoremRef -> ProofResult
  | rejected : ViolationReport -> ProofResult
  | unknown  : MissingCertificate -> ProofResult
```

`accepted` 表示 proof checker 已验证 contract。`rejected` 表示发现违反规范。`unknown` 表示信息不足，例如缺少人手距离 certificate 或对象身份置信度过低。对于安全执行，`unknown` 应默认不执行或降级到 safe stop / re-observe。

## 适合 Lean 证明的内容

Lean 适合证明以下离散抽象层面的性质：

1. **对象引用一致性**：动作目标必须属于任务目标集合，禁止对象不能被操作。
2. **动作 schema 合法性**：`Pick` 必须作用于支持 grasp 的安全部件。
3. **precondition satisfaction**：当前 WorldState 中存在动作所需关系和 certificate。
4. **postcondition satisfaction**：后继 WorldState 中动作期望效果成立。
5. **frame condition**：非目标对象的关键关系未被改变。
6. **invariant preservation**：动作前后世界状态均满足安全不变量。
7. **任务意图持续约束**：replan 后动作仍在 TaskIntent 允许空间中。
8. **certificate composition**：多个外部 certificate 可以组合推出 Lean predicate。
9. **拒绝原因可解释性**：失败 proof obligation 对应可读 violation report。

示例 proposition：

```text
theorem pick_target_preserves_intent:
  IsTarget intent obj ->
  SafeGraspPart state obj part ->
  PreconditionHolds state (Pick obj part) spec ->
  IntentAlign intent state (Pick obj part) spec
```

这类定理不需要 Lean 知道图像像素，只需要 state observer 已把对象、部件、关系和 certificate 编码为抽象事实。

## 应由外部模块生成 certificate 的内容

以下内容不适合直接由 Lean 从原始数据证明，应由 perception / planner / simulator / runtime monitor 计算并提供 certificate：

1. **物体检测与身份绑定**：图像中的物体是否为指令中的 cup。
2. **部件检测**：handle、blade、rim 等部件位置。
3. **连续碰撞检查**：轨迹与网格、点云或包围体是否相交。
4. **最小距离计算**：robot-human、robot-object、object-object 的连续距离。
5. **可达性与逆解**：机器人是否能到达某 pose。
6. **抓取稳定性**：grasp quality、force closure、slip risk。
7. **动态仿真**：放置后是否可能倾倒、推动是否引发碰撞。
8. **状态估计置信度**：pose uncertainty、occlusion、tracking loss。
9. **低层控制安全**：torque limit、velocity limit、emergency stop status。

Lean 检查的是 certificate 的形状、引用对象、阈值、时刻、与 SafetySpec 的一致性。例如外部 planner 声称 `path p` 与 `human_guard_region` disjoint，Lean 检查该 certificate 是否对应当前 `s_t`、是否覆盖 action chunk 的时间区间、是否满足 spec 中要求的 clearance class。

## 不直接证明连续动力学

本项目必须明确避免过度 claim。Lean 层不直接证明：

- 真实世界接触动力学的完整正确性。
- 神经感知输出的真实性。
- 点云分割、pose estimation 或 object tracking 无误。
- Motion planner 的连续轨迹优化过程正确。
- 机器人硬件永远不会失效。

连续世界被外部模块压缩为离散事实和 certificates。Lean 证明的是：

> 如果这些抽象事实和 certificates 可信，则该 action chunk 满足声明的 symbolic safety contract。

这是一种 assumption-explicit safety architecture。它把系统依赖暴露出来，而不是隐藏在神经策略或黑箱 verifier 中。

## Certificate Schema 示例

### CollisionFreeCert

```text
CollisionFreeCert {
  path_id: p,
  time_interval: [t0, t1],
  robot_body: robot,
  avoided_regions: [human_guard, obstacle_region],
  min_clearance_class: above_required_threshold,
  state_ref: s_t
}
```

Lean obligation：

```text
CertMatchesState(cert, s_t)
∧ CoversAction(cert, a_t)
∧ ClearanceSatisfiesSpec(cert, Σ)
=> NoCollisionDuring(a_t, protected_regions)
```

### AffordanceCert

```text
AffordanceCert {
  object: knife,
  part: knife_handle,
  affordance: graspable,
  unsafe_parts_excluded: [knife_blade],
  confidence_class: high
}
```

Lean obligation：

```text
AffordanceCertValid(cert, s_t)
∧ part = knife_handle
∧ IsSafeContact(part)
=> AffordanceValid(s_t, Pick(knife, knife_handle), Σ)
```

### StateTransitionCert

```text
StateTransitionCert {
  before: s_t,
  action: a_t,
  after: s_{t+1},
  changed_objects: [cup],
  contact_events: [],
  observed_effects: [Holding(robot, cup)]
}
```

Lean obligation：

```text
ExpectedEffectHolds(s_t, a_t, s_{t+1}, Σ)
∧ FrameConditionHolds(s_t, a_t, s_{t+1}, Σ)
∧ InvariantsHoldAfterExecution(s_{t+1}, Σ)
=> EffectAlign(s_t, a_t, s_{t+1}, Σ)
```

## Proof Failure Taxonomy

Lean checker 应返回可分类的失败原因：

- `IntentTargetMismatch`：动作目标与任务目标不一致。
- `ForbiddenObjectTouched`：动作涉及禁止对象。
- `UnsafeAffordance`：使用危险部件或不支持 affordance。
- `MissingPrecondition`：缺少可达、可见、清空区域等前置条件。
- `InvariantViolation`：动作会破坏安全不变量。
- `MissingCertificate`：外部模块未提供必要证据。
- `PostconditionFailed`：动作后预期效果未成立。
- `FrameViolation`：非目标对象发生不允许变化。
- `UnexpectedHazard`：动作后引入新危险。
- `StateUncertain`：状态估计不足以安全决策。

这些失败类型直接驱动 reject / repair / replan 策略。

