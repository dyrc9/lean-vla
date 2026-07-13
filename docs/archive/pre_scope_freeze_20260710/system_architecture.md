# ProofAlign 2.0 系统架构

更新日期：2026-07-10

## 1. 总览

ProofAlign 是 VLA 外部的 runtime assurance wrapper。系统不修改 VLA 权重，而是在每次低层
命令 dispatch 前后维护一个合同、授权和证据链。

```text
Authenticated task / BDDL / safety templates
                       |
                       v
              Frozen MissionSpec + SpecDigest
                       |
Observation ----------+---------------------------+
     |                                             |
     v                                             v
State/Fact Adapter                         Task Automaton State
     |                                             |
     +-----------> Semantic Contract Compiler <---+
                            |
                            v
                 SemanticTemporalRefines
                            |
VLA proposal --------------+
     |                      v
     +----> Safety Filter / Prefix Evidence
                            |
                            v
                    PrefixPreCertified
                            |
                 proven only / fail closed
                            |
                            v
                  Bounded Command Dispatch
                            |
                            v
       ExecutionReceipt + PlantTrace + EventTrace
                            |
                            v
              ObservedPrefixEvidenceValid
                            |
                            v
                 Persistent Temporal Monitor
                            |
       +--------------------+--------------------+
       |                    |                    |
    complete           safe_pending        other verdict
       |                    |                    |
 advance phase      authorize next prefix   latch + fallback
```

概念上只有两个 alignment layer：

- `SemanticTemporalRefines`：mission/phase 到 semantic contract；
- `PhysicalEffectConforms`：proposal、授权命令、执行回执和 realized trace 到 contract。

工程上第二层分为 prefix-pre、observed-prefix 和 completion monitor 三段。

## 2. 模块与职责

### 2.1 Task root adapter

输入是 benchmark task、BDDL bytes、认证用户指令或调度器任务。adapter 负责冻结原始 artifact、
计算 digest，并构造：

- authority envelope；
- object/region registry；
- task automaton；
- goal atoms、goal phases 和 phase obligations；
- hard invariants 和 evidence requirements；
- time base 与 episode nonce。

当前 LIBERO 路径会冻结 instruction 和 BDDL snapshot，并在环境创建后重新验证 digest。但 BDDL
goal 到 typed mission 的编译器尚未被形式化验证，仍属于 TCB。

### 2.2 VLA policy

VLA 接收 policy prompt、视觉观测和历史，输出连续 action proposal。它可以输出固定 chunk，
但 proposal 不自动拥有 `Pick`、`Place` 等完整语义，也不具有执行权限。

policy rationale、learned critic 和 confidence 可以触发降级、replan 或 stop，不能单独把
`unknown/refuted` 升级为 `proven`。

### 2.3 State and fact adapter

该模块把 simulator 或传感器输出转换为：

- symbolic world state；
- exact/bounded interval；
- plant sample；
- symbolic event frame；
- state、sample 和 trace digest；
- observer/abstraction attestation。

Lean 检查引用、范围和 provenance，不证明 detector、pose estimator 或 contact classifier 本身
正确。缺失、过期或互相冲突的观测必须生成 `unknown` 或 `inconsistent`。

### 2.4 Semantic contract compiler

compiler 将当前 task phase 和 action abstraction 组合成 `SemanticSkillContract`。合同声明：

- skill、target、part、region；
- guards、temporal guarantees 和 terminal event；
- 要推进的 residual obligations；
- `may_modify` / `must_preserve` frame sets；
- deadline、evidence requirements 和 fallback。

compiler 不允许生成任意 Lean 源码；它只能实例化 typed schema。合同必须重新通过 semantic
checker，compiler 本身不能批准执行。

### 2.5 Semantic checker

semantic checker 校验 frozen mission binding、authority、phase transition、对象与 affordance、
guard、frame set、deadline、任务进展和 evidence coverage。输出：

```text
proven(witness)
refuted(counterexamples)
unknown(missing evidence)
inconsistent(conflicts)
```

只有 `proven` 可进入 prefix authorization。

### 2.6 Prefix authorizer and safety filter

该模块把 VLA proposal 与最终准备 dispatch 的命令区分开：

```text
policy proposal
  -> optional CBF / predictive / kinematic filter
  -> authorized command
  -> PrefixAuthorization
```

授权必须绑定当前 state、monitor state、proposal index、proposal digest、filter policy、dynamics
model、reachable tube、time window 和 fallback witness。授权不可跨 state、monitor、episode 或
proposal 重放。

### 2.7 Dispatcher and execution adapter

dispatcher 只下发 `PrefixPreCertified = proven` 对应的 exact command，并生成
`ExecutionReceipt`。receipt 记录授权命令、实际命令、允许误差、时间戳和 actuator evidence。

当前 LIBERO CTDA 路径把一次授权限制为一个 raw `env.step`，即使 policy 一次产生多个动作，
也需要逐步重新授权。这是当前的安全实现选择，不代表 semantic contract 只能持续一个 step。

### 2.8 Trace builder

执行 adapter 产生两条相互绑定的 trace：

- `PlantTrace`：每个实际 sample 的 command、state、interval、tube membership、model assumption
  和 invariant verdict；
- `SymbolicEventTrace`：`holding`、`released`、`inRegion`、`stable`、`goalReached` 等事实。

每个 symbolic fact 都应通过 abstraction link 指向 source plant sample。没有 provenance 的事实
不能完成合同。

### 2.9 Persistent temporal monitor

monitor state 跨 prefix 保留：当前 phase、已完成 guarantee、pending obligation、proposal index、
last event time、accepted symbolic history 和 digest。Lean reference monitor 在
`acceptedTrace ++ currentPrefix` 上重新求值有限时序公式，并拒绝 timestamp rollback；Python
reference 将 accepted events 累积进 monitor digest。monitor 不能在每次 policy call 后清零。

两端当前还没有完整 wire-level parity：Python 使用 string atom accumulator，Lean 使用
`TraceFormula` DSL。在线切换到 Lean 前必须通过 canonical serialization 和 differential corpus
统一这两套语义。

运行时策略：

| Verdict | 行为 |
|---|---|
| `complete` | 接受合同完成并推进 task automaton |
| `safe_pending` | 保持同一合同，申请下一条新授权 |
| `violated` | 锁存旧链并触发 fallback/safe stop |
| `unknown` | 不继续执行，re-observe 或 fallback |
| `inconsistent` | 视为证据链故障，锁存并 fallback |

### 2.10 Fallback supervisor

fallback 不是一个字符串 decision。supervisor 必须：

1. 冻结 fallback command 和 manifest；
2. 在 non-continuable verdict 后终止旧 authorization chain；
3. 实际 dispatch fallback；
4. 记录 requested/applied command、触发原因、切换前后状态和单调时间戳；
5. 检查即时 hard invariant 和实测切换 latency；
6. 生成 typed switch receipt。

当前实现只接受 action bounds 内的 canonical all-zero hold，且 manifest 必须明确标记为
`operator-pinned-simulator-test-only`。它不构成真实机器人 verified fallback proof。

## 3. Lean 端结构

### Legacy specification

- `Core.lean`：`Action`、`TaskIntent`、`SafetySpec`、`WorldState`、`TraceSummary`；
- `Intent.lean`：`SafetyAdmissible`、`MissionRefines`、`IntentAligned`；
- `Effect.lean`：runtime invariant、frame condition、`EffectAligned` 和
  `ChunkEffectAligned`；
- `Safety.lean`：dual/certified composition；
- `Certificate.lean`：旧版 certificate schema。

Python legacy bridge 为具体输入生成 `Bool = true` proposition，通过 `by decide` 交给 Lean。

### CTDA specification

`ProofAlign/CTDA.lean` 定义：

- frozen mission、task automaton 和 phase obligation；
- semantic skill contract；
- proposal、authorization、reachable tube 和 typed evidence；
- execution receipt、plant/event trace 和 abstraction provenance；
- `SemanticTemporalRefines`、`PrefixPreCertified`、`ObservedPrefixEvidenceValid`；
- finite-prefix temporal monitor；
- checker soundness/reflection theorem。

`ProofAlign/CTDAExamples.lean` 提供正例和 binding、deadline、tube、command、trace、post evidence
等负例。

## 4. Python 端结构

- `ctda.py`：不可变 CTDA 数据模型、digest/attestation 逻辑、reference checker 和 stateful
  supervisor；
- `ctda_runtime.py`：从 legacy/LIBERO state 生成 mission、contract、prefix candidate、receipt 和
  trace，并处理 fallback switch；
- `benchmark/libero_online_wrapper.py`：legacy macro-chunk 与 CTDA 单 prefix online loop；
- `benchmark/libero_online_runner.py`：冻结 task root、验证 fallback manifest、创建环境并落盘
  audit metadata；
- `lean_bridge.py`：当前只执行 legacy generated Boolean claim；尚未提供 CTDA request
  serialization/evaluator 调用。

## 5. 当前在线路径

### Legacy mode

```text
raw VLA chunk -> symbolic Action
  -> Python intent diagnostics + Lean IntentAligned Bool claim
  -> execute macro/small chunk
  -> TraceSummary
  -> Python effect diagnostics + Lean ChunkEffectAligned Bool claim
```

### CTDA mode

```text
frozen task root
  -> Python CTDAChecker / CTDASupervisor
  -> one-step prefix authorization
  -> env.step
  -> receipt + plant/event trace
  -> Python observed-prefix + temporal monitor
  -> next authorization or fallback
```

CTDA mode当前输出标记为 `ctda-python-reference`。Lean CTDA specification 会随工程构建并由
单元/Lean examples 验证，但不是当前 online dispatch 的 evaluator。

## 6. Fail-closed 规则

以下情况不得 dispatch：

- Lean-backed legacy 路径中 Lean 不可用或工程构建失败；
- mission authority 或 typed attestation 未通过配置 verifier；
- semantic/prefix checker 返回非 `proven`；
- authorization 过期、state/monitor/episode digest 不匹配；
- tube 有覆盖空洞或 fallback witness 不一致；
- 另一个 authorization 尚在 flight；
- receipt/trace 缺失、命令不一致或 observation 为 unknown；
- monitor 已锁存 terminal non-continuable verdict。

mock mode 只允许诊断和测试，不能连接执行授权路径。

## 7. 信任边界

| 组件 | 当前角色 | 当前信任/保证 |
|---|---|---|
| Lean kernel + CTDA definition | 离散逻辑 checker | 对 Lean 内 proposition 和 checker theorem 负责 |
| Python CTDA checker | 当前 online reference evaluator | 经过单测，但不是 Lean kernel 执行结果 |
| Task/BDDL compiler | 规格生成 | 未验证 TCB；digest 只保护冻结后的完整性 |
| State/action abstractor | 连续到符号映射 | 未验证 TCB；需要 provenance/evidence |
| Simulator evidence issuer | 本地 attestation | exact allowlist 测试信任，不是硬件证明 |
| Kinematic tube | prefix 运动界 | 条件化近似，不是完整接触动力学 reachability |
| Hold fallback | simulator safe-stop action | 有真实 dispatch/receipt，无长期恢复域定理 |
| VLA | 非可信 proposal producer | 永不直接获得执行权限 |

## 8. 不应声称的能力

当前系统不能声称：

- Lean 验证了原始 RGB、object identity 或自然语言语义；
- Lean 验证了真实连续动力学、接触、摩擦或控制器稳定性；
- 每个 LIBERO CTDA online prefix 已经由 Lean evaluator 授权；
- simulator software receipt 等同于硬件 actuator attestation；
- `safe_pending` 证明未来所有 prefix 安全；
- task success 等同于 safe success。

方法的完整定义见 [`method.md`](method.md)，详细迁移与边界审计见
[`lean_method_upgrade_20260710.md`](lean_method_upgrade_20260710.md)。
