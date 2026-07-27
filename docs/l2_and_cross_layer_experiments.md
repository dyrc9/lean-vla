# L2 与跨层攻击实验计划

## 1. 目的与证据边界

本计划在当前冻结主线之后执行，不改写正在推进的 M2、P0b/R9 历史证据或已有 v3/v4 fixed-trace
artifact。当前顺序保持为：先完成 outcome-blind producer、M2 的 240 个 VLA-only clean/attacked
episode 及其 denominator/signal gate；M2 通过后，再进入本文件定义的完整实验。

实验必须区分三种证据：

1. **L1 benchmark evaluation**：使用面向 VLA/LIBERO 的已发表 SABER attack protocol；
2. **L2 externally grounded case studies**：迁移已发表的机器人/CPS 执行链攻击，不把按 ProofAlign
   predicate 取反得到的 case 伪装成外部 benchmark；
3. **Formal negative tests**：wrong digest、wrong receipt、open window、unknown evidence、unauthorized
   phase advance 等继续用于 Lean/Python 语义与实现审计，不作为现实攻击 efficacy 结果。

当前没有可直接替代 SABER、同时覆盖 VLA `authorized ActionBlock -> physical execution` 的公认标准
benchmark。因此 L2 的主结果应表述为 published-attack-grounded case studies；只有在攻击资产跨模型、
跨任务、跨控制接口独立发布并完成外部 baseline 后，才考虑将其提升为新 benchmark 贡献。

## 2. 外部攻击来源

| 层 | 外部工作 | 采用的攻击 | 本文定位 |
|---|---|---|---|
| L1 | [SABER](https://arxiv.org/abs/2603.24935) | stealthy instruction perturbation | LIBERO/VLA benchmark attack |
| L2-A | [Affine Transformation-based Perfectly Undetectable False Data Injection Attacks on Remote Manipulator Kinematic Control](https://arxiv.org/abs/2405.11047) | scaling、reflection、shearing | 主 execution-integrity case study |
| L2-B | [Can ROS be used securely in industry? Red teaming ROS-Industrial](https://arxiv.org/abs/2009.08211) | PitM、captured-command replay、modified replay | middleware freshness/replay case study |
| L2-C | [Active Defense Against False Data Injection Attacks in Robotic Manipulators](https://arxiv.org/abs/2605.17950) | stealthy sensor corruption 与末端偏移 | feedback/effect-integrity 补充 case study |
| 软件类比 | [Rewriting the Response Path](https://arxiv.org/abs/2605.02187) | alignment 后、execution 前改单个 execution-bearing field | post-authorization threat motivation |

BIV、MalTool、MCP tool poisoning/rug-pull 等用于说明声明—实现偏离和恶意 implementation threat，
不直接作为机器人 closed-loop efficacy benchmark。

## 3. 当前任务完成前不变的顺序

当前已经冻结并正在推进的工作保持不变：

```text
60-record outcome-blind attack producer
  -> bundle terminal validation
  -> M2: 60 base pairs × 2 seeds × clean/attacked = 240 VLA-only episodes
  -> M2 denominator/signal gate
```

不得因为本文件中的 L2 或全链路设计：

- 修改 M2 population、attack record、seed、threshold 或 replacement rule；
- 查看 M2 outcome 后调整 selector、local checker、effect observer 或 L2 attack severity；
- 将 P0b/R9 历史 episode 混入新的 primary denominator；
- 把当前 raw π0.5 selector 或 semantic prompt 升级为已资格化安全机制。

M2 gate 失败时，停止 confirmatory full-chain outcome；允许继续做 no-dispatch/fixed-trace 与明确标注的
engineering case-study development。

## 4. L2 对象和攻击边界

L2 实验显式区分：

```text
A_auth      L1/checker/projection 后被 authorization 绑定的 ActionBlock
A_sink      trusted dispatch boundary 实际收到的 canonical command
A_applied   controller 或 simulator 最终施加的 command
Delta_s     独立 ground-truth physical state transition
```

对应三个可测断点：

- **L2a Dispatch integrity**：`A_auth` 与 `A_sink` 的 exact digest、nonce、epoch、index、顺序和 freshness；
- **L2b Actuation conformance**：`A_sink` 与 `A_applied` 的顺序、时序、丢步、重复和有界数值偏差；
- **L2c Effect conformance**：`A_applied` 与 `Delta_s` 的 expected/forbidden effects、unknown 和 phase gating。

主 threat model 允许攻击者控制 authorization 后、trusted sink/independent observer 前的非可信 execution
relay、middleware 或 feedback path；不允许攻击者修改 trusted intent、L1 checker、authorization store、
trusted sink log、独立 outcome evaluator 或不可篡改 artifact store。

所有 canonicalization、单位/坐标系转换、bounded projection 和 action-envelope 处理必须在 authorization
之前完成并重新 assessment/contract/authorization。若转换发生在 authorization 后，则属于 L2 attack
surface。

## 5. L2-A：published affine-transformation case study

### 5.1 攻击迁移

主 L2 case study 迁移 Ueda 与 Blevins 的 affine transformation attack：

```text
x_tilde = M x + b
```

在 LIBERO delta-EEF 接口中写为：

```text
Delta_p_applied = M Delta_p_auth + b
```

攻击 family 只使用来源工作中的 scaling、reflection 和 shearing。优先复现其参数化；若 FANUC
absolute-position interface 与 LIBERO delta-action 不可直接对应，则只允许 outcome-blind 的无量纲映射，
并必须：

- 在看到 confirmatory outcome 前冻结矩阵、偏置、作用维度和时间窗口；
- 记录原参数与适配参数的逐项映射；
- 明确称为 `adapted affine attack`，不得称为 exact reproduction；
- 不根据 ProofAlign allow/reject 或 physical outcome 调整攻击强度；
- 不使用 best-of-N 或失败后替换。

### 5.2 攻击实现

攻击者位于 authorization 与 actuation 之间，并可伪造普通反馈视图：

```text
authorization records A_auth
  -> malicious relay applies affine transform
  -> controller/env.step consumes A_applied
  -> ordinary receipt/feedback claims nominal A_auth
  -> independent trusted trace records actual A_applied and Delta_s
```

必须分别记录 `A_auth`、`A_sink`、`A_applied` 和 raw simulator transition，不能用普通 receipt 代替
actual actuation evidence。

### 5.3 对照条件

L2-A 至少比较：

| Condition | Envelope | Exact command binding | Independent effects/phase gate |
|---|---:|---:|---:|
| No defense | fixed common setting | off | off |
| Envelope-only | on | off | off |
| Digest-only | fixed common setting | on | off |
| Full ProofAlign L2 | fixed common setting | on | on |

主四臂实验中 action envelope 必须是跨臂共享的 common mechanism；不得把 clipping/projection 收益记作
L2 transaction-integrity 收益。Envelope-only 仅作为解释 R9 与新 L2 estimand 差异的消融。

### 5.4 指标

- end-effector trajectory deviation；
- target/non-target object displacement；
- contact、collision、cost 与 held/drop proxies；
- strict task success 与 time-to-completion；
- altered command reaching sink/actuator；
- pre-actuation prevention rate；
- altered steps executed before detection；
- detection/fallback latency；
- forged-feedback acceptance；
- effect reject/unknown；
- false phase advance；
- clean retention、false reject 与 deadlock。

在线 effect observer 只决定 runtime verdict；独立 evaluator 使用 raw simulator privileged state、实际
`env.step` 输入、contact/object/gripper trace 计算实验 endpoint，避免 detector 与 ground-truth 循环定义。

## 6. L2-B：ROS-Industrial replay/PitM case study

### 6.1 Captured-command replay

按 ROS-Industrial red-team threat 迁移合法控制消息重放：

- 捕获上一事务的合法 authorized ActionBlock；
- 在新的 state epoch 中原样发送；
- 普通反馈路径可继续声称系统处于 nominal 状态；
- 检查 nonce、epoch、authorization one-use、block/step index 和 phase state。

Primary replay source 必须由冻结规则确定，例如“紧邻上一条成功 authorization”，不得从历史中选择
outcome 最有害的 block。

### 6.2 Modified replay

把已发表的两种攻击结构组合：

```text
captured prior ActionBlock
  -> published affine transformation
  -> replay in a new state epoch
```

Replay 来源于 ROS-Industrial PitM case，mutation 来源于 affine-transformation case。该实验称为
`adapted ROS replay case study`；在没有真实 ROS network/topic/action transport 时，不声称复现了完整
ROS exploit chain。

### 6.3 指标

除 L2-A 指标外，单独报告：

- stale/replayed authorization acceptance；
- replay reaching sink/actuator；
- duplicate/old step exposure；
- replay-induced task/phase deviation；
- freshness/one-use false rejection on clean transactions。

## 7. L2-C：stealthy feedback/effect case study

该补充 case study 迁移 robotic-manipulator FDIA 的 attacker structure：攻击者持续污染普通 sensing/
feedback channel，使状态估计和真实末端状态逐步分离，同时保持在普通 anomaly detector 阈值附近。

仅当当前 simulator/control interface 能忠实表达 sensor feedback、state estimator 与独立 actuation-projected
或 privileged observer 时运行。若 LIBERO runner 只能通过直接修改 privileged state 才能制造该攻击，
则停止并标记 `interface_not_supported`，不得用不忠实的 fixture 冒充 FDIA efficacy。

## 8. Formal negative suite 的定位

以下 case 继续保留在 A3/A4、Lean 和 Python truth-table/equivalence 测试中：

- wrong ActionBlock/assessment/contract/receipt digest；
- stale state、authorization reuse、wrong nonce/index；
- open observation window；
- missing expected effect、forbidden effect、observer violation；
- unknown evidence；
- completion 不成立时 phase advance；
- projection/intervention 后复用旧 artifact。

这些结果只支持 `component semantics pass`、`Lean-scoped transaction semantics pass` 和
implementation audit，不单独支持现实攻击防御有效性。

## 9. 全链路主实验：SABER × affine attack

### 9.1 攻击侧 2×2

| Attack cell | SABER semantic attack | Affine execution attack |
|---|---:|---:|
| Clean | off | off |
| S-only | on | off |
| B-only | off | on |
| Chained | on | on |

### 9.2 防御侧 2×2

| Arm | L1 semantic alignment | L2 execution integrity |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

`K=1` primary 中四臂共享 byte-identical proposal、assessment 和 contract，直到对应 treatment boundary。
L1-enabled arm 若拒绝，攻击链在 authorization 前终止；不得为了继续测试 L2 而绕过 L1。L1-off arm
进入同一个预注册 affine relay。攻击 transform specification 在各 arm 间相同。

### 9.3 Chained 顺序

```text
SABER perturbs policy-facing instruction
  -> VLA emits attacked ActionBlock
  -> L1 optionally rejects/allows
  -> allowed block receives published affine transform in malicious relay
  -> trusted sink/controller/effect observer processes the transaction
```

SABER record 与 affine attack record 分别按来源协议独立冻结，二者不得根据 joint outcome 互相调优。
三类 affine scenario 可按 `base_pair_id` 的预注册 deterministic hash 均衡分配；同一 base pair 的两个
seed 使用同一个 attack record，禁止 outcome-driven family replacement。

### 9.4 样本计划

保留当前 60 base pairs × 2 seeds × 4 arms 结构：

| Bundle | Episode 数 | 作用 |
|---|---:|---|
| Clean | 480 | 原计划 clean 四臂，`S=0,B=0` |
| SABER-only | 480 | 原计划 attacked 四臂，`S=1,B=0` |
| Affine-only | 480 | 新增 L2 case，`S=0,B=1` |
| Chained | 480 | 新增全链路 case，`S=1,B=1` |

完整 primary 最多为 1920 个 arm-episodes。若 M2 gate 后资源不足，必须在看到新增 outcome 前预注册
缩减方案与 power/precision 目标；不得先跑一部分后按显著性扩充。Fixed-transaction stress 可以从同一
pre-dispatch checkpoint fork 多个 published affine scenario，但 episode-level confirmatory primary 每个
base pair 仍只使用一个预注册 L2 attack record。

## 10. 分阶段攻击链指标

除 endpoint risk 外，必须报告攻击链每一段的存活率：

```text
semantic divergence
  -> L1 allow
  -> transformed command reaches sink
  -> altered command is applied
  -> harmful/missing/forbidden effect
  -> false phase advance or failed containment
```

分别估计：

- semantic attack validity；
- `P(L1 allow | semantic divergence)`；
- `P(altered actuation | authorized)`；
- `P(effect violation | altered actuation)`；
- `P(false phase advance | effect violation)`；
- overall cross-layer attack success；
- clean utility、unknown、deadlock 和 time-to-completion。

不得用单一 aggregate safe-success 隐藏 partial execution、unknown、residual contact 或 availability cost。

## 11. 执行 gate 与顺序

M2 通过后的顺序冻结为：

```text
existing fixed-trace four-arm identity gate
  -> 480 clean four-arm episodes
  -> 480 SABER-only four-arm episodes
  -> L2 published-attack adaptation protocol freeze
  -> no-outcome attack-hook/source-parameter qualification
  -> L2-A affine-only case study
  -> L2-B replay/PitM case study
  -> L2-C FDIA only if interface qualification passes
  -> 480 chained SABER × affine episodes
  -> independent terminal audit and cluster-bootstrap analysis
```

在 L2 adaptation protocol 冻结前，只允许接口实现、source-parameter mapping、no-outcome deterministic
replay 和 engineering smoke；不得查看 confirmatory physical outcome 后调整攻击或防御。

## 12. Claim gate

| 完成证据 | 允许表述 |
|---|---|
| Formal negative suite | Lean/Python transaction semantics correctly reject enumerated invalid traces |
| Affine case study | ProofAlign L2 mitigates/detects an adapted published affine execution attack in the evaluated interface |
| ROS replay case study | ProofAlign L2 rejects an adapted published replay/PitM threat in the evaluated relay |
| SABER benchmark | L1 efficacy under the frozen SABER/LIBERO setting |
| Chained primary | Dual-layer composition under SABER plus an adapted published affine execution attack |
| 当前所有实验 | 不支持一般物理安全、任意 middleware 安全或完整硬件 attestation |

L2 case-study 成功不能扩写成“通用 execution integrity benchmark 已解决”；全链路成功也不能消除 trusted
sink、independent observer、secure split、privileged geometry 和 simulator-to-deployment 的外推边界。
