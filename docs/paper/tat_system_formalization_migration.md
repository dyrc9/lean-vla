# TAT 系统描述与形式化迁移审计

更新日期：2026-08-18

## 1. 结论

TAT 最值得 ProofAlign 学习的不是它的轨迹误差指标，而是其系统论文组织方式：先指出现有完整性对象缺少物理运动语义，再定义一个顶层安全性质，随后依次给出程序模型、模型构造、运行时测量、验证规则和可信假设。这样读者始终知道每个组件在为哪个形式条件提供证据。

ProofAlign 已经拥有比 TAT 更明确的授权、receipt、effect 和 Lean 事务语义，但原稿将它们分散在 G1/G2/G3、Design 和 Implementation 中，没有首先凝结成一个统一的形式对象。本轮迁移因此集中在“组织和绑定”，而不是把 TAT 的离线参考轨迹移植到在线 VLA。

## 2. TAT 的有效写法

TAT 的核心论证链为：

1. **Background**：先解释工业机械臂控制器的 main computer、axis computer、运动规划和伺服控制边界，再介绍 remote attestation 的 prover/verifier 模型。
2. **Motivation**：把攻击拆成任务程序逻辑篡改和运动参数篡改，并说明 CFI/DFI 为什么不能唯一刻画物理轨迹。
3. **Threat Model**：明确 TEE、secure time、compiler、trampoline 和 instrumented task program 的可信假设；sensor spoofing 与 DoS 明确排除。
4. **Security Property**：先定义 Trajectory Integrity，并区分 movement event 与 static event 的时空要求。
5. **Program Model**：将任务程序形式化为 `G=(Σ,E,α,β,γ)`，明确节点、边、命令序列、reference profile 和跨分支 profile relation。
6. **Construction / Measurement / Verification**：分别说明 TMEG 如何产生、哪些运行时证据被采集，以及 verifier 如何用 duration、ATE、RPE 作出判断。
7. **Discussion**：将 vendor toolchain、TEE 接口、bypass encoder 和 offline profile 的部署限制逐项对应到系统设计。

这里最关键的写作习惯是：**形式对象中的每一项，都能在运行时找到生产它的组件和验证它的规则；每一个强结论，也都能追溯到明确的可信假设。**

## 3. 已迁移到 ProofAlign 的部分

### 3.1 可信任务图成为显式形式对象

将原先只在 prose 中出现的 task graph 写成：

```text
G_T = (V_T, E_T, ℓ_T, Φ_T)
```

- `V_T`：合法任务阶段；
- `E_T`：允许的阶段转换；
- `ℓ_T`：节点到 canonical skill/entity tuple 的映射；
- `Φ_T(O_t^T)`：可信状态下当前启用的 frontier。

Selector 只能从 `Φ_T(O_t^T)` 中产生 `Z_t`，否则返回 `unknown`。这借鉴了 TAT 用图结构把程序路径和 motion profile 关系说清楚的方式，但 ProofAlign 的图只表达语义合法性，不伪装成参考轨迹。

### 3.2 将系统流程分成三个阶段

系统 Overview 现在明确区分：

1. **construction and qualification**：编译任务图、注册 checker/effect vocabulary、资格化实现；
2. **online authorization**：冻结可信状态和子任务、接收唯一 ActionBlock、评估、编译 contract、必要时筛选 guard；
3. **execution closure**：一次性授权、唯一 dispatch boundary、有序 receipts/effects、阶段推进。

这对应 TAT 的 profile construction、runtime measurement、remote verification 三段式表达，使组件职责不再混在一段 runtime prose 中。

### 3.3 明确三个证据端点

借鉴 TAT 的 endpoint measurement 思路，ProofAlign 现在显式说明：

- authority tap 只能建立任务和可信 observation authority；
- dispatch boundary 只能证明 actuator interface 实际接受的命令；
- post-dispatch effect window 只能建立 dispatch 之后的效果证据。

端点之外的日志不能被提升为对应安全事实。这比笼统地说“系统记录了很多 digest”更接近系统安全论文的证据模型。

### 3.4 定义统一的顶层性质

对最终 Dual 系统，将单次 proposal 的对象收集为：

```text
χ_t = (T, O_t^T, Z_t, A_t, S_t, C_t, Auth_t, R_t, E_t, g_t)
```

并定义：

```text
ProofAligned(χ_t) :=
    L1_t
  ∧ L2a_t
  ∧ (Triggered_t → L2b_t)
```

阶段推进还必须同时满足 task-completion atoms。这个定义将原先分散的 G1/G2/G3 变成一个可追踪的顶层性质，同时保留“checker-relative”边界。

### 3.5 将 L2b 从阈值 prose 变成验证条件

触发后的 guard 必须同时满足：同一个 source action、snapshot restoration、14 个 joint-side 的最小预测 margin 不低于 `0.15 rad`、force proxy 不高于 `10000`。该定义只覆盖冻结 simulator 中注册的 joint-side containment，不扩张成任意物理安全或轨迹完整性。

### 3.6 补强 Lean 的有序逐步动作绑定

Python 已保存完整 `final_command` 和二维 shape，并在第 `i` 步用 `authorization.action_at(i)` 核对 applied action。原 Lean 只证明 receipt 内的 `appliedActionDigest = authorizedActionDigest`，没有把 receipt 自报的 authorized digest 连回授权对象中的第 `i` 项。

本轮在 `ActionBlock` 和 `PrefixAuthorization` 中加入 typed `orderedActionDigests`，并新增：

- `authorization_binds_ordered_actions`；
- `every_bound_receipt_matches_authorized_step`。

现在 Lean 证明每个 bound receipt 的 `stepIndex` 在授权的有序列表中解析为实际 applied digest。Python 仍额外负责 contiguous receipt indices；Python canonical tuple/serializer 到 Lean digest list 的完整 refinement proof 尚未建立。

## 4. 不应迁移的部分

以下 TAT 机制依赖预编程工业任务，不能直接移植到在线 action-only VLA：

- 从 10--15 次离线执行拟合 reference trajectory；
- 以 ATE/RPE 和 `4σ` 阈值定义轨迹一致性；
- 将 task program 的事件路径视为权威 motion program；
- TEE remote attestation、secure time 与 bypass raw encoder 所提供的硬件信任；
- 将“符合 reference path”解释为 ProofAlign 的自然语言任务一致性。

ProofAlign 的在线 ActionBlock 在产生前不存在唯一 intended trajectory，而且一个合法子任务允许多条轨迹。强行引入 TAT 的 profile 会改变问题定义，并可能把代理阈值误写成任务语义证明。

## 5. 仍需保留的形式化边界

迁移后仍不能声称“形式化验证了机器人安全”：

- Lean 不证明 `T` 正确、`Z_t` 选择正确或 local checker 对现实后果正确；
- task graph/frontier selector 尚未在 Lean 中重建，只通过冻结语料资格化；
- Python serializer、observer 与 Lean 抽象对象之间没有完整 refinement proof；
- guard/controller configuration 尚未作为独立 typed digest 进入 `BlockExecutionContract`；
- effect observer、trusted tap 和 simulator-to-robot relation 仍是可信或资格化假设；
- 当前系统没有 TAT 的硬件 root of trust、bypass encoder 或 remote attestation guarantee。

因此最准确的系统定位仍是：**ProofAlign 定义并检查一个 checker-relative、跨层绑定的在线 VLA 执行事务；Lean 检查其中有限的 identity/authorization/receipt/evidence/phase-transition semantics。**
