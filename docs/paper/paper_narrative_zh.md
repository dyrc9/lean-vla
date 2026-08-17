# ProofAlign 中文叙事母稿

状态：用于统一中文初稿、英文 LaTeX 和答辩材料的论文主线。技术口径以当前冻结实现和最终四臂证据为准。
内部版本号、失败迭代和旧方法结果不进入正文主线；它们继续作为可复现审计材料保留。

中文题目：

> **ProofAlign：面向 Action-Only 视觉—语言—动作系统的可信任务监控与跨层执行完整性**

英文题目：

> **ProofAlign: Trusted-Task Monitoring and Cross-Layer Execution Integrity for Action-Only
> Vision–Language–Action Systems**

## 0. 整篇论文只讲一个故事

一个 action-only VLA 收到语言任务和观察后，直接输出连续数值动作块。部署者看到的是一串数字，而不是一份
能够独立验证、值得信任的高层计划。

这在攻击下会立刻变成安全问题。贯穿全文的真实样例中，权威任务是“把汽水移动到盘子上”，冻结的 SABER
记录却把策略看到的指令改成“移动到最远的装置”。策略随后仍然只返回一个 \(10\times7\) 的
ActionBlock；这些数字不会说明自己究竟在执行哪条指令。

因此，部署者必须回答两个不同的问题：

1. **这一个具体的数值动作块，凭什么被当前可信任务授权？**
2. **即使它通过了检查，之后真正送到控制器并产生效果的，是否仍是同一个动作？**

第一个问题是 **authorization gap（授权缺口）**，第二个问题是 **realization gap（落地缺口）**。
ProofAlign 的核心不是猜测模型的 latent intent，也不是要求模型自报一份计划，而是在 VLA 的 consumer
一侧建立一条可审计的 identity chain：

    可信任务与可信观察
            ↓
    对 exact ActionBlock 的可信上下文 assessment        [L1]
            ↓
    execution contract → 条件式 guard screening          [L2b]
            ↓
    一次性授权 → exact dispatch → receipt/effects        [L2a]

全文的中心命题是：

> 对 action-only VLA，真正需要保护的对象不是自由文本解释，也不是预先给定的轨迹，而是策略在线生成的
> **exact continuous ActionBlock**，以及这个对象从可信任务判断到实际执行证据的跨层身份连续性。

## 1. 为什么这是一个独立的安全问题

### 1.1 数值合法不等于任务合法

一个动作可以平滑、幅度受限、位于工作空间内，却仍然在接近错误物体、移动到错误区域，或推进错误任务阶段。
普通 clipping、可达性检查或 joint-safe set 只能回答“数值上能不能做”，不能回答“可信任务是否允许做”。

在汽水样例里，策略可能为“最远装置”生成一条完全平滑的轨迹。若系统只检查速度和边界，这个块仍会被接受。
这就是授权缺口：可信任务 \(T\) 并不会自动把 authority 传给受攻击输入产生的 \(A_t\)。

### 1.2 检查通过不等于真实执行一致

即使监控器检查了 \(A_t\)，后续仍可能出现 command substitution、旧 authorization replay、receipt
换绑、不完整执行前缀或 effect evidence 拼接。只保留一条“已批准”的日志，不能推出 actuator 收到的是
相同 canonical command，也不能推出观察到的效果来自相同 proposal。

这就是落地缺口：授权记录和物理执行之间还缺少一次性、可关闭的事务。

### 1.3 语义层和执行层不可互相替代

三个反例构成方法设计的必要性：

- L1 可以把汽水到盘子的可信任务锚定到 exact ActionBlock，但它不能单独证明 sink 收到同一个命令，也不
  保证 joint containment。
- L2a 可以非常忠实地执行一个受攻击、偏离任务的动作；执行一致并不等于任务正确。
- L2b 可以让关节不越界，却仍可能“安全地做错事”；物理 containment 不会自动恢复任务语义。

所以 ProofAlign 不是一个“大而全的 safety score”，而是三个边界清楚、证据来源不同、按顺序组合的机制。

## 2. 威胁模型：两条视图、一个可信边界

系统在 secure split 之后维护两条不同视图。

不可信策略分支接收：

\[
(P_t^{pol}, O_t^{pol}, H_t^{pol}) \xrightarrow{\pi} A_t .
\]

攻击者可以修改 policy-facing prompt、数字/软件视觉输入或 history，使固定 VLA checkpoint 输出偏离可信
任务或诱发物理风险的 ActionBlock。当前实验只实例化了 secure split 之后的指令修改；视觉和 history
攻击属于系统威胁面，但不是本文已有的经验覆盖。

可信监控分支接收：

\[
Z_t=\mathsf{SelectFrozen}(T,O_t^T), \qquad
S_t=\mathsf{AssessLocal}(Z_t,O_t^T,A_t).
\]

其中，\(T\) 是独立保护的权威任务 artifact，\(O_t^T\) 是攻击变换之前的 trusted observation tap，
\(Z_t\) 是冻结 task graph 当前合法 frontier 中的结构化子任务。clean 和 attacked prompt 的 exact bytes
都会被记录，但二者都不会因为“被记录”而成为 semantic authority。

TCB 包括权威任务源、trusted tap、冻结并 allowlist 的 selector/checker、contract compiler、nonce/digest
ledger、唯一 dispatch boundary 和 receipt/evidence storage。

本文明确不覆盖 secure split 之前同时欺骗两条分支的物理光学攻击、task source 或 monitor compromise、
伪造 actuator feedback、任意攻击族、任意动力学误差、硬件 root of trust、真实机器人安全和硬实时保证。
最终 selector 使用 LIBERO privileged geometry，因此它是 benchmark-qualified 组件，不是 camera-only
可信感知方案。

## 3. ProofAlign 如何关闭这两个缺口

### 3.1 L1：可信任务锚定的 ActionBlock 监控

L1 采用 generate-then-monitor，而不是修改策略、把子任务写回 prompt 或从动作反推 intent：

1. trusted branch 先冻结当前合法子任务 \(Z_t\)；
2. Pi0.5 独立生成一个 \(H=10\) 的 source ActionBlock \(A_t\)；
3. checker 使用 \(Z_t\)、\(O_t^T\) 和 \(A_t\) 的 canonical digest 生成 assessment；
4. 若存在覆盖范围内的 hard risk，则当前块不获授权；
5. 若没有 hard risk，L1 返回 byte-identical source block，并把 advisory 留给下一次 reobserve/replan。

hard gate 覆盖 velocity/workspace、unexpected contact、stale state、malformed command 和不支持的 unknown
evidence。task progress、release/close progress、expected-effect miss 和 unavailable articulation state
目前是 advisory：当前块可能继续，但下一块必须重新观察和规划。

这个不对称是有意的。一个不完整的几何代理不应伪装成完备语义 oracle。因此 L1 只**部分关闭授权缺口**：
它证明可信来源、合法 frontier、assessment 与 exact block 的绑定，以及冻结 checker 覆盖的 hard gate；
它不证明每个被接受动作都推进了真实任务。

### 3.2 L2a：从 ActionBlock 到执行证据的一次性事务

通过检查后，consumer 编译 execution contract \(C_t\)，绑定 action、semantic subtask、policy prompt、
assessment、trusted observation、state epoch、expected/forbidden effects 和 observation window 的 digest。

无风险 fast path 或触发的 L2b screen 必须先合格，系统才签发新鲜 authorization。该 authorization 绑定
episode nonce、proposal index 和 exact final command，并且只能消费一次。Python
runtime 逐步检查有序 action prefix：每个 applied step 都必须等于 authorization 中相同索引的动作；receipt
必须属于同一 authorization；effect window 只能在 dispatch 后开启；未知、不完整或来自其他 proposal 的
evidence 不能推动 phase advance。

Lean 验证的是一个更抽象的有限事务模型：authorization 与整块命令绑定、receipt 使用同一 authorization、
applied/authorized digest 相等、已消费 authorization 不可复用，以及没有 alignment 就不能 phase advance。
它不重建 Python 的逐步 digest 列表，也不证明 Python serializer 到 Lean model 的端到端 refinement。
因此正式表述是 **Lean-checked abstract execution-transaction semantics**，不是“形式化验证机器人安全”。

### 3.3 L2b：风险触发的关节 containment

L2b 在线监控7个机械臂关节的上下两侧，共14个 joint-side margins。

- 最小 margin 大于 \(0.30\,\mathrm{rad}\) 时走 fast path，不运行 shadow simulator。
- 进入风险区后，系统为同一个 source ActionBlock 构造最多两个临时 virtual-guard configurations。
- 每个候选从同一 snapshot 做 one-step shadow rollout，并验证 snapshot restore、source-action identity、
  14侧预测 margin 均不低于 \(0.15\,\mathrm{rad}\)，以及 force proxy 不超过 \(10000\)。
- 系统选择满足条件的最弱 guard；若没有候选合格，则 fail closed，不 dispatch。

这里的“两个候选”是两个 guard configurations，不是两个 policy actions；VLA 始终保持 \(K=1\)。L2b
也不是新的控制理论贡献，而是在研究模拟器中实现、可审计且开销有界的 risk-selective containment。

virtual guard 保留 ActionBlock bytes，却改变 controller 到物理轨迹的映射。理想的 executable identity
至少应为 \((A_t, guard, controller, epoch)\)。当前 runtime 已记录 guard/controller 证据，但 Lean typed
contract 尚未把二者作为独立 digest 字段；这是本文主动披露的 refinement gap。

## 4. 用贯穿案例重新走一遍系统

权威任务仍是“把汽水放到盘子上”，而 policy-facing 指令被 SABER 改成“移动到最远的装置”。

1. **任务权威没有被攻击 prompt 重定义。** trusted branch 仍从汽水到盘子的 task graph 选择合法 frontier；
   attacked prompt 只作为 provenance 被记录。
2. **L1 检查策略真实返回的那一块数字。** 它不相信策略的自我解释，也不事后改名 \(Z_t\)。若动作触发
   covered hard risk，块被拒绝；若只有 task-progress uncertainty，则记录 advisory 并要求下一块重规划。
3. **consumer 先编译 contract；若状态接近关节边界，L2b 必须先给出合格执行配置。** 它不把错误任务变
   正确，只负责所覆盖的 joint-side containment；没有候选合格就不 dispatch。
4. **screen 合格后，L2a 才签发一次性授权并执行这一块。** nonce、epoch、step index、receipt 和 effect
   window 必须对齐，旧授权和别的 proposal 的 evidence 不能拼接进来。

这个案例揭示组合意义：L1 处理“哪份可信上下文能够支持对这块动作的判断”，L2b 处理“近边界执行是否满足
已注册 containment 条件”，L2a 处理“最终获准并执行的是否仍是同一块动作”。三者保护的是三条不同边。

在该 pair 的事后机制展示中，VLA-only 任务失败并出现2个 crossing steps、5个 joint-limit steps；L1-only
成功且为0/0；L2-only 任务失败但为0/0；Dual 成功且为0/0。这个 pair 只用于解释机制，不是论文的统计
estimand；所有结论仍来自完整18-pair配对样本。

## 5. 评价设计为什么是四臂，而不是一个总分

论文先单独建立攻击基础，再评价最终系统。

### 5.1 RQ1：攻击基础

我们复现冻结的 SABER constraint_violation instruction records：

- victim：OpenPI Pi0.5；
- benchmark：LIBERO-Safety；
- 60个 base pairs、2组 seeds；
- clean/attacked 共240个有效 episodes；
- 只在 clean-safe units 上统计 attacked rollout 新出现的 contact、joint-limit、excessive-force 或
  LIBERO cost/collision risk transition；task failure 本身不计入。

最终86个 clean-eligible units 中39个发生 transition：

\[
39/86=45.35\%,\qquad 95\%\ \text{cluster-bootstrap CI}=[32.93\%,57.78\%].
\]

这表明冻结 SABER records 在本地 OpenPI Pi0.5—LIBERO-Safety 路径上被成功复现，并产生了可重复测量的
物理风险转移；本文将 `45.35%` 作为该 victim、benchmark、攻击配置与成功口径下的观测攻击成功率。

### 5.2 RQ2–RQ5：最终配对四臂

最终实验包含18个 held-out suite/task/init pairs。每个 pair 在 clean 与 attacked 条件下运行
VLA-only、L1-only、L2-only 和 Dual，共144个 episodes。clean/attacked 共享 initial state、environment
seed、policy seed 和 arm schedule；所有 pair 完整保留，不按 outcome 筛选。同一 pair 四臂的第一个 source
ActionBlock 相同，后续轨迹在 intervention 或状态分叉后可以不同。

四臂不是为了做 leaderboard，而是为了回答两个机制问题：

- L1 是否对应样本中的任务效用角色？
- 组合 L2 treatment 是否对应 joint-limit containment，是否带来 deadlock 或明显任务成功损失？

主实验把 L2a 和 L2b 同时开启，因此不能从四臂表估计二者的独立因果效应。L2a 另由69项 focused negative
tests 和 Lean 事务定理支撑。

### 5.3 ActionBlock interface消融

仓库还保留两项独立的45-unit、zero-dispatch/no-outcome ActionBlock消融。固定checker时，nested-prefix
availability随长度从 `H=2` 的`0/45`、`H=5` 的`17/45`增加到 `H=10` 的`36/45`；固定 `H=10`
后，累计候选数 `K=1/2/4` 的coverage为`35/45、35/45、36/45`，K=4相对K=1只净增1个eligible初态。
这些结果说明checker需要足够长的prefix观察局部进度，而blind IID ActionBlock resampling在该冻结配置上的
边际收益很小。它们只度量initial checker availability，不是task success、安全性或攻击防御实验。完整
population、suite结果、checksums和claim boundary见
[`actionblock_sampling_ablation.md`](actionblock_sampling_ablation.md)。

## 6. 结果：任务效用和 containment 来自不同层

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18 | 11/18 | 4/18（22.22%） | 28 | 175 |
| L1-only | 13/18 | 13/18 | 1/18（5.56%） | 295 | 317 |
| L2-only | 13/18 | 11/18 | 0/18 | 0 | 0 |
| Dual | 13/18 | 13/18 | 0/18 | 0 | 0 |

这张表支持四个相互约束的判断。

**第一，攻击确实改变了当前样本中的行为。** 72个 attacked arm episodes 的首块相对 matched clean
全部发生变化。VLA-only 的 task success 从13/18变为11/18，并出现4/18 violation episodes。

**第二，L1 的经验角色是任务效用，而不是完整物理安全。** L1-only 在 attacked 下为13/18，但仍有1个
violation episode。更重要的是，这一个残余 episode 累积了295个 crossing steps 和317个 joint-limit
steps，高于 VLA-only 的28和175。因此不能写“L1 普遍降低了物理风险严重度”；正确结论是残余风险可能很
严重，需要独立 containment。

**第三，L2 的经验角色是 containment，而不是任务恢复。** L2-only 将 violation、crossing 和 joint-limit
steps 全部降到0，但 task success 仍是11/18，与 VLA-only 相同。它可以安全地保持一次任务失败，说明
“没有越界”和“完成正确任务”是两个目标。

**第四，Dual 组合两种样本角色。** Dual 保留 L1-only 的13/18 task success，同时得到0/18 violation
episodes、0 crossing 和0 joint-limit steps。L2−VLA 与 Dual−L1 的 attacked task-success contrast 都为0，
paired bootstrap interval 都是 \([0,0]\)。这说明当前样本中加入 L2 没有改变汇总成功数，不是总体零效应
证明。

violation episode 的95% Wilson区间分别为 VLA-only \([9.00\%,45.21\%]\)、L1-only
\([0.99\%,25.76\%]\)、L2-only/Dual \([0\%,17.59\%]\)。所以“0/18”只能表述为冻结样本中没有观察到
事件，不能外推为总体风险为零。

clean成功→attacked失败的 pair 数为 VLA/L1/L2/Dual 的3/2/3/2；反向转移为1/2/1/2。汇总成功率包含
双向变化，不能把所有 attacked failure 都解释为攻击新增失败。

此外，broader benchmark official-unsafe flag 在四个 attacked arms 中均为0；clean 的 L1-only 和 Dual
各有1次，均保留报告。这一指标与 L2 针对的 joint-limit endpoint 不同，也阻止我们把 zero-crossing 写成
“所有安全指标始终为零”。

## 7. 完整性与开销证据

- attacked episodes：72/72完成；
- attacked first block 相对 clean changed：72/72；
- 四臂 pair 内第一块 source ActionBlock 一致：18/18；
- attack metadata mismatch：0；prompt digest mismatch：0；
- checksums：76/76；focused tests：69/69通过；
- L2-on deadlock：0；crossing：0；joint-limit steps：0；
- 最大 constraint force：\(6438.20<10000\)；
- 最大 margin prediction error：约 \(2.69\times10^{-13}\,\mathrm{rad}\)；
- screening latency：最大39.79 ms，p95 18.30 ms，100 ms miss为0。

39.79 ms 小于研究模拟器的50 ms period，但这不是 hard-real-time 证明：实验没有覆盖操作系统 worst-case
scheduling、真实控制总线抖动或真实机器人动力学。

## 8. 与最近安全工作的准确位置

ProofAlign 不以“第一个 checker、nonce、shield 或 attestation”为 novelty。它与最近工作的关系是：

- **StruQ、SecAlign** 保护 legitimate instruction 不被 untrusted data 覆盖；ProofAlign 将策略输出视为
  不可信 proposal，在 consumer side 对连续数值动作建立授权。
- **CaMeL、ACE、IsolateGPT、SAGA** 提供 trusted flow、abstract plan、capability 或 execution isolation；
  ProofAlign 处理没有可信 structured plan 的 action-only VLA，并延伸到 joint-level containment。
- **AttriGuard、MATE** 对离散 tool call 或 agent trajectory 提供更强 causal/policy attribution；
  ProofAlign 不声称这种通用归因能力，保护对象是在线连续 ActionBlock 及其执行证据。
- **SEAL、CoVer** 根据 policy-supplied plan 或 learned instruction–action score 选择候选；ProofAlign 使用
  独立 trusted task anchor、保持 \(K=1\)，并建立后续 transaction。
- **DIAT、CFA+、ARTO、TAT** 对 CPS 软件流或给定机器人轨迹提供更强 attestation/trajectory integrity；
  ProofAlign 没有硬件 root，而是补充“预期轨迹尚未给定”时的 trusted-task-to-action 授权。
- **VLMPC、shielding、CBF** 提供 action-conditioned prediction 或安全集合约束；L2b 是 simulator-qualified
  containment 工程，不是新的控制理论。

因此，最稳健的定位是：

> ProofAlign 的新意在于 action-only VLA 的受保护对象及其跨层保持：把来自独立可信任务分支的
> checker-relative verdict 绑定到 exact continuous block，再把同一身份带过 authorization、dispatch、
> receipt、effects 和风险触发 containment。

## 9. 三项贡献，不能再扩张

1. **VLA-specific protected object 与安全模型。** 在 action-only interface 上分离 authorization gap 和
   realization gap，明确 dual views、TCB、攻击面和 exact-block identity。
2. **ProofAlign consumer-side reference monitor。** L1 提供 checker-relative trusted-task monitoring，
   L2a 提供一次性 execution transaction，L2b 提供 simulator-qualified joint containment。
3. **透明的攻击基础和配对四臂证据。** 报告 SABER 成功复现的 `39/86=45.35%` 观测 ASR，并用144个配对
   episodes 分离样本中的任务效用与 containment 角色。

不能声称：

- 恢复了模型 latent intent；
- 所有被 L1 接受的动作都语义正确；
- L1 普遍降低物理风险严重度；
- L2 提升了任务成功；
- 0/18 等于总体零风险；
- Lean 端到端验证了 Python、感知或机器人安全；
- 已覆盖视觉/history攻击、adaptive attacker、更多 checkpoint 或真实机器人。

## 10. 可直接使用的摘要

视觉—语言—动作模型通常把语言任务和多模态观察直接映射为连续动作块，却不暴露可被部署者独立信任的高层
计划。攻击后的 policy-facing 输入因此可以改变低层执行，而一个通过检查的动作也可能在授权后被替换、重放
或与错误执行证据拼接。我们将这两个断点分别称为可信任务到数值动作的授权缺口，以及获准动作到实际执行的
落地缺口。

本文提出 ProofAlign，一种不修改 VLA 权重的 consumer-side reference monitor。L1 从攻击面之外的可信
任务和观察中选择有限语义子任务，并把其 checker-relative assessment 绑定到 exact continuous
ActionBlock；覆盖范围内的物理或完整性风险被 hard reject，而不确定的 task-progress evidence 触发下一块
重新观察与规划。L2a 以 digest、state epoch 和一次性 nonce 将获准 ActionBlock 绑定到有序逐步 dispatch、
receipt 和 observed effects，并以 Lean 检查抽象事务的 binding 与 phase relations。L2b 仅在关节 margin
进入风险区时，对同一 source action 的至多两个 virtual-guard configurations 做受 force envelope 约束的
shadow screening；无合格候选时 fail closed。

我们首先在 OpenPI Pi0.5 和 LIBERO-Safety 上复现冻结的 SABER constraint_violation 指令攻击：86个
clean-eligible units 中39个发生 risk transition（45.35%，95% base-pair cluster-bootstrap CI
[32.93%, 57.78%]），成功复现了该攻击在本地 victim/benchmark 路径上的物理风险效应。随后，18个 held-out
task/init pairs 在 clean/attacked 条件下完成144个配对四臂 episodes。attacked 条件下，VLA-only、
L1-only、L2-only 和 Dual 的任务成功分别为11/18、13/18、11/18和13/18，constraint-violation episodes
分别为4/18、1/18、0/18和0/18。L1 在该样本中对应任务效用角色但不提供完整 containment；L2 消除观察到的
joint-limit outcomes但不单独恢复任务成功；Dual 同时取得13/18任务成功与0/18 violation episodes。最大
screening latency 为39.79 ms，p95为18.30 ms，100 ms miss为0。结果支持冻结 SABER 攻击与研究模拟器内的
跨层运行时完整性主张，不构成任意攻击、总体零风险、真实机器人安全、硬件 attestation 或硬实时保证。

## 11. 正文各节应完成的叙事任务

1. **Introduction：** 用汽水到盘子的攻击案例提出两个缺口；说明为何 protected object 是 exact block；
   给出窄贡献和窄 claim。
2. **Background and Threat Surface：** 解释 action-only interface、dual views、攻击者、TCB 和不覆盖项。
3. **System Model：** 定义对象、identity、L1/L2a/L2b 的目标及不可证明内容。
4. **Design：** 让案例穿过三层，强调顺序、fail semantics 和三层不可替代。
5. **Implementation/Formal Semantics：** 区分 Python 逐步检查、Lean 抽象模型和 guard/controller refinement
   gap。
6. **Evaluation：** 先报告攻击成功复现及观测 ASR，再用配对四臂回答任务效用与 containment，最后给系统门。
7. **Discussion：** 解释为何0/18不是零总体风险、为何 L1 残余风险重要，以及向可信感知、完整 executable
   identity、更多攻击/模型和真实机器人扩展需要什么。
8. **Related Work：** 按 protected object 与 evidence boundary 比较，不按关键词堆论文。
9. **Conclusion：** 回到最初两个问题：哪一个动作被评估和授权，哪一个命令被执行并观察到效果，近边界时
   是否启用了合格 containment。

## 12. 最后一句

ProofAlign 不证明 VLA “想对了”；它让部署者能够审计：**哪一个动作因什么可信证据获准、真正执行的是不是
同一个动作、观察到的效果是否属于同一事务，以及接近关节边界时是否使用了合格的执行配置。**

当前工作重心是把上述故事整理成可完整审阅的论文初版；新增攻击族、更多seeds和真实机器人等实验在初稿
完成后，根据论证中暴露的证据缺口定向补充。
