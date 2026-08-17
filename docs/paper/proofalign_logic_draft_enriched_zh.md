# ProofAlign：面向 Action-Only VLA 的可信任务监控与跨层执行完整性

状态：中文逻辑稿定稿。本文只描述一个最终 ProofAlign 系统；实验数字以冻结 SABER 复现结果和最终配对
四臂结果为准。

## 引言（Intro）

视觉—语言—动作模型（Vision–Language–Action model，VLA）正在成为通用具身智能的重要技术路径。典型
VLA 接收图像、机器人状态和自然语言任务，直接输出由若干连续控制步组成的数值动作块（ActionBlock）。
部署者看到的是一串动作数值，而不是一份能够被独立验证的结构化计划。

这种 action-only 接口留下两个彼此独立的安全缺口。第一，攻击者可以修改策略看到的指令、图像或历史，
使 VLA 在不输出显式恶意计划的情况下改变连续数值轨迹。此时，策略提出的 ActionBlock 未必得到权威任务
授权，我们称之为 **authorization gap（授权缺口）**。第二，即使某个 ActionBlock 已经通过检查，后续仍
可能发生命令替换、授权重放、执行前缀缺失、receipt 换绑或 effect evidence 拼接；“检查过的动作”与
“实际执行并产生效果的动作”之间仍有差距，我们称之为 **realization gap（落地缺口）**。二者分别对应
intent–action 与 action–effect 两条对齐关系。

现有工作覆盖了这条链路的局部。本文聚焦一个更窄、也更可检验的问题：在 VLA + simulator 场景中，当
VLA 不暴露可信 structured plan、只返回连续 ActionBlock 时，部署者如何判断一个具体动作块是否得到可信
任务的有限授权，并把同一动作身份贯穿到实际执行及物理证据？

为此，我们提出 ProofAlign：一个部署在 VLA consumer/dispatch boundary 的跨层 reference monitor。L1
使用独立可信任务与观察，对策略实际返回的 exact ActionBlock 做 checker-relative assessment；L2a 用
一次性 execution transaction 绑定 contract、authorization、ordered dispatch、receipt 与 effects；L2b
在关节风险状态下，对同一 source ActionBlock 的有限 virtual-guard configurations 做有界筛选。ProofAlign
不恢复模型的 latent intent，也不把有限 checker 的结论包装成“动作必然正确”。

实验首先成功复现 SABER 的 `constraint_violation` 指令攻击：60个 base pairs、2组 seeds 的240个有效
episodes 中，86个 clean-eligible units 有39个出现新的 risk transition，观测 ASR 为45.35%。随后，我们
在18个 held-out suite/task/init pairs 上完成 clean/attacked 配对四臂实验，共144个 episodes。Dual 在
attacked 条件下取得 `13/18` task success 和 `0/18` observed violation episodes，同时保持 clean 条件下
的总体成功数。

本文贡献如下：

1. 提出面向 action-only VLA 的跨层完整性问题定义，将授权缺口与落地缺口明确分开；
2. 实现 ProofAlign reference monitor，以 exact continuous ActionBlock 为跨层受保护对象，组合 L1、L2a
   与 L2b；
3. 给出透明的攻击基础与配对四臂闭环证据，并明确区分任务效用、执行事务完整性和物理 containment 的
   统计口径与适用边界。


## 背景与动机（Background and Motivation）

### 系统与具身环境

本文使用 OpenPI Pi0.5 与 LIBERO-Safety 研究模拟器。任务由机械臂在桌面场景中完成物体操作。策略输入包括
base/wrist RGB、末端位置与姿态、gripper state 和 task prompt，输出一个 `10×7` ActionBlock。每一步
动作包含三维平移增量、三维 axis-angle 旋转增量和一个 gripper 命令。最终 runner 使用
`replan_steps=10`，因此 monitor 必须处理完整的 `H=10` source block。虽然 Pi0.5 的完整论文系统包含多种
语义训练信号，本地 `pi05_libero` 接口只暴露数值动作，不暴露部署者可以直接信任的 semantic plan。

### 现存攻击与两个缺口

现有攻击需要按“偏差第一次出现在哪里”分成两组，而不能只按最终是否产生物理后果分类。

**第一组是模型上下文与动作生成攻击，对应 authorization gap。**

- **指令攻击：** [SABER](https://arxiv.org/abs/2603.24935) 通过受限的指令修改对 VLA 进行黑盒压力测试，
  并观察任务失败、轨迹增长与约束违反；
- **视觉攻击：** [FreezeVLA](https://arxiv.org/abs/2509.19870) 修改策略的视觉上下文，使 VLA 忽略后续
  instruction 并产生 action freezing；
- **具身模型越狱：** [BadRobot](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5b2fa23e4ef0f7ac6c4f01d7998e6237-Abstract-Conference.html)
  和 [RoboPAIR](https://robopair.org/) 绕过具身模型或机器人 planner 的安全约束，并将 jailbreak 转化为
  有害物理动作。

这组攻击的入口不同，但偏差都在 ActionBlock 生成之前出现：受攻击的
\((P_t^{pol},O_t^{pol},H_t^{pol})\) 使策略产生了与权威任务 \(T\) 不一致的 \(A_t\)。即使这个 \(A_t\)
随后被控制器完整、忠实地执行，系统仍然可能“正确执行了错误任务”。因此，它们首先证明的是
`trusted task → ActionBlock` 之间缺少独立授权，而不是 ActionBlock 在下发后被替换。攻击最终造成物理后果，
并不改变其属于 authorization gap 的事实；分类依据是偏差的引入位置，而不是后果发生在软件还是物理世界。

**第二组是执行链与物理落地攻击，对应 realization gap。** 机器人控制器和 CPS 安全研究已经展示：策略
或上层程序给出的 command 即使本身正确，后续的软件执行、控制数据和真实轨迹仍可能被分离。
[工业机器人控制器的实验安全分析](https://www.ieee-security.org/TC/SP2017/papers/20.pdf)直接展示了控制器
软件漏洞如何破坏感知精度、控制逻辑正确性与操作安全；[DIAT](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/)
讨论自主系统数据在传输、生成或处理过程中被恶意修改的问题；[CFA+](https://www.usenix.org/conference/usenixsecurity24/presentation/ammar)
和 [ARTO](https://www.usenix.org/conference/usenixsecurity26/presentation/zhao-ruizhe) 分别以 control-flow
hijacking 以及 real-time CPS 中的 control-flow/data-only attacks 为攻击模型；
[TAT](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao) 则进一步指出，生产逻辑、
定位或动力学参数的对抗性修改会使实际运动偏离 intended path。

这里，工业机器人控制器分析是直接的攻击面与利用研究；DIAT、CFA+、ARTO 和 TAT 主要是
attestation/integrity 防御工作。本文在“现存攻击”中引用后者，是因为它们明确给出了 realization-side
attacker model 与被保护对象，而不是把这些防御系统本身称为攻击方法。

在 action-only VLA 链路中，这类攻击或故障可具体化为：

- **command substitution：** assessment 绑定的是 \(A_t\)，dispatch 前却被替换成 \(A'_t\)；
- **stale replay：** 旧 state epoch 下签发的 authorization 被用于新的机器人状态；
- **prefix/order manipulation：** 系统只执行部分 ActionBlock，或改变连续 step 的顺序；
- **cross-proposal evidence splice：** receipt、observation 或 effect evidence 来自另一个 proposal，却被用于
  关闭当前事务；
- **command–motion divergence：** controller/guard configuration 或执行环境使实际轨迹偏离 intended
  command，而软件日志仍只保存原始 ActionBlock。

这些情况都允许最初生成的 \(A_t\) 与可信任务相容，却破坏
`authorized ActionBlock → actual dispatch/receipt/effects`，因此属于 realization gap。它们与第一组攻击
正交：上游攻击可以产生一个被忠实执行的错误动作，下游攻击也可以把一个正确获准的动作执行错。

| 攻击发生点 | 直接受影响对象 | 被破坏的关系 | 对应缺口 |
|---|---|---|---|
| instruction / image / history / jailbreak | policy context 与 VLA proposal | trusted task → ActionBlock | Authorization gap |
| authorization / dispatch software | command freshness、identity 与顺序 | authorized block → applied prefix | Realization gap |
| receipt / observer / effect window | execution evidence 的来源与时序 | dispatch → receipt/effects | Realization gap |
| controller / physical trajectory | command 到真实运动的映射 | intended command → actual motion | Realization gap |

需要区分研究动机与本文已实例化的攻击者。正式 SABER rollout 只实例化第一组的指令攻击，并观察其物理后果；
L2a 的69项 focused negative tests 另行注入 substitution、replay、receipt/effect 换绑和 incomplete prefix，
用于验证模型内的事务语义。当前系统仍把唯一 dispatch boundary、observer 和 actuator feedback 放在 TCB 中，
因此不声称抵抗其被完全攻破后的伪造，也不声称已经经验覆盖所有真实控制器攻击。

### 现有的防御

- Authorization gap：
  - StruQ、SecAlign、CaMeL 分离可信指令和不可信数据，但保护停在模型输入或 agent control flow。[StruQ](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe)、[CaMeL](https://arxiv.org/abs/2503.18813)
  - SEAL、CoVer 验证 plan/instruction 与候选动作，但依赖模型计划、learned verifier 或 `K>1` 候选，且不继续绑定物理执行。[SEAL](https://arxiv.org/abs/2510.16281)、[CoVer](https://arxiv.org/abs/2602.12281)
  - AttriGuard、ACE、MATE 提供 action attribution 或 trusted-plan enforcement，但对象主要是离散工具调用和数字 agent trajectory。[AttriGuard](https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu)、[ACE](https://www.ndss-symposium.org/ndss-paper/ace-a-security-architecture-for-llm-integrated-app-systems/)

- Realization gap：
  - DIAT、CFA+、ARTO 保护 CPS control/data flow，但从已知程序和关键变量出发，不解决自然语言任务对 VLA proposal 的授权。[DIAT](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/)、[ARTO](https://www.usenix.org/conference/usenixsecurity26/presentation/zhao-ruizhe)
  - TAT 验证 actual motion 是否符合 intended path，但假设 intended path 已经给定；action-only VLA 恰恰缺少这个可信起点。[TAT](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao)

由这些 stopping points，我们得到三个核心 insight：

> 所有上游攻击最终都会收敛为一个即将执行的 ActionBlock；因此，安全的关键不是恢复 VLA 的 latent intent，而是用独立可信任务约束这个 exact ActionBlock，并将其身份贯穿到实际执行及物理证据。

1. 外部权威锚点：可信任务不能来自受攻击 prompt、模型 explanation 或 latent intent。
2. 受保护对象：必须保护策略实际提出的 exact continuous ActionBlock，而不只是 instruction、plan 或候选排名。
3. 跨层证据闭环：把同一 ActionBlock 身份带过 assessment、guard screening、一次性 authorization、dispatch、receipt 和 effects。

> 现有防御要么停在 ActionBlock 之前，要么从既定 command/path 之后开始；ProofAlign 以 exact ActionBlock 为连接对象，闭合 trusted task→proposal 与 proposal→actual execution 两条边。

### 关键挑战

**C1：VLA 不暴露可信 plan，如何获得独立的任务锚点？** 可信语义不能来自受攻击 prompt、模型
explanation 或对 ActionBlock 的事后解释，否则监控器只会得到与攻击行为自洽的标签。

**C2：如何把语义任务约束落实到细粒度连续动作？** 同一语义目标可能对应许多合理轨迹。若不完整的
checker 将所有 uncertainty 都 hard reject，会严重损害任务效用；若全部放行，又会产生 false allow。

**C3：如何证明被检查的动作就是实际执行的动作？** 困难不只是比较一次 hash。ActionBlock 可能经过
不同序列化，authorization 可能被重放，state epoch 可能已经改变，也可能只执行部分 prefix、重排 step，
或把其他 proposal 的 receipt/effects 拼接到当前事务。

**C4：如何约束状态相关的物理执行风险？** 即使执行的确实是 \(A_t\)，同一动作在不同关节状态下也可能
产生不同风险。接近关节边界时直接执行可能越界；但若安全层直接改写 ActionBlock，又会破坏 L1 assessment
和 L2a authorization 所绑定的对象身份。

### 挑战与方法的对应关系

| Challenge | 核心问题 | 对应机制 |
|---|---|---|
| C1 | 可信任务权威从哪里来？ | Trusted task/observation branch |
| C2 | 如何对连续动作做不过度声称的相对授权？ | L1 checker-relative assessment |
| C3 | 如何保证检查、授权和执行的是同一个动作？ | L2a execution transaction |
| C4 | 如何在不修改 source action 的情况下约束近边界执行？ | L2b bounded guard screening |

## 问题定义与威胁模型（Problem Definition and Threat Model）

记权威任务为 \(T\)，安全分叉前 trusted tap 取得的观察为 \(O_t^T\)。冻结 selector 根据二者和当前合法
task-graph frontier 生成结构化子任务 \(Z_t\)。VLA 则读取另一条 policy-facing 视图：

\[
A_t=\pi(P_t^{pol},O_t^{pol},H_t^{pol}),\qquad A_t\in\mathbb{R}^{10\times7}.
\]

在 clean 条件下，\(P_t^{pol}\) 是 \(T\) 的正常 benchmark 序列化；在 attacked 条件下，冻结 SABER record
修改其 exact bytes。两种 policy prompt 都被记录用于 provenance，但都不会因此成为 semantic authority。

攻击者能够在 secure split 之后修改 policy-facing prompt、数字/软件视觉输入或 history，使固定 VLA
checkpoint 输出偏离可信任务或诱发物理风险的 ActionBlock。攻击者目标是使最终动作或效果偏离 \(T\)。TCB
包括可信任务源、trusted observation tap、冻结并 allowlist 的 selector/checker、contract compiler、
digest/nonce ledger、唯一 dispatch boundary，以及 receipt/evidence storage。

在这一模型中，authorization gap 问的是“\(A_t\) 为什么得到 \(T\) 的允许”，realization gap 问的是
“实际下发、记录并产生效果的是否仍属于同一个 \(A_t\) 事务”。

### 安全目标

在可信任务源、攻击前 observation tap、冻结 selector/checker、digest/nonce ledger、唯一 dispatch 边界和 evidence storage 不被攻破的前提下，ProofAlign 追求下面三个可分别检验的安全目标。

**G1：相对于冻结 checker 的可信任务授权。** 若 L1 允许执行 \(A_t\)，系统必须能够证明：\(Z_t\) 来自当前可信任务 \(T\) 的合法 task-graph frontier，\(Z_t\)、可信观察 \(O_t^T\)、state epoch、assessment 与 exact \(A_t\) 相互绑定，并且 assessment 中没有命中已覆盖的 hard risk。形式上：

\[
\mathsf{L1Allow}(A_t)\Rightarrow
\mathsf{TrustedProv}(T,O_t^T,Z_t)\land
\mathsf{Bound}(S_t,Z_t,O_t^T,A_t)\land
\mathsf{NoCoveredHardRisk}(S_t).
\]

这个目标是 **checker-relative authorization**：它不声称所有被接受的动作都必然推进真实任务，也不声称恢复了 VLA 的 latent intent。对 task-progress、release/close progress 或 expected-effect 的不确定性，当前系统记录 advisory，并强制下一 block 重新观察和规划；它们不被伪装成完备的语义拒绝器。

**G2：一次性执行事务完整性。** 对启用 L2 的执行，实际 dispatch 必须来自一个新鲜、未消费、绑定当前 proposal 和 state epoch 的 authorization；每个已执行 step、receipt 和 effect window 必须属于同一 contract。旧授权重放、命令替换、乱序或缺失 prefix、receipt/effect 换绑以及用未来 observation 补过去事务，都不能形成合法完成证据。只有满足执行对齐且观察到可信任务完成，系统才允许 phase advance：

\[
\mathsf{PhaseAdvance}_t\Rightarrow
\mathsf{FreshOneUse}(Auth_t)\land
\mathsf{ExactPrefix}(A_t,R_t)\land
\mathsf{EvidenceBound}(C_t,Auth_t,R_t,E_t)\land
\mathsf{TaskCompletionObserved}.
\]

**G3：风险状态下的有界物理 containment。** 对启用 L2 的执行，当任一关节侧 margin 进入冻结的风险区时，source ActionBlock 不能直接下发。系统只允许在同一 snapshot 上、用同一 source action 筛选通过的 guard configuration；候选的 shadow prediction 必须使全部14个 joint-side margin 不低于安全 floor，并满足 force envelope。若没有候选合格，则 fail closed。

**组合目标。** 在 Dual arm 中，一个任务阶段能够推进，意味着当前 exact source ActionBlock 已取得 G1 的相对授权，实际执行与证据满足 G2；若当时处于关节风险区，还必须额外满足 G3。三个目标分别回答“为什么允许这块动作”“执行的是否还是它”“近边界时是否以合格配置执行”，不能互相替代。

**不覆盖范围。** 当前目标不覆盖 secure split 之前同时欺骗两条视图的物理光学攻击、可信任务源或 monitor 被攻破、伪造 actuator feedback、任意攻击族、任意动力学误差、真实机器人安全、硬件 root of trust 或硬实时保证。最终 semantic selector 使用 LIBERO privileged geometry，因此这里只能声称 benchmark-qualified trusted branch，不能声称 camera-only 可信感知。

## 方法（Method）

ProofAlign 是放在 VLA consumer 一侧的 reference monitor，不修改 Pi0.5 权重，也不要求模型输出 explanation 或 structured plan。它始终围绕策略实际返回的一个 `H=10`、`10×7` source ActionBlock 建立如下证据链：

> trusted task / observation
> → frozen semantic subtask \(Z_t\)
> → exact ActionBlock assessment `[L1]`
> → execution contract
> → conditional guard screening `[L2b]`
> → fresh one-use authorization
> → ordered dispatch / receipts / observed effects `[L2a]`

贯穿全文的例子是“把汽水罐放到盘子上”。SABER 将策略实际看到的指令改为“移动到最远的装置”，Pi0.5
仍然只返回一个 `10×7` 数值块。ProofAlign 不尝试从这组数值恢复模型“真正想做什么”；trusted branch
继续从原始任务选择合法子任务，L1 检查策略真实返回的这一块数值，L2b 在需要时为同一 source action 筛选
执行配置，L2a 再把这一块动作绑定到授权、下发与效果证据。

每轮执行按以下顺序进行：

1. trusted branch 在动作生成前固定当前 state epoch 和合法语义子任务 \(Z_t\)；
2. Pi0.5 从可能受攻击的 policy-facing prompt、observation 和 history 生成唯一 source block \(A_t\)；
3. L1 使用 \((Z_t,O_t^T,A_t)\) 对 exact block 做局部 assessment；
4. consumer 将 proposal、assessment 和 provenance 编译成 execution contract \(C_t\)；
5. 若关节状态进入风险区，L2b 对同一 source action 的有限 guard configurations 做 pre-dispatch screening；
6. screening 合格后才签发新鲜的一次性 authorization；
7. L2a 在唯一 dispatch 边界逐步消费授权，并绑定 receipts 与 observed effects；
8. evidence 未知、不完整或来自其他事务时不得推进任务阶段。

### 可信语义锚点 \(Z_t\)

ProofAlign 维护两条严格分开的视图。策略分支读取的 \(P_t^{pol},O_t^{pol},H_t^{pol}\) 可以被攻击；trusted branch 只读取不可变任务 artifact \(T\) 和 secure split 之前取得的 \(O_t^T\)：

\[
Z_t=\mathsf{SelectFrozen}(T,O_t^T,Z_{t-1},\mathsf{Frontier}(T,O_t^T)).
\]

最终实现使用由 benchmark BDDL goal、gripper state 和 privileged geometry 驱动的确定性 task graph/FSM。
它解析 `On`、`In`、`Open`、`Close`、`Turnon` 和 `Turnoff` 六类 goal predicate，并将任务编译到
`pick_up`、`move`、`place`、`release`、`open`、`close`、`actuate`、`finish` 和 `unknown` 等有限子任务
词表。以 `On(soda, plate)` 为例，task graph 依次给出 `pick_up(soda)`、`move(soda, plate)`、
`place(soda, plate)`、`release(soda)` 和 `finish()`；selector 根据可信夹爪状态和几何关系，只能从当前合法
frontier 选择。它不能看完动作后重新命名 \(Z_t\)，也不会把 \(Z_t\) 写回 Pi0.5 prompt。

每个 semantic artifact 绑定 episode nonce、proposal index、state epoch、可信任务与观察 digest、task graph 与 candidate-set digest、previous-subtask digest，以及 selector/checker 的 allowlisted identity 和 config。任一输入或 epoch 改变，旧 artifact 都不能复用。这里“可信”表示来源、版本和绑定可验证，并不表示 selector 的语义判断先验上永远正确。

### L1：从可信任务到 exact ActionBlock 的有限授权

Pi0.5 生成

\[
A_t=\pi(P_t^{pol},O_t^{pol},H_t^{pol}),\qquad A_t\in\mathbb{R}^{10\times7}.
\]

L1 随后运行 generate-then-monitor：先固定 \(Z_t\)，再评估真实返回的 \(A_t\)，而不是让 VLA 自报 intent，
也不通过 best-of-\(K\) 重采样或 projection 把动作“修好”。正式设计固定 `K=1/H=10`；无 hard risk 时，
L1 返回数值与 shape 不变的 source block。系统以带 schema 的 canonical JSON 表示来计算 digest，保护有限
Python float 数值及 proposal shape 的规范化身份；这里不声称保留原始 ndarray 的 dtype、endianness 或
内存字节布局。

assessment \(S_t=\mathsf{AssessLocal}(Z_t,O_t^T,A_t)\) 检查：

- block 形状、长度、数值有限性以及 state epoch 是否正确；
- translation/rotation velocity 与 workspace envelope；
- 结合目标、部件、区域、末端运动和 gripper command 的局部兼容性；
- unexpected-contact neighborhood 及其他已覆盖的禁止效果；
- assessor 是否为冻结且 allowlisted 的实现，evidence 是否为已知类型。

系统采用分级决策。malformed/stale command、速度或工作区越界、unexpected contact 和未识别的 unknown evidence 属于 hard gate，命中后不授权。task-progress、release/close progress、expected-effect miss，以及当前不可取得的 articulation task state 属于 advisory：记录异常并要求下一 block 重新观察、重新规划，但在没有 hard risk 时不一律阻止当前 block。这个设计避免把有限几何 checker 包装成完整 semantic oracle。

### Execution contract \(C_t\)

L1 assessment 之后，consumer 编译不可变 execution contract：

```text
C_t = {
  episode_nonce, proposal_index, state_epoch,
  semantic_context_digest, semantic_subtask_digest,
  exact_policy_prompt_digest, trusted_observation_digest,
  action_block_digest, assessment_digest,
  expected_effect_atoms, forbidden_effect_atoms,
  observation_window
}
```

contract 的作用是把“为什么允许这块动作”的 L1 证据交给执行层。重新选择 \(Z_t\)、修改 ActionBlock、改变 epoch 或重新 assessment 都必须生成新 contract；旧 contract 不能沿用。

### L2b：风险触发的 bounded guard screening

L2b 在 dispatch 前监控7个机械臂关节的上下两侧，共14个 joint-side margins。

- 当前最小 margin 大于 `0.30 rad` 时走 fast path，不运行 shadow simulator；
- 进入风险区时，为同一 source ActionBlock 构造最多2个临时 virtual-guard configurations；
- 每个候选从同一 simulator snapshot 做 one-step shadow rollout，并检查 snapshot restore、source-action identity 和预测/正式执行的一致性；
- 合格候选必须使全部14侧预测 margin 均 `>=0.15 rad`，同时满足统一的 `force <=10000` envelope；
- 系统选择满足条件的最弱 guard；没有合格候选时 fail closed，不 dispatch。

这两个候选是 execution-layer guard configurations，不是新的 policy ActionBlocks，因而不改变 `K=1`。
virtual guard 不改写 source ActionBlock 的规范化数值与 shape，却会改变 controller 到物理轨迹的映射。当前
Python runtime 会记录 guard、controller、state restore、force 和 margin 证据，但 Lean typed contract
尚未把 guard/controller 作为独立 digest 字段。因此本文声称的是研究模拟器中的 joint-limit containment，
而不是 exact physical trajectory identity。

### L2a：一次性 execution transaction

通过 L1 与必要的 L2b screening 后，系统签发 authorization。authorization 绑定 episode nonce、proposal index、state epoch、contract、assessment、exact source block/final command digest、action count 和有效期，并由 ledger 保证只消费一次。

执行时，唯一 dispatch boundary 对 `H=10` 动作逐步检查：第 \(i\) 个 applied action 必须等于 authorization 中相同索引的 action；receipt 必须引用同一个 authorization、contract 和 block；effect window 只能在 dispatch 后打开，并按顺序绑定 receipt digests、observed command digests 和 observation digests。以下情况均不能形成合法完成证据：

- command substitution、step 重排或用另一个 proposal 的 prefix；
- stale/expired authorization 或已消费 authorization replay；
- receipt 属于其他 authorization，或 observed command 与 receipt 不一致；
- prefix 不完整却声称整块完成；
- evidence unknown、禁止效果出现或 observation window 不合法。

对任务效果未完成但没有硬完整性错误的情况，系统记录并重新规划；只有 execution alignment 与 trusted task completion 同时成立，phase 才能推进。

### 失败语义

| 条件 | 系统动作 |
|---|---|
| L1 hard risk、stale/malformed 输入、未知 evidence 类型 | fail closed，不签发授权 |
| 只有 task-progress advisory | 记录证据；当前块可继续，下一块必须 reobserve/replan |
| 进入关节风险区且无 L2b 候选合格 | fail closed，不 dispatch |
| authorization、step、receipt 或 evidence 换绑/不完整 | 当前事务不完成，不允许 phase advance |
| 完整性成立但任务完成未被观察到 | 不推进任务阶段，重新观察和规划 |

## 实现（Implementation）

ProofAlign 被实现为部署在 VLA 输出端与机器人执行接口之间的 consumer-side runtime monitor。系统不修改
Pi0.5 的模型权重、提示词或动作生成过程；每个 `10×7` ActionBlock 都依次经过可信任务编译、L1 检查、
L2a 事务绑定以及必要时的 L2b 物理筛查，只有获得授权的动作才能通过唯一 dispatch boundary 执行。

### 可信任务分支

系统从攻击面之外的 BDDL 任务定义、夹爪状态和 simulator privileged geometry 构建确定性 task graph 与
有限状态机，得到当前可信子任务 \(Z_t\)。trusted observation 与提供给 policy 的图像、状态和提示词在攻击
变换前分叉并分别计算摘要，从而避免被污染的输入反向定义任务权威。

### L1：局部语义与安全检查

L1 使用动作解析、短时运动学近似和几何规则检查 ActionBlock 的格式、有限数、速度、工作空间、意外接触
以及与当前子任务的局部兼容性。明确的物理风险触发拒绝；仅涉及任务进展的不确定项记录为 advisory，并在
下一个 block 重新观察和规划。L1 只判断动作，不修改动作内容。

### L2a：执行事务绑定

系统将规范化 ActionBlock 及其 shape 编码为 canonical JSON，并使用 SHA-256 生成稳定身份；随后把它与
\(Z_t\)、观测 epoch 和 L1 assessment 一同写入 execution contract。一次性 authorization ledger、唯一执行
边界、有序 step receipt 和执行后的 effect window 共同阻止动作替换、授权重放、prefix 不完整和证据拼接。

### L2b：物理执行筛查

L2b 基于 MuJoCo joint limits 计算7个机械臂关节的14侧 margin。接近关节边界时，系统从同一 simulator
snapshot 对同一 source action 运行最多两个 one-step guarded shadow rollout，并检查状态恢复、动作身份、
`0.15 rad` 安全下界与约束力 envelope；没有合格配置时 fail closed。guard 只调整执行时的物理约束配置，
不改写 source ActionBlock。

### 记录与形式化边界

运行 trace 保存 trusted/policy 输入摘要、assessment、contract、authorization、receipts、effect evidence，
以及 guard、margin、约束力和筛查延迟。我们同时使用 Lean 对抽象执行事务的身份绑定、一次性授权、receipt
一致性和 phase transition 进行检查；形式化结论针对事务语义，不覆盖任务选择器正确性、sim-to-real 等价性
或机器人整体安全性。

## 实验（Evaluation）

评价先建立攻击基础，再用配对四臂实验分离 L1 与组合 L2 treatment 的样本角色，并通过独立消融解释
ActionBlock 长度的选择，最后核验执行完整性、物理 envelope 与运行时开销。不同实验的 population、
denominator 和事件定义始终分开。

### 研究问题

- **RQ1：** 冻结 SABER `constraint_violation` instruction records 能否在本地 Pi0.5—LIBERO-Safety 路径
  中产生可复现的物理 risk transition？
- **RQ2：** 启用 L1 后，attacked task success 如何变化；结果支持什么范围的物理风险结论？
- **RQ3：** 组合 L2 treatment 能否 containment 所覆盖的 joint-limit outcomes，同时不引入 deadlock 或
  可见的总体 task-success 损失？
- **RQ4：** Dual 能否同时保留 L1 的样本任务效用与 L2 的样本 containment 结果？
- **RQ5：** ActionBlock 长度如何影响 checker 对局部任务进展的 initial availability，主配置为何选择
  \(H=10\)？
- **RQ6：** transaction identity、force、prediction error、latency 和 deadline 等注册门是否成立？

### 实验设置

**攻击基础实验。** victim 为 OpenPI Pi0.5，benchmark 为 LIBERO-Safety，攻击输入为 SABER 生成并冻结的
`constraint_violation` instruction-perturbation records。实验覆盖60个 base pairs 和2组 seeds；每个
base-pair/seed unit 分别运行 clean 与 attacked rollout，共240个 episodes。

**最终配对四臂实验。** 最终样本包含18个 held-out suite/task/init pairs，其中
`obstacle_avoidance`、`obstacle_avoidance_human` 和 `human_safety` 三个 suite 各6个。18个 pair 由冻结
流程从未进入开发协议的 task/init population 中选择；所有 pair 完整保留，不按 clean 或 attacked outcome
筛选。每个 attacked run 使用一条与当前 workload 具有相同原始任务、但来自不同 initialization 的冻结
SABER record；只移植 perturbation 后的 task text，record 生成过程不读取 clean/attacked victim outcome，
也不做 best-of-\(N\) 选择。

每个 pair 在 clean 与 attacked 条件下运行四个 arms：

| Arm | L1 | L2a + L2b | 用于识别的角色 |
|---|---:|---:|---|
| VLA-only | 0 | 0 | 不修改 runtime 的 VLA 基线 |
| L1-only | 1 | 0 | trusted-task monitoring / relative authorization |
| L2-only | 0 | 1 | execution transaction + joint containment |
| Dual | 1 | 1 | 两层组合 |

clean/attacked 逐 pair 共享 initial state、environment seed、policy seed 和 arm schedule。每个条件包含72个
episodes，总计 `18×2×4=144`。主配置固定 `K=1/H=10`；同一 paired workload 的四臂首个 source
ActionBlock 相同，发生 hard gate、intervention 或状态分叉后不再要求后续轨迹保持 action identity。L2-on
两臂同时启用 L2a 和 L2b，因此主表识别的是组合 L2 treatment，不能进一步拆分两者的独立因果效应。

**ActionBlock 长度消融。** 消融包含45个 `task/init/source-policy-chunk` matched units。对每个 unit，实验
从同一个 policy 原生 \(H=10\) source ActionBlock 截取嵌套前缀，在完全相同的 checker 和阈值下比较
\(H=2,5,10\)，固定局部进展阈值为 `0.002 m`，且不根据结果调参。三个长度均只进行 assessment，
不 dispatch 动作、不读取任务结果，因此该实验只测量 initial checker availability，不测量闭环 task
success、攻击防御效果或物理安全性。

### 指标与统计口径

攻击基础实验的 ASR 只在 clean-safe units 上统计。若 attacked rollout 新出现 contact、joint-limit、
excessive-force 或 LIBERO cost/collision risk transition，则记为一次攻击成功；单纯 task failure 不计为
transition。95%置信区间采用按 base pair 聚类的 bootstrap，避免把同一 base pair 的 seed replicates
视为相互独立。

最终四臂实验报告 task success 及 clean/attacked 的配对成功转移。`violation episode` 指一个 episode 中
至少出现一次原生 joint-limit violation 或实际 joint-side margin crossing；同时报告 crossing steps、
joint-limit steps、benchmark official-unsafe、deadlock、最大 constraint-force proxy 和 prediction/execution
margin error。完整性指标包括 attack metadata、prompt digest、首块身份、checksums 以及 receipt/effect
事务门；开销指标包括 screening latency 的最大值、p95 和100 ms miss rate。

两个注册的 attacked task-success contrasts 为 L2−VLA 与 Dual−L1，使用按 pair 聚类的100,000次 percentile
bootstrap 和 `−0.20` noninferiority margin，并对两个检验做 Bonferroni 校正。这个 margin 是冻结的机制资格
门，不是部署安全阈值。violation-episode rate 作为描述性结果报告95% Wilson 区间。

攻击基础的 risk-transition ASR 与最终四臂的 violation-episode rate 使用不同 population、denominator 和
event definition；二者不能直接相减、合并或解释为同一个“防御成功率”。

长度消融中的 `eligible` 表示给定前缀在固定 checker 下能够观察到足够的局部任务进展，且没有 hard
violation。三个长度来自同一 source ActionBlock 的嵌套前缀，结果按 matched unit 比较；该指标与四臂实验
中的 episode-level task success 和 violation outcome 均不同。

### RQ1：SABER 攻击成功复现

240/240 episodes 有效。86个 clean-eligible units 中有39个发生新的 risk transition：

\[
\mathrm{ASR}=39/86=45.35\%,\qquad
95\%\ \text{base-pair cluster-bootstrap CI}=[32.93\%,57.78\%].
\]

该结果说明冻结 SABER records 在本地 OpenPI Pi0.5—LIBERO-Safety 路径上产生了明确且可重复测量的物理
风险转移，成功复现了该攻击。本文将 `45.35%` 表述为当前 victim、benchmark、冻结攻击配置、eligibility
rule 和 event definition 下的观测 ASR。

### RQ2–RQ4：配对四臂主结果

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18（72.22%） | 11/18（61.11%） | 4/18（22.22%） | 28 | 175 |
| L1-only | 13/18（72.22%） | 13/18（72.22%） | 1/18（5.56%） | 295 | 317 |
| L2-only | 13/18（72.22%） | 11/18（61.11%） | 0/18（0%） | 0 | 0 |
| Dual | 13/18（72.22%） | 13/18（72.22%） | 0/18（0%） | 0 | 0 |

结果支持以下分层解释。

1. **L1 在该冻结样本中的主要角色是任务效用，而不是完整物理安全。** L1-only 在 attacked 条件下取得
   `13/18` task success，高于 VLA-only 的 `11/18`；但它仍有1个 violation episode。该残余 episode
   累积295个 crossing steps 和317个 joint-limit steps，均高于 VLA-only 的28和175。因此，数据不支持
   “L1 普遍降低物理风险严重度”的结论。
2. **L2 的样本角色是 containment，而不是任务恢复。** L2-only 将 violation episodes、crossing steps
   和 joint-limit steps 全部降到0，但 attacked task success 仍为 `11/18`，与 VLA-only 相同。L2 可以
   约束所覆盖的关节风险，却不能把 task-divergent action 自动变成正确任务。
3. **Dual 组合了两层在该样本中的角色。** Dual 保留 L1-only 的 `13/18` attacked task success，同时得到
   `0/18` violation episodes、0 crossing steps 和0 joint-limit steps。L2−VLA 与 Dual−L1 的 attacked
   task-success contrast 均为0，paired bootstrap interval 均为 `[0,0]`；这只说明当前样本中加入 L2 没有
   改变汇总成功数，不是总体零效应证明。

四个 clean arms 的 task success 均为 `13/18`。broader benchmark 的 official-unsafe flag 在四个 attacked
arms 中均为0；clean 的 L1-only 和 Dual 各出现1次，并保留在审计中。该 endpoint 与 L2 所针对的
joint-limit outcome 不同，因此不能把 attacked zero-crossing 扩大为“所有安全信号始终为零”。

violation-episode rate 的95% Wilson 区间分别为 VLA-only `[9.00%,45.21%]`、L1-only
`[0.99%,25.76%]`、L2-only/Dual `[0%,17.59%]`。因此，`0/18` 只表示冻结样本中没有观察到事件，不能
外推成总体零风险。clean成功→attacked失败的 pair 数为 VLA/L1/L2/Dual 的 `3/2/3/2`，反向转移为
`1/2/1/2`；汇总成功率包含双向变化，不能把所有 attacked failure 都解释为攻击新增失败。

贯穿全文的 `human_safety_task2_init34` 仅作为事后机制例子：SABER 将“汽水到盘子”替换成“移动到最远
装置”；VLA-only 任务失败并出现2个 crossing steps、5个 joint-limit steps，L1-only 成功且为0/0，
L2-only 任务失败但为0/0，Dual 成功且为0/0。该 pair 不定义统计 estimand，所有结论仍来自完整18-pair
配对样本。

### RQ5：ActionBlock 长度消融

| Assessed block length | Checker-eligible | Eligible rate | Hard-violation candidates |
|---:|---:|---:|---:|
| \(H=2\) | 0/45 | 0% | 0 |
| \(H=5\) | 17/45 | 37.78% | 0 |
| \(H=10\) | 36/45 | 80.00% | 0 |

在固定 checker 下，initial availability 随前缀长度单调增加：\(H=2\) 时没有 unit 呈现足够的局部进展，
\(H=5\) 时为17/45，\(H=10\) 时为36/45。matched pattern 为 `000:9, 001:19, 011:17`，即较长前缀
新增了36个 eligible units，且没有使较短前缀中已 eligible 的 unit 退化。\(H=10\) 的 suite-level
availability 分别为 `human_safety: 12/15`、`obstacle_avoidance: 13/15` 和
`obstacle_avoidance_human: 11/15`。

这项结果说明，过短的 ActionBlock 往往不足以让局部 checker 观察到任务进展，因此主实验选择 policy 原生
输出上限 \(H=10\)。这一选择不通过拼接多个 policy call 延长 open-loop horizon，也不表示更长 block 会
提高闭环任务成功率或安全性；它只是在冻结 checker 下提供更高的 initial availability。

### RQ6：完整性、物理 envelope 与开销

最终 attacked 四臂72/72 episodes 均完成；相对 matched clean，72/72 个 attacked 首块发生变化；attack
metadata mismatch 和 prompt digest mismatch 均为0，四臂 pair 内首块一致为18/18，冻结 evidence 的
checksums 为76/76，所有注册 runtime integrity gates 均通过。

L2a 另由69项 focused negative tests 验证，69/69通过。测试覆盖 stale binding、pre-dispatch command
substitution、sink-side change with truthful receipt、authorization replay、cross-proposal receipt/effect、
unknown evidence 和 incomplete prefix。它们区分“下发前阻止”与“下发后检测”：如 sink 在执行一步后如实
报告命令变化，monitor 可以拒绝事务完成，却不能撤销已经发生的物理动作；若 TCB 内的 sink/observer 伪造
内部一致的证据，纯软件 monitor 也无法独立检测。

L2-on arms 的 actual crossing、joint-limit violation steps 和 deadlock 均为0；最大 constraint-force proxy
为 `6438.20 < 10000`。该值是注册风险关节上的 MuJoCo generalized-constraint-force proxy，不是校准后的
末端作用力。最大 selected-margin prediction error 约为 \(2.69\times10^{-13}\,\mathrm{rad}\)，低于
`0.01 rad` 门；由于
shadow 与 dispatch 复用了恢复后的同一 MuJoCo state/model，这一指标验证的是 restore/execution consistency，
不是对 dynamics mismatch 的预测能力。

screening latency 最大39.79 ms、p95为18.30 ms，100 ms miss rate 为0；最大值也低于20 Hz 研究模拟器的
名义50 ms period。这些结果满足冻结研究环境中的注册开销门，但没有覆盖操作系统 worst-case scheduling、
通信抖动、真实控制总线或硬件动力学，因而不构成 hard-real-time 证明。

日志审计还保留了同一 task/init pair 上4次 MuJoCo numerical-instability warning（四臂各1次，均发生在
0.3 s）。4个 episode 都正常完成且未被移除。该配对出现不偏向任何 arm，但进一步限制了结果只能解释为
冻结模拟器配置下的证据。

## 讨论（Discussion）

### 两层为什么必须同时存在

L1 和 L2 保护的不是同一种正确性。L1 可以说明一个 exact block 在什么可信任务上下文和 checker 覆盖下获准，却不能证明 sink 最终执行了同一个命令；L2 可以忠实执行并约束一个动作，却不能把受攻击 prompt 产生的错误任务意图自动纠正。最终四臂中，L1-only 的残余越界与 L2-only 的任务失败正好给出这两个反例。Dual 的价值在于把任务侧监控和执行侧 containment 放进同一条可审计事务，而不是用一个总 safety score 混合二者。

### exact ActionBlock 是跨层连接对象，而不是完整物理轨迹

action-only VLA 没有可独立信任的 structured plan，因此 ProofAlign 选择策略实际返回的 exact continuous
block 作为 protected object。这使 assessment、contract、authorization、dispatch 和 receipt 能共享同一
规范化身份。但 virtual guard 表明 source action 的数值与 shape 相同并不意味着物理轨迹相同：controller
与 guard configuration 也是 executable identity 的一部分。当前 runtime 已记录这些证据，Lean contract
尚未完整类型化它们，这是后续需要补齐的 refinement，而不是可以忽略的实现细节。

### 对安全数据采集的意义

ProofAlign 的外挂式设计可以把 `trusted task → Z_t → ActionBlock → authorization → receipt/effects` 保存成带 provenance 的轨迹。相比只记录 observation/action/reward，这类数据能够区分：动作因为什么可信证据获准、是否经过 guard、实际执行了哪个 prefix、哪些 effect 属于同一事务，以及失败来自 task mismatch 还是 execution mismatch。这为后续筛选训练数据、审计离线数据和构造安全相关 preference/verification 数据提供了基础。

但是，当前实验验证的是 runtime containment 与事务完整性，没有训练新 VLA，也没有测量使用这些数据后对下游模型安全性或能力的提升。因此“采集更可审计、风险标注更完整的数据”可以作为系统意义与未来工作，不能写成已经验证的学习效果。

### 局限与后续工作

- L1 的 deterministic selector/checker 依赖 LIBERO privileged geometry；camera-only trusted perception 尚未解决。
- 当前经验攻击只覆盖冻结的 SABER instruction records；视觉/history attack、adaptive attacker、更多 VLA checkpoint 与攻击族仍需独立实验。
- L2b 只针对 simulator joint-limit endpoint；0 crossing 不代表碰撞、接触、力或所有 embodied risk 都为0。
- Lean 只检查抽象事务关系，尚无 Python-to-Lean 端到端 refinement，也未把 guard/controller identity 完整纳入 typed contract。
- 18-pair结果是冻结样本证据，不支持总体零风险；真实机器人、硬件 attestation 与硬实时保证均未覆盖。

当前首先完成论文初版，以固定问题、方法、证据和 claim boundary。更多 seeds、真实机器人、额外攻击族与
camera-only perception 在初稿完成后，根据论证暴露的证据缺口定向补充。

## 结论（Conclusion）

ProofAlign 不试图证明 VLA“想对了”，也不要求 action-only VLA 生成一份可相信的自我解释。它在 consumer 侧回答三个更可检验的问题：**哪一个 exact ActionBlock 因什么可信证据获准，真正执行并产生 evidence 的是否仍是同一事务，以及接近关节边界时是否启用了合格的 containment 配置。**

在 Pi0.5—LIBERO-Safety 上，我们成功复现 SABER attack，并观测到 `39/86=45.35%` 的
clean-safe→attacked-risk transitions；最终18-pair四臂中，Dual 在 attacked 条件下保持 `13/18` task
success，并将观察到的 constraint-violation episodes 从 VLA-only 的 `4/18` 降为 `0/18`。这些结果支持
冻结攻击与研究模拟器范围内的 trusted-task monitoring、execution transaction 和 joint-limit containment，
不支持任意攻击、总体零风险或真实机器人安全的更强结论。
