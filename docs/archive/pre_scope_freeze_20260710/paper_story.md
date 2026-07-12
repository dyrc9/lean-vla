# 论文核心故事：从两种失配到双层执行完整性

> 状态说明（2026-07-10）：当前主方法是 **ProofAlign 2.0: Contract-Carrying
> Temporal Dual Alignment（CTDA）**。攻击复现与防御方法是两条并行研究线：攻击线用于
> 建立威胁、产生可复用 workload 和发现绕过面；防御线用于定义并验证双层对齐。攻击跑通
> 不等于防御有效，防御失败也不否定攻击 workload 的研究价值。

## 一句话定位

> A VLA command is authorized only when its semantic contract refines an
> authenticated frozen mission, and it remains authorized only while every
> dispatched and observed prefix conforms to that contract and its evidence.

中文表述：安全关键的 VLA 执行必须同时满足两种对齐：候选语义合同忠实于认证且冻结的
任务授权；实际下发命令和观测轨迹持续实现该合同。ProofAlign 用 CTDA 将这两种对齐变成
逐前缀、fail-closed、可审计的运行时协议。

## 1. 起点：高成功率不等于受授权且安全的执行

VLA 将自然语言、视觉观测和连续控制放进同一个闭环。模型可以完成 benchmark goal，
同时在过程中抓错对象、采用危险 affordance、插入无关子目标、碰撞障碍或人手，甚至执行
被攻击 prompt 引入的动作。只看最终 task success 会把以下情况混在一起：

- `safe success`：按原始授权完成任务且过程满足安全约束；
- `unsafe success`：完成任务，但过程发生碰撞、危险接触或 frame-condition violation；
- `unauthorized success`：完成了被篡改 prompt 的目标，却偏离最初授权任务；
- `safe refusal`：拒绝危险或未授权动作，任务未完成但安全机制行为正确；
- `availability failure`：由于规格、证据或 checker 过度保守而不必要地拒绝安全动作。

攻击不是这个问题成立的前提，但它会把问题放大并使其可复现。SABER 类 instruction attack
可以让 policy-facing prompt 与用户原始授权分离；动作膨胀、约束违反、动态干扰和执行器
偏差则会让一个表面合理的计划在执行链上失真。

## 2. 核心观察：VLA 执行存在两个独立的完整性断点

### 2.1 任务授权断点

policy 当前看到的 prompt、重规划提示或攻击后 instruction 不等于用户最初授权的任务。
一个动作可以完全对齐当前 prompt，却不对齐认证任务。例如：

```text
authorized mission: 把杯子放到托盘上，并保持刀具不动
policy prompt:      先拿起刀确认托盘位置，再移动杯子
proposal:           Pick(knife)
```

碰撞检查器可能认为 `Pick(knife)` 几何可行，神经 verifier 也可能认为它符合当前 prompt；但
它没有被原始任务授权。这里缺失的是从认证任务到当前 semantic macro-contract 的持续授权
关系。

### 2.2 效果实现断点

即使语义合同本身合法，VLA proposal、过滤后命令、实际执行命令和真实效果仍可能不一致：

```text
semantic contract -> policy proposal -> authorized command
                  -> actuator-applied command -> observed plant/event trace
```

偏差可能来自 action chunk 中间步骤、filter 替换、执行器误差、动态障碍、感知丢失、抓取
滑移或证据重放。只检查合同是否合法不能保证它被正确实现；只检查局部几何安全又会允许
与任务无关但物理稳定的动作。

因此安全执行不是单一 gate，而是两个同时必要的关系：

```text
Mission Authorization Integrity
  authenticated mission + active phase
    -> authorized semantic macro-contract

Execution / Effect Realization Integrity
  proposal + authorized command + execution receipt + observed trace
    -> realized semantic macro-contract
```

## 3. 双层对齐

### 第一层：Semantic-Temporal Alignment

第一层判断 `SemanticTemporalRefines(M, q, s, kappa)`：候选 macro-contract 是否是冻结
`MissionSpec`、当前 task phase 和 residual obligations 的合法时序 refinement。

它负责阻止：

- prompt injection 或重规划导致的任务漂移；
- 错对象、错部件、错区域和危险 affordance；
- 跳过必要 phase、插入无关技能或把 `Stop` 当作任务完成；
- 满足局部动作语义、但违反 mission hard invariant 的捷径。

第一层产生的是语义授权，不是低层动作的物理安全证明。

### 第二层：Physical-Effect Alignment

第二层判断 `PhysicalEffectConforms(kappa, A, R, tau)`：被授权、实际执行和观测到的每个
prefix 是否仍然绑定同一合同，并满足执行前、执行中和执行后的效果义务。

它包含三个阶段，但仍属于同一种 alignment：

1. `PrefixPreCertified`：执行前绑定 state、monitor、proposal、command、tube、fallback 和
   fresh evidence；
2. `ObservedPrefixEvidenceValid`：执行后绑定 authorization、actuator receipt、plant trace、
   symbolic events 和 abstraction provenance；
3. `TemporalCompletionAudit`：跨 prefix 保存未决义务，只有 terminal event、guarantee 和
   post evidence 同时成立才推进任务 phase。

第二层负责阻止 command substitution、stale/replay evidence、monitor reset、trace injection、
动作中间碰撞和“计划正确但实现错误”。

### 为什么不增加第三层

任务 authority、evidence provenance、uncertainty、time base 和 fallback supervisor 是两层
共同依赖的基础设施，不是新的 alignment。保持两层结构可以让论文主张清晰：第一层回答
“这个合同是否被任务授权”，第二层回答“实际执行是否实现这个合同”。

### 两个系统不变量

方法主体应围绕两个可审查的不变量展开，而不是围绕字段列表展开：

```text
No dispatch without dual authorization:
  Dispatch(u_i)
    => SemanticWitness(M, q_i, kappa)
       and FreshPrefixAuthorization(kappa, s_i, monitor_i, u_i)

No phase advance without realized completion:
  Advance(q_i, q_{i+1})
    => CompletedTraceWitness(kappa, accepted_trace, post_evidence)
```

第一个不变量要求每条 raw command 同时继承任务授权和当前 prefix 授权；第二个不变量防止
系统把局部 `safe_pending`、自报 terminal event 或旧 trace 错当成任务完成。

## 4. 为什么叫 Contract-Carrying Temporal Dual Alignment

- **Contract-Carrying**：每个可执行 prefix 都必须引用冻结任务、active contract、当前 state、
  monitor state、proposal、authorized command、证据和 fallback；不能只携带裸 action。
- **Temporal**：一个 `Pick`/`Place` 合同可以跨越多个 action chunks 和 policy calls；phase、
  deadline、history 和 residual obligations 不能在每次模型重推理时重置。
- **Dual Alignment**：任务授权完整性与效果实现完整性缺一不可。第一层通过不代表第二层
  自动通过，局部物理安全也不能升级成任务授权。

## 5. 系统角色与信任边界

CTDA 位于非可信 VLA policy 与执行器之间：

```text
authenticated mission authority
  -> frozen MissionSpec
  -> semantic contract
  -> Layer 1: semantic-temporal refinement

untrusted VLA / attacked prompt
  -> action proposal
  -> optional physical filter and evidence producers
  -> Layer 2a: bounded prefix authorization
  -> exact dispatch + actuator receipt
  -> Layer 2b: observed-prefix conformance
  -> Layer 2c: temporal completion or fallback
```

威胁模型必须区分恶意行为与条件假设：

- 攻击者可以影响 policy-facing prompt、VLA proposal，并尝试重放或错绑旧 artifact；
- 动态障碍、动作误差和 observation loss 属于运行时故障/环境扰动，即使没有攻击者也要处理；
- 任务 authority、reference monitor 和 checker 是声明的信任根；若要抵抗 host-level attacker，
  还需要签名、authenticated IPC、隔离执行和可信 actuator/observer evidence；
- digest 只提供对象身份与完整性绑定，不能证明 producer 的声明为真；
- 当前 simulator allowlist、软件 receipt 和 zero-hold fallback 不等于硬件 attestation 或
  verified recovery controller。

## 6. 攻击线与防御线如何双管齐下

### 攻击线：独立建立威胁 workload

GPU 机器继续运行官方或增强攻击，不依赖 CTDA 是否已经完成。攻击线回答：

- 哪些 VLA、任务和初始状态容易出现 task failure、action inflation、constraint violation；
- 攻击是否跨模型、跨 seed 和跨任务迁移；
- 哪些攻击只改变任务完成率，哪些真正改变过程安全或授权语义；
- 攻击如何产生可保存、可重放、可配对的 proposal/instruction records。

攻击结果首先是 threat evidence 和 workload。攻击成功率不能直接当作防御效果，攻击较弱也
不能通过调整防御指标来掩盖。

### 防御线：独立优化并验证双层对齐

本地 method 工作不等待攻击批次完成。防御线回答：

- 第一层能否拒绝偏离 frozen mission 的合同，同时保留合法任务进展；
- 第二层能否发现 prefix、command、trace、timing 和 evidence-chain 的偏差；
- persistent monitor 是否真正跨 prefix 保存时序义务；
- fallback 是否实际接管，以及接管前风险暴露时间和切换延迟；
- 安全收益是否来自准确检测，而不是 always-stop。

最终只在相同 task/init/policy seed/proposal 上做配对：clean、attacked、attacked+defense。
攻击线和防御线通过版本化 attack record 与 proposal trace 对接，而不是共享隐式运行状态。

攻击/故障可以统一映射到双层 taxonomy：

| workload | 主要破坏面 | 主要检测机制 |
|---|---|---|
| instruction perturbation、prompt takeover、目标/约束替换 | 第一层 | frozen mission refinement |
| replan drift、无关技能插入、phase skipping | 第一层 | phase obligation 与 task progress |
| action inflation、跨 chunk 累积效果 | 第二层时序 | accepted history 与 deadline |
| command substitution、actuator mismatch | 第二层 binding | authorization/receipt equality |
| stale/replay、monitor reset、trace tampering | 第二层证据链 | nonce、freshness、history digest |
| dynamic obstacle、slip、observation loss | 第二层 runtime | prefix conformance、unknown/fallback |
| 给恶意 raw control 套合法 skill label | 跨层 | proposal-to-contract 与 command binding |

## 7. 论文贡献应如何表述

1. **问题与安全属性。** 将 VLA 安全执行定义为从认证自然语言任务到实际机器人轨迹的
   双重完整性问题：mission authorization integrity 与 effect realization integrity。
2. **方法。** 提出 CTDA：冻结任务、持久 semantic macro-contract、逐 prefix 授权、
   proposal/authorized/executed/observed binding 和 fail-closed supervisor 的双层协议。
3. **形式化与系统。** 给出 typed staged judgments、finite-trace monitor、checker theorem 和
   LIBERO reference runtime；所有保证明确依赖 task grounding、observer、dynamics、timing 和
   actuator assumptions。
4. **攻击驱动评测。** 将独立生成的 instruction/action attack workload 与防御做配对评估，
   同时报告攻击成功、安全成功、false block、intervention lead time、fallback 和 verifier tax。

其中第 3 项必须按实际 evaluator mode 报告。当前可以声称 Lean 中存在 executable CTDA
specification、Python reference runtime 已接入 LIBERO；在线 Lean CTDA evaluator 接通前，不能
写成“每个在线 prefix 已由 Lean 授权”。

## 8. 主张边界

当前论文可以主张：

- 两种 alignment 捕获不同且互补的 VLA failure/attack surface；
- 冻结任务根使被攻击 prompt 不能直接改写授权语义；
- typed binding 和 freshness rules 能在声明的 TCB 内拒绝 stale、replay、cross-state、
  cross-contract 和 command mismatch；
- finite-prefix verdict 将“当前未违反”与“合同已完成”分开；
- 攻击 workload 与防御 evaluator 可以独立复现并通过 artifact 配对。

当前不能主张：

- Lean 证明了像素 grounding、连续动力学或真实硬件动作；
- 非空 witness、digest 或 producer 自报 Boolean 本身构成物理 proof；
- simulator zero-hold 在所有机器人状态下都是 verified safe fallback；
- 攻击跑通已经证明 CTDA 防御有效；
- task success 等于 safe execution，或 fail-closed 等于零 availability cost。

## 9. 推荐论文叙事顺序

```text
攻击/失败案例揭示两种完整性断点
  -> 单一 collision/verifier/plan monitor 为什么不够
  -> 双层对齐安全属性
  -> frozen mission 与 semantic macro-contract
  -> per-prefix physical-effect conformance
  -> persistent monitor 与 fallback
  -> 条件形式保证和 TCB
  -> 独立攻击 workload
  -> clean/attacked/defended 配对实验与 ablation
```

论文的核心不应是“我们使用 Lean”，也不应是“我们复现了某个攻击”。核心是：**VLA 从自然
语言授权到物理执行存在两个必须同时闭合的完整性断点；CTDA 给出一个可检查、可组合、可被
攻击实验验证的双层闭环。**
