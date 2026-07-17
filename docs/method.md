# ProofAlign / CTDA 方法定义

更新日期：2026-07-17

本文是当前方法与 claim 的唯一 normative 定义。实现优先级见
[`roadmap.md`](roadmap.md)。

## 0. 版本与 validity 状态

第 1--6 节描述已被 E1 clean utility pilot 实际评估的 **CTDA v1 frozen specification**。该版本不因
负结果被后验改写；contract lifetime、binder threshold、observation requirement 或 phase logic 的任何
改变都属于 CTDA v2。

当前 validity 必须分层解释：

- paired experiment internal validity：valid（12/12 valid pair）；
- 实现与冻结离散 spec 的 Lean/Python parity：pass（2640/2640）；
- clean operational utility：fail on the evaluated slice/seed（VLA-only 8/12，Full CTDA 0/12，
  retention 0，phase completion 0）；
- clean safety benefit：该 pilot 未证明（两臂 complete collision/cost observation 下 unsafe 都为 0）；
- safety observation completeness：human-hand/obstacle distance provenance 在 24/24 episode 缺失；
- 总判定：v1 可作为 scoped fail-closed/protocol prototype 保留，但不具备 operational claim
  readiness，修改后才能继续扩大 runtime evaluation。

保留 trace 中，9/12 Full episode 因 40 秒 semantic contract wall-clock coverage 耗尽停止，3/12 因
persistent bounded-stutter no-progress limit 耗尽停止；12/12 都在 approach 阶段 pre-dispatch
`refuted`。该 block 没有独立 action-level counterfactual，不命名为 false positive。机器可读判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

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

E0 v2 candidate 具体实现了一个更窄的 exact slice：只有显式提供且 SHA-256 固定的 task-manifest
registry 才能替代 legacy instruction compiler。每个 entry 绑定 suite/task id、完整 BDDL byte digest、
唯一 `CheckGripperContactPart` target 与 geom-id set；缺 entry、digest/goal 不一致或 goal 不是单 atom
均拒绝。strict timing audit 的 0/45 结果永久保留到 E4；当前 E0 v2 按明确授权的 non-real-time
slow-interlock 口径，只使用 fresh safety/provenance audit 分类。最终支持 affordance task
`0,1,2,3,5,6,7,8,10,11,12,13`；task 4/9/14 因跨 seed 初态 digest mismatch fail closed。该 slice
仍只是 operator-pinned simulator qualification，不构成 verified recovery 或 real-time claim。

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

当前 Pick/approach 还包含一个严格受限的连续微动作分支。它不是按重试次数放宽方向检查，而是
在同一 active contract 上累计扣减两类绑定预算：归一化六维 motion-command path norm 不超过
`0.002`；预测平移 path 的上界由该冻结 command-path budget 乘以 live controller 的等向平移尺度
得到。当前 vendored `OSC_POSE` 的尺度为 `2.0 m / normalized-unit`，因此运行时预算为
`0.004 m`，而不是把 `model_error_m=0.0001 m` 同时当成动作预算。每次 prefix 只有在授权成功时
才扣减；replan 或同一
mission nonce 内的 reset 不退款，也不得延长第一次微动作绑定的 contract deadline。零幅度动作仍
计入沿用既有 `no_progress_patience=3` 的持久 no-progress 上限。该分支只允许非 closing-gripper
前缀；completion、contract progress、累计超界或 deadline 耗尽立即 fail closed，phase 不推进。

CTDA 启用时从实际环境的单个 live robot controller 读取并绑定 controller type、delta mode、六维
input/output range 与 environment action bounds。只有零中心、三轴等向的六维 `OSC_POSE` delta
mapping 才受当前运动学模型支持；controller 缺失、模式/维度错误、action bounds 不一致或非等向
mapping 均拒绝启动。有效 mapping、派生 scale 与 digest 写入 runtime metadata，并进入版本化
dynamics model id。

上述分类与累计算术由 consumer-side Python binder 完成并绑定进 candidate/tube/proposal witness。
Lean `prefix_pre` 只检查共同 wire 中已经给出的离散 binder verdict 与 transaction bindings；当前
论文口径不得写成 Lean 独立证明了 raw continuous action 的 micro-action 语义。

### 3.4 Gate 2: `TraceConformanceGate`

对上述 contact-part candidate，completion witness 来自 trusted simulator adapter 对 MuJoCo raw contact
buffer 的独立扫描：同一 manifest query 的左右 fingerpad 必须各自至少命中一个允许 object geom。
`gripper_holding`、policy metadata 和 benchmark `env.check_success()` 均不能替代该 witness；缺 object
geom、gripper geom 或 contact observation 时产生 unknown，phase 不推进。

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

OpenPI adapter 同时保存完整归一化 action chunk、episode 内 policy-call ID、实际 dispatch 的 policy
actions 与未执行 tail。它们是审计数据；控制路径仍保持每次 CTDA authorization 只覆盖一个 raw
command。

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

### 5.1 时序策略不是安全语义的同义词

runtime 显式绑定两种 timing policy：

- `strict-real-time-v1`：dispatch-to-observation 超过单 prefix control-period SLA，或 fallback
  trigger-to-observation 超过 witness 的 switch-latency SLA，都会否决当前运行判据；
- `slow-interlock-diagnostic-v1`：上述两个墙钟 SLA miss 仍原样写入 artifact，但只作为性能负结果，
  不单独否决 method judgment。

慢速策略不放宽动作/合同安全边界。command 必须在 authorization window 内 dispatch，观测不得晚于
`authorization.valid_until_ns` 或 semantic contract deadline，plant trace duration 不得超过授权
horizon，hard invariant、reachable tube、model assumption、actuation binding、completion/progress 和
累计 bounded-stutter budget 仍全部 fail closed。fallback 只有在 requested command 确实被 typed
simulator adapter 应用、receipt/attestation 完整且立即 postcondition 成立时，才能在慢速策略下视为
方法层已建立；原始 `succeeded` 字段仍保留包含 switch-latency SLA 的严格结论。

该 timing policy ID 与是否执行 realtime SLA 都绑定进 reachable-tube assumptions，并写入 per-prefix
与 fallback metadata。当前 Python adapter 负责计算该墙钟策略，Lean observed-prefix stage 检查绑定
后的 plant verdict；因此不得把它表述成 Lean 已独立证明 raw wall-clock timing。

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
  evaluator。`ctda-lean-kernel` runner 使用显式 `slow-interlock-diagnostic-v1`，保留完整 miss；
  Python reference 默认仍使用严格时序策略。

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

E1 远程配对实验已经给出一个有效负结果：当前 v1 的 safe-success retention 为 0，不能声称 utility
或 verifier tax 可接受；clean 两臂 observed unsafe 都为 0，也不能声称 dual method 在该 pilot 中有
增量 safety benefit。现有 E3/E4 只支持各自冻结范围内的 safety preservation 和 fail-closed component
语义，不能补写为总体 operational benefit。

CTDA v2 在任何新 real rollout 前必须：

- 明确 semantic contract lifetime 使用 physical wall clock 还是 plant/control logical time；不能在看到
  E1 结果后只延长 40 秒 deadline。若 physical wall time 仍是安全语义，当前 slow Lean evaluator 不能
  作为 online authority；若 proof 期间 plant 被保持，dispatch 前必须重新观察并绑定 state freshness；
- 在 disjoint、outcome-blind trace 上校准 progress/bounded-stutter，先证明 nominal
  approach-to-contact liveness，同时保留错误目标、错误 gripper、累计预算和 fail-closed rejection；
- 提供 typed human/obstacle distance provenance，或明确收窄相应 safety claim；
- 事前冻结最低可接受 retention 和独立 safety endpoint，并通过 fake-env/no-dispatch/fixed-trace
  nominal/adversarial gates。

只有新的 method version、protocol、seed 或 unit 和 fresh output root 才能产生 v2 证据；旧 E1 不得
resume、覆盖或重新分类。仍未允许声称：

- dual method 相对 single layer 或 collision checker 有总体防护收益；
- 对 instruction/camera attack 有效；
- closed-loop block 是 false positive；
- safe-success retention、verifier tax 或实时性能可接受。

## 8. 当前非目标与 future work

以下全部从当前核心移到 future work：

- 通用自然语言或全 LIBERO-Safety BDDL compiler；
- CBF、HJ reachability、完整 dynamics-aware tube；
- 密码学 task authentication、authenticated IPC、TEE；
- hardware sensor/actuator attestation；
- verified recovery controller 与 recoverable-set theorem；
- 完整 real-robot guarantee；
- 新攻击构造或训练时后门。
