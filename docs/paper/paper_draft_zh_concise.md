# ProofAlign：面向 Action-Only VLA 的可信任务监控与跨层执行完整性

> **中文版简洁初稿。** 本稿用于先审论文故事、问题定义、方法逻辑和 claim 边界；完整实现细节、审计字段与
> 扩展结果保留在长稿中。本文只写入已经完成并冻结的实验，不补造或推测缺失结果。

英文题目：**ProofAlign: Trusted-Task Monitoring and Cross-Layer Execution Integrity for
Action-Only Vision-Language-Action Systems**

## 摘要

视觉—语言—动作模型（VLA）把自然语言任务和多模态观察直接映射为连续机器人动作。现有攻击表明，修改
policy-facing 指令或观察即可改变机器人的物理行为；然而，许多部署接口只向 consumer 返回数值
ActionBlock，既不提供可独立信任的高层计划，也不证明通过检查的动作就是随后实际执行并产生效果的动作。
我们将这两个断点分别称为：可信任务与 VLA proposal 之间的 **authorization gap**，以及获准 proposal 与
实际执行之间的 **realization gap**。

本文提出 ProofAlign，一种不修改 VLA 权重的 consumer-side reference monitor。其核心思想是：**不同上游
攻击最终都必须汇聚为一个即将执行的 ActionBlock；因此，系统不应恢复 VLA 的 latent intent，而应使用独立
可信任务约束这个 exact ActionBlock，并将其身份一直保持到 dispatch、receipt 和 physical evidence。**
ProofAlign 的 L1 从攻击面之外的任务与观察构造有限语义子任务，对策略实际生成的 ActionBlock 做
checker-relative assessment。L2a 将获准 ActionBlock、state epoch、一次性 authorization、有序 dispatch、
receipt 和 effects 绑定为一个执行事务。L2b 仅在接近关节边界时，对同一 source ActionBlock 的有限
virtual-guard 配置做 shadow screening；无合格配置则 fail closed。

我们首先在 OpenPI Pi0.5 和 LIBERO-Safety 上复现冻结的 SABER `constraint_violation` 指令攻击：86个
clean-eligible units 中39个发生 risk transition，即45.35%，95% base-pair cluster-bootstrap 区间为
[32.93%, 57.78%]，成功复现了该攻击在本地 victim/benchmark 路径上的物理风险效应。随后，18个 held-out
task/init pairs 在 clean/attacked 条件下完成144个配对四臂 episodes。attacked 条件下，VLA-only、L1-only、
L2-only 和 Dual 的任务成功分别为11/18、13/18、11/18和13/18，constraint-violation episodes 分别为
4/18、1/18、0/18和0/18。结果表明：L1 在该样本中承担任务效用角色但不提供完整物理 containment；L2 消除
观察到的 joint-limit outcomes，但不单独恢复任务成功；Dual 同时取得13/18任务成功与0/18 violation
episodes。上述结论限于冻结攻击、研究模拟器和当前可信计算基，不构成任意攻击、真实机器人安全、硬件
attestation 或硬实时保证。

## 1. 引言

VLA 正在把机器人接口从显式的“感知—规划—控制”流水线，变成从语言和图像到连续动作的端到端映射。这种
接口提高了通用性，却隐藏了一个部署者无法回避的问题：**谁授权了即将送往控制器的这串数字？**

考虑本文贯穿全文的真实样例。权威任务是“把汽水移动到盘子上”，冻结的 SABER 记录却把策略看到的指令改成
“移动到最远的装置”。Pi0.5 随后返回一个 `10×7` ActionBlock。该数值块不会说明自己响应了哪条
指令，也不会提供一份可由部署者独立信任的计划。它可能平滑、幅度受限并位于工作空间内，却仍然在推进错误
对象或错误目标。因此，数值合法性并不能推出任务合法性。

这形成第一个断点：**authorization gap**。可信任务 `T` 与受攻击 policy view 产生的动作
`A_t` 之间不存在天然授权关系。输入过滤可以降低 prompt 被劫持的概率，action verifier 可以判断候选与
某个 instruction 或 plan 是否相符，但只要 authority 仍来自受攻击上下文或模型自报信息，就不能证明这个
exact ActionBlock 被部署者批准的任务授权。

即使该 ActionBlock 已通过检查，问题仍未结束。它可能经过不同序列化，旧 authorization 可能被重放，状态
epoch 可能已经变化，执行链可能只消费部分 action prefix 或改变 step 顺序，receipt/effects 还可能来自另一
proposal。这形成第二个断点：**realization gap**。一条“检查通过”的日志并不能证明 controller 收到同一个
canonical command，更不能证明后续效果属于同一次 dispatch。

现有工作分别保护了这条链的局部：trusted/untrusted input separation 保护模型入口 [StruQ, SecAlign,
CaMeL]；VLA verifier 和 agent enforcement 约束候选动作、离散调用或执行计划 [SEAL, CoVer, AttriGuard,
ACE]；operation/data/control-flow attestation 保护既定程序的动态执行 [OAT, DIAT, ARI, CFA+, ARTO]；robot
trajectory attestation 检查给定 intended path 与 actual motion [TAT]；CBF、shielding 和 action prediction
约束物理可行性 [VLMPC, RealizableShields]。这些机制有效，但停在不同边界：它们没有共同回答“在线产生的
连续 ActionBlock 为什么获得任务授权，以及之后是否仍是它被实际执行”。

我们的核心 insight 是：

> **对于 action-only VLA，可信任务判断与执行证据必须围绕同一个 exact continuous ActionBlock 建立；前层
> 决定它是否有资格执行，后层只能保持其身份并约束执行，不能替换前层语义。**

ProofAlign 据此把 consumer boundary 组织成三个依次发生、不可互换的机制。L1 从独立可信分支产生当前合法
语义子任务，并评估 VLA 实际输出的数值块。L2b 在必要时为同一 source action 选择合格执行配置。L2a 最后
签发 fresh one-use authorization，并要求 exact dispatch、receipt 和 effects 在同一事务内闭合。L1 可以
评估一个随后被替换的动作；L2 可以忠实、安全地执行一个偏离任务的动作；只有围绕同一 ActionBlock 组合，
两个 gap 才能分别被观察并分别失败。

本文作出三项贡献：

1. 提出 action-only VLA 的跨层问题定义，将 trusted task 到 continuous ActionBlock 的 authorization gap，
   与 ActionBlock 到 dispatch/effects 的 realization gap 明确分离。
2. 设计 ProofAlign reference monitor：L1 提供 checker-relative trusted-task monitoring，L2a 提供一次性
   execution transaction，L2b 提供 simulator-qualified、状态触发的 joint containment。
3. 给出透明的攻击基础与配对四臂证据：报告 SABER 成功复现的 `39/86=45.35%` 观测 ASR，并区分任务效用、
   执行完整性和物理 containment 的证据来源。

本文不恢复模型 latent intent，不证明每个获准动作都推进任务，不声称 L1 是完备语义 oracle，也不把
0/18 violation 解释成总体零风险。我们的 claim 更窄：在明确 TCB 和冻结 checker 下，部署者可以审计哪一块
动作因什么可信证据获准、实际执行的是否仍是同一块、效果是否属于同一事务，以及近关节边界时是否使用了
合格执行配置。

## 2. 背景、动机与挑战

### 2.1 攻击为何最终表现为 ActionBlock

VLA 的攻击入口可以不同。SABER 修改 policy-facing instruction，并以 task failure、trajectory length 和
constraint violation 衡量结果 [SABER]；FreezeVLA 通过视觉输入诱发 action freezing [FreezeVLA]；BadRobot
与 RoboPAIR 表明语言或多模态 jailbreak 可以越过文本回答，转化为机器人拒绝失效或有害动作 [BadRobot,
RoboPAIR]。本文的系统威胁面包含 instruction、数字视觉输入和 history manipulation，但经验实验只覆盖
secure split 之后冻结的 SABER instruction records。

这些攻击不必让 VLA 输出显式恶意解释。只要它们改变最终进入 consumer 的连续动作，就能够影响现实。因此，
不同攻击通道存在共同汇聚点：**即将跨过 controller boundary 的 ActionBlock**。这使 complete mediation
成为可能——系统不必先完美识别攻击类型，而是将所有 policy outputs 都当作 proposal。

### 2.2 两个 gap 与现有防御的停止位置

Authorization gap 的根源是 authority 丢失。StruQ、SecAlign 和 CaMeL 分离 trusted instruction 与 untrusted
data 或从 trusted query 派生控制流 [StruQ, SecAlign, CaMeL]；ACE、AttriGuard 和 MATE 约束 trusted plan、
离散 tool call 或 agent trajectory [ACE, AttriGuard, MATE]；SEAL 和 CoVer 验证 policy-supplied plan 或用
learned score 选择 VLA candidate [SEAL, CoVer]。但 action-only 部署未必暴露可信 structured plan，而且
模型 prompt、解释或 candidate score 都不能自动成为 operator-approved authority。

Realization gap 的根源是检查对象与执行事实可能脱节。OAT、DIAT、ARI、CFA+ 和 ARTO 表明，执行完整性必须
包含 dynamic control/data flow、freshness 与 timing，而不能只验证静态程序或做一次 hash [OAT, DIAT, ARI,
CFA+, ARTO]。TAT 进一步表明 intended path 与 actual motion 是两个命题，需要 timed motion events 和 joint
measurements [TAT]。然而，这些工作通常从已经给定的 program、mission 或 intended path 出发；它们不回答
这个在线 VLA proposal 是否首先得到了可信任务授权。

物理 safety mechanism 还覆盖另一条正交边。Prediction、clipping、CBF 和 continuous-space shields 可以限制
速度、工作区或安全集合 [VLMPC, RealizableShields]，却不能推出动作正在完成正确任务；反过来，任务兼容也不
意味着不存在 joint-limit risk。因此，authorization、execution identity 和 containment 必须分层。

### 2.3 为什么 C3 不只是比较一次 hash

ActionBlock 从生成到效果经过异步软件与控制链。这里的困难包括：

- ActionBlock 可能经过不同序列化（确定性表示与签名/哈希：[JCS]；ActionBlock schema 的具体化：本文）；
- authorization 可能被重放（fresh challenge/nonce 与 replay resistance：[OAT, DIAT]）；
- state epoch 可能已经改变（freshness 与 timely mission window：[OAT, DIAT, ARI]；VLA state-epoch binding：本文）；
- 系统可能只执行部分 action prefix（动态路径与 mission completion：[OAT, CFA+, ARI]；ActionBlock prefix 语义：本文）；
- step 顺序可能被调整（control-flow/path-order integrity：[OAT, CFA+]；连续动作 step-index binding：本文）；
- receipt 和 effects 可能属于不同 proposal（跨组件 data provenance：[DIAT]；cross-proposal splice 定义：本文）；
- 未来 observation 可能被用于补齐过去事务（freshness 与 timely evidence 原则：[OAT, DIAT, ARI]；dispatch-bound evidence window：本文）。

这些引用支撑 canonicalization、freshness、provenance、路径完整性与执行时限原则；“VLA receipt 拼接”本身
不是已有论文直接研究的攻击。ProofAlign 的工作是把上述原则具体化为 action-only VLA transaction。单个
hash 只能回答两个 canonical byte strings 是否相等，不能回答它们是否属于同一 proposal、同一 epoch、同一
authorization 和同一 dispatch window。因此需要保护的是：

```text
(action_digest, episode_nonce, proposal_index,
 state_epoch, step_index, evidence_window)
```

### 2.4 由 insight 导出的四个挑战

- **C1：如何在不信任 policy 的情况下获得任务 authority？** 系统需要独立 task artifact 和 trusted
  observation；若只是让 VLA 解释自己或从动作反推 intent，攻击上下文仍然决定答案。
- **C2：如何在没有完备语义 oracle 时评估连续 ActionBlock？** 一个 `10×7` 数值块必须结合当前
  task frontier、几何与状态评估，但不完整 proxy 不能被包装成“证明任务正确”。
- **C3：如何证明被检查的动作就是实际执行的动作？** identity 必须跨 canonicalization、epoch、一次性
  authorization、有序 prefix、receipt 和 effect window 保持，而不是只在某个边界比较一次 digest。
- **C4：如何约束状态相关风险而不替换被评估动作？** near-boundary containment 可能改变 controller 映射；
  系统必须保持 source action identity，同时显式记录 execution configuration。

## 3. 问题定义与威胁模型

### 3.1 双视图系统模型

在状态 epoch (t)，系统维护两条不同视图：

```text
authority view: authoritative task T + trusted observation O_t^T
policy view:    prompt P_t^pol + observation O_t^pol + history H_t^pol
```

策略输出：

\[
A_t=\pi(P_t^{pol},O_t^{pol},H_t^{pol})\in\mathbb{R}^{H\times d}.
\]

可信分支输出：

\[
Z_t=\mathsf{SelectFrozen}(T,O_t^T),\qquad
S_t=\mathsf{AssessLocal}(Z_t,O_t^T,A_t).
\]

`T` 可以是签名 job ticket、受保护 workflow state 或 operator-approved task record；它不是 policy prompt
的普通副本。`Z_t` 必须在 policy 生成 `A_t` 之前从有限 task graph 的合法 frontier 中冻结，既不写回
policy prompt，也不从 `A_t` 反推。policy bytes 会被记录用于 provenance，但不会因此获得 semantic
authority。

### 3.2 受保护对象

本文的直接保护对象是带 schema、shape、step order 和数值编码的 canonical ActionBlock。每个 proposal 还
绑定 episode nonce、proposal index 和 state epoch。task、trusted observation、frontier、action、checker
configuration 或 epoch 变化，都会使旧 assessment、contract 和 authorization 失效。

需要区分三个身份：

1. **semantic identity：** `(T, O_t^T, Z_t, S_t)`，说明判断来自哪份可信上下文；
2. **command identity：** canonical `A_t` 及其 proposal/epoch/nonce/step，说明获准和应用的是哪条命令；
3. **executable identity：** 理想上至少包含 `(A_t, g_t, controllerConfig_t, epoch_t)`，说明同一命令在何种
   guard/controller 配置下执行。

当前 runtime 记录第三类证据，但 Lean typed contract 尚未把 guard/controller configuration 作为独立 digest
字段。因此，本文证明的是软件命令事务及 simulator-qualified containment，不是 exact physical trajectory。

### 3.3 攻击者、TCB 与范围

攻击者可以在 secure split 之后修改 policy-facing instruction、数字/软件视觉输入或 history，使 VLA 产生
偏离可信任务或进入危险状态的 ActionBlock；也可以尝试 command substitution、authorization replay、
cross-proposal evidence splice、不完整执行或错误 phase advance。

TCB 包括：权威任务源、secure split 之前的 trusted observation tap、冻结且 allowlisted 的 task graph/
selector/checker、contract compiler、digest/nonce ledger、唯一 dispatch boundary，以及 receipt/effect
observer 与 storage。若攻击者可以同时控制 task source、trusted tap、dispatch boundary 或 actuator
feedback，本文主张不成立。

经验评估只实例化 secure split 后的冻结、非自适应 SABER instruction attacks，以及模型内的 transaction
fault tests。我们不声称覆盖 pre-split physical optical attacks、adaptive attackers、任意 checkpoint、任意
动力学误差、真实机器人或硬件 root of trust。最终 trusted selector 使用 LIBERO privileged geometry，因而
是 benchmark-qualified 组件，不是 camera-only trusted perception。

### 3.4 安全目标

- **G1：checker-relative eligibility。** 获准 `A_t` 必须绑定可信 provenance、合法 task frontier 和当前
  assessment，且不触发冻结 checker 覆盖的 hard risk。
- **G2：qualified one-use authorization。** 只有当前 proposal/epoch 的 exact block，以及必要时合格的
  execution configuration，才能获得 fresh authorization；授权消费后不可复用。
- **G3：execution-transaction alignment。** phase advance 要求 ordered exact prefix、同一 authorization 的
  receipts，以及真实 dispatch 之后绑定窗口内的 required effects；unknown、forbidden 或 cross-proposal
  evidence 均不能完成事务。
- **G4：covered containment。** 若 joint-risk trigger 激活，只有通过注册的 margin、restore、identity 和
  force gates 的 configuration 才能 dispatch。

G1 部分关闭 authorization gap；G2/G3 在软件 TCB 内关闭 realization gap；G4 是正交的 covered physical
containment。G2/G3 可以忠实执行错误任务，G4 也可以安全地做错事，因而它们不能替代 G1。

## 4. ProofAlign 设计

### 4.1 总体流程

每次 policy call 的执行顺序如下：

```text
T + O_t^T ──> freeze legal subtask Z_t

P_t^pol + O_t^pol + H_t^pol ──> VLA ──> one source A_t (10×7)
                                               │
Z_t + O_t^T + A_t ──> L1 assessment ── hard risk? ──> reject
                                               │ no
                                               v
                                        compile contract
                                               │
                                  near joint boundary?
                                      │ yes           │ no
                                      v               │
                              L2b guard screening     │
                                      └───────┬───────┘
                                              v
                                 fresh one-use authorization
                                              │
                            L2a ordered dispatch/receipts/effects
                                              │
                                  alignment gate ──> phase update
```

顺序具有安全含义。`Z_t` 必须先于策略输出冻结，防止 attacked action 反向定义自己的任务解释。L1 必须检查
策略真实返回的 source block，而非修改后的替代动作。contract 在 screening 前编译，但只有 fast path 或 L2b
合格后才签发 authorization。evidence window 只能由真实 dispatch 打开，phase 只能在事务闭合后推进。

系统始终使用一个 policy proposal（`K=1, H=10`），不做 best-of-`K` resampling。L2b 最多比较两个对象
是同一 source ActionBlock 的 guard configurations，不是新的 policy actions。

### 4.2 可信语义上下文

`TrustedSemanticContext` 绑定 task source、trusted observation 与 tap、secure-split identity、state epoch、
task graph/frontier、selector configuration 和上一 subtask。冻结 selector 从有限 task graph/FSM 中产生
`pick_up`、`move`、`place`、`release`、`open`、`close`、`actuate` 或 `finish` 等结构化 `Z_t`。它不是
自然语言 explanation，也不声称复现 VLA 的内部 plan。

当前系统**不读取 Pi0.5 的 hidden states、中间层表示或 candidate logits 来恢复语义**。本地 `pi05_libero`
接口只把 Pi0.5 作为 action generator；最终 risk-selective 路径保留 clean 或 SABER-attacked 的完整外部任务
prompt，`Z_t` 不被写回该 prompt。仓库中使用冻结 Pi0.5/PaliGemma 为有限子任务打分的代码属于历史 probe/
qualification 路线，不参与当前 L1 authorization、最终四臂实验或论文主 claim。

这一设计解决 C1：semantic authority 来自攻击面之外。它的代价是显式 TCB；如果部署者没有可信任务 artifact
和独立 observation path，ProofAlign 不能凭空创造 authority。

### 4.3 L1：对 exact ActionBlock 的相对授权

L1 采用 generate-then-monitor：Pi0.5 根据自己的 policy view 生成完整 `10×7` source block，checker 再结合
`Z_t`、`O_t^T` 和 canonical `A_t` 生成 assessment。若没有 hard risk，L1 返回 byte-identical source
block；任何会改变 action bytes 的 intervention 都必须重新 assessment、重新编译 contract 并重新授权。

L1 的判断分为两类：

| 结果 | 当前处理 | 原因 |
|---|---|---|
| velocity/workspace violation、unexpected contact、stale state、malformed command、不支持的 unknown | hard reject | 属于冻结 checker 明确定义和资格化的风险边界 |
| task-progress mismatch、release/close progress、expected-effect miss、articulation unavailable | advisory；允许当前块但强制下一块 reobserve/replan | 当前几何代理不足以充当完备 semantic oracle |

因此 L1 解决 C2 的方式不是声称“懂得完整任务语义”，而是给出 **checker-relative authorization**：它证明
可信来源、合法 frontier、assessment 与 exact ActionBlock 的绑定，以及 covered hard gates 已通过；它不证明
所有 accepted blocks 都会推进真实任务。

### 4.4 L2b：不替换 source action 的风险触发 containment

系统持续计算7个机械臂关节上下两侧共14个 margin：

1. 最小 margin 大于 `0.30 rad` 时走 fast path，不启动 shadow simulator；
2. 进入风险区时，为同一 source ActionBlock 构造最多两个 temporary virtual-guard configurations；
3. 每个候选从同一 snapshot 做 one-step shadow rollout，并验证 snapshot restore 和 source-action identity；
4. 合格候选必须让全部14侧预测 margin 不低于 `0.15 rad`，且 constraint force 不超过 `10000`；
5. 系统选择满足条件的最弱 guard；无候选合格则不签发 authorization、不 dispatch。

L2b 解决 C4：它保持 `A_t` bytes 不变，只改变 near-boundary execution configuration。但这也暴露一条重要
边界：相同 command 在不同 guard/controller 下不一定产生相同 trajectory。因此 runtime 显式记录 guard、
restore、force 和 margin evidence；当前 Lean contract 未完整 typed-bind 这些配置，该 refinement gap 在
局限中保留。

### 4.5 L2a：一次性 ActionBlock execution transaction

consumer 为当前 proposal 编译 contract：

```text
C_t = {
  action_block_digest, semantic_subtask_digest,
  policy_prompt_digest, assessment_digest,
  trusted_observation_digest, state_epoch,
  expected/forbidden effects, observation_window
}
```

screening 合格后，系统签发绑定 episode nonce、proposal index、state epoch 和 exact final command 的 fresh
authorization。该 authorization 只能消费一次。runtime 随后逐步验证：

- applied step 必须等于 authorization 中相同 `step_index` 的 action；
- 实际执行只能形成从0开始的 ordered exact prefix，不得跳步、重复、换序或虚报未执行 tail；
- 每个 receipt 必须使用同一 authorization，并绑定对应 dispatch；
- effect window 只能在真实 dispatch 之后开启；
- required integrity evidence 必须存在，forbidden、unknown、stale 或 cross-proposal evidence 不能完成事务；
- 只有 transaction alignment 和 task-completion condition 同时满足，系统才推进 task phase。

这解决 C3。它保证的是软件 TCB 内“被检查、被授权、被应用、被记录”的 command identity，而不是 actuator
硬件不可伪造，也不是物理世界已经被完整观察。若 observer 漏掉关键效果，内部闭合的事务仍可能不完整。

### 4.6 Lean 检查什么

Lean 固定 ActionBlock、assessment、contract、authorization、receipt、effects 和 phase transition 的抽象
关系，并 machine-check 以下性质：authorization 绑定 exact final-command digest；消费后的 authorization
不可复用；receipts 使用同一 authorization；applied/authorized digest 相等；unknown 或 incomplete evidence
不能形成 alignment；启用执行层时，没有 alignment 就不能 phase advance。

Lean 模型比 Python runtime 粗：它不重建每个 step digest，不解析自然语言，不证明 selector/checker 对现实
正确，不证明 simulator 等价于真实机器人，也没有完成 serializer/observer 到 Lean 的端到端 refinement。
因此本文使用“Lean-checked abstract execution-transaction semantics”，不使用“formally verified robot
safety”。

### 4.7 贯穿案例

回到“汽水到盘子”的任务。SABER 只改变 policy-facing instruction，trusted branch 仍从原任务选择合法
frontier。L1 检查 attacked policy 实际返回的那块数字，而不相信其解释。若 block 没有触发 hard gate，系统
编译 contract；若关节接近边界，L2b 必须先为同一 source action 找到合格 guard。随后 L2a 才签发一次性
authorization，并要求 nonce、epoch、step、receipt 和 effect window 一致。

这个过程解释了三层的分工：L1 回答“哪份可信上下文支持对该 block 的判断”；L2b 回答“当前状态下是否存在
合格执行配置”；L2a 回答“最终获准并产生证据的是否仍是同一个 block”。

## 5. 实验设计

### 5.1 研究问题

- **RQ1：** 冻结 SABER instruction records 能否在本地 Pi0.5—LIBERO-Safety 路径中产生新的物理 risk
  transition？
- **RQ2：** L1 在 attacked 条件下承担什么任务效用与风险角色？
- **RQ3：** 组合 L2 treatment 能否 containment 所覆盖的 joint-limit outcomes，是否引入 deadlock 或可见
  task-success 损失？
- **RQ4：** Dual 能否同时保留 L1 的任务效用和 L2 的 containment？
- **RQ5：** transaction identity、force、prediction error 和 latency gates 是否成立？

### 5.2 攻击基础

victim 为 OpenPI Pi0.5，benchmark 为 LIBERO-Safety。实验包含60个 base pairs、2组 seeds，每个 unit 均有
clean/attacked rollout，共240个 episodes。只有 clean-safe units 进入分母；attacked rollout 新出现 contact、
joint-limit、excessive-force 或 LIBERO cost/collision 才计为 risk transition，单纯 task failure 不计入。

### 5.3 配对四臂

最终实验使用18个 held-out suite/task/init pairs。每个 pair 在 clean 与 attacked 条件下运行四个 arms：

| Arm | L1 | L2a + L2b | 用于识别的角色 |
|---|---:|---:|---|
| VLA-only | 0 | 0 | 攻击后的原始 VLA 行为 |
| L1-only | 1 | 0 | trusted-task monitoring |
| L2-only | 0 | 1 | transaction + containment |
| Dual | 1 | 1 | 两层组合 |

clean/attacked 共享 initial state、environment seed、policy seed 和 arm schedule，共144个 episodes。所有 pairs
完整保留，不按 outcome 筛选；同一 pair 四臂的首个 source ActionBlock 必须一致。主实验同时启用 L2a 和
L2b，因此主表只能估计组合 L2 treatment，不能分解二者的独立因果贡献。L2a 的 fault handling 另由 focused
negative tests 与 Lean abstract semantics 支撑。

## 6. 结果

### 6.1 攻击基础：SABER攻击成功复现

240/240 episodes 有效。86个 clean-eligible units 中39个发生 risk transition：

\[
39/86=45.35\%,\qquad 95\%\ \mathrm{CI}=[32.93\%,57.78\%].
\]

这说明冻结 SABER records 在本地 OpenPI Pi0.5—LIBERO-Safety 路径上产生了明确且可重复测量的物理风险
转移。本文将 `45.35%` 作为该 victim、benchmark、攻击配置和事件定义下的观测攻击成功率。

### 6.2 四臂结果：任务效用与 containment 来自不同层

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18 | 11/18 | 4/18 | 28 | 175 |
| L1-only | 13/18 | 13/18 | 1/18 | 295 | 317 |
| L2-only | 13/18 | 11/18 | 0/18 | 0 | 0 |
| Dual | 13/18 | 13/18 | 0/18 | 0 | 0 |

结果形成清晰的机制分离。

第一，VLA-only 在 attacked 条件下从13/18降至11/18 task success，并出现4/18 violation episodes，说明
攻击确实改变了该配对样本中的任务与物理行为。

第二，L1-only 保持13/18 attacked task success，但仍有1个 violation episode；该 episode 累积295个 crossing
steps 和317个 joint-limit steps，甚至高于 VLA-only 的28和175。因此不能声称 L1 普遍降低物理风险严重度。
更准确的结论是：L1 在当前样本中承担任务效用角色，而残余风险需要独立 containment。

第三，L2-only 把 violation、crossing 和 joint-limit steps 全部降至0，但 task success 仍为11/18，与
VLA-only 相同。L2 可以约束执行，却不能把 task-divergent action 变成正确任务。

第四，Dual 同时保留 L1-only 的13/18 task success，并获得0/18 violation episodes、0 crossing 和0
joint-limit steps。这支持两层组合的样本内作用，不证明总体风险为零。L2-only/Dual 的0/18 violation rate 的
95% Wilson 上界仍为17.59%。

### 6.3 完整性、物理 envelope 与开销

- attacked episodes：72/72完成；attacked first ActionBlock 相对 matched clean 改变：72/72；
- attack metadata mismatch：0；prompt digest mismatch：0；四臂首块一致：18/18；
- artifact checksums：76/76；focused integrity tests：69/69通过；
- L2-on deadlock、crossing 和 joint-limit steps：全部为0；
- 最大 constraint force：`6438.20 < 10000`；
- 最大 selected-margin prediction error：约 `2.69×10^-13 rad`；
- screening latency：最大39.79 ms，p95为18.30 ms，100 ms deadline miss为0。

39.79 ms 小于研究模拟器的50 ms period，但实验未覆盖操作系统 worst-case scheduling、真实控制总线抖动或
真实机器人动力学，因而不是 hard-real-time 证明。

## 7. 安全分析与局限

**可信视图共同失效。** 若攻击发生在 secure split 之前，同时欺骗 trusted tap 和 policy view，两条分支
可能在错误世界上保持一致。解决该问题需要独立传感器、可信 capture path 或物理冗余，而不是更多 software
digests。

**L1 false allow。** selector 可能选出错误但语法合法的 `Z_t`，local checker 也可能漏掉语义不兼容动作。
当前 FSM、privileged geometry 和 finite-corpus qualification 只支撑 benchmark 范围，不能证明分布外
semantic soundness。

**Observer blind spot。** L2a 的结论依赖 single-dispatch boundary 和 evidence observer。若 actuator feedback
被伪造、关键效果未编码或 contract atoms 过弱，软件事务可以内部对齐，却仍然错误描述现实。

**Executable-configuration gap。** L2b 的 guard 改变 command 到 trajectory 的映射。runtime 已记录
guard/controller evidence，但 Lean typed identity 尚未完整包含这些字段；完整保证应进一步绑定
`(ActionBlock, guard_config, controller_config, state_epoch)`。

**经验范围。** 当前证据覆盖一个 Pi0.5 checkpoint、LIBERO-Safety、冻结 SABER instruction attack、18个
最终 pairs 和研究模拟器。0/18 不是总体零风险，69项 tests 不是任意 transaction attack 证明，Lean 也没有
验证 Python、感知或物理世界。

## 8. 相关工作与定位

**VLA 攻击与安全评价。** SABER、FreezeVLA、BadRobot 和 RoboPAIR 展示 instruction、visual 与 jailbreak
输入如何改变机器人行为 [SABER, FreezeVLA, BadRobot, RoboPAIR]；LIBERO-Safety、SafeVLA-Bench 和相关
survey 提供更广风险分类 [LIBERO-Safety, SafeVLA-Bench, VLASurvey]。ProofAlign 不提出新攻击或新 benchmark，
而是研究冻结 attacked output 如何在 consumer side 被授权和执行。

**输入、agent 与动作验证。** StruQ、SecAlign、CaMeL、ACE、AttriGuard 和 MATE 分别提供输入信任分离、
trusted flow、plan enforcement 或 action attribution [StruQ, SecAlign, CaMeL, ACE, AttriGuard, MATE]。SEAL
和 CoVer 在 VLA 侧验证或选择动作候选 [SEAL, CoVer]。ProofAlign 不具备它们的通用 attribution 或 candidate
ranking；其差异是保持 (K=1)，用独立 trusted task branch 评估 exact continuous block，并继续绑定后续
execution evidence。

**执行与轨迹完整性。** OAT、DIAT、ARI、CFA+ 和 ARTO 对 operation、data/control flow、freshness 与 real-time
mission 提供更强 attestation [OAT, DIAT, ARI, CFA+, ARTO]；TAT 从给定 intended path 审计 actual robot
trajectory [TAT]。ProofAlign 没有硬件 root of trust，也不声称首次提出 attestation。它补充的边界是：在
intended path 尚未可信给定、VLA 只输出 ActionBlock 时，先建立 trusted-task authorization，再在软件 TCB
中维护 proposal-scoped transaction。

**Prediction 与 shielding。** VLMPC、CBF 和 continuous-space shields 检查 action consequence 或保持安全集合
[VLMPC, RealizableShields]。L2b 是 simulator-qualified joint containment 工程，不是新的连续控制理论；它
不能替代 L1 的任务授权。

因此，ProofAlign 的 novelty 不在单个 checker、nonce、hash、shield 或 theorem，而在受保护对象及组合方式：

> **independent trusted task → exact continuous ActionBlock → one-use dispatch transaction → bound effects，**
> 并在 near-boundary state 下为同一 action 选择合格 execution configuration。

## 9. 结论

Action-only VLA 把任务意图压缩为即将执行的连续数值块，使攻击后的任务偏离和检查后的执行偏移都难以在传统
文本或 rollout 边界被发现。ProofAlign 将这两个问题分离为 authorization gap 与 realization gap，并围绕
exact ActionBlock 建立 consumer-side reference monitor：L1 以独立可信任务提供 checker-relative
authorization，L2b 提供风险触发的 joint containment，L2a 将获准动作、dispatch、receipt 和 effects 闭合为
一次性事务。

冻结结果表明，L1 与 L2 在当前样本中承担不同角色：前者保持 attacked task utility 但不能消除残余物理
风险，后者消除观察到的 joint-limit outcomes 但不单独恢复任务成功；Dual 组合得到13/18 task success 与
0/18 violation episodes。这个结果不是对 VLA 意图、所有攻击或真实机器人安全的证明。ProofAlign 的贡献是
让一条更窄但关键的运行时链可以被审计：**哪一个动作因什么可信证据获准，实际执行的是不是同一个动作，
观察到的效果是否属于同一事务，以及近边界时是否使用了合格执行配置。**

## 工作参考文献

> 以下使用工作引用键；迁移到投稿 LaTeX 时统一替换为正式 BibTeX，并复核2026论文的最终元数据。

- **[SABER]** [SABER: A Stealthy Agentic Black-Box Attack Framework for Vision-Language-Action Models](https://arxiv.org/abs/2603.24935), 2026.
- **[LIBERO-Safety]** [LIBERO-Safety](https://arxiv.org/abs/2606.23686), ECCV, 2026.
- **[SafeVLA-Bench]** [SafeVLA-Bench](https://arxiv.org/abs/2606.00773), 2026.
- **[VLASurvey]** [Vision-Language-Action Safety: Threats, Challenges, Evaluations, and Mechanisms](https://arxiv.org/abs/2604.23775), 2026.
- **[FreezeVLA]** [FreezeVLA](https://arxiv.org/abs/2509.19870), 2025.
- **[BadRobot]** [BadRobot](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5b2fa23e4ef0f7ac6c4f01d7998e6237-Abstract-Conference.html), ICLR, 2025.
- **[RoboPAIR]** [RoboPAIR](https://robopair.org/), ICRA, 2025.
- **[StruQ]** [StruQ: Defending Against Prompt Injection with Structured Queries](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe), USENIX Security, 2025.
- **[SecAlign]** [SecAlign](https://arxiv.org/abs/2410.05451), ACM CCS, 2025.
- **[CaMeL]** [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813), IEEE SaTML, 2026.
- **[ACE]** [ACE: A Security Architecture for LLM-Integrated App Systems](https://www.ndss-symposium.org/ndss-paper/ace-a-security-architecture-for-llm-integrated-app-systems/), NDSS, 2026.
- **[AttriGuard]** [AttriGuard](https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu), USENIX Security, 2026.
- **[MATE]** [MATE](https://www.usenix.org/conference/usenixsecurity26/presentation/jiang-changyue), USENIX Security, 2026.
- **[SEAL]** [Do What You Say: Runtime Reasoning–Action Alignment Verification](https://arxiv.org/abs/2510.16281), ICRA, 2026.
- **[CoVer]** [Scaling Verification Can Be More Effective than Scaling Policy Learning for VLA Alignment](https://arxiv.org/abs/2602.12281), ECCV, 2026.
- **[OAT]** [OAT: Attesting Operation Integrity of Embedded Devices](https://www.longlu.org/publication/oat/), IEEE S&P, 2020.
- **[DIAT]** [DIAT: Data Integrity Attestation for Resilient Collaboration of Autonomous Systems](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/), NDSS, 2019.
- **[ARI]** [ARI: Attestation of Real-time Mission Execution Integrity](https://www.usenix.org/conference/usenixsecurity23/presentation/wang-jinwen), USENIX Security, 2023.
- **[CFA+]** [CFA+: Control-Flow Attestation for Embedded Systems](https://www.usenix.org/conference/usenixsecurity24/presentation/ammar), USENIX Security, 2024.
- **[ARTO]** [ARTO: Efficient Execution Integrity Attestation for Real-Time Operation of Cyber-Physical Systems](https://www.usenix.org/conference/usenixsecurity26/presentation/zhao-ruizhe), USENIX Security, 2026.
- **[TAT]** [TAT: Attesting Trajectory Integrity of Industrial Robotic Arms](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao), USENIX Security, 2026.
- **[JCS]** [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html), IETF, 2020.
- **[VLMPC]** [VLMPC: Vision-Language Model Predictive Control](https://www.roboticsproceedings.org/rss20/p106.pdf), RSS, 2024.
- **[RealizableShields]** [Realizable Continuous-Space Shields for Safe Reinforcement Learning](https://proceedings.mlr.press/v283/kim25c.html), L4DC, 2025.
