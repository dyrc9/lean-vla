# ProofAlign：NDSS 叙事简版

英文题目：**ProofAlign: Cross-Layer Runtime Integrity for Embodied Vision–Language–Action Systems**

本文的中心论点是：

> 具身VLA的安全边界不应停留在输入文本、模型解释或最终任务结果。策略实际生成的连续ActionBlock是VLA推理
> 与物理执行之间唯一共同且可精确识别的在线对象；系统应围绕它建立任务相对评估、执行身份连续性和状态相关
> 约束三项可验证义务。

## 1. 问题与动机

具身VLA把语言任务、多模态观察和机器人状态直接映射为连续动作。每次策略调用都会产生一段即将跨过控制
边界的ActionBlock。这个数值块不天然说明三件事：它是否适合当前任务；经过软件栈后是否仍是原动作；以及
它在当前机器人状态下是否满足需要覆盖的物理约束。

攻击使这一缺口变得具体。在本文的贯穿样例中，操作者要求把汽水放到盘子上，SABER却把policy-facing
instruction改成“向最远的装置直线移动”。VLA返回的是一个`10×7`数值块，而不是一份可独立信任的计划。
该动作可以格式正确、数值平滑，却仍然服务于错误任务。即使某个检查器批准了它，旧授权重放、动作替换、
step乱序、部分执行或跨proposal拼接receipt/effects，仍可能让“检查通过”与“实际执行”脱节。同一动作在
不同关节状态和controller配置下也可能产生不同物理后果。

语言、视觉和history攻击拥有不同入口，但要影响物理世界，最终都必须改变或利用执行端接收的动作。因此，
ActionBlock是攻击路径和防御路径的共同汇聚点。这一观察比“让VLA解释自己”更可靠，也不要求系统事先知道
唯一正确轨迹。

## 2. 三个挑战

### C1：连续动作的任务相对评估

同一任务阶段允许多条合理轨迹。完整的自然语言语义无法直接还原成唯一的连续动作，因此局部checker既不能
把所有不确定性都判为攻击，也不能把有限几何proxy包装成任务正确性证明。系统需要给出checker-relative
assessment，并明确hard violation、advisory uncertainty和unknown的不同语义。

### C2：跨层执行身份连续性

一次digest比较只能说明两个canonical表示相等，不能说明它们属于同一episode、proposal、state epoch、
authorization和evidence window。系统必须同时处理canonicalization、freshness、one-use、ordered prefix、
receipt provenance、effect timing和phase transition。

### C3：不替换source action的状态相关约束

动作风险依赖执行状态。接近joint limit时直接下发可能越界，但安全层若改写ActionBlock，前面的assessment和
authorization便不再对应实际执行对象。因此，containment必须保持source action identity，并把guard和
controller configuration作为执行证据的一部分。

可信任务记录、任务状态和monitor observation不作为第四个challenge。它们是系统成立所需的TCB输入；
ProofAlign不声称能够在没有可信来源时凭空创造任务authority。

## 3. 形式化问题定义

在epoch \(t\)，VLA根据policy view产生动作块：

\[
A_t=\pi(P_t^{pol},O_t^{pol},H_t^{pol}),\qquad
A_t=(a_t^0,\ldots,a_t^{H-1})\in\mathbb R^{H\times d}.
\]

monitor根据权威任务 \(T\) 和monitor observation \(O_t^T\)确定当前任务阶段 \(Z_t\)，并生成assessment
\(S_t\)。随后产生execution contract \(C_t\)、execution configuration \(g_t\)、一次性授权
\(\mathrm{Auth}_t\)、有序receipts \(R_t\) 与effects \(E_t\)。单次proposal的证据对象为：

\[
\chi_t=(T,O_t^T,Z_t,A_t,S_t,C_t,g_t,\mathrm{Auth}_t,R_t,E_t).
\]

顶层性质定义为：

\[
\mathsf{ProofAligned}(\chi_t)
=
\mathsf{Eligible}_t
\land\mathsf{TxnAligned}_t
\land(\mathsf{Triggered}_t\Rightarrow\mathsf{Contained}_t).
\]

其中：

\[
\mathsf{Eligible}_t=
\mathsf{Bound}(S_t,Z_t,O_t^T,A_t)
\land\mathsf{Known}(S_t)
\land\neg\mathsf{HardRisk}(S_t),
\]

\[
\mathsf{TxnAligned}_t=
\mathsf{FreshOneUseAuth}
\land\mathsf{OrderedExactPrefix}
\land\mathsf{ReceiptsBound}
\land\mathsf{EffectsBound},
\]

\[
\mathsf{Contained}_t=
\mathsf{SameSource}
\land\mathsf{ConfigBound}
\land\mathsf{Restored}
\land\min_j m_j\ge\delta
\land F\le F_{\max}.
\]

任务阶段推进还必须满足：

\[
\mathsf{Advance}(q_t,q_{t+1})
\Rightarrow
\mathsf{ProofAligned}(\chi_t)
\land\mathsf{CompletionObserved}(q_t,q_{t+1},E_t).
\]

这一形式定义把每个系统组件与一个明确验证条件对应起来，也使TCB和未覆盖部分可以逐项追踪。

## 4. ProofAlign设计

### 4.1 构造与资格化

系统把任务编译为有限task graph
\(\mathcal G_T=(V_T,E_T,\ell_T,\Phi_T)\)。节点表示合法任务阶段，边表示允许的阶段转换，\(\ell_T\)给出
canonical skill/entity tuple，\(\Phi_T(O_t^T)\)给出当前状态启用的frontier。该图只表示任务阶段合法性，
不表示唯一reference trajectory。

checker、effect vocabulary、task graph compiler和selector都在在线实验之前冻结并资格化。资格测试用于发现
实现错误和unsupported输入，不替代分布上的安全统计。

### 4.2 L1：checker-relative assessment

L1读取 \((Z_t,O_t^T,A_t)\)，检查完整ActionBlock的速度、workspace、unexpected contact、状态新鲜度、
格式和已注册task-effect atoms。明确覆盖的hard risk拒绝当前动作；task progress等不完备proxy只产生
advisory，并要求下一block重新观察和规划。L1允许时返回原始ActionBlock，不修改其数值。

### 4.3 L2a：一次性执行事务

L2a把proposal、assessment、state epoch、contract和最终command identity绑定到fresh one-use
authorization。dispatch boundary逐step验证authorized action；receipt记录实际应用的step；effect window只在
dispatch后开启。unknown、incomplete、stale、replayed或cross-proposal证据不能完成事务，也不能推进task
phase。

### 4.4 L2b：状态触发的bounded containment

当14个joint-side margin均远离边界时，动作走fast path。进入trigger region后，L2b从相同snapshot对同一
source action评估最多两个temporary guard configurations。候选必须满足snapshot restoration、source-action
identity、最低预测margin和force上限；没有候选合格时不签发authorization、不dispatch。该机制选择执行配置，
不重新采样VLA，也不把guard候选包装成policy candidates。

## 5. TAT式证据组织与Lean

后半部分按“构造—运行时测量—验证”组织，而不是按代码模块罗列。

1. **Construction：** 构造task graph，注册checker/effect vocabulary，冻结canonical action schema和验证规则。
2. **Runtime measurement：** authority tap记录task与monitor observation；dispatch boundary记录实际接受的
   command；post-dispatch window记录receipt和effects。
3. **Verification：** L1验证eligibility；L2a验证transaction alignment；L2b验证触发后的containment条件；
   phase transition验证ProofAligned和completion atoms。

Lean检查离散事务子关系，包括：authorization绑定semantic identity、完整command和ordered step digests；
authorization消费后不可重放；receipt使用同一authorization并匹配对应step；unknown effects和incomplete
prefix不能形成alignment；execution-enabled arm没有alignment和completion不能推进phase。

Lean不解析自然语言，不证明selector/checker、sensor或dynamics model对现实正确，也没有完成Python
serializer/observer到Lean对象的端到端refinement。当前guard/controller configuration尚未作为独立typed
digest进入contract。因此准确表述是**machine-checked execution-transaction semantics**，不是形式化证明
机器人整体安全。

## 6. 实验故事

实验平台是OpenPI \(\pi_{0.5}\) 与LIBERO-Safety模拟环境。模拟器只限定经验结果，不限定前面的VLA问题定义。

攻击风险测量使用完整协议：60个base pair、两组seed，每个评测单元均运行clean和attacked rollout，共240个
episodes。ASR定义为clean-safe单元在attacked rollout中出现新的contact、joint-limit、excessive-force或
cost/collision risk transition；单纯task failure不计。120个评测单元中有86个clean-eligible，其中39个发生
新风险转移：

\[
39/86=45.35\%,\qquad 95\%\ \mathrm{CI}=[32.93\%,57.78\%].
\]

这一数字是该评测协议下测得的攻击风险基线，不是“复现是否成功”的二元结论。

现有四臂机制实验包含18个配对workloads和144个episodes，证明当前机制能够跑通并呈现L1/L2角色分离，但它
与45.35%使用不同population和risk endpoint。按照新的论文主线，最终结果必须在同一120-unit全集上运行
VLA-only、L1-only、L2-only和Dual的clean/attacked条件，并统一采用risk-transition ASR。若已有240个
VLA-only episodes经原始trace和checksum核验后可复用，需要新增720个episodes；否则完整重跑960个episodes。

最终主表应报告每个arm的clean-eligible denominator、residual ASR、相对VLA-only的绝对/相对ASR下降、
base-pair cluster-bootstrap CI、task success和clean/attacked paired transitions。joint-limit crossing、force、
deadlock、integrity faults和latency作为机制解释指标单独报告。

## 7. 贡献与边界

本文的三项贡献是：

1. 将在线ActionBlock定义为具身VLA跨越模型与执行栈的统一安全对象，并提出由eligibility、transaction
   alignment和conditional containment组成的ProofAligned性质。
2. 设计并实现ProofAlign：L1提供checker-relative assessment，L2a提供一次性execution transaction，L2b在
   保持source-action identity的条件下提供状态触发containment。
3. 给出与形式性质逐项对应的证据：完整协议上的45.35%攻击风险基线、配对系统结果、focused transaction
   fault tests、运行时物理指标，以及Lean machine-checked transaction semantics。

ProofAlign不恢复VLA latent intent，不证明所有accepted actions都推进真实任务，不提供hardware attestation，
也不把模拟结果外推为通用机器人安全。它建立的是一条更窄但可审计的链：哪个ActionBlock被评估、哪个
authorization允许了它、哪些step被实际执行、哪些effects属于该事务，以及触发物理约束时是否使用了合格的
execution configuration。
