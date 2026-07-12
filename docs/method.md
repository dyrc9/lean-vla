# ProofAlign / CTDA 方法定义

更新日期：2026-07-10

本文是当前方法与 claim 的唯一 normative 定义。实现优先级见
[`roadmap.md`](roadmap.md)。

## 1. 研究问题

VLA policy 同时消费可被扰动的语言、视觉和历史，并输出连续 action chunks。一个执行即使
最终完成 benchmark goal，也可能发生两类独立失配：

1. **Mission authorization mismatch**：policy 当前遵循的 prompt 或局部技能没有被原始任务
   授权。
2. **Execution realization mismatch**：合法合同对应的 proposal、实际 dispatch 和累计物理效果
   不一致，或未完成的局部 prefix 被错误当成任务完成。

ProofAlign 当前把问题收缩为：在一个 trusted, locally frozen benchmark mission、可信但边界
明确的状态/dispatch adapter 和不可信 VLA proposal 之间，实现一个 persistent dual reference
monitor。

方法不以“证明完整机器人安全”为目标。

## 2. 威胁模型与 TCB

攻击者或故障可以影响：

- policy-facing instruction、replan context 和 policy RGB observation；
- VLA 输出的任意 raw proposal/action chunk；
- policy 自报的 symbolic action、expected effect 或 admissibility metadata；
- stale、replayed、cross-state 或 cross-episode artifact；
- action chunk 中的累积任务漂移、错误 gripper 操作或错误目标运动。

当前 prototype 明确信任：

- benchmark-owned task artifact、BDDL bytes、task id/init id 和 trusted instruction 的本地冻结
  结果；
- CTDA reference monitor 进程及其 persistent state；
- 唯一 dispatch path；
- 配置为 TCB 的 simulator state/receipt adapter；
- Lean kernel，以及真正送入 Lean evaluator 的离散 typed judgment。

当前不抵抗：

- mission authority 或 monitor 进程已经被攻陷；
- 同 host/UID 任意代码执行；
- 伪造的硬件 sensor/actuator 信号；
- 未建模的连续接触动力学；
- 唯一 observer 与 policy 同时受到同一视觉攻击时的确定性失效。

普通 digest 只提供对象身份和绑定，不提供密码学认证或 producer 真值。

## 3. 最小方法核心

### 3.1 Trusted frozen mission

每个 episode 在 dispatch 前冻结一个有限域 `MissionSpec`。它至少绑定：

- benchmark/task/suite/init identity；
- BDDL/task artifact digest；
- trusted benchmark instruction digest；
- object/region registry；
- hard safety constraints；
- supported task phases 和 residual obligations；
- episode nonce 和 time base。

当前只要求一个确定性的有限 task-template compiler。未支持的 task 必须产生
`unsupported/unknown` 并 fail closed；不得把它包装成通用、已验证的 BDDL/NL compiler。

policy-facing instruction 可以与 trusted instruction 不同，但无权改变 `MissionSpec`。

### 3.2 Gate 1: `MissionRefinementGate`

合同由：

```text
MissionSpec + active phase + residual obligations + trusted state
  -> allowed SemanticContract
```

生成或选择。paper CTDA 路径不得从 attacked prompt、
`heuristic_contract_from_instruction()` 或 policy 自报 `proofalign_action` 生成授权合同。

Gate 1 检查合同是否：

- 对应当前 phase 的合法 primitive；
- 绑定正确 target、part 和 region；
- 不违反 hard invariant；
- 保留未完成义务；
- 不能用 `Stop`、文本声明或局部 pending 替代任务进展。

第一阶段只支持一个有限 manipulation slice：persistent `Pick` 和 `Place`
macro-contract；approach/transport 是合同内 raw prefixes，而不是由 prompt 反复创建的新合同。

### 3.3 Independent raw proposal binder

VLA 输出 raw commands。一个独立、保守、版本化的 binder 判断这些 commands 是否可能继续实现
当前 mission-rooted contract。binder 只能读取：

- frozen mission 与 active contract；
- trusted current state；
- raw commands；
- 明确阈值、模型 id 和版本化配置。

它不能信任 policy 自报的 `proposal_admissible=true`，也不能因为 raw proposal 携带正确
`contract_id` 就认为语义成立。

最小 slice 的预期语义：

- `Pick`：approach prefix 朝 mission target 接近；仅在 target 邻近且 gripper-close 与合同一致
  时允许 grasp prefix。
- `Place`：只允许搬运当前 held mission target；运动朝 mission region；仅在 region 条件满足时
  允许 release prefix。

错误目标、错误 held object、错误 gripper 操作、方向不明、观测不足或目标歧义必须
`refuted/unknown`。

### 3.4 Gate 2: `TraceConformanceGate`

每个可执行 prefix 形成一笔 fresh transaction：

```text
raw proposal
  + frozen mission / active contract
  + state / monitor / proposal index
  + independent binder result
  -> prefix authorization
  -> exact dispatch
  -> receipt + observed plant/event trace
  -> persistent monitor transition
```

Gate 2 分成三段，但仍属于同一个 alignment：

1. `prefix_pre`：执行前绑定 state、contract、raw proposal、authorized command、time budget 和
   monitor state。
2. `observed_prefix`：绑定实际 dispatch/receipt、observed trace、episode 和 authorization。
3. `monitor_step`：把 current prefix 拼到 accepted history；区分 `safe_pending` 与 `complete`。

一个 semantic contract 可以跨多个 policy calls。每次新 proposal 不得重置历史、deadline 或
residual obligation。

## 4. 两个系统不变量

论文形式化主体只围绕两个不变量：

```text
No dispatch without dual authorization:

Dispatch(u_i)
  => MissionRefines(M, phase_i, contract_i)
     and FreshPrefixBound(M, contract_i, state_i, monitor_i, u_i)
```

```text
No phase advance without checked completion:

Advance(phase_i, phase_i+1)
  => Concat(accepted_trace, current_prefix) satisfies contract completion
     and required post evidence is present
```

这些是不依赖攻击实现的协议属性。物理结论仍条件化于 state abstraction、observer、dynamics、
timing 和 actuation assumptions。

## 5. Verdict 与事务语义

静态/evaluator verdict：

- `proven`
- `refuted`
- `unknown`
- `inconsistent`

temporal monitor verdict：

- `safe_pending`
- `complete`
- `violated`
- `unknown`
- `inconsistent`

只有 `proven` 的 pre-dispatch judgment 才能 dispatch。`safe_pending` 表示当前 prefix 尚未违反
合同，但不能推进 phase。任何 evaluator failure、serialization error、timeout、parity mismatch
或状态冲突都 fail closed。

contract、proposal index、monitor history 和 phase 更新必须事务化：选定 evaluator 成功前不能
提前提交状态。

## 6. Lean 与 Python 的职责

目标路径使用一个严格版本化的 `ctda-wire-v1`：

- Python 负责 task/state/raw-action adapter、canonical serialization、dispatch 和 trace capture；
- Lean 负责共同支持的离散 CTDA judgment；
- Python reference evaluator 只作为 differential oracle 和 diagnostic；
- online 输出必须准确区分 `ctda-python-reference`、`ctda-lean-kernel` 和 `ctda-shadow`。

当前真实状态：

- Lean CTDA specification、checker、theorem 与 `CTDAWire` 共同支持 semantics 已存在；
- runner 可显式选择 `ctda-python-reference`、`ctda-lean-kernel` 或 `ctda-shadow`；只有
  `ctda-lean-kernel` 的成功 request 写 `proof_verified=true`，shadow 不授权 dispatch；
- 四个 online stage 都保存 canonical request、generated Lean source、checker/build digest、
  stdout/stderr 和 verdict；
- 27-case golden/shadow corpus 为零 Python/Lean mismatch；
- 当前实现逐 request 编译 Lean replay，本地 p99 约 0.65--1.95 秒，明显不是 real-time control
  evaluator。它目前是 slow online interlock/offline audit reference。

## 7. 当前与未来 claim

当前允许：

- Lean 中存在可执行的离散 CTDA specification；
- paper path 的 mission-rooted Pick/Place contract 不依赖 policy prompt 或 policy symbolic
  metadata；
- 共同支持的 semantic/prefix-pre/observed-prefix/monitor-step 可由 Lean kernel 实际检查；
- fake-env 与 golden corpus 验证零提前 dispatch、零未检查 phase advance 和零 parity mismatch；
- frozen local task artifact、nonce 和 digest 能在声明 TCB 内拒绝部分 stale/replay/cross-episode
  mismatch；
- pending 与 completion 被显式区分。

必须经过远程配对实验后才允许：

- dual method 相对 single layer 或 collision checker 有防护收益；
- 对 instruction/camera attack 有效；
- false block、safe-success retention 和 verifier tax 可接受。

## 8. 当前非目标与 future work

以下全部从当前核心移到 future work：

- 通用自然语言或全 LIBERO-Safety BDDL compiler；
- CBF、HJ reachability、完整 dynamics-aware tube；
- 密码学 task authentication、authenticated IPC、TEE；
- hardware sensor/actuator attestation；
- verified recovery controller 与 recoverable-set theorem；
- 完整 real-robot guarantee；
- 新攻击构造或训练时后门。
