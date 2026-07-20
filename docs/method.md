# ProofAlign / CTDA 方法定义

更新日期：2026-07-20

本文是 ProofAlign/CTDA 的方法、威胁模型与 claim boundary 的规范性来源。当前唯一允许的执行工作仍是
VLA-only 发布攻击复现；本次方法重构只修改后续设计，不授权任何 CTDA、AEGIS 或 defense rollout。
当前执行顺序见 [`optimization_plan.md`](optimization_plan.md)，历史结果见
[`evaluation_results.md`](evaluation_results.md)。

## 0. 方法状态

ProofAlign 只研究两个不可互相推出的完整性关系：

```text
trusted task intent  -- Intent–Plan Integrity --> accepted planned action
accepted planned action -- Plan–Execution Integrity --> applied/observed action
```

方法核心只有：

- **两个关系**：任务授权完整性与执行/效果实现完整性；
- **两个不变量**：无双重授权不 dispatch；无 checked completion 不推进 phase；
- **三个转换**：建立合同、授权 exact prefix、检查执行效果并更新 monitor。

`MissionSpec`、contract、binder、receipt 和 monitor 是实现这些属性所需的最小对象。canonical JSON、
digest、nonce、signature、provenance、Lean replay、certificate、lease、CBF 和 recovery controller 都不自动
构成新的方法层或论文贡献。

### 0.1 已评估版本与保留资产

- **CTDA v1**：冻结并完成 scoped clean pilot。12/12 pair valid；VLA-only 为 8/12 task/safe success，
  Full CTDA 为 0/12，retention 0，12/12 block/deadlock，0 phase completion。9/12 在 approach 阶段耗尽
  40 秒 semantic-contract wall-clock coverage，3/12 耗尽 bounded-stutter no-progress limit。
- **CTDA v2 no-dispatch prototype**：已保存独立 core/wire、certificate/rebind、六阶段 replay、21/21
  Python/Lean parity、typed evidence 和 AEGIS/crypto no-action 资产。它们证明局部协议和实现性质，不证明
  clean utility、安全收益或 online liveness。

v1 结果不得后验改写。v2 资产保持 replayable，但不再把其六阶段 wire 或全部 plumbing 当作下一版方法
的预设架构。后续设计只在它们确实支持核心不变量、独立消融或必要 TCB 时复用。

## 1. 研究问题

VLA 同时消费可能受攻击的语言、视觉和历史，并产生闭环连续 action chunks。攻击或故障会形成两类不同
偏移：

1. **Intent–plan mismatch**：proposal 对 attacked prompt 自洽，却偏离独立冻结的任务对象、部件、顺序、
   gripper 操作或 residual obligation。
2. **Plan–execution mismatch**：proposal 已被接受，但 filter、dispatch、actuator-applied command、receipt、
   observed effect 或 completion report 与被接受的 exact prefix 不一致。

单一 semantic gate 不能证明已接受的动作被真实实现；单一 collision/filter/trajectory checker 又不能判断
一个物理上局部安全的动作是否得到原始任务授权。因此问题不是“增加更多 checker”，而是让同一任务合同
在两个边界上得到 complete mediation。

ProofAlign 不以证明完整机器人安全为目标。它研究的是：在可信任务根、明确的 reference monitor 和声明
TCB 下，如何让动态 VLA proposal 在 checked completion 前始终受到同一任务授权与执行绑定约束。

## 2. 威胁模型与 TCB

### 2.1 不可信输入

攻击者或故障可以影响：

- policy-facing instruction、replan context、policy RGB observation 和模型内部状态；
- VLA 输出的 raw action proposal/action chunk；
- policy 自报的 symbolic action、expected effect、admissibility 或 completion metadata；
- stale、replayed、cross-state、cross-episode artifact；
- action chunk 的累积任务漂移、错误 gripper 操作、command substitution 和伪 completion。

### 2.2 当前声明的 TCB

- benchmark-owned task artifact、task/init identity 与 trusted instruction 的本地冻结结果；
- reference monitor 的代码、持久状态与唯一 dispatch boundary；
- 配置为 TCB 的 simulator state/receipt adapter；
- 真正进入形式 checker 的 typed judgment 及相应 checker implementation。

### 2.3 当前不抵抗

- mission authority 或 reference monitor 已被攻陷；
- 同 host/UID 任意代码执行；
- 恶意硬件 sensor/actuator 或伪造的物理信号；
- 未建模的接触动力学与完整连续物理安全；
- policy 与 monitor 共用同一已被攻陷 observer 时的确定性失效。

普通 digest 只证明对象身份和绑定，不能证明 producer 诚实。签名只在密钥与隔离假设成立时证明 producer
身份，也不自动证明感知、物理模型或数据内容为真。

## 3. 最小方法

### 3.1 方法对象

最小方法只保留五类对象：

| 对象 | 方法职责 | 不能偷带的结论 |
|---|---|---|
| `MissionRoot` | 独立冻结 task、phase、target、constraints、residual obligations | 不代表通用 NL/BDDL 已验证 |
| `ActiveContract` | 表达当前阶段允许完成什么及何时算完成 | 不代表 proposal 已可执行 |
| `ActionProposal` | VLA 提出的 raw prefix | policy metadata 不能自证 admissible |
| `PrefixAuthorization` | 对 fresh state 下一个 exact final command 的短时、单次授权 | 不能覆盖 filter 后不同命令 |
| `ExecutionEvidence` | 绑定 dispatch、applied command、receipt、observed effect 与 completion | receipt/digest 不等于物理真值 |

跨 proposal 的历史、deadline、residual obligation 和 completion state 由一个 persistent monitor 保存，不再
把 monitor 单列成第三个 alignment layer。

### 3.2 转换一：建立任务合同

```text
MissionRoot + active phase + residual obligations
  -> ActiveContract
```

合同必须由 trusted mission root 导出。policy-facing prompt、RGB、`proofalign_action`、自然语言重述或
policy 自报 contract id 都无权改变合同。未支持或歧义任务返回 `unknown/unsupported`。

合同可以跨多个 VLA calls 和 action chunks 持续存在，直到：

- phase 或 residual obligation 合法变化；
- checked completion 成立；
- hard invariant 被违反；
- 声明的状态依赖或有效期不再成立。

### 3.3 转换二：授权 exact prefix

```text
MissionRoot + ActiveContract + fresh state + monitor state + ActionProposal
  -> PrefixAuthorization(exact final command) | reject | unknown
```

这一步同时建立两个事实：当前 proposal 仍实现 mission-rooted contract；最终将 dispatch 的 exact command
在当前状态和监控历史下可接受。实现可以内部使用 semantic checker、raw-action binder、membership
checker 或 filter witness，但论文层只暴露一个原子 prefix authorization transaction。

必要条件：

- consumer 独立计算判断，不能信任 proposal 自报 Boolean；
- authorization 绑定 mission、contract、state/monitor epoch、proposal index 和 final command；
- freshness、deadline、cumulative budget 和 replay protection 不能被 replan/reset 退款或重置；
- 若 filter 修改 nominal command，必须对 adjusted command 重新授权；
- 不确定、状态不足或 evaluator failure 不得 dispatch。

### 3.4 转换三：检查执行效果并更新 monitor

```text
PrefixAuthorization + dispatch/applied command + receipt + observed effect
  -> monitor update: pending | complete | violated | unknown
```

实际 dispatch、applied command、receipt 和 observed trace 必须绑定同一 authorization。`pending` 只表示
当前 prefix 尚未推翻合同，不能升级为 completion。只有来自声明 TCB、覆盖合同 postcondition 的 checked
completion witness 才能推进 phase。

一个 prefix 完成后，monitor 原子提交 accepted history、residual obligation、progress 和 phase；任何失败
不得留下部分 state mutation。

## 4. 两个系统不变量

```text
No dispatch without dual authorization:

Dispatch(u_i)
  => Refines(ActiveContract_i, MissionRoot, phase_i)
     and AuthorizedExactPrefix(u_i, state_i, monitor_i, ActiveContract_i)
```

```text
No phase advance without checked completion:

Advance(phase_i, phase_i+1)
  => CheckedCompletion(accepted_history ++ observed_prefix,
                       ActiveContract_i,
                       required_post_evidence)
```

形式化主体只应围绕这两个不变量及其必要的 state transition。物理结论仍条件化于 observer、state
abstraction、dynamics、timing、actuation 和 fallback assumptions。

## 5. 方法、plumbing 与 intervention 的边界

| 层级 | 内容 | 进入论文主方法的条件 |
|---|---|---|
| 方法核心 | mission root、persistent contract、exact prefix authorization、execution/effect monitor | 直接定义两个关系或两个不变量 |
| Assurance plumbing | schema、digest、nonce、signature、provenance、attestation、wire、cache、Lean replay | 只描述其支撑的 TCB/实现属性，不独立列贡献 |
| Optional intervention | pass、projection、brake、replan、hard block、CBF、recovery | 作为可替换 policy 或 baseline；修改后 command 必须重新授权 |

任何新组件只有满足至少一个条件才能进入核心路径：

1. 关闭一个已定义、现有核心无法覆盖的攻击面；
2. 对两个不变量的可机检实现不可缺少；
3. 在预注册消融中产生独立 unique catch；
4. 为达到 clean utility/liveness gate 所必需且不改变安全属性。

否则它应留在 adapter、audit、baseline 或 appendix。组件数量、stage 数量和 proof artifact 数量都不是
贡献。

## 6. Verdict 与事务语义

统一外部 verdict 足够表达为：

- `allow`：形成 exact、fresh、单次 prefix authorization；
- `pending`：已检查执行，合同尚未完成；
- `complete`：checked completion 成立，可原子推进 phase；
- `reject`：已知违反 mission、contract、binding 或 hard invariant；
- `unknown`：输入、观测、checker 或 TCB evidence 不足。

`replan`、`project_or_brake` 和 `hard_block` 是 intervention decision，不是新的逻辑真值。内部实现可保留
更细诊断枚举，但 paper/API 主语义不得让 protocol vocabulary 取代方法属性。

所有转换遵守：先构造 judgment，后验证，再原子提交。验证前不得 dispatch；失败后不得推进 proposal
index、phase、deadline、budget 或 monitor history。

Fail-closed 是协议行为，不等于有用的防御。实验必须同时报告 block、unknown、deadlock、availability、
clean retention 和 recovery。

## 7. Lean 的角色

Lean 是 assurance mechanism，不是独立 novelty，也不应该成为每个 control step 的默认架构负担。

目标分工：

- Lean 定义两个不变量、核心 state transition 和 fast checker 必须满足的离散性质；
- 离线或低频路径验证 mission/contract template、checker equivalence 与关键 proof obligation；
- online control path 使用版本固定、确定性、可审计的 fast checker；
- full request 可在 shadow/offline 路径重放给 Lean，但 shadow 结果不授权历史 dispatch。

只有在建立 core theorem 与实际 wire/fast checker 的明确 refinement/equivalence 后，才能写“Lean-backed
online judgment”。若 online authority 仍来自 Python，只能写“Lean specification + Python reference
runtime”。当前逐 request 编译的 v1 Lean evaluator约 0.65--1.95 秒 p99，不支持 real-time claim。

现有 `CTDAV2Wire` 六阶段 parity 是可复用测试资产，但下一架构不要求保留六个公开 stage；它们可以折叠
进三个外部转换，只要历史 artifact 仍由只读 decoder replay。

## 8. 后续评估的最小证据

当前攻击复现 terminal 前不执行本节。恢复方法工作时，首先比较：

| arm | Intent–Plan | Plan–Execution | 目的 |
|---|---:|---:|---|
| VLA-only | 否 | 否 | unguarded 基准 |
| Intent-only | 是 | 否 | semantic authorization 的 unique catch 与误阻断 |
| Execution-only | 否 | 是 | binding/receipt/effect monitor 的 unique catch 与误阻断 |
| Dual | 是 | 是 | 检验两关系组合是否必要 |

CBF/AEGIS、SAFE/FIPER、RoboGuard/SafeGate 属于外部或可选 baseline，不替代上述因果消融。

执行顺序必须是：

1. fixed-trace/shadow：同一 proposal/trace 上测 unique catch、parity 和 latency；
2. clean closed loop：先通过预注册 retention、phase completion、deadlock 和 evidence coverage gate；
3. qualified attack：只使用已独立证明会造成 clean-safe→attacked-unsafe 的 workload；
4. optional intervention：最后评估 filter/recovery 是否改善 physical safety/utility。

若 Dual 没有同时显示两层独有收益，或 clean utility 仍不合格，应收缩为单层 monitor、offline audit 或
execution-integrity protocol，而不是继续增加 stage。

## 9. Claim boundary

当前允许写：

- 两类 integrity relation 与两个协议不变量已经明确定义；
- v1 的离散实现/parity 通过冻结测试，但 clean operational utility 在 evaluated slice/seed 上失败；
- v2 no-dispatch 资产建立若干局部 binding、parity、authentication 与 filter plumbing 性质；
- 当前系统是 simulator-scoped、slow-interlock/offline research prototype。

当前不允许写：

- 双层方法相对 single-layer、collision checker 或外部 baseline 已有总体防护收益；
- 已对发布 instruction/camera attack 建立 defense efficacy；
- Lean 证明了 raw continuous action、sensor truth、actuation truth 或机器人整体安全；
- digest/signature/provenance 单独建立 malicious-host resistance；
- zero-hold、CBF、replan 或现有 v2 plumbing 构成 verified recovery；
- clean utility、availability、real-time enforcement 或硬件安全可接受。

## 10. 历史兼容与未来版本规则

- CTDA v1 code、wire、protocol 和结果保持 immutable/replayable；
- CTDA v2 no-dispatch schema 和 artifact 作为历史实现资产保留，不给旧 JSON 补默认字段冒充新版本；
- 下一次方法恢复必须使用新的 method id、protocol、disjoint unit/seed 或明确的新实验单位和 fresh root；
- 新架构优先复用语义与测试，不承诺复用旧 stage 拆分、class hierarchy 或 runtime orchestration；
- 当前 VLA-only threat qualification terminal 后仍必须停止，等待用户明确授权，不能自动进入方法重构、
  clean pilot 或 attacked+defended comparison。
