# ProofAlign 2.0 方法定义

更新日期：2026-07-10

## 1. 方法概述

ProofAlign 2.0 的当前方法是 **Contract-Carrying Temporal Dual Alignment
（CTDA）**：一个位于 VLA policy 与机器人执行器之间的、fail-closed 的运行时保障层。

CTDA 不验证或替代 VLA 本身。它把候选低层 action chunk 绑定到一个语义合同，并检查：

1. 合同是否是对冻结任务及当前任务阶段的合法时序 refinement；
2. 被授权、实际执行和实际观察到的每个 action prefix 是否与合同及证据链一致。

方法仍然只有两类核心 alignment：

```text
SemanticTemporalRefines:
  frozen mission + active phase -> semantic macro-contract

PhysicalEffectConforms:
  proposal -> authorized command -> execution receipt -> realized trace
                                      -> semantic macro-contract
```

第二类 alignment 在实现上必须拆成执行前、执行中和执行后三个 staged judgments，避免
用尚未发生的 trace 为执行前授权背书。

## 2. 问题设定

在离散决策、连续执行的 VLA 系统中，policy 在时间 `t` 根据任务、观测和历史提出一段
控制 proposal：

```text
u[t:t+H] = VLA(instruction, observation_t, history_t)
```

连续世界不直接进入 Lean。外部感知、状态估计、控制过滤器和仿真/硬件 adapter 产生：

- 离散世界状态；
- 带 digest 的 action proposal 和授权命令；
- reachable-tube、clearance、fallback 等执行前证据；
- actuator receipt、plant trace、symbolic event trace 和执行后证据。

Lean 或 reference checker 只检查这些 typed object 之间的逻辑关系、时序关系、完整性绑定和
证据覆盖关系。

## 3. 冻结任务根 `MissionSpec`

每个 episode 在执行前建立不可变 `MissionSpec`：

```text
authenticated task authority
  + instruction / BDDL digest
  + object and region registry
  + non-overridable hard invariants
  + task automaton
  + phase obligations and goal atoms
  + evidence requirements
  + time base
  + episode nonce
  -> MissionSpec
  -> SpecDigest
```

任务根与 policy 当前看到的 prompt 分离。攻击或 replan 可以影响 policy proposal，但不能
重写已经授权的 mission、hard invariant 或 goal。hash/digest 只证明对象没有被替换，不证明
规格本身正确；任务 authority 和编译器仍属于显式信任边界。

### 3.1 Task automaton

任务被表示为 phase 和允许的 skill transition，例如：

```text
q0 --Approach(cup)--> q1
q1 --Pick(cup, handle)--> q2
q2 --Transport(cup)--> q3
q3 --Place(cup, coaster)--> q4
q4 --Release(cup)--> q5_goal
```

每个 transition 对应一组 residual obligations。合同必须推进当前 phase 的已声明 transition，
不能跳 phase、停留在不产生任务进展的自环，或以 `Stop` 冒充 mission completion。

## 4. 语义技能合同 `SemanticSkillContract`

policy action chunk 本身不天然等于 `Pick`、`Place` 等完整技能。CTDA 将若干 policy proposal
组织到一个可跨多次模型调用持续存在的 semantic macro-contract：

```text
SemanticSkillContract κ =
  contract/spec digest binding
  phase_before / expected_next_phase
  skill, target, part, region
  guards
  temporal guarantees
  advances_obligations
  may_modify / must_preserve
  issued_at / deadline
  semantic / physical / runtime / post evidence requirements
  fallback class / fallback id
```

一个 `Pick` contract 可以覆盖 approach、contact、close、grasp、lift 和 stable hold。每次只
授权风险允许的短 prefix，但合同 phase、deadline、pending obligations 和 evidence history
不会在 policy 每次重新推理后重置。

## 5. 第一层：`SemanticTemporalRefines`

第一层回答：

> 当前 macro-contract 是否是对冻结 MissionSpec、当前 phase 和 residual obligation 的合法、
> 非阻塞且有明确任务进展的 refinement？

其核心条件可写为：

```text
SemanticTemporalRefines(M, q, s, κ, E_sem) :=
  Authenticated(M.authority)
  ∧ κ.specDigest = M.specDigest
  ∧ κ.phaseBefore = q
  ∧ ActiveWithinDeadline(κ)
  ∧ M.taskAutomaton.allows(q, κ.skill, κ.expectedNextPhase)
  ∧ TaskProgresses(q, κ.expectedNextPhase)
  ∧ NonBlocking(M.taskAutomaton, κ.expectedNextPhase)
  ∧ TargetPartRegionWellTyped(M, κ)
  ∧ GuardsHold(s, κ.guards)
  ∧ GuaranteeRefinesResidualObligation(M, κ)
  ∧ FrameSetsConsistent(M, κ)
  ∧ EvidenceCovers(E_sem, M.requiredEvidence ++ κ.semanticPreRequirements)
```

成功返回 semantic witness；失败返回 `refuted`、`unknown` 或 `inconsistent`，不能产生执行
权限。

## 6. 第二层：`PhysicalEffectConforms`

### 6.1 执行前：prefix authorization

VLA proposal 先经过可选 safety filter，形成实际准备下发的命令。`PrefixPreCertified`
检查：

- proposal、contract、spec、episode 和 monitor state 的 digest 绑定；
- proposal index 单调递增，授权未过期且不超过合同 deadline；
- `authorizedCommandDigest` 与 reachable tube、filter policy 和 dynamics model 一致；
- tube 覆盖整个授权时域，每个 slice 均声明 invariant safety 与 recoverability；
- fallback id/witness 一致，最坏切换时延不超过证据和 monitor 上界；
- proposal/filter evidence 的 producer、版本、subject 和有效期满足要求；
- 当前 state guard 仍成立。

只有 `proven` 可以 dispatch。`unknown`、`refuted`、`inconsistent` 都 fail closed。

### 6.2 执行中：observed-prefix conformance

执行后追加不可变 `PrefixExecutionRecord`：

```text
PrefixCandidate
  + ExecutionReceipt
  + PlantTrace
  + SymbolicEventTrace
  + RuntimeEvidence
  + TraceAbstractionEvidence
  + monitor-before / monitor-after digest
```

`ObservedPrefixEvidenceValid` 检查：

- receipt 确实引用先前授权，实际命令在允许误差内；
- plant sample 使用同一 authorization、command 和 time base；
- sample 时间戳严格递增且位于授权窗口；
- hard invariants、reachable tube 和 model assumptions 在每个已观察 prefix 成立；
- symbolic event 可追溯到具体 plant sample；
- abstraction link 和 runtime evidence 覆盖合同要求；
- state、authorization 和 monitor chain 连续，拒绝 replay、stale 或跨 episode 复用。

### 6.3 执行后：temporal completion audit

合同 monitor 在多个 prefix 之间持久保存。有限 trace 语义区分：

- `complete`：terminal event、全部 guarantee、目标 phase 和 post evidence 均已满足；
- `safe_pending`：当前已检查 prefix 未出现 violation，但仍有未来义务；
- `violated`：hard invariant、时序约束、deadline 或 binding 被违反；
- `unknown`：关键 observation/evidence 缺失；
- `inconsistent`：digest、trace 或 monitor chain 自相矛盾。

`safe_pending` 不是未来轨迹安全证明，只允许在新的、短时有效的 prefix authorization 下继续。
除 `complete` 和 `safe_pending` 外，其余 verdict 都锁存当前授权链并触发 fallback/recovery。

## 7. 时序语言

Lean CTDA 使用有限 trace DSL 表达状态和事件约束，包括：

```text
Always(phi)
EventuallyWithin(duration, phi)
phi Until psi
Sequence([event_1, event_2, ...])
StableFor(duration, phi)
PrecededBy(effect, cause)
```

典型合同：

```text
Always(NoBadContact)
EventuallyWithin(2s, Holding(cup))
Holding(cup) Until InRegion(cup, coaster)
PrecededBy(Released(cup), InRegion(cup, coaster))
StableFor(0.5s, InRegion(cup, coaster))
```

## 8. Runtime algorithm

```text
Input: frozen MissionSpec M, observation o_t, persistent monitor μ_t

1. s_t, observer evidence <- observe(o_t)
2. proposal <- VLA(policy prompt, o_t, history)
3. κ <- activate or continue semantic macro-contract
4. semantic <- checkSemantic(M, active_phase, s_t, κ)
5. if semantic != proven: reject / replan / fallback
6. candidate <- bind proposal, filtered command, tube, fallback and evidence
7. pre <- checkPrefixPre(M, κ, s_t, μ_t, candidate)
8. if pre != proven: do not dispatch; fallback or replan
9. dispatch exactly the authorized bounded prefix
10. receipt, plant trace, event trace <- observe execution
11. observed <- checkObservedPrefix(M, κ, record)
12. verdict, μ_{t+1} <- monitorStep(M, κ, μ_t, record)
13. complete     -> advance task phase
    safe_pending -> repeat from step 2 under the same contract
    otherwise    -> latch chain, dispatch fallback, record switch receipt
```

## 9. 与 legacy 双层 checker 的关系

仓库保留旧版：

```text
IntentAligned(intent, action, spec)
EffectAligned(before, action, after, spec)
ChunkEffectAligned(before, action, after, traceSummary, spec)
```

Python 把具体输入编码成 Lean expression，并检查：

```lean
example : ConcreteBooleanExpression = true := by decide
```

该路径适合作为兼容 baseline、toy example 和离散检查实验，但不具备 CTDA 的 immutable task
root、proposal/authorized/executed command binding、persistent temporal monitor 和 trace provenance。

## 10. 当前实现状态

截至 2026-07-10：

- Python 已实现 typed CTDA object、digest/attestation 检查、fail-closed staged checker、
  persistent supervisor 和 LIBERO 单 raw-step 授权闭环；
- Lean 已实现 semantic、prefix-pre、observed-evidence checker、finite-prefix monitor，以及
  checker soundness/reflection theorem；
- legacy Boolean path 已接真实 Lean，并在 Lean 不可用时默认 fail closed；
- **LIBERO CTDA 在线授权目前仍调用 Python reference checker，尚未调用 Lean CTDA evaluator**；
- 当前 tube 是带假设的保守运动学证据，fallback manifest 明确为
  `operator-pinned-simulator-test-only`；
- BDDL 到 typed mission 的编译、observer/actuator evidence 和时间戳仍不是经过验证的硬件证据链。

因此可以声称“Lean 中有可执行 CTDA specification 和 checker theorem”“Python reference CTDA
已接入 simulator online loop”，但不能声称“每个在线 prefix 已由 Lean CTDA 授权”或“真实
机器人连续动力学已经形式化证明安全”。

## 11. 设计原则

1. **Lean checks contracts, not pixels.**
2. **Frozen intent remains authoritative across replans and attacks.**
3. **Every dispatch needs a fresh, bounded authorization.**
4. **Proposal, filtered command, executed command and observed trace must be bound.**
5. **Evidence may downgrade authorization; untrusted learned scores cannot upgrade it.**
6. **Unknown and inconsistent are fail-closed outcomes.**
7. **Task success and safe execution are independent metrics.**
8. **All guarantees are conditional on the stated abstraction, producer and dynamics assumptions.**

详细设计推导、相关工作与未完成边界见
[`lean_method_upgrade_20260710.md`](lean_method_upgrade_20260710.md)。
