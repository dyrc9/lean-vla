# ProofAlign 2.0：Lean 双层对齐调研与升级方案

日期：2026-07-10

> 阅读说明：第一至八节记录从 legacy Boolean prototype 推导 CTDA 的调研、差距和目标设计，
> 因而其中“当前实现”的表述对应升级前基线。当天已经完成的落地结果以第九节
> “2026-07-10 实现状态与剩余边界”为准；简明权威口径见
> [`method.md`](method.md) 和 [`docs/README.md`](README.md)。

## 结论摘要

当前 ProofAlign 已经证明了一个重要工程事实：VLA、LIBERO-Safety、符号动作抽象、
执行前 intent check、执行后 effect check 和真实 Lean 调用可以在同一个 online
rollout 中工作。但从方法论和形式保证看，当前系统仍然是：

```text
untrusted observation / heuristic abstraction
  -> concrete Boolean expression
  -> Lean checks expression = true by decide
```

它尚不能称为完整的 runtime safety proof。Lean 当前证明的是给定离散输入上的
Boolean predicate 为真，而不是证明真实 VLA action chunk 的所有连续执行前缀安全，
也没有证明感知、动作抽象、动力学模型和 certificate producer 的输出为真。

广泛调研后的核心判断是：仅用“执行前 Intent-Action Alignment + 执行后
Action-Effect Alignment”描述创新已经不够。RoboSafe 已经提出前向风险预测和后向
轨迹反思；SafeManip 已经使用 LTLf/DFA 做 manipulation trace monitoring；CaM 已经
把执行中与完成时约束编译为实时 monitor；VASO 已经提出 formal/planner-facing
双接口 skill contract；语义约束结合 CBF safety filter 也已有直接先例。

建议将方法升级并定位为：

> **ProofAlign 2.0: Contract-Carrying Temporal Dual Alignment (CTDA)**，即面向
> VLA action chunks 的 proof-carrying dual runtime assurance。第一层证明候选
> macro-action 是认证且冻结的任务合同的合法时序 refinement；第二层将 proposal、
> filter 后授权命令、实际执行回执和拼接 trace 逐一绑定，在执行前授权、执行中逐前缀
> 监控、执行后审计是否实现合同，并与连续动力学 safety filter、可恢复域和已验证
> fallback 做 assume-guarantee 组合。

升级后仍然只有两类核心 alignment：

1. `SemanticTemporalRefines`：intent / task automaton 到 macro-contract 的 refinement。
2. `PhysicalEffectConforms`：raw action prefixes / realized trace 到 macro-contract 的
   conformance；实现上必须拆成执行前、执行中和执行后三个 staged judgments。

Trusted Spec Root、evidence provenance、uncertainty 和 runtime assurance supervisor 是
两层共享的基础设施，不额外包装成新的 alignment layer。

## 一、相关工作全景

### 1. VLA 安全训练与安全基准

| 工作 | 核心贡献 | 对 ProofAlign 的启示 | 仍未解决的问题 |
|---|---|---|---|
| SafeVLA, NeurIPS 2025 | 用 CMDP、风险 elicitation 和 constrained learning 优化 safety-performance trade-off | proof failures 可反哺安全 post-training；安全必须独立于 task success | 给出策略分布上的安全改善，不证明某个具体 chunk 安全 |
| LIBERO-Safety, ECCV 2026 | 同时评测物理和语义安全，提供 19,664 条严格无碰撞演示及五类 L0-L2 场景 | 当前项目最直接的主 benchmark；必须同时处理 semantic misalignment、collision-free incompletion 和 temporal overflow | 主要是数据与评测，不提供 runtime enforcement |
| SafeVLA-Bench, 2026 | 用 task-aware STL 做 post-hoc trajectory scoring，报告 SBU 和 VSI | 应直接采用 Succ-But-Unsafe、Violation Severity Index 和 task-aware applicability | 事后评分无法阻止第一次危险事件，也不检查 instruction authorization |
| SafeManip, 2026 | 10 个 LTLf 模板覆盖 8 类 manipulation temporal safety，并编译为 DFA monitor | Effect 层需要跨 chunk 的持久 monitor state 和事件顺序 | 偏 evaluation；依赖可信 symbolic trace，没有 theorem-prover certificate |
| HazardArena, 2026 | safe/unsafe twin scenes 暴露相同动作在不同语义上下文中的风险，并提出 Safety Option Layer | 非常适合测试 spec compiler 和 semantic grounding | VLM judge / semantic attribute 不是可机检 proof，缺少实际效果证明 |
| ForesightSafety-VLA, 2026 | Safe-Core/Safe-Lang/Safe-Vis 13 类 taxonomy，报告 CC 和 risk exposure time | 实验必须分解语言、视觉、结构与控制风险，并报告 intervention lead time | 诊断为主，不提供形式化 online guard |
| SafeManip / OopsieVerse 类 damage-aware benchmark | 将碰撞、力、温度、液体和累计 damage 区分开 | Effect 层不能继续只有一个 Boolean collision bit | simulator privileged signal 到真实传感器 certificate 仍有 gap |

这组工作的共同结论是：高 task success 不等于 safe execution。ProofAlign 的目标不能
只是提高 rejection rate，而应优化 `safe success`、减少 unsafe success、缩短 risk
exposure，并明确 intervention 带来的 verifier tax。

### 2. VLA 攻击与红队

| 工作 | 攻击面 | 对 CTDA 的直接要求 |
|---|---|---|
| SABER, 2026 | 对 instruction 做有预算的字符、token 和 prompt 攻击，目标覆盖 task failure、action inflation、constraint violation | 任务合同不能从每次收到的当前 prompt 重新生成；必须绑定 immutable task root、SpecHash、progress variant 和 time/action budget |
| Adversarial Attacks on Robotic VLA Models, 2025 | 单次文本 jailbreak 可以长期控制 VLA action space | 初始授权 intent 与送给 policy 的文本必须分离；后续 chunk 必须持续 refine 原始合同 |
| EDPA, 2025 | 可物理放置的视觉 patch 扰乱 visual-language latent alignment | 语言 parser 通过不代表视觉 grounding 正确；object binding 必须有 provenance 和 uncertainty |
| RedVLA, 2026 | 保持语言不变，在关键交互位置加入风险物体 | 只防 instruction 不够；动态 obstacle set 和 state certificate 必须逐步刷新 |
| AttackVLA / action-chain attacks | backdoor 或表面无害的局部动作组合成长时危险轨迹 | 需要跨 chunk event ordering、forbidden cumulative effects 和 resource/liveness properties |

这组工作说明，当前“解析 instruction 后就把它当可信 TaskIntent”的做法不够。特别是
SABER 场景中，一个 action 可以完全对齐被攻击后的 prompt，却不对齐用户最初授权的
任务。因此升级后的 intent 层必须从 **可信任务根** 出发，而不是从 policy 当前看到的
字符串出发。

### 3. 高层语义 guard、formal planning 和执行 monitor

| 工作 | 已覆盖能力 | 与 CTDA 的边界 |
|---|---|---|
| Plug in the Safety Chip, ICRA 2024 | NL-to-LTL、安全约束解释、unsafe action pruning | 主要针对高层离散 agent action；没有低层 VLA chunk 与实际 effect proof |
| SafePlan, 2025 | prompt、plan、pre/postcondition 的 formal-logic/COT 检查 | reasoner 本身仍参与安全判断，且重点是 planning pipeline |
| SENTINEL, 2025/2026 | semantic、plan、trajectory 三层 temporal-logic safety evaluation | 更偏 formal evaluation；不是针对 VLA raw action chunks 的 proof-carrying runtime |
| SafeGate / Task Safety Contracts, 2026 | pre-execution gate；合同包含 invariants、guards、abort conditions；Z3 enforcement | 与本项目很接近，但面向 LLM command/code，未形成低层 action-effect 双向 proof chain |
| RoboGuard, 2025 | root-of-trust LLM 把规则环境化成 temporal logic，再做 control synthesis | spec grounding 和 preference conflict resolution 很值得吸收，但 root LLM 不能直接成为本项目 TCB |
| RoboSafe, ES-Reasoning @ ICLR 2026 Oral | Forward Predictive Reasoning + Backward Reflective Reasoning，生成 executable safety predicates | 已覆盖“前向/后向”叙事；CTDA 必须靠 immutable spec、Lean witness、raw chunk binding 和连续 safety guarantee 区分 |
| Code-as-Monitor, CVPR 2025 | VLM 生成 spatio-temporal constraint code，做 proactive/reactive failure detection | 不能再声称首次执行中/完成时双阶段 monitor；区别应是 generated code 不作为 trusted proof |
| VASO, 2026 | formal/planner-facing 双接口 skill contract，model checking 和 counterexample-guided skill evolution | 不能声称首次 formal skill contract；CTDA 的重点应是 actual VLA trace、proof-carrying evidence 和 compositional runtime theorem |
| Proof-Carrying Plans, 2020 | 用资源逻辑和 Curry-Howard 验证 classical plans 的 pre/postconditions | 证明“计划携带可检查 proof”可行；仍需处理闭环感知、连续执行偏差和动态 replan |

### 4. 运行时保障、shielding 与连续控制

| 工作 | 核心机制 | 对 CTDA 的启示 |
|---|---|---|
| Simplex / Neural Simplex | advanced controller + verified baseline controller + decision module；在离开 recoverable region 之前切换 | `safe_stop` 不能只是标签；必须有真实 fallback controller、recoverable set 和 switching condition |
| SOTER, DSN 2019 | 组合式 runtime assurance modules，显式建模 sampling period、reachability 和 reverse switching | supervisor 和时序假设应进入合同，多个 safety modules 要有组合定理 |
| Safe RL via Shielding, AAAI 2018 | 从 temporal logic spec 合成 reactive shield，给安全动作集或修正不安全动作 | 不是所有失败都应直接 reject；可在可证明范围内做 minimally invasive correction |
| ModelPlex, FMSD 2016 | 从已证明的 hybrid model 自动合成正确 runtime monitor，验证真实执行是否仍符合模型 | 需要 assumption/conformance monitor；模型假设失效时原 proof 不能继续沿用 |
| FEARL, 2026 | 大 foundation controller + 小型、低维、可验证 safety module | 不验证完整 VLA 是正确方向；CTDA 可把低层 safety module 作为 certificate / shield producer |
| CBF-QP | 用 forward-invariant safe set 对 nominal action 做实时最小投影 | 适合 raw-step 高频局部过滤，但依赖模型且可能 infeasible / deadlock |
| Predictive Safety Filter | 候选动作只有在存在 N-step 安全 backup plan 并进入 terminal safe set 时才执行 | chunk authorization 应包含 terminal recoverability，而不是只看当前 state |
| HJ reachability / reachable tubes | 对扰动下的未来状态集合做 conservative safety analysis | 可为 chunk 提供 per-prefix tube witness，但高维机械臂存在扩展性问题 |
| Semantically Safe Robot Manipulation, RA-L 2025 | 将 LLM 推断的 semantic unsafe conditions 与 geometric constraints 一起转为 CBF safety filter | 已证明语义约束可以落到连续 shield；CTDA 的差异应是任务时序 refinement、效果闭环与 proof chain |
| PACS, 2025/2026 | 按生成 action chunk 的 intended path 做 path-consistent braking，并用 set reachability 验证 | 对 diffusion/flow action chunk 很合适，可减少普通 reactive filter 造成的 OOD shift |

连续 safety filter 和 Lean 不应互相替代。建议的职责分工是：

```text
Lean / temporal checker:
  authorization, object/part/region semantics, task phase,
  event ordering, postconditions, frame conditions, evidence coverage

CBF / predictive filter / reachability:
  continuous collision, joint/workspace limits, human clearance,
  bounded disturbances, prefix safety, terminal recoverability
```

下面的 close-work matrix 用 `✓` 表示论文明确提供，`△` 表示相邻或部分能力，`—` 表示
不是该工作的主要机制。它不是简单的“谁更强”排名；不同工作解决的层级不同。

| 工作 | 认证且冻结的任务根 | 跨 policy proposal 合同 | 最终控制命令绑定 | every-prefix online check | consumer-checkable witness | actual-effect audit | verified RTA fallback | 显式 uncertainty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SafeGate | △ | — | — | — | △ Z3 condition | — | △ abort | — |
| RoboSafe | — | △ | △ trajectory | △ | — | ✓ reflection | △ recovery | — |
| Code-as-Monitor | — | ✓ monitor state | △ visual trajectory | ✓ | — | ✓ | △ reactive action | △ |
| VASO | △ formal spec | ✓ skill contract | — | △ model checking | ✓ formal artifact | △ skill outcome | △ | — |
| ModelPlex / VeriPhy | ✓ verified model | — | ✓ controller/plant | ✓ | ✓ monitor/proof | ✓ model conformance | ✓ | △ bounded disturbance |
| **CTDA target** | ✓ authority + digest | ✓ semantic contract | ✓ proposal/filtered/executed | ✓ | ✓ Lean-checkable | ✓ | ✓ | ✓ interval + assumptions |

因此 novelty 不属于表中任何一个单独组件，而是它们在 **VLA manipulation action chunk**
上的特定组合、端到端对象绑定，以及在明确假设下连接两层的组合定理。

### 5. 失败检测与不确定性

| 工作 | 可提供证据 | 不应被当作什么 |
|---|---|---|
| AHA / Guardian | open-set failure category、执行解释、subtask verification | 不能作为 sound allow proof |
| Model-Based Runtime Monitoring | imagined futures、OOD、future failure probability | 不能证明 dynamics prediction 正确 |
| KnowNo | conformal uncertainty、ask-for-help policy | statistical coverage 不等于 deterministic physical safety |
| SAFE / FIPER | VLA hidden feature、chunk entropy、failure score、conformal threshold | learned risk score 不能单独产生 certified allow；适合触发 unknown/replan |
| Pre-VLA | 候选 chunk 的 safety confidence 与 critic advantage，低质量候选 resampling | learned verifier 不是 trusted checker，但 resampling 机制值得复用 |

因此 learned monitor 应遵守单向权限原则：

```text
learned evidence may downgrade:
  authorized candidate -> unknown / replan / stop

learned critic / risk score alone must not upgrade:
  rejected / unknown -> certified_allow
```

这个原则不排斥 learned perception。object identity、pose 或 contact classifier 可以提供带
producer provenance、校准误差和显式 observation assumptions 的 interval evidence；由它得到的
结论必须标成 assumption-qualified / statistical authorization，而不是无条件 deterministic
physical proof。simulator oracle 与真实传感器证据也必须分别报告。

### 6. Action chunk、skill abstraction 与时序抽象

ACT、Diffusion Policy、OpenVLA-OFT 和 pi0/pi0.5 都会输出固定或 receding-horizon action
chunks，但 policy chunk 只是控制 proposal，不天然具有 `Pick`、`Place`、`Handover` 或
`Pour` 的完整语义。Options framework 的 initiation/termination、RT-H 的中间 motion
language、ReKep 的 path/subgoal constraints 都说明时间抽象很重要，但它们也没有自动
提供 execution invariant 和 effect proof。

CTDA 必须显式区分：

```text
policy action chunk:
  one model call returned u[t:t+H]

semantic macro-contract:
  a stateful skill contract that may span several policy calls and ends only at
  a semantic milestone, an explicit violation, or a deadline
```

这意味着不能在每个 policy call 后重置 semantic monitor。一个 `Pick` contract 可以跨越
approach、contact、close、grasp、lift 和 stable-hold；每次只执行风险允许的 prefix，
但 contract phase 和 evidence history 持续存在。

## 二、当前实现的形式化差距

### 1. Boolean evaluation 不是组合式安全定理

当前 runtime 生成：

```lean
example : ConcreteExpression = true := by decide
```

这能够确保具体 Boolean predicate 的求值经过 Lean，但没有一个通用定理证明：

```text
initial invariant
∧ pre-authorized prefix contract
∧ valid execution witness
∧ monitored assumptions
  => every observed prefix is safe
     ∧ post-state preserves the mission invariant
```

升级后必须为 checker 建立 reflection/soundness theorem，而不是只为每条输入重新编译
一个 `Bool = true` 例子。

### 2. Python 与 Lean 不是单一语义源

当前 Python intent checker 对 place task 允许 `Pick`、`MoveTo`、`Place` 作为合法 refinement，
而 Lean `IntentAligned` 的 `Action.pick` 只接受 verb 为 `pick`。这类 divergence 会造成：

- Python 认为合法、Lean 认为非法的 false block；
- 修改一侧后另一侧没有同步；
- 无法准确解释到底是哪套 semantics 进入论文结果。

升级后 Python 只负责 observation/evidence adapter 和执行控制；authoritative semantics 应
只有一份，并由 Lean checker 或从 Lean specification 生成的共享 evaluator 实现。

### 3. 当前动作和世界模型过窄

当前 Lean action 只有 `pick/place/moveTo/avoid/stop/reject`；WorldState 主要只有
`holding/inRegion/collision/two distances`。缺少：

- task phase 和跨 chunk obligations；
- open/close/pour/handover/push/wait；
- contact type、force、velocity、joint/workspace、orientation、stability；
- time、deadline、retry budget 和 progress measure；
- state uncertainty、sensor freshness 和 contradictory observations；
- backup controller 和 recoverable set。

此外，`Stop` / `Reject` 在 intent 中恒通过，`MoveTo` 的 effect 基本恒真。它们最多是
`SafetyAdmissible`，不能等同于 `MissionRefines` 或任务进展。

### 4. 当前 certificate 只是结构化声明，不是 witness

现有 certificate 主要检查 producer 自报的：

```text
status == valid
confidence >= threshold
value >= threshold
```

但没有绑定：

- 具体 state、action、spec 和 dynamics model；
- 有效时间、控制周期和 horizon；
- producer version、assumptions 和 provenance；
- reachable tube、barrier margin、input bound、terminal recoverability；
- raw action chunk 与 symbolic contract 的对应关系。

真正的 proof-carrying certificate 必须携带 consumer 可以复核的 witness，而不是 producer
声称“valid”。外部 solver 不必被信任，但其 witness 必须可检查。

### 5. 执行后发现 collision 已经太晚

当前 chunk runtime 会在 `env.step` 后读取 collision/cost，再执行 effect audit。这对可恢复
postcondition failure 是合理的，但对不可逆 contact/human hazard 不够。升级后的 Effect
层需要包含：

1. 执行前 reachable/predictive check；
2. 每个 raw-step prefix 的 barrier/tube/assumption monitor；
3. chunk 完成后的 effect/frame/temporal audit。

这三项概念上属于同一个 `PhysicalEffectConforms` alignment，不新增第三层；但实现和定理中
必须拆成执行前 authorization、执行中 conformance、执行后 completion 三个 judgments，避免
用尚未发生的 trace 做执行前判定。

### 6. 当前数值和 fallback 不足以支持 safety claim

- Python float 通过 `round(value * 100)` 转为 Lean `Nat`，边界附近可能向安全方向舍入。
- Lean 不可用时 mock mode 目前可以 fail-open。
- `safe_stop` 是 decision label，没有证明哪一个低层 controller 会把系统带到安全状态。
- 没有最坏检查延迟、采样周期、reverse-switch hysteresis 和 backup availability。

这些是升级 P0，优先级高于扩展更多自然语言动词。

## 三、ProofAlign 2.0 方法设计

### 1. Trusted Spec Root

每个 episode 首先从受认证来源生成并冻结一个 `MissionSpec`：

```text
authenticated user / benchmark task authority
signed or versioned task ID + BDDL goal
versioned environment manifest / object registry
non-overridable suite safety templates
explicit human authorization scope
  -> typed MissionSpec
  -> SpecHash
```

LLM 可以用于候选 slot extraction 或歧义解释，但不能输出任意 Lean code，也不能直接决定
最终规格。最终合同由 typed schemas、固定模板、ontology resolution 和 deterministic
well-formedness checks 组装。

`SpecHash` 只提供完整性，不能自己证明规格正确。因此 threat model 必须另含 authority policy：

1. benchmark 中由 task manifest / BDDL 标识任务根；部署中由认证用户或调度器签发任务根；
2. suite hard-safety template 优先级高于任务语言，任务语言不能覆盖它；
3. policy prompt 是非可信输入，与 authorized instruction 分开存储；
4. instruction、BDDL、object registry 或 template 冲突时返回 `inconsistent`，不让 LLM
   猜一个优先级；
5. authority、source、version、signature / attestation 和 digest 全部进入 evidence chain。

建议结构：

```lean
structure MissionSpec where
  specId            : SpecId
  authority         : AuthorityEnvelope
  instructionDigest : Digest
  goal              : GoalFormula
  hardInvariants    : List TraceFormula
  softPreferences   : List Preference
  taskAutomaton     : TaskAutomaton
  objectRoles       : List ObjectBinding
  defaultMustPreserve : List ObjectId
  deadlines         : List Deadline
  resourceBudgets   : List ResourceBudget
  requiredEvidence  : List EvidenceRequirement
  timeBase          : TimeBase
```

关键点：送给 VLA policy 的语言可以被攻击或重写，但 checker 永远对齐已经通过 authority
policy 的冻结 `SpecHash`；冻结一个未经认证的恶意 prompt 不构成安全根。

### 2. Stateful semantic macro-contract

不再把 place task 压成单一 `verb = place`。例如 `Place(obj, region)` 应编译为 task automaton：

```text
q0 locate/approach
  -> q1 pregrasp
  -> q2 holding
  -> q3 transport
  -> q4 inside/on target
  -> q5 released-and-stable
```

在 q0-q1，`MoveTo(obj)` 是合法 refinement；q1-q2，`Pick(obj,safe_part)` 合法；q2-q4，
transport 合法；q4-q5，release/place 合法。这样可以消除当前 exact-verb matching 带来的
大量 false rejection，同时阻止不相关动作和顺序错误。

每个 semantic skill 使用一个可跨 policy calls 持续存在的 contract：

```lean
structure SemanticSkillContract where
  contractId        : ContractId
  specId            : SpecId
  phaseBefore       : PhaseId
  expectedNextPhase : PhaseId
  skill             : Skill
  target            : Option ObjectId
  part              : Option PartId
  region            : Option RegionId
  deadline          : Deadline
  guards            : List StateFormula
  guarantee         : List TraceFormula
  mayModify         : List ObjectId
  mustPreserve      : List ObjectId
  fallbackClass     : FallbackClass
  semanticPreRequirements : List EvidenceRequirement
  physicalPreRequirements : List EvidenceRequirement
  runtimeRequirements     : List EvidenceRequirement
  postRequirements        : List EvidenceRequirement
```

一次 policy proposal、过滤后的授权命令和执行回执是三个不同对象，不能塞进持久的
semantic contract：

```lean
structure ActionProposalBinding where
  contractId       : ContractId
  proposalIndex    : Nat
  proposalDigest   : Digest
  proposedHorizon  : Duration

structure PrefixAuthorization where
  contractId              : ContractId
  specDigest              : Digest
  stateDigest             : Digest
  monitorStateDigest      : Digest
  proposalIndex           : Nat
  proposalDigest           : Digest
  authorizedCommandDigest  : Digest
  filterPolicyDigest       : Digest
  dynamicsModelDigest      : Digest
  timeBaseDigest           : Digest
  tubeDigest               : Digest
  maxAuthorizedDuration    : Duration
  fallbackId               : FallbackId
  issuedAt                 : Timestamp
  validUntil               : Timestamp

structure ExecutionReceipt where
  authorizationDigest : Digest
  authorizedCommandDigest : Digest
  executedCommandDigest   : Digest
  actuatorEvidence        : EvidenceRef

structure PrefixCandidate where
  proposal    : ActionProposalBinding
  authorization : PrefixAuthorization
  tube        : ReachableTube
  preEvidence : PrefixPreEvidenceBundle

structure PrefixExecutionRecord where
  candidate           : PrefixCandidate
  receipt             : ExecutionReceipt
  plantTrace          : PlantTrace
  eventTrace          : SymbolicEventTrace
  runtimeEvidence     : PrefixRuntimeEvidenceBundle
  abstractionEvidence : TraceAbstractionEvidence

structure ContractExecution where
  contractId : ContractId
  prefixes   : List PrefixExecutionRecord
```

若 CBF / predictive filter 修改 nominal action，reachable tube 必须覆盖最终授权、实际下发的
command，而不是原始 VLA proposal。proof chain 明确为
`proposal -> filter/version -> authorized command -> executed command -> plant trace -> symbolic event trace`。
若 filter 每个控制周期根据新观测重算，则每步产生新的 `PrefixAuthorization`，但
`SemanticSkillContract` 和 monitor state 继续保持。

dispatch 前只需构造 `PrefixCandidate` 并检查 authorization 的 spec/state/monitor-state/timebase
digest、有效期和单调递增的 proposal index，防止旧授权在新状态或新 phase 被 replay。
`receipt`、realized traces 和 runtime evidence 只在执行后追加成 `PrefixExecutionRecord`，
不能在执行前用占位值伪造。

如果 VLA 不原生输出 skill label，abstractor 必须返回一个候选集合和 grounding uncertainty，
而不是把 heuristic 猜测伪装成唯一事实。

同时，semantic contract 不应与一次 policy inference 一一绑定：

```text
one SemanticSkillContract
  -> policy proposal 0 -> execute safe prefix
  -> policy proposal 1 -> execute safe prefix
  -> ...
  -> semantic milestone / violation / timeout
```

这正面解决当前 runtime 虽有 `step_chunk`，但真实 trace 经常退化成 1 到数步小 chunk 的
问题。

### 3. Layer 1：Semantic-Temporal Refinement

第一层回答：

> 这个 macro-contract 是否是当前任务 phase 下、对不可变 MissionSpec 的合法且在任务自动机上非阻塞的 refinement？

形式上：

```text
SemanticTemporalRefines(M, q, s, kappa, E_pre) :=
  WellFormed(kappa)
  ∧ BoundTo(kappa, M.specId, q)
  ∧ TransitionAllowed(M.automaton, q, kappa, kappa.expectedNextPhase)
  ∧ TargetAndAffordanceConsistent(M, s, kappa)
  ∧ GuardsHold(s, kappa)
  ∧ SameSymbolicAlphabetAndTimeBase(M, kappa)
  ∧ Nonempty(ContractTraceLanguage(M, kappa))
  ∧ ContractTraceLanguage(M, kappa)
      ⊆ PermittedResidualLanguage(M, q)
  ∧ (∀ trace,
       trace ∈ ContractTraceLanguage(M, kappa) ->
       Advances(trace, ResidualMission(M, q)))
  ∧ EvidenceCovers(E_pre, kappa.semanticPreRequirements)
  ∧ AutomatonNonblocking(M.automaton, kappa.expectedNextPhase)
```

最后一项只是任务自动机层面的 `HasMissionContinuation`：防止合同把任务推进到无合法
后继的 phase。物理可恢复性属于第二层，不能在第一层用同名条件偷渡 dynamics claim。

`ContractTraceLanguage(M, kappa)` 在 `M` 的 symbolic-event alphabet 和 `TimeBase` 上同时解释
guarantee、`mayModify`、`mustPreserve` 和 hard invariants；
要求它非空且是 residual mission 允许语言的子集，避免用不可满足或过弱 guarantee 做 vacuous
refinement。这里验证的是“若合同被真实 trace 实现，它必然推进 residual mission”，以及
当前 guard 是否由证据支持；第一层不预测保证一定发生。因果可达性、prefix safety 和
terminal physical recoverability 全部属于第二层。

### 4. Layer 2：Predictive Physical-Effect Conformance

第二层回答：

> 候选 raw chunk 的未来状态集合及实际执行 trace，是否逐前缀保持安全并实现 macro-contract？

概念上它是一个 alignment，但形式化为三个不能互换的 staged judgments：

```text
Pre-execution:
  reachable tube / CBF / predictive-filter witness

During execution:
  every-prefix invariant and assumption conformance

Post-execution:
  expected effect, frame, temporal order, progress and stability
```

执行前只可证明候选 prefix 的条件安全性：

```text
PrefixPreCertified(M, s0, kappa, monitorState, candidate) :=
  AuthorizationFreshAndMonotonic(M, s0, monitorState, candidate.authorization)
  ∧ BoundTo(candidate.proposal, kappa.contractId)
  ∧ ActivePhaseGuardsDeadlineHold(M, s0, kappa, monitorState)
  ∧ ProposalAdmissibleForContract(candidate.proposal, kappa,
                                  monitorState, candidate.preEvidence.binding)
  ∧ AuthorizationDerivedFrom(candidate.authorization, candidate.proposal)
  ∧ FilterPreservesContractEnvelope(candidate.authorization,
                                    candidate.proposal, kappa,
                                    candidate.preEvidence.filter)
  ∧ TubeBinds(candidate.tube,
              candidate.authorization.authorizedCommandDigest,
              candidate.authorization.dynamicsModelDigest)
  ∧ TubeCoversAllAuthorizedPrefixes(candidate.tube,
                                    candidate.authorization.maxAuthorizedDuration)
  ∧ EveryPrefixPreservesHardInvariant(M, candidate.tube)
  ∧ AllPermittedCutStatesRecoverable(
       candidate.tube, candidate.authorization.fallbackId,
       candidate.preEvidence.worstCaseSwitchLatency)
  ∧ EvidenceCovers(candidate.preEvidence,
                    kappa.physicalPreRequirements)

ObservedPrefixEvidenceValid(M, kappa, record) :=
  ReceiptBinds(record.receipt, record.candidate.authorization)
  ∧ ActuationReceiptWithinAuthorizedError(record.receipt,
                         record.runtimeEvidence.actuationBound)
  ∧ PlantTraceEvidenceWithinTube(record.plantTrace,
                                 record.candidate.tube,
                                 record.runtimeEvidence.observer)
  ∧ TraceAbstractionEvidenceValid(
       M.timeBase, record.plantTrace, record.eventTrace,
       record.abstractionEvidence)
  ∧ ObserverEvidenceSatisfiesContract(record.runtimeEvidence.observer)
  ∧ TimingReceiptValid(record.runtimeEvidence.timing)
  ∧ ModelAssumptionEvidenceValid(record.runtimeEvidence.modelAssumptions)
  ∧ SwitchReceiptValidIfTriggered(record.runtimeEvidence.switchReceipt)
  ∧ EvidenceCovers(record.runtimeEvidence,
                    kappa.runtimeRequirements)

CompletedTraceConforms(M, s0, q0, kappa, eventTrace, s1, E_post) :=
  TemporalGuaranteeHolds(kappa.guarantee, eventTrace, s1)
  ∧ FrameConditionHolds(kappa.mayModify, kappa.mustPreserve,
                          s0, eventTrace, s1)
  ∧ (∃ q1,
       q1 = MonitorDerivedPhase(M.automaton, q0, eventTrace, s1)
       ∧ q1 = kappa.expectedNextPhase
       ∧ Progresses(M.automaton, q0, q1))
  ∧ EvidenceCovers(E_post, kappa.postRequirements)

PhysicalEffectConforms(M, s0, q0, kappa, execution, s1, E_post) :=
  execution.prefixes ≠ []
  ∧ (∀ record ∈ execution.prefixes,
       PrefixPreCertified(M, StateBefore(record), kappa,
                          MonitorBefore(record), record.candidate))
  ∧ (∀ record ∈ execution.prefixes,
       ObservedPrefixEvidenceValid(M, kappa, record))
  ∧ PlantAndEventTraceChainEvidenceValid(execution.prefixes)
  ∧ CompletedTraceConforms(
       M, s0, q0, kappa,
       Concat(execution.prefixes.map PrefixExecutionRecord.eventTrace),
       s1, E_post)
```

`expectedNextPhase` 是合同声明，实际 `q1` 只能由 monitor 和 automaton transition function
从观察 trace 推出；不能把 binder 预填的 phase 当作已经取得的任务进展。执行前只允许依据
`PrefixPreCertified` 授权，完整 `PhysicalEffectConforms` 只能在对应 trace 完成后成立。

一个合同可以包含任意多条 `PrefixExecutionRecord`；每次授权都重新检查 active phase、guard、
deadline、proposal-to-contract admissibility 和 filter 是否保留 contract envelope。这样不能靠
给任意 raw controls 贴一个合法 `contractId` 冒充语义对齐。`AllPermittedCutStatesRecoverable`
覆盖 event boundary、uncertainty cutoff 和 emergency switch 等允许中止点；
`SwitchReceiptValidIfTriggered` 是条件命题，不假设每条 prefix 都真的发生切换。

连续 `PlantTrace` 保存 timestamped command/state interval，供 tube、barrier 和 dynamics
assumption 检查；`SymbolicEventTrace` 保存 `Holding/Release/InRegion/...` 等原子，供 LTLf / DSL
monitor 使用。二者不能共用一个含混的 `RawTrace` 类型，必须由带 provenance 的
`TraceAbstractionEvidenceValid` 连接，并使用同一个 `TimeBase`。

`ObservedPrefixEvidenceValid` 只表示 Lean 可复核的 receipt/evidence 满足合同，不直接证明
camera observation 等于真实 plant state。observer soundness、plant 被 tube 覆盖以及真实
actuator/timing assumptions、plant-to-event abstraction soundness 只作为后面的 meta-level
theorem hypotheses 出现。

CBF-QP 适合每个 raw step 的高频局部修正；predictive filter / reachable tube 适合 chunk
级 horizon 和 terminal recoverability。建议组合使用，而不是二选一。

### 5. Temporal trace logic

Lean 中应提供一个有限 trace DSL，而不是继续只比较 pre/post state：

```lean
inductive TraceFormula where
  | atom             : Atom -> TraceFormula
  | not              : TraceFormula -> TraceFormula
  | and              : TraceFormula -> TraceFormula -> TraceFormula
  | implies          : TraceFormula -> TraceFormula -> TraceFormula
  | always           : TraceFormula -> TraceFormula
  | eventuallyWithin : Duration -> TraceFormula -> TraceFormula
  | until            : TraceFormula -> TraceFormula -> TraceFormula
  | sequence         : List TraceFormula -> TraceFormula
  | stableFor        : Duration -> TraceFormula -> TraceFormula
  | precededBy       : TraceFormula -> TraceFormula -> TraceFormula
```

示例：

```text
Always(NoBadContact)
Always(HumanClearance >= margin)
EventuallyWithin(2.0 seconds, Holding(target))
Holding(target) Until InRegion(target, destination)
PrecededBy(Release(target), InRegion(target, destination))
StableFor(0.5 seconds, InRegion(target, destination))
Always(Unchanged(nonTarget))
EventuallyWithin(taskBudget, GoalReached)
```

`Duration` 必须携带单位；`TimeBase` 固定 monotonic clock、control period、最大 sampling jitter
和 monitor / switch latency。不能让裸 `Nat = 8` 同时可能表示 raw step、policy call 或秒。
若实际 jitter 超出合同界限，返回 assumption violation 并切换 fallback，而不是继续沿用 deadline
proof。

monitor state 必须跨 policy chunks 持久化，否则 action-chain attack 和跨 chunk contamination
不会被检测到。partial-trace semantics 应明确复用 LTL3 / RV-LTL 的有限前缀思想和 robust
online STL interval semantics；`safePending` 是工程 verdict 名称，不主张为新的逻辑语义。

### 6. Partial-trace verdict，而不是 Boolean

静态 refinement / authorization 与时序 monitor 不能复用一个 verdict type：

```lean
inductive StaticCheckResult where
  | proven       : WitnessRef -> StaticCheckResult
  | refuted      : List Counterexample -> StaticCheckResult
  | unknown      : List MissingEvidence -> StaticCheckResult
  | inconsistent : List EvidenceConflict -> StaticCheckResult

inductive MonitorVerdict where
  | complete     : WitnessRef -> MonitorVerdict
  | violated     : List Violation -> MonitorVerdict
  | safePending  : MonitorState -> MonitorVerdict
  | unknown      : List MissingEvidence -> MonitorVerdict
  | inconsistent : List EvidenceConflict -> MonitorVerdict
```

映射到 runtime policy：

| Verdict | 执行策略 |
|---|---|
| complete | 当前 contract 已有完整 witness，允许推进 task automaton |
| violated | 执行前 reject/repair；执行中切 fallback；执行后 replan 或 safe recovery |
| safePending | 当前 prefix 未违反 safety，但 future/deadline obligation 尚未完成；继续受监控执行 |
| unknown | 不把缺信息误报为 unsafe；reobserve、clarify、resample 或 ask human |
| inconsistent | 隔离冲突 evidence source，并进入保守 hold/fallback |

执行前的 `SemanticTemporalRefines` / `PrefixPreCertified`，以及对已经观察到的 receipt / raw
trace evidence 做结构和数值复核，都使用 `StaticCheckResult`；跨 prefix 的 contract progress
monitor 使用 `MonitorVerdict`。因此 evidence bundle 可以是 `.proven`，同时整个 contract
仍然是 `.safePending`；后者只说明当前 evidence 下尚无 violation、仍有未决义务，不是对
真实 plant 的无条件安全证明。这比当前 `passed: Bool` 更适合处理 partial observability，
也避免把未完成 future obligation 错写成静态“已证明”。

### 7. Robust interval semantics

距离、速度、力、位姿和 perception uncertainty 不应过早压成 Boolean。每个连续 atom 返回
一个 outward-rounded robustness interval：

```text
rho_p(t) = [lower, upper]

lower > 0  -> definitely satisfied
upper < 0  -> definitely violated
otherwise  -> unknown
```

`always/eventually/until` 的 min/max semantics 在 interval 上传播；future window 尚未结束时
返回 `safePending`。Conformal calibration 可以用来构造 observation interval，但它提供的
是统计 coverage，不是 deterministic Lean guarantee。

### 8. Proof-carrying evidence

每份 evidence 至少绑定：

```text
contract_id
authorization_digest
authority_digest
state_digest
monitor_state_digest
monotonic_proposal_index
proposal_digest
authorized_command_digest
executed_command_digest
plant_trace_digest
symbolic_event_trace_digest
trace_abstraction_digest
spec_digest
model_digest
filter_policy_digest + time_base_digest
producer_id + producer_version
valid_from + valid_until
time_base + control_period + horizon + worst_case_latency
assumptions
uncertainty_set
witness_payload
```

关键 witness 类型：

- object grounding / identity binding；
- action-to-contract binding；
- exact rational interval state；
- per-prefix barrier lower bounds；
- swept volume / reachable tube；
- input and disturbance bounds；
- terminal recoverability and fallback membership；
- plant trace、symbolic event trace 和 abstraction provenance；
- frame-condition changed-object set。

数值应使用 exact rational、fixed point 和 outward-rounded interval；不能用普通 Float
round-to-nearest 后声称 sound threshold check。

### 9. Verified runtime supervisor

运行时结构采用 Simplex/RTA 原则：

```text
Advanced controller: VLA policy
Safety filters: CBF / PACS / predictive filter
Trusted checker: Lean temporal/refinement/evidence checker
Baseline controller: hold / brake / retreat / task-specific recovery
Decision module: switching + hysteresis + deadline enforcement
```

`safe_stop` 不能被假设为总是安全。例如机器人正拿着热液体时，立即松开和原地保持的
风险不同。每个 fallback 本身需要 guard、effect 和 safe-set membership proof。

### 10. Lean soundness theorem

Lean 的核心不再是孤立 Boolean，而应有 checker reflection theorem：

```lean
theorem checkSemantic_sound
  (h : checkSemantic req = .proven witness) :
  SemanticTemporalRefines req.mission req.phase req.state req.contract req.evidence := ...

theorem checkPrefixPre_sound
  (h : checkPrefixPre req = .proven witness) :
  PrefixPreCertified req.mission req.before req.contract
                     req.monitorState req.candidate := ...

theorem checkObservedEvidence_sound
  (h : checkObservedEvidence req = .proven witness) :
  ObservedPrefixEvidenceValid req.mission req.contract req.record := ...

theorem monitor_pending_sound
  (h : monitorStep req = .safePending st) :
  CurrentPrefixSafeUnderCheckedEvidence req
  ∧ PendingObligations st
  ∧ (MayContinue st ->
       AuthorizationStillFresh req ∧ NextCommandPreCertified req) := ...

theorem monitor_complete_sound
  (h : monitorStep req = .complete witness) :
  CompletedTraceConforms req.mission req.before req.phase req.contract
                         req.eventTrace req.after req.evidence := ...

theorem authorized_execution_preserves_global_invariant
  (h0 : GlobalInvariant mission initialState)
  (hplant : PlantCoveredByCertifiedTubes execution)
  (hobs : ObserverRelationSound execution)
  (habstract : TraceAbstractionSound execution)
  (hact : ActuatorReceiptsFaithful execution)
  (hmodel : RecordedModelAssumptionsHoldOnPlant execution)
  (htime : SamplingAndSwitchBoundsHold execution)
  (hbase : BaselinePreservesInvariant execution)
  (hswitch : SwitchBeforeRecoverabilityBoundary execution)
  (hchain : StateContinuousAndSpecImmutable execution)
  (hw : EveryDispatchedPrefixHasStagedWitnesses execution) :
  EveryObservedPrefixSatisfies mission.hardInvariants execution := ...
```

术语必须固定：`authorized` 是执行前通过 `PrefixPreCertified`、允许下发；`certified` 是
对应执行 trace 已通过 execution/post checks。只有后者是 retrospective complete witness，
不能拿它解释 prevention。全局 prevention theorem 需要上面列出的 plant over-approximation、
observer relation、采样与最坏延迟、fallback invariant、及时切换、相邻状态连续性和 spec
immutability，以及 plant-to-event abstraction soundness 假设，不能只从“每个 chunk 有证书”
推出。

外部 perception/dynamics certificate 的真值仍然是条件假设，但假设必须被显式记录并由
conformance monitor 持续检查。论文 claim 应写成：

> 在绑定的 grounding、uncertainty、plant/model 和 timing assumptions 持续成立，且
> baseline controller 与切换条件满足所列 obligation 时，每个 authorized raw prefix
> 保持所声明的 physical invariants；completed trace 另行证明 semantic-temporal effect。

## 四、运行时算法

```text
Input:
  authenticated immutable MissionSpec M and SpecHash
  task-automaton phase q
  observation o_t

1. Verify authority, source versions and cross-source consistency, then freeze M.
2. State observer returns an interval-valued state and evidence provenance.
3. VLA proposes nominal action chunk u[0:H] and proposalDigest.
4. Only when no contract is active, or the previous one is complete, the binder creates a new
   SemanticSkillContract. Otherwise it reuses the active contract and persistent monitor state.
5. For a new contract, Layer 1 checks SemanticTemporalRefines with StaticCheckResult.
6. If refuted: bounded repair/resample, then reject if budget exhausted.
7. If unknown/inconsistent: reobserve / clarify / ask human / conservative hold; never fail-open.
8. Physical filter transforms the nominal proposal into candidate authorized commands and
   produces a tube, per-prefix bounds and fallback witness.
9. Verify PrefixPreCertified over the final authorized-command digest, not the nominal proposal.
10. Dispatch only that PrefixCandidate; append executed-command and actuator receipt to a
    PrefixExecutionRecord.
11. At every raw step:
      update PlantTrace, derive SymbolicEventTrace with abstraction provenance, and update monitor;
      check ObservedPrefixEvidenceValid and obtain MonitorVerdict;
      if command binding fails or monitor is violated/inconsistent, switch to verified fallback.
      safePending may continue only while authorization remains fresh and the next command is
      separately PrefixPreCertified.
12. At semantic boundary, check CompletedTraceConforms on all concatenated prefix traces.
13. Derive the actual next phase from trace; advance only after completion is proven.
14. Persist proposal/auth/execution, plant/event trace abstraction chain, failure core,
    intervention and recovery result.
```

这一流程可以总结为 `Predict -> Monitor -> Attest -> Recover`，但核心 formal method 仍是
两种 alignment relation。

### Contract-aware adaptive prefix

一次真正执行的 raw prefix 长度不应只由 policy 固定 chunk size 决定：

```text
execute_h = min(
  policy_proposed_horizon,
  next_contract_deadline,
  predicted_phase_or_event_boundary,
  first_prefix_whose_robustness_lower_bound <= risk_margin,
  uncertainty_or_entropy_budget
)
```

free-space approach 且 margin 大时可以执行较长 prefix；contact、release、handover 或人手
进入时缩短到 1 到数步；phase transition 后强制重观测。monitor state 不因 prefix 结束而
重置。

## 五、与当前代码的迁移关系

### P0：先修形式可信度

1. Lean unavailable / compile failure 时 fail-closed，移除 safety path 的 mock pass。
2. 统一 Python/Lean intent/effect semantics，避免两套规则漂移。
3. 将 `SafeAdmissible`、`MissionRefines`、`TaskProgresses` 分开。
4. 移除 float 到 Nat 的 round-to-nearest safety threshold；改 exact fixed point / interval。
5. 默认 runtime 使用 fail-closed authorization path；mandatory evidence 不得用空 bundle。
6. 给 authority、request、spec、state、proposal、authorized/executed command、trace、filter 和
   model 加 digest、source 和 version。
7. 在 dispatch path 中强制 proposal-to-contract admissibility、filter-envelope preservation、
   authorization freshness 和 monotonic index；不能只检查 `contractId` 相等。

### P1：时序任务合同

1. 新增 `MissionSpec`、`TaskAutomaton`、`Phase`、`SemanticSkillContract`、
   `ActionProposalBinding`、`PrefixAuthorization`、`ExecutionReceipt`、
   `PrefixCandidate`、`PrefixExecutionRecord` 和 `ContractExecution`。
2. 为 LIBERO-Safety 五个 suites 编写 deterministic typed templates。
3. 首先覆盖 `approach/pick/transport/place/release/stop/reject`。
4. 加跨 chunk LTLf monitor state、deadline、retry budget 和 progress variant。
5. 分离 timestamped `PlantTrace` 与 `SymbolicEventTrace`；扩展 event atoms：contact type、
   grasp/release、object motion、region、stability、force/damage，并验证 abstraction provenance。
6. 将 fixed `max_chunk_steps` 改为 contract-risk-aware adaptive prefix，同时保留 hard cap。
7. active contract 未 complete 前禁止重新创建合同；新 proposal 追加到同一 execution record。

### P2：physical shield 与 fallback

1. LIBERO 第一版先做 simulator / kinematic swept-volume authorization，给出明确的条件保证。
2. 对 action chunk 增加 N-step backup，并证明所有允许 cutoff / switch states 可恢复，而不只
   检查名义授权终点。
3. 定义真实 baseline controller：hold、brake、retreat、task-aware recovery。
4. 在线监控 state 是否留在 certified tube，并记录 min barrier/tube margin。
5. 明确该阶段只给 simulator/kinematic conditional guarantee，不夸大真实动力学。
6. 只有在低层接口能提供 Jacobian、signed-distance gradient、control bounds、disturbance
   model 和足够控制频率后，再加入 discrete-time CBF-QP；它不是简单 wrapper 接线。

### P3：Lean compositional theorem 与 runtime 性能

1. 为静态 checker 建立 `check = proven -> proposition`，为 monitor 同时建立
   `safePending -> current-prefix evidence safety + pending obligations` 和
   `complete -> completed-trace proposition` reflection theorem。
2. 先分别证明三段 physical judgments，再在显式 plant/observer/timing/fallback assumptions
   下证明 authorized prefix sequence 的条件 invariant preservation。
3. 将通用 checker 预编译为持久进程或可验证 evaluator，避免每次生成临时 Lean 文件。
4. 保留 kernel-audit 模式；如果在线使用 compiled checker，明确额外 codegen/runtime TCB。
5. 用 content digest cache，但 cache key 必须包含 spec/model/version。

### P4：有限 primitive 的更强连续保证

1. 对少量 `Move/Pick/Place/Hold/Retreat` primitive 离线生成 reachability/tube templates。
2. 评估 KeYmaera X、CORA、Flow* 或专用 interval checker。
3. 在线只实例化模板并检查 assumptions/witness。
4. 不尝试验证整个大 VLA 网络。

## 六、实验方案

### 1. 主要方法对照

必须使用相同 policy checkpoint、task、init state、policy seed、camera 和 horizon：

1. VLA only。
2. Collision / CBF safety filter only。
3. 当前 flat Boolean Intent only。
4. 当前 flat Boolean Effect only。
5. 当前 Dual Lean。
6. Temporal semantic layer only。
7. Predictive physical-effect layer only。
8. CTDA without proposal/filtered/executed command binding。
9. CTDA without uncertainty handling。
10. CTDA without verified fallback。
11. Full CTDA。

相邻强 baseline 应至少包括可复现的 VLM/LLM judge 或 Safety Option Layer，以及一个
learned failure detector，避免只和弱 collision checker 比较。

### 2. Benchmark 与攻击矩阵

- LIBERO-Safety：主 closed-loop physical + semantic benchmark。
- SafeManip：跨 chunk event ordering 和 LTLf properties。
- SafeVLA-Bench instrumentation：SBU、VSI 和 task-aware STL。
- HazardArena：safe/unsafe semantic twins。
- SABER：instruction perturbation、action inflation 和 constraint violation。
- EDPA / RedVLA 类攻击：visual grounding 和动态场景风险。
- state abstraction noise：object ID、pose interval、missed contact、stale evidence。
- dynamics mismatch：friction、delay、gripper failure、moving human/obstacle。
- proof-chain attacks：stale authorization replay、proposal index rollback、filter output tampering、
  authorized/executed command mismatch、monitor-state reset、plant/event trace abstraction tampering。

### 3. 指标

任务与安全：

- task success；
- strict safe success；
- Succ-But-Unsafe；
- cumulative cost / damage；
- risk exposure time；
- Violation Severity Index；
- per-property temporal violation rate。

guard quality：

- unsafe chunk blocking recall；
- false intervention / false rejection；
- unknown and inconsistent rates；
- intervention lead time；
- correction norm；
- fallback success and recovery success；
- bounded-retry exhaustion；
- action inflation / progress timeout detection。

formal/runtime：

- certificate coverage；
- proposal-to-contract binding coverage、stale/replay rejection 和 command-chain mismatch recall；
- trace-abstraction coverage、event extraction precision/recall 和 provenance mismatch recall；
- assumption-monitor violation rate；
- proof mode and TCB mode；
- p50/p95/p99 intent, physical-filter, monitor and effect latency；
- policy throughput and verifier tax；
- min barrier / reachable-tube margin；
- average semantic chunk length and checks per raw step。
- policy chunk length、executed prefix length 和 semantic contract duration 分别统计。

### 4. 两种互补实验协议

Offline paired replay：冻结相同 action traces，使用 oracle/privileged labels 测 checker 的
unsafe recall、false block、temporal property coverage，隔离 policy closed-loop distribution
shift。

Online intervention：在相同 init state 和 policy seed 下运行各方法，测实际 task success、
risk reduction、recovery 和 verifier tax。两类结果不能混在一个表中。

## 七、论文主张与边界

### 可主张

1. 将认证且冻结的任务合同到 VLA macro-action，以及最终授权/实际执行 raw prefix 与
   realized trace 到 macro-contract，统一成两类 Lean-checkable alignment。
2. 每个授权 prefix 携带绑定 spec/state/proposal/filtered command/model/fallback 的执行前
   witness；执行回执和 completed trace 再分别产生 conformance witness，而不是依赖
   self-reported certificate status。
3. 将 semantic temporal proof、continuous safety filter、assumption monitor 和 verified
   fallback 组合成一个 action-chunk runtime assurance architecture。
4. 在显式 plant over-approximation、observer、timing、fallback 和 switching assumptions
   下，给出 authorized raw-prefix sequence 保持 invariants 的条件组合定理，并单独证明
   completed trace 的任务效果，保证边界和 TCB 清晰可审计。

### 不应主张

1. 不应声称首次做执行前/执行后 robot safety check；RoboSafe、SafeGate 等已有强先例。
2. 不应声称首次 temporal manipulation monitor；SafeManip 和 CaM 已覆盖。
3. 不应声称首次 formal skill contract；VASO 已非常接近。
4. 不应声称 Lean 证明像素、object identity、真实接触动力学或 hardware 永不失效。
5. 不应把 learned confidence、LLM-generated rule 或 solver 自报 status 称作 proof。
6. 不应把 collision 发生后的正确 `safe_stop` 解释为 prevention success。

### 建议的一句话定位

> ProofAlign 2.0 provides proof-carrying dual runtime assurance for VLA action
> chunks: each persistent semantic macro-contract must refine an authenticated,
> immutable temporal mission specification; every filtered, authorized raw prefix
> and its realized trace must satisfy staged conformance checks under monitored
> assumptions and a verified recovery envelope.

## 八、主要一手参考

### VLA safety / benchmark / attack

- SafeVLA: https://arxiv.org/abs/2503.03480
- LIBERO-Safety: https://arxiv.org/abs/2606.23686
- SafeVLA-Bench: https://arxiv.org/abs/2606.00773
- SafeManip: https://arxiv.org/abs/2605.12386
- HazardArena: https://arxiv.org/abs/2604.12447
- ForesightSafety-VLA: https://arxiv.org/abs/2606.27079
- OopsieVerse: https://arxiv.org/abs/2606.31993
- SABER: https://arxiv.org/abs/2603.24935
- RedVLA: https://arxiv.org/abs/2604.22591
- AttackVLA: https://arxiv.org/abs/2511.12149
- Adversarial Attacks on Robotic VLA Models: https://arxiv.org/abs/2506.03350
- EDPA: https://arxiv.org/abs/2510.13237
- Pre-VLA: https://arxiv.org/abs/2605.22446
- ASIMOV / Robot Constitutions: https://arxiv.org/abs/2503.08663

### Semantic / temporal guard and failure monitoring

- Plug in the Safety Chip: https://arxiv.org/abs/2309.09919
- SafePlan: https://arxiv.org/abs/2503.06892
- SENTINEL: https://arxiv.org/abs/2510.12985
- SafeGate / Task Safety Contracts: https://arxiv.org/abs/2604.05427
- RoboGuard: https://arxiv.org/abs/2503.07885
- RoboSafe: https://openreview.net/forum?id=wyKCkQ2GyO
- Code-as-Monitor: https://arxiv.org/abs/2412.04455
- VASO: https://arxiv.org/abs/2606.05395
- AHA: https://arxiv.org/abs/2410.00371
- Guardian: https://arxiv.org/abs/2512.01946
- KnowNo: https://arxiv.org/abs/2307.01928
- Model-Based Runtime Monitoring: https://arxiv.org/abs/2310.17552
- SAFE: https://arxiv.org/abs/2506.09937
- FIPER: https://arxiv.org/abs/2510.09459
- ACT: https://arxiv.org/abs/2304.13705
- Diffusion Policy: https://arxiv.org/abs/2303.04137
- RT-H: https://arxiv.org/abs/2403.01823
- Lang2LTL: https://arxiv.org/abs/2302.11649
- AutoTAMP: https://arxiv.org/abs/2306.06531
- ReKep: https://proceedings.mlr.press/v270/huang25g.html
- Options framework: https://doi.org/10.1016/S0004-3702(99)00052-1
- LTL3 finite-prefix semantics: https://doi.org/10.1145/2000799.2000800
- RV-LTL finite-prefix semantics: https://doi.org/10.1093/logcom/exn075
- Robust Online Monitoring of STL: https://arxiv.org/abs/1506.08234
- RTAMT: https://arxiv.org/abs/2005.11827

### Formal runtime assurance / control safety

- Safe RL via Shielding: https://arxiv.org/abs/1708.08611
- SOTER: https://arxiv.org/abs/1808.07921
- Neural Simplex Architecture: https://arxiv.org/abs/1908.00528
- ModelPlex: https://doi.org/10.1007/s10703-016-0241-z
- FEARL: https://arxiv.org/abs/2606.23754
- CBF-QP: https://arxiv.org/abs/1609.06408
- Predictive Safety Filter: https://arxiv.org/abs/1812.05506
- HJ reachability safety framework: https://arxiv.org/abs/1705.01292
- Semantically Safe Robot Manipulation: https://arxiv.org/abs/2410.15185
- PACS: https://arxiv.org/abs/2511.06385
- Proof-Carrying Plans: https://arxiv.org/abs/2008.04165
- VeriPhy: https://doi.org/10.1145/3192366.3192406

## 九、2026-07-10 实现状态与剩余边界

### 已实现

1. **Fail-closed Lean bridge 与保守数值编码。** Lean 不可用或工程编译失败时，默认拒绝
   安全 claim；mock 仅能显式用于诊断。连续量进入 Lean 前，对观测下界向下取整、对要求
   阈值向上取整，非有限值按失败方向编码，避免量化误差把不安全边界变成通过。
2. **Python typed CTDA reference path。** 已有不可变 mission/contract/proposal/
   authorization/receipt/plant-trace/event-trace 数据结构及 digest 完整性检查；mission 包含
   typed goal atoms、goal phases 和 phase obligations，contract 必须推进当前 transition 的
   residual obligations。`CTDAChecker` 与有状态 `CTDASupervisor` 已覆盖 semantic refinement、
   prefix authorization、observed-prefix/trace provenance、monitor chain、replay/stale rejection
   和 fail-closed verdict。
3. **Lean 三段 checker 与三值 monitor。** Lean 已实现并证明 semantic、prefix-pre、observed
   evidence checker 的 soundness/reflection；monitor 使用 `satisfied / violated / pending`
   finite-prefix 语义，完成必须绑定可信 terminal event、deadline 和 post evidence。回归负例
   覆盖错 spec、错 semantic witness、稀疏 tube、未授权 command、空 trace、过期合同和缺失
   post evidence。
4. **LIBERO 单步授权闭环。** 启用 CTDA 时，wrapper 将每次环境执行限制为一个 raw step，
   在 `env.step` 前完成 Python reference prefix authorization 和 dispatch freshness 检查，执行后
   记录 plant/event trace 并推进持久 monitor；batch 输出已统计 CTDA static/monitor verdict、
   record 数量和相关延迟。monitor 失败或 episode 在 obligation pending 状态耗尽预算时，runtime
   会真实派发 manifest 中冻结的 fallback action，并生成绑定 episode、触发原因、requested/
   simulator-applied command、切换前后状态、hard-invariant evaluation 和单调时间戳的 typed
   switch receipt。成功条件由 runtime 内生计算，必须同时满足完整观测、安全距离、collision/
   cost、不变量、actuator evidence 和 trigger-to-observe latency；任一未知或失败都升级为
   `safe_stop`。fallback attempt 会原子清除并锁存旧 contract/authorization/execution/monitor，
   独立 trace、reward、cost/collision 和 batch 计数也已落盘。
5. **Simulator task root 与运行配置冻结。** CTDA online runner 在环境创建前冻结 benchmark
   instruction 与 BDDL bytes，将环境指向只读 snapshot 并在创建后重验 digest；attack record
   不能重定义 trusted instruction。v2 fallback manifest 绑定 BDDL、SafetySpec、真实环境 action
   bounds 和 manifest 声明的切换上界，只允许 canonical zero hold；输出持久化 mission/spec/
   fallback/config digests。由于离线缓存无法重新验证 live init state、environment action bounds
   和 observer，batch 直接拒绝 `--skip-existing`。只读 snapshot 的本地威胁模型排除同 UID
   恶意进程；未监控 warmup 在 CTDA 模式下也被拒绝。

### 尚未完成，因此当前不可声称

1. **Python runtime 尚未调用 Lean CTDA evaluator。** 当前 LIBERO 运行路径标记为
   `ctda-python-reference`；Lean CTDA 已编译并有定理与例子，但尚未成为在线授权的实际
   evaluator，因而不能声称每次 LIBERO prefix 都由 Lean 判定。
2. **尚无真实动力学 reachable-tube 或 verified fallback proof。** 当前实现是带显式 assumptions
   的保守运动学界、明确标记为 `operator-pinned-simulator-test-only` 的外部 fallback manifest、
   真实 simulator dispatch 和软件 switch receipt。receipt 证明的是一次请求/模拟器施加、即时
   postcondition 与实测时限，不证明长期 `StableFor` 或全恢复域；这仍不是对真实机器人动力学、
   接触、切换时延或恢复域的 CBF、HJ reachability 或 theorem-level proof。
3. **尚无可信 BDDL 编译器与硬件证据链。** 目前 legacy intent/state 到 mission 的转换不是
   已验证的 authenticated BDDL compiler；虽然 benchmark instruction 与 BDDL 内容已做冻结和
   digest binding，BDDL goal 到 typed mission 的语义编译仍未验证。observer、actuator receipt、
   时间戳和 abstraction witness 主要来自模拟器/软件路径，也不是硬件 attestation。因此不能
   声称像素 grounding、真实执行命令、传感器完整性或硬件时序已由 Lean 证明。
