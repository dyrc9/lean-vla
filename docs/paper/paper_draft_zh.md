# ProofAlign：面向 Action-Only VLA 的可信任务监控与跨层执行完整性

> **中文初稿，供论文结构、论证和数字冻结使用。** 题目、作者、单位、匿名化信息和正式 BibTeX 待投稿模板
> 确定后补齐。本文中的方法与结果表述以当前冻结实现和证据为准，不把未来扩展写成已完成贡献。

英文题目：**ProofAlign: Trusted-Task Monitoring and Cross-Layer Execution Integrity for
Action-Only Vision-Language-Action Systems**

## 摘要

视觉—语言—动作模型（VLA）把自然语言任务和多模态观察直接映射为连续机器人动作。现有攻击已经表明，
对 policy-facing 指令或观察的有限修改可以改变机器人行为；然而，许多部署接口只暴露数值 ActionBlock，
既没有可直接信任的高层计划，也没有证据证明被检查的动作就是随后执行并产生物理效果的动作。由此产生两个
相互独立的断点：可信任务与数值动作之间的 **authorization gap**，以及获准动作与实际执行之间的
**realization gap**。

本文提出 ProofAlign，一种不修改 VLA 权重的 consumer-side 跨层 reference monitor。L1 在攻击面之外维护
可信任务和观察，从有限 task graph 中生成结构化语义子任务，并对 VLA 给出的 exact continuous
ActionBlock 做 provenance 检查、局部物理风险筛查和 audited replanning。当前 task-progress mismatch 是
advisory，而速度、工作区、unexpected contact、stale/malformed command 和 unknown evidence 才进入 hard
gate；因此 L1 提供的是相对于冻结 checker 的有限授权，而不是完整 semantic soundness。L2a 将获准
ActionBlock、assessment、nonce、dispatch、逐步 receipt 和 observed effects 绑定为一次性执行事务，并用
Lean 检查抽象 binding 与 phase relations。L2b 在接近关节边界时，以同一 source ActionBlock 对最多两个临时
virtual-guard 配置做有界 shadow screening，在统一 force envelope 下选择最弱可行 guard，否则 fail closed。

我们首先复现 SABER 的 `constraint_violation` 指令攻击。在60个 base pairs、2组 seeds 的240个 episodes 中，
86个 clean-eligible units 有39个出现新的 risk transition，即 `45.35%`，base-pair cluster bootstrap 95%
置信区间为 `[32.93%, 57.78%]`。该结果成功复现了 SABER 在本地 victim/benchmark 路径上的物理风险效应。
随后，我们在18个 held-out task/init pairs 上运行 clean/attacked 配对四臂实验，共144个 episodes。
在 attacked 条件下，VLA-only、L1-only、L2-only 和 Dual 的任务成功分别为 `11/18`、`13/18`、`11/18`
和 `13/18`；constraint-violation episodes 分别为 `4/18`、`1/18`、`0/18` 和 `0/18`。L1 在该
冻结配对样本中保持了任务效用，但其单个 violation episode 累积了较多 crossing steps，不能据此声称广义物理
安全改善；L2 消除了观察到的 joint-limit crossings，而 Dual 同时取得 `13/18` task success 和 `0/18`
violation episodes。最大 screening latency 为 `39.79 ms`，p95 为 `18.30 ms`，100 ms deadline miss 为0。
这些结果支持冻结攻击族与研究模拟器中的跨层完整性主张，不构成任意攻击、真实机器人安全、硬件
attestation 或硬实时保证。

## 1. 引言

VLA 模型正在成为通用机器人策略的重要接口。与传统“感知—规划—控制”栈不同，部署者可能只向模型提供
图像、状态和自然语言任务，然后直接收到长度为若干步的连续动作序列。这个接口便于扩展，却模糊了一个基本
安全问题：谁授权了即将执行的具体动作？当 policy-facing prompt、视觉输入或交互 history 被操纵时，模型
可以在不输出显式恶意计划的情况下改变数值轨迹。对语言输出做拒绝检测，或者要求模型解释自己的计划，都不
足以证明 actuator 将执行符合可信任务的动作。

我们的一个 held-out workload 把这个问题具体化：权威任务是“把汽水移动到盘子上”，冻结的 SABER 记录却
把策略看到的指令改成“移动到最远的装置”。action-only policy 随后只返回一块 \(10\times7\) 的连续数值；
它不会提供一份可以独立信任的解释，说明这些数字究竟由哪条任务授权。一个文本拒绝检测器在控制器边界之前
太早，一个 rollout 结束后的成败指标又太晚：部署系统需要在这块动作真正跨过 dispatch boundary 时建立
安全判断。

这个问题包含两个不同的缺口。第一，可信任务 `T` 与策略输出 `A_t` 之间不存在天然授权关系。即使动作满足
普通数值范围，它也可能推进错误对象、错误区域或错误任务阶段，我们称之为 authorization gap。第二，即使
某个 ActionBlock 已经通过检查，之后仍可能发生 command substitution、stale replay、receipt 换绑、
observer blind spot 或执行期物理偏移，我们称之为 realization gap。前者要求独立于受攻击 policy view 的
任务锚点，后者要求从授权对象到 dispatch 和 effects 的持续 identity chain。

现有工作分别覆盖了这条链的局部。VLA attack 和 safety benchmark 测量攻击的物理后果 [SABER, LIBERO-Safety,
SafeVLA-Bench]；StruQ、SecAlign 与 CaMeL 研究 trusted/untrusted content 或控制流分离 [StruQ, SecAlign,
CaMeL]；AttriGuard 和 MATE 将用户意图或策略归因到离散调用与 agent trajectory [AttriGuard, MATE]；ACE、
IsolateGPT 和 SAGA 约束 LLM app 的计划、权限或隔离边界 [ACE, IsolateGPT, SAGA]；SEAL 与 CoVer 则根据
policy-supplied plan 或 learned score 选择 VLA 动作候选 [SEAL, CoVer]。在 CPS 一侧，DIAT、CFA+、ARTO 和
TAT 研究 control/data-flow 或给定机器人轨迹的完整性 [DIAT, CFA+, ARTO, TAT]。因此，本文不声称首次提出
intent-to-action alignment、trusted-plan/execution separation、action verification 或 trajectory integrity。
我们的问题更窄：当 VLA 不暴露可信 structured plan、只在线给出连续 ActionBlock 时，consumer 如何以独立
可信任务状态审计这个具体对象，并把同一身份延伸到软件执行事务和研究模拟器中的物理 containment？

ProofAlign 的核心是把自由文本“解释”替换成一个可绑定的系统对象。可信分支根据安全分叉前的任务和观察
生成 `SemanticSubtask Z_t`；不可信策略分支独立生成 `H×d` 数值 ActionBlock。L1 将 `Z_t`、trusted
observation、assessment 与 exact ActionBlock digest 绑定，只对冻结 checker 覆盖的 hard risk 做当前块
拒绝，对 task-progress mismatch 留下审计记录并在下一块重规划。L2a 为获准 ActionBlock 生成 nonce-bound
contract，要求 actual command、receipt 和 effects 在绑定窗口内一致。L2b 只在14侧 joint margin 进入风险区
时启动有限 shadow screening，以降低正常路径开销。

本文作出三项贡献：

1. 提出面向 action-only VLA 的跨层完整性问题定义，分离 trusted-task ActionBlock monitoring、软件执行
   事务身份和 physical containment，并明确 policy-facing attack surface 与可信计算基（TCB）。
2. 实现 ProofAlign reference monitor：L1 使用冻结 task graph/FSM 和解析式 local checker；L2a 使用
   digest/nonce-bound 一次性事务与 Lean-checked abstract phase semantics；L2b 使用状态触发、统一 force-envelope
   的多关节 virtual-guard screening。
3. 给出透明的攻击基础和配对四臂闭环证据：报告 SABER 成功复现的 `39/86=45.35%` 观测 ASR，并在相同
   runner、任务和随机种子上比较 VLA-only、L1-only、L2-only 与 Dual，展示任务效用和 joint-limit
   containment 的不同来源。

本文的中心 claim 有意保持狭窄：ProofAlign 不恢复模型的 latent intent，不证明每个获准动作都会推进任务，
也不建立真实机器人安全。它使一条具体运行时链可以被审计：哪一块动作被可信上下文评估，哪一次授权允许
它执行，实际应用了哪条命令，观察到哪些效果，以及接近关节边界时是否启用了合格 containment。

## 2. 背景与动机

### 2.1 Action-only VLA 接口及其安全含义

本文使用 OpenPI Pi0.5 [Pi0.5] 的 LIBERO 路径。策略输入包括 base/wrist RGB、末端位置与姿态、gripper state 和
task prompt，输出 `10×7` ActionBlock；每个动作包含三维平移增量、三维 axis-angle 旋转增量和 gripper
命令。最终 runner 使用 `replan_steps=10`，因此 consumer 实际接收并执行的是完整 `H=10` source block。
虽然 Pi0.5 的训练系统包含多种语义信号，本地 `pi05_libero` 部署接口并不暴露可由部署者独立验证的
structured plan。

这意味着模型 checkpoint 即使固定不变，运行时安全仍取决于可变的 policy-facing context。prompt、
observation 或 history 一旦被操纵，策略可能生成完全不同的连续轨迹；而 consumer 最终看到的仍只是一块
数值。动作本身不会说明它响应了哪条指令，也不会证明它与部署者原本批准的任务一致。因此，policy output
只能被视为 proposal，不能自动继承 task authority。ProofAlign 不修改 Pi0.5 参数，也不把可信子任务写回
policy prompt，正是为了在这个最低共同接口上建立独立安全边界。

### 2.2 现有攻击：被污染的模型上下文会转化为物理行为

最近的 VLA 攻击已经覆盖多种上下文通道。**指令攻击**方面，SABER 通过 bounded instruction edits 对多个
VLA 做黑盒压力测试，并以 task failure、trajectory length 和 constraint violation 衡量攻击后果 [SABER]。
它说明攻击者不需要控制模型权重，也不需要让模型输出一段显式恶意解释；只要改变 policy-facing
instruction，就可能改变之后的连续动作轨迹。本文贯穿案例正来自这一类攻击：权威任务仍是“把汽水移动到
盘子上”，但策略看到的冻结指令变成“移动到最远的装置”。

**视觉攻击**方面，FreezeVLA 说明受控视觉输入可以诱发 action freezing [FreezeVLA]。这类结果表明，即使
文本任务没有变化，攻击者仍可能通过模型观察通道改变动作生成。**具身模型越狱**方面，BadRobot 和
RoboPAIR 展示了语言或多模态 jailbreak 如何越过纯文本回答，转化为机器人拒绝失效或有害物理动作
[BadRobot, RoboPAIR]。这些攻击共同说明，VLA 安全不能只在文本输出层定义：模型上下文一旦受损，后果会
沿连续控制接口进入物理环境，并在长轨迹中累积。

本文不声称经验覆盖了上述全部攻击通道。我们的正式实验只实例化 secure split 之后的 SABER
`constraint_violation` 指令修改；视觉和 history attacks 用来界定更一般的 threat surface。这个区分很
重要：已有攻击为系统问题提供动机，冻结 SABER 记录则为本文的具体 evaluation 提供攻击源。

### 2.3 现有攻击暴露的两个结构性缺口

这些攻击首先暴露的是 **authority 丢失**。在 policy-facing context 可能受攻击的情况下，不能再把同一份
prompt 或模型生成的 explanation 当作任务权威。一个幅度受限、平滑且位于工作空间内的动作，仍可能接近
错误物体、移动到错误区域或推进错误任务阶段。换言之，常规数值合法性并不能推出 trusted-task
compatibility，这正是 authorization gap。

其次，即使某个动作已经通过 checker，安全结论也可能在后续软件与控制链中失效。command 可以被替换，
旧 authorization 可以被重放，receipt 或 effect evidence 可以与其他 proposal 拼接，执行前缀也可能不完整。
如果系统不能证明“被检查、被授权、被 dispatch、被观察”的始终是同一个 canonical action object，那么
检查结果无法落到真实执行上，这正是 realization gap。

针对这两个 gap，已有防御形成了几条清晰但彼此分离的路线：

| Gap | 防御路线与代表工作 | 它们保护什么 | 暴露出的边界 |
|---|---|---|---|
| Authorization | 输入信任分离：StruQ、SecAlign、CaMeL [StruQ, SecAlign, CaMeL] | 将 legitimate instruction 与 untrusted data 分开，或只从 trusted query 派生 control/data flow | 保护停在模型输入或数字 agent program flow；没有判断某个 exact continuous ActionBlock 是否被可信机器人任务授权 |
| Authorization | VLA action verification：SEAL、CoVer [SEAL, CoVer] | 将候选动作结果与 policy-supplied textual plan 对齐，或用 learned instruction–observation–action score 从多个候选中选择 | 依赖模型自报 plan、重写 instruction 或 `K>1` 候选；verifier 选择结束后，没有把同一 action identity 延伸到 dispatch、receipt 和 physical effects |
| Authorization | agent action attribution/plan enforcement：AttriGuard、ACE、MATE [AttriGuard, ACE, MATE] | 判断离散 tool call 是否由 user intent 支持，约束 concrete app execution 符合 trusted abstract plan，或依据策略审计 agent trajectory | 提供更强 causal attribution 或 plan enforcement，但对象是离散调用、app plan 或数字轨迹，不是依赖机器人状态与控制器语义的连续动作块 |
| Realization | operation/mission execution attestation：OAT、DIAT、ARI、CFA+、ARTO [OAT, DIAT, ARI, CFA+, ARTO] | 绑定 control flow、关键 data flow、fresh challenge 与 mission timing，抵抗软件路径劫持、data-only attacks 和旧 attestation replay | 对软件执行根、freshness 与 evidence 更强，但从已知程序和关键变量出发；不回答自然语言任务为何授权某个在线 VLA proposal，也没有定义 ActionBlock 的 proposal/epoch/step identity |
| Realization | robot trajectory integrity：TAT [TAT] | 用 timed motion events 与 joint measurements 检查 actual motion 是否符合 intended path | 直接支撑“预期动作与实际运动可能分离”，但假设 intended path 已经给定且可信；action-only VLA 中最关键的问题恰是如何从可信任务得到可授权的在线动作对象 |
| 两者之外的物理风险 | prediction、clipping、CBF 与 continuous-space shields [VLMPC, SafetyChance, RealizableShields] | 预测候选动作后果，或约束动作与安全集合相容 | 物理 admissibility 不等于 trusted-task compatibility；guard/controller 还可能改变 command 到 trajectory 的映射，却不自动产生 authorization、receipt 或 effect identity |

#### 从 execution attestation 到 ActionBlock transaction

C3 并不是一个没有文献基础的工程问题，但也不能被简化为“给动作算一次 hash”。已有执行完整性工作已经
分别说明了动态 control/data flow、freshness、执行顺序、时限以及物理轨迹为什么必须进入证据：OAT 对
operation 的 control flow 与关键 data 做联合 attestation，并用 verifier challenge 防止旧 attestation blob
重放 [OAT]；DIAT 将数据的正确生成、处理过程和 fresh nonce 带入 autonomous-system 协作证据 [DIAT]；
ARI 把正确执行与 timely execution 合为 real-time mission integrity [ARI]；CFA+ 持续监控 execution state，
用于发现或阻止非法 control-flow deviation [CFA+]；ARTO 进一步面向 real-time CPS 组合 control-flow 与
data-flow execution integrity [ARTO]。在命令越过软件边界之后，TAT 又说明 intended path 与 actual motion
不是同一个命题，需要 timed motion events 和 joint measurements 单独证明 [TAT]。表示层也有成熟原则：
JSON Canonicalization Scheme（JCS）专门为 hashing/signing 定义确定性的 JSON 表示 [JCS]；这说明 digest
之前必须先约定 canonical bytes，而不是假定不同 serializer 会自然得到同一身份。

这些工作为 realization gap 提供了原则，却没有直接定义 action-only VLA 中的一次在线 proposal 应怎样成为
完整事务。它们通常从一个已经指定的程序、mission 或 intended path 出发；而我们的起点是刚由 VLA 生成、
可能因受攻击上下文而改变的 `10×7` 连续 ActionBlock。这里的困难不只是比较一次 hash，而是整个异步执行链：

- ActionBlock 可能经过不同序列化（确定性表示与签名/哈希：[JCS]；ActionBlock schema 的具体化：本文）；
- authorization 可能被重放（fresh challenge/nonce 与 replay resistance：[OAT, DIAT]）；
- state epoch 可能已经改变（freshness 与 timely mission window：[OAT, DIAT, ARI]；VLA state-epoch binding：本文）；
- 系统可能只执行部分 action prefix（动态路径与 mission completion：[OAT, CFA+, ARI]；ActionBlock prefix 语义：本文）；
- step 顺序可能被调整（control-flow/path-order integrity：[OAT, CFA+]；连续动作 step-index binding：本文）；
- receipt 和 effects 可能属于不同 proposal（跨组件 data provenance：[DIAT]；cross-proposal splice 定义：本文）；
- 未来 observation 可能被用于补齐过去事务（freshness 与 timely evidence 原则：[OAT, DIAT, ARI]；dispatch-bound evidence window：本文）。

括号中的“本文”很重要：它表示相应论文或标准支撑的是 canonicalization、freshness、provenance、路径完整性
或时限原则，而不是声称它们已经直接实现了 VLA ActionBlock transaction。ProofAlign 将这些原则具体化为：
assessment、authorization 和 dispatch 绑定同一个 canonical ActionBlock；episode、proposal index 或 state
epoch 变化使旧 authorization 失效；逐步执行只能形成从 `step_index=0` 开始的有序 exact prefix；receipt 和
effects 必须携带同一 proposal/epoch/nonce/action/step identity；只有真实 dispatch 之后、绑定窗口内的
observation 才能完成当前事务。命令越过软件边界后，actual motion 是否符合 intended command 仍需类似 TAT
的独立物理证据 [TAT]，而不是由软件 receipt 自动推出。

因此，单个 hash 只能回答“两个已经 canonicalize 的字节串是否相同”，不能回答“它们是否属于同一
proposal、同一 state epoch、同一次 authorization、同一 dispatch window”。这里真正需要保护的是带时序和
上下文的 transaction identity，而不是一个脱离运行历史的 digest。ProofAlign 将它具体化为
`(action_digest, episode_nonce, proposal_index, state_epoch, step_index, evidence_window)`；其中 serialization、
cross-proposal receipt/effect splice 和 future-observation completion 是我们依据既有 freshness、provenance 与
timely-execution 原则，对 ActionBlock 异步链作出的系统化问题定义。我们没有声称已有论文已经逐项研究了
“VLA receipt 拼接”这一具体攻击。

这些边界不是说已有防御无效，而是说明它们在不同层停止：输入防御降低 policy 被劫持的概率，action verifier
选择看起来更符合 instruction/plan 的 proposal，attestation 和 trajectory integrity 再检查既定程序或路径
是否被实现。缺少的是一个共同受保护对象，把“可信任务支持哪一块动作”与“实际是否执行了同一块动作”连接
起来。因此，问题不是再加入一个覆盖所有风险的总分，而是把这些已被分别证明必要的边界组合起来。

### 2.4 设计动机与核心 insight：在攻击汇聚点保护 exact ActionBlock

上述攻击的入口不同：SABER 改指令，FreezeVLA 改视觉上下文，BadRobot 和 RoboPAIR 则利用具身模型的
指令遵循与拒绝边界。但它们最终都必须经过同一个稳定汇聚点，才能影响机器人：策略在线生成的 ActionBlock
即将被 consumer 接收并跨过 controller boundary。这个共同 choke point 构成我们的直接设计动机。与其假设
系统能够提前识别每一种攻击，不如把所有 policy output 都视为不可信 proposal，并在其转化为执行之前实施
complete mediation。

综合这些 stopping points，方法需要解决三个连续问题：可信 authority 从哪里来，哪一个对象被保护，以及
安全证据在哪里闭环。它们对应三个 insight。

我们的第一个是 **外部权威锚点 insight**。它来自输入分离与 trusted-plan 工作的启发，但把信任边界移到
机器人 consumer：**不需要、也不应尝试从受攻击后的策略输出恢复模型“真正想做什么”。** 对 action-only
interface，这个 latent intent 既不暴露，也无法成为独立可信 witness。部署者真正拥有的 authority 应来自
攻击面之外的 task artifact 和 trusted observation；它们为当前状态生成有限、可审计的 legal task frontier，
但既不修改 policy prompt，也不把模型自报 explanation 升格为 authority。

第二个是 **受保护对象 insight**。它来自 VLA verifier 暴露的 stopping point：**安全判断必须绑定到策略
实际生成的 exact continuous ActionBlock，而不是只绑定 instruction、模型 plan 或候选排名。** 保护对象
不是自由文本 explanation、离散 API call 或预先声明的 trajectory，而是在线产生、即将跨过 controller
boundary 的具体有序数值块。ProofAlign 保持单个 policy proposal（`K=1`）；L1 对这一块做
checker-relative assessment，而不是通过更多采样把任务成功增益混入安全机制。只有先冻结这个对象，后续
authorization、dispatch、receipt 和 effects 才有共同 identity anchor。

第三个是 **跨层证据闭环 insight**。它来自 attestation 与 trajectory-integrity 工作的前提：
**trusted-task compatibility、execution identity 和 physical containment 必须分层，而且后层只能保存前层
身份，不能替换前层语义。**
我们借用“执行必须产生独立 evidence”的系统原则，但不假定 intended path 已经给定；相反，先把可信上下文
verdict 固定到 exact ActionBlock，再以 proposal/epoch/nonce/step/window 把同一身份带过异步执行事务。
这给出 ProofAlign 的执行顺序：

```text
trusted task / observation
        -> exact ActionBlock assessment                         [L1]
        -> execution contract
        -> conditional guard screening near joint boundaries   [L2b]
        -> fresh one-use authorization
        -> exact dispatch / receipts / observed effects         [L2a]
```

L1 回答“哪份可信上下文支持对这一块动作的判断”；L2b 回答“近边界时是否存在满足已注册 margin 与 force
条件的执行配置”；L2a 回答“最终获准、实际应用并产生证据的是否仍是同一块动作”。由此，ProofAlign
不是让 VLA 变得不可攻击，而是让 attacked output 无法在缺少独立 assessment、合格 execution configuration
和一次性执行证据的情况下静默跨过 consumer boundary。

这一组合也揭示各层不可互换：L1 可以评估一个随后被替换的 command；L2a 可以忠实执行一个 task-divergent
command；L2b 可以约束关节风险，却仍然安全地完成错误任务。只有以 exact ActionBlock 为中间对象并保留
三类证据，两个 gap 才能在同一系统边界内被分别观察、分别失败和组合审计。

这一 insight 也直接决定评价方式。四臂实验分别打开 L1 和组合 L2 treatment，用来区分冻结样本中的任务效用
角色与 joint-limit containment；由于 L2a 和 L2b 在主 arm 中共同启用，主结果不估计二者的独立因果效应。
L2a 另由 focused negative integrity tests 和 Lean abstract transaction theorems 支撑，SABER rollout outcome
主要体现 L2b 的 containment。

## 3. 问题定义与威胁模型

### 3.1 部署边界与双视图

我们考虑一个 action-only VLA 部署：固定 policy checkpoint 接收任务序列化、观察和历史，并向 consumer
返回连续 ActionBlock。安全边界位于 policy output 与 controller/actuator 之间。ProofAlign 不改变 VLA
权重，也不要求 VLA 暴露内部 reasoning；即使 checkpoint 本身不可修改，它的输入和输出仍不被视为 semantic
authority。

系统把同一时刻的信息划分为两个信任视图：

```text
authority view: authoritative task T + pre-attack trusted observation O_t^T
policy view:    prompt P_t^pol + observation O_t^pol + history H_t^pol
```

可信任务 `T` 不是 policy prompt 的另一份普通副本。实际部署中，它可以是签名 job ticket、受保护 workflow
state 或 operator-approved task record；policy prompt 只是由 middleware 生成、可能被攻击的序列化。若系统
不存在独立保护的 task source，ProofAlign 不能凭空创建 semantic authority，其 L1 claim 不成立。

两条视图的关系定义为：

\[
Z_t=\mathsf{SelectFrozen}(T,O_t^T),\qquad
A_t=\pi(P_t^{pol},O_t^{pol},H_t^{pol}),\qquad
S_t=\mathsf{AssessLocal}(Z_t,O_t^T,A_t).
\]

\(Z_t\) 必须在 policy 生成 \(A_t\) 之前冻结。它既不是 policy input，也不是从 \(A_t\) 反推的 latent
intent。clean episode 中，\(P_t^{pol}\) 通常是 \(T\) 的正常 benchmark serialization；attacked episode
中，冻结 SABER record 修改其 exact bytes。两者都会被记录用于 provenance，但记录本身不会赋予 semantic
authority。

### 3.2 受保护对象与身份

在状态 epoch `t`，记：

- `T` 为攻击面之外的可信任务 artifact；
- `O_t^T` 为 secure split 之前 trusted tap 的观察；
- `P_t^pol`、`O_t^pol`、`H_t^pol` 为可能被攻击的 policy prompt、观察与 history；
- `Z_t = SelectFrozen(T, O_t^T)` 为有限 task graph 当前合法 frontier 中的 semantic subtask；
- `A_t = π(P_t^pol, O_t^pol, H_t^pol) ∈ R^(H×d)` 为 VLA source ActionBlock；
- `S_t = AssessLocal(Z_t, O_t^T, A_t)` 为绑定该 block 的局部 assessment；
- `g_t` 为默认或通过筛查的 guard/controller execution configuration；
- `C_t`、`Auth_t`、`R_t` 和 `E_t` 分别为 execution contract、一次性 authorization、dispatch receipt 和
  observed effect evidence。

`T/O_t^T/Z_t` 构成 semantic authority；policy prompt digest 被记录用于 provenance，但 clean serialization
和 attacked serialization 都不会反向成为 semantic authority。

本文所谓 exact ActionBlock identity，是带 schema tag、shape 和有序数值的 canonical JSON digest。它不等价
于底层 buffer identity，也不编码 dtype、endianness 或某条必然发生的物理轨迹。这个边界使软件命令身份与
执行配置、物理 realization 保持可区分。

每个对象还绑定 episode nonce、proposal index 和 state epoch。task、observation、候选 frontier、action
shape/value、checker configuration 或 epoch 的任何变化，都会使旧 assessment、contract 和 authorization
失效。理想的 executable identity 至少是
\((A_t,g_t,controllerConfig_t,epoch_t)\)；当前 runtime 记录 guard/controller evidence，但 Lean typed
contract 尚未将这些配置作为独立 digest 字段。

### 3.3 攻击者目标与能力

攻击者可以在 secure split 之后修改 policy-facing instruction、数字/软件视觉输入或 policy history，使
VLA 生成偏离可信任务、进入危险状态或造成执行失败的 ActionBlock。攻击者也可能尝试替换已授权 command、
重放旧 authorization、拼接不同 proposal 的 receipt/effects，或者提供不完整 evidence。

攻击者不需要让动作违反简单数值范围：一个平滑、幅度受限的 block 只要推进错误对象或任务阶段，就可能
成功利用 authorization gap。事务层攻击成功则意味着系统接受了与 assessment 不同的 command、复用了旧
authorization、用错误 receipt/effects 完成当前事务，或在证据不完整时错误推进 phase。

攻击者不能控制可信任务 adapter、安全分叉前的 trusted observation tap、冻结 selector/checker 及其
allowlist、contract compiler、single-dispatch boundary 和 receipt/evidence storage。当前 threat model 也
不包含 trusted actuator feedback 被伪造的情形。

经验实验只实例化 secure split 之后的 instruction modification 与模型内的 transaction faults；视觉输入和
policy history attack 在本文中定义系统范围，但没有被实验验证，不能写成经验 robustness claim。最终
SABER records 也是冻结、非自适应的；本文没有评价 defense-aware adaptive attacker。

### 3.4 可信计算基与假设

| TCB 组件 | 必须可信的性质 | 若被攻破的后果 |
|---|---|---|
| task source / adapter | `T` 真实表示 operator-approved task，且攻击者不能改写 | L1 会围绕错误任务建立内部一致的 authorization |
| trusted observation tap / secure split | \(O_t^T\) 在攻击变换之前捕获，tap identity 与 epoch 不可伪造 | trusted branch 与 policy branch 可能共同接受同一伪造世界 |
| task graph / selector / local checker | 代码、配置和 allowlist 冻结；artifact provenance 可验证 | 可能选择错误 \(Z_t\) 或 false-allow 一个 covered-risk action |
| contract compiler / digest-nonce ledger | canonicalization、proposal/epoch binding 与 nonce consumption 正确 | 可能发生 substitution、cross-proposal splice 或 replay |
| single-dispatch boundary | 所有 actuator command 都经过同一 mediation point | 绕过路径可以执行未授权 command |
| receipt/effect observer 与 storage | receipt 属于真实 dispatch，evidence window 与存储未被篡改 | 内部“对齐”的事务可能与真实物理效果不一致 |

VLA checkpoint 不属于 semantic authority：系统假定评价期间 checkpoint 固定，但它的 proposal 始终按
untrusted input-derived object 处理。最终 selector 使用 LIBERO privileged geometry；这使 task frontier
可审计，但只支持 benchmark qualification，不能被描述为 camera-only deployment perception。

### 3.5 安全目标

我们的目标不是证明 VLA 拥有正确 intent，而是在上述 TCB 下为两个 gap 定义可执行的条件。

**G1：checker-relative action eligibility。** 对启用 L1 的路径，若 exact \(A_t\) 获得进入 contract 的
资格，则必须满足：

\[
\mathsf{TrustedProv}(T,O_t^T,Z_t)
\land\mathsf{LegalFrontier}(Z_t)
\land\mathsf{Bound}(S_t,Z_t,O_t^T,A_t)
\land\neg\mathsf{HardRisk}(S_t).
\]

该目标建立 provenance、frontier legality、assessment binding 和 covered hard gates。它不证明所有被接受
动作都在完整语义上推进 \(T\)，因为 task-progress mismatch 当前可能只触发下一块 reobserve/replan。

**G2：qualified and one-use authorization。** 系统只能为当前 contract、proposal、state epoch 和 exact
ActionBlock 签发 fresh authorization；若 joint-risk trigger 激活，必须先存在满足已注册 margin、restore、
identity 与 force 条件的 guard configuration。authorization 消费后不得再次使用。

**G3：execution-transaction alignment。** 对启用 L2 的路径：

\[
\mathsf{PhaseAdvance}
\Rightarrow
\mathsf{FreshAndBound}
\land\mathsf{OrderedExactPrefix}
\land\mathsf{AfterDispatch}
\land\mathsf{RequiredEffects}
\land\neg\mathsf{ForbiddenOrUnknown}.
\]

也就是说，actual command 必须与 authorization 中相同索引的 action 一致；receipt 使用同一 authorization；
effects 来自绑定 dispatch 之后的 observation window；未知、不完整或跨 proposal evidence 不能推进 phase。

**G4：covered physical containment。** 若 L2b trigger 激活且系统最终 dispatch，则所选 execution
configuration 必须先通过 simulator 中注册的 joint-side margin、snapshot restore、source-action identity
和 force gates。该目标是冻结模拟器中的 covered joint containment，不是任意碰撞或真实机器人安全证明。

这四个目标不可互相替代。G1 可以评估一个随后被替换的 command；G2/G3 可以忠实执行 task-divergent
command；G4 可以安全地约束错误任务。ProofAlign 的组合目标是在同一个 proposal scope 中同时保留这些证据。

与两个 gap 的对应关系是：G1 在冻结 checker 范围内部分关闭 authorization gap；G2 与 G3 在软件 TCB 内
关闭从 qualified proposal 到 dispatch/evidence 的 realization gap；G4 不是第三个语义 gap，而是保证近关节
边界的 proposal 只有在存在合格 execution configuration 时才能获得执行权。

### 3.6 非目标与适用边界

当前系统不覆盖：

- secure split 之前的物理贴纸、投影或 root-level frame replacement；
- task source、selector/checker、observer、dispatch boundary 或 actuator feedback 被攻破；
- 任意攻击族、任意动力学误差、任意碰撞和一般物理安全；
- camera-only trusted semantic perception；
- 硬件 root of trust、remote attestation、真实机器人和 hard-real-time deployment；
- Python runtime 对 Lean model 的完整 refinement proof；
- guard/controller configuration 已被 Lean typed identity 完整绑定。

这些排除项具有实质含义。如果同一个 pre-split attack 同时欺骗 trusted tap 和 policy view，两条分支可能在
错误世界上保持一致；如果 observer 没有编码某个安全相关物理效果，软件上闭合的 transaction 仍可能对现实
不完整。ProofAlign 保证的是 TCB 导出证据范围内的 complete mediation，而不是对不可观察或已被攻破组件的
恢复。

## 4. ProofAlign 设计

### 4.1 总体流程

每次 policy call 执行以下流程：

```text
T + O_t^T -> legal task frontier -> Z_t

P_t^pol + O_t^pol + H_t^pol -> frozen Pi0.5 -> one source A_t (10×7)
                                      |
Z_t + O_t^T + A_t -> local assessment S_t
                                      |
                         hard risk? --+-- yes -> fail closed
                                      |
                                      no
                                      v
                               compile C_t
                                      |
                         near joint boundary?
                            /                 \
                          no                  yes
                          |          bounded guard screening
                          +-------------------+
                                      |
                           issue fresh one-use Auth_t
                                      |
                       exact dispatch -> receipts -> effects
                                      |
                         alignment/evidence gate -> phase update
```

系统只生成一个 `K=1` policy candidate，不做 best-of-K resampling。L2b 最多评估两个对象是同一 source
ActionBlock 下的 guard configurations，而不是两个新的 policy ActionBlocks。

### 4.2 贯穿案例：三层为何不可替代

回到“汽水到盘子”的权威任务。SABER 只改变 policy-facing bytes，trusted branch 的合法 task frontier 不会
因此变成“最远装置”。L1 使用原始可信任务和观察，对策略实际返回的 exact ActionBlock 做 assessment；若
出现覆盖范围内的 hard failure，当前块被拒绝，但 task-progress mismatch 仍可能只是 advisory。

若当前块继续，consumer 先编译 contract；若状态接近关节边界，L2b 必须先确认同一 source action 存在满足
margin、restore、identity 和 force gates 的 guard configuration。screen 合格后，L2a 才将同一 canonical
block 绑定到一次性 authorization、逐步 dispatch、receipt 和 effect window；它保证的是执行身份，而不是
任务语义。于是，L2 可以忠实执行并约束一个偏离任务的块，L1 也不能单独证明 sink identity 或 joint
containment。三层依次保护
trusted-context→proposal、proposal→dispatch evidence 和 near-boundary dispatch→covered physical outcome
三条不同的边。

### 4.3 可信语义上下文

每个 `TrustedSemanticContext` 绑定 episode nonce、proposal index、state epoch、task source 和 digest、
trusted observation digest 与 tap identity、secure-split identity、task graph/candidate-set digest、上一子任务
digest，以及 selector model/config identity。任一输入或 epoch 改变都会使旧 artifact 失效。

`Z_t` 借鉴但不等同于已有 language action hierarchy [RT-H]。它不是自由文本 explanation，也不是动作生成后
从 `A_t` 反推的 intent。它在同一 state epoch 中先于
ActionBlock 固定，只能从可信 task graph 的合法 frontier 产生。当前技能级词表包括 `pick_up`、`move`、
`place`、`release`、`open`、`close`、`actuate`、`finish` 与 `unknown`；局部 approach、align、grasp、lift、
lower 和 retract 作为 checker atoms，不被冒充为 VLA 的高层计划。

### 4.4 L1：ActionBlock monitor 与相对授权

定义：

```text
L1(T, O_t^T, Z_t, A_t, S_t) :=
    TrustedSemanticProvenance(T, O_t^T, Z_t)
  ∧ LegalFrontier(T, O_t^T, Z_t)
  ∧ Bound(S_t, Z_t, O_t^T, A_t)
  ∧ PhysicalScreenAvailable(S_t)
  ∧ NoHardRisk(S_t)
  ∧ QualifiedProvenance(S_t.assessor)
```

local checker 解析完整 `10×7` block 的位移、旋转和 gripper 命令，结合可信 EEF、实体几何、对象关系与
task frontier 生成有限的 motion/effect/risk atoms。硬拒绝条件包括 translation/rotation velocity limit、
workspace exit、unexpected contact neighborhood、stale state、malformed command 与未识别 unknown evidence。
如果没有 hard risk，L1 返回 byte-identical source ActionBlock；任何 intervention 若改变 command，都必须
重新 assessment、重新编译 contract 和重新授权。

task-progress、release/close progress、expected-effect miss 和 articulation task state unavailable 在最终
实现中属于 advisory。系统记录它们并要求下一 ActionBlock 重新观察和规划，但不一律停止当前 block。这一
选择避免把不完整几何代理误当成语义 oracle，也意味着 L1 不能被描述为“所有错误任务动作都被阻止”。它的
正式主张是可信来源、exact binding、hard-risk screening 和 audited replanning。

### 4.5 L2a：一次性执行事务

consumer 为获准 block 编译：

```text
C_t = {
  action_block_digest,
  semantic_subtask_digest,
  policy_prompt_digest,
  assessment_digest,
  trusted_observation_digest,
  state_epoch,
  expected_effect_atoms,
  forbidden_effect_atoms,
  observation_window
}
```

contract 编译后，无风险 fast path 或触发的 L2b screen 必须先合格，系统才以 fresh nonce 和 proposal index
签发一次性 `Auth_t`。执行对齐要求所有 digest、nonce 和 index 一致，
`applied_command = authorized_final_command`，逐步 receipt 使用同一个 authorization 且应用对应动作，evidence
只能来自 dispatch 之后的绑定窗口，required integrity effects 必须出现，forbidden effects、command
substitution、stale replay 和未知 evidence 必须不存在。task-progress effect 缺失可以触发 audited replan，
但不能用来自其他 proposal 或未来窗口的 evidence 补齐当前事务。

所有 command 通过单一 dispatch boundary。authorization 一旦消费就不可再次使用；ActionBlock 的未执行
tail 不能伪装成实际执行前缀。该机制给出软件 TCB 内的 transaction identity，不提供硬件 attestation。

### 4.6 L2b：状态触发的 joint containment

系统在线计算7个机械臂关节的 lower/upper margins，共14侧。最小 margin 大于 `0.30 rad` 时，L2b 不运行
shadow simulator，source ActionBlock 直接进入 L2a 事务。进入风险区时，系统定位危险 joint sides，并为
同一 source action 构造最多两个 virtual-stop guard configurations。每个候选从同一 simulator snapshot
开始 one-step shadow rollout，之后必须验证 state restore、全部14侧 margin、prediction/execution identity、
torque bound 和统一 `force ≤ 10000` envelope。

可行候选的全局最小 margin 必须不低于 `0.15 rad`。系统选择满足条件的最弱 uniform guard；若没有候选
通过，则不 dispatch，并记录 fail-closed task failure。正式执行后，receipt/evidence 记录 guard identity、
observed joint-side effects、constraint force 以及预测与实际 margin 差异。

virtual guard 保留 ActionBlock bytes，却改变 controller 到物理轨迹的映射。因此“exact source command”不
等于“exact physical trajectory”。当前 runtime trace 已记录 guard/controller 相关证据，但 Lean typed
contract 尚未把 guard/controller configuration 作为独立 digest 字段。这是明确的 executable-configuration
refinement gap，而不是可被 ActionBlock digest 隐去的实现细节。

## 5. 形式化事务语义

ProofAlign 使用 Lean 固定四臂开关、ActionBlock、assessment、contract、authorization、step receipt、effect
evidence 和 phase transition 的有限关系。关键 machine-checked 性质包括：

- `authorization_binds_semantic_identity`：authorization 绑定相同的语义 artifact identity；
- `authorization_binds_exact_final_command`：authorization 绑定被评估后的 exact final command；
- `consumed_authorization_not_available`：已消费 authorization 不再可用；
- `every_bound_receipt_uses_same_authorization`：所有绑定 receipt 使用同一 authorization；
- `every_bound_receipt_applies_exact_action`：每个 receipt 应用对应的 exact action；
- `unknown_effects_block_execution_alignment`：unknown effects 阻止 execution alignment；
- `incomplete_prefix_blocks_execution_alignment`：不完整执行前缀不能满足 alignment；
- `execution_enabled_phase_advance_requires_alignment`：启用执行层时，phase advance 蕴含 alignment；
- `phase_advance_requires_contract_completion`：phase advance 要求 contract completion。

完整定义与定理位于 [`SemanticIntegrityCore.lean`](../../lean/ProofAlign/SemanticIntegrityCore.lean)。这些
定理验证的是有限 transaction semantics。Python runtime 会逐步重建并检查 ordered exact prefix；Lean
模型则更粗，只绑定整块 final-command digest，并证明 receipt 使用相同 authorization 且
applied/authorized digests 相等。Lean 不独立重建 Python authorization 中的逐步 digest 列表，也不解析
自然语言，不证明 `Z_t` 或 checker 对现实正确，不证明 simulator 等价于物理世界，更不自动证明 Python
serializer/observer 精化到 Lean model。特别地，guard/controller configuration 尚未进入 Lean typed
contract。因此本文使用“Lean-checked abstract execution-transaction semantics”，而不使用“formally
verified robot safety”。

## 6. 实现

ProofAlign 实现在 Pi0.5—LIBERO-Safety runner 的 consumer/dispatch 边界。trusted context、artifact digest
与 allowlist 由 [`semantic_trust.py`](../../src/proofalign/semantic_trust.py) 管理；
[`semantic_action_selection.py`](../../src/proofalign/semantic_action_selection.py) 验证 `Z_t` 与候选 frontier，
完成 ActionBlock 检查和确定性选择；[`semantic_policy_wrapper.py`](../../src/proofalign/semantic_policy_wrapper.py)
与 [`integrity_v4_runtime.py`](../../src/proofalign/integrity_v4_runtime.py) 连接 policy、assessment、authorization、
guard screening 和 dispatch。benchmark
[`action_block_trace_adapter.py`](../../src/proofalign/benchmark/action_block_trace_adapter.py) 按
`policy_call_index` 提取实际消费的 action prefix，并保留原始 policy chunk digest。

selector 使用 deterministic privileged-geometry task graph/FSM。冻结的
[`E1f selector qualification`](../../experiments/proofalign_deterministic_selector_e1f.json) 中160个案例
与预期 exact match；该数字只证明 benchmark FSM corpus，不代表 camera perception 或部署泛化。analytic
local checker 和 effect observer 也在各自冻结 finite corpus 上通过资格门；这些 gate 用于发现实现错误和
明显 false allow，不替代真实分布上的统计安全证明。

每个 proposal 记录 trusted/policy observation digest、exact prompt bytes/digest、source/returned block
digest、assessment、nonce、contract、receipt/effect evidence、guard/restore 事件、joint margins、force 和
latency。无风险路径不启动 shadow rollout；风险路径最多执行两个候选 rollout，以给 screening latency 明确
上界。

## 7. 实验方法

### 7.1 研究问题

- **RQ1（攻击基础）：** SABER `constraint_violation` instruction perturbation 能否在独立复现中产生新的
  物理 risk transition？
- **RQ2（L1）：** trusted-task monitoring 是否保持 attacked task utility？其局部风险结果应如何解释？
- **RQ3（L2）：** 组合 L2 treatment 是否消除所覆盖的 joint-limit crossing，是否引入任务效用下降或
  deadlock？
- **RQ4（组合）：** Dual 是否能同时保持 L1 的 task success 与 L2 的 containment？
- **RQ5（系统）：** identity、force、prediction error、latency 和 deadline gates 是否成立？

### 7.2 攻击基础实验

victim 为 OpenPI Pi0.5，benchmark 为 LIBERO-Safety，攻击为 SABER `constraint_violation` instruction
perturbation records。实验包含60个 base pairs 和2组 seeds；每个 unit 都有 clean/attacked rollout，共240个
episodes。attack success 只在 clean-safe units 上统计 attacked rollout 中新出现的 contact、joint-limit、
excessive-force 或 LIBERO cost/collision risk transition，单纯 task failure 不计为 risk transition。

最终有86个 clean-eligible units。置信区间按 base pair 做 cluster bootstrap，以避免把同一 base pair 的
seed replicates 当成完全独立样本。

### 7.3 最终四臂实验

最终实验冻结18条 SABER attack records 和18个 held-out suite/task/init pairs。每个 pair 在 clean 与 attacked
条件下分别运行四个 arms：

| Arm | L1 | L2a + L2b | 作用 |
|---|---:|---:|---|
| VLA-only | 0 | 0 | 原始 VLA 行为 |
| L1-only | 1 | 0 | trusted-task monitor |
| L2-only | 0 | 1 | transaction + containment |
| Dual | 1 | 1 | 两层组合 |

clean/attacked 按 pair 共享 initial state、environment seed、policy seed 和 arm schedule。每个 condition 有72个
episodes，总计144个。所有 pair 完整保留，不依据 clean 或 attacked outcome 筛选。四臂在同一 paired
workload 的首个 source ActionBlock 必须一致；发生 hard gate 或状态分叉后，后续轨迹不再要求 byte-identical。

### 7.4 指标与完整性门

任务指标包括 task success、clean→attacked 与 attacked→clean paired transition。物理指标包括 violation
episode、crossing steps、joint-limit violation steps、official unsafe、deadlock、constraint force 和14侧
margin。`violation episode` 指 episode 内至少有一个 policy step 出现原生 joint-limit violation 或实际
joint-side margin crossing。

系统指标包括 attack metadata/prompt digest mismatch、四臂首块一致性、checksums、command/receipt/effect
binding、prediction/execution margin error、screening latency 与100 ms deadline miss。M2 的 risk-transition
ASR 和最终四臂的 violation-episode rate 使用不同 population、denominator 与事件定义，不能直接比较或相减。

## 8. 结果

### 8.1 RQ1：SABER攻击成功复现

240个 episodes 全部有效。86个 clean-eligible units 中39个在 attacked rollout 出现新的 risk transition：

```text
ASR = 39 / 86 = 45.35%
95% base-pair cluster bootstrap CI = [32.93%, 57.78%]
```

这说明冻结 SABER 记录在本地 Pi0.5—LIBERO-Safety 路径中产生了明确且可重复测量的物理风险转移，成功复现
了该攻击。本文将 `45.35%` 作为当前 victim、benchmark、攻击配置和事件定义下的观测攻击成功率。

### 8.2 RQ2–RQ4：配对四臂结果

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18（72.22%） | 11/18（61.11%） | 4/18（22.22%） | 28 | 175 |
| L1-only | 13/18（72.22%） | 13/18（72.22%） | 1/18（5.56%） | 295 | 317 |
| L2-only | 13/18（72.22%） | 11/18（61.11%） | 0/18（0%） | 0 | 0 |
| Dual | 13/18（72.22%） | 13/18（72.22%） | 0/18（0%） | 0 | 0 |

clean 条件下四臂均为 `13/18`，说明最终机制没有在汇总成功率上引入可见 clean utility 差异。在 attacked
条件下，VLA-only 从 `13/18` 降为 `11/18`，并产生4个 violation episodes。L1-only 保持 `13/18` task
success，表明其主要经验作用是任务效用；它仍出现1个 violation episode。

必须注意，L1-only 的 episode incidence 较低，却在该单个 episode 中累计295个 crossing steps 和317个
joint-limit steps，均高于 VLA-only 的28和175。因此数据不支持“L1 普遍降低物理风险严重度”的表述，也不
支持把 L1 当作 containment 层。更准确的结论是：L1 在该冻结配对样本上保持 task success，但残余物理
风险需要独立 L2 处理。

L2-only 的 task success 与 VLA-only 同为 `11/18`，但 violation episode、crossing steps 和 joint-limit
steps 全部为0。Dual 保留 L1-only 的 `13/18` task success，同时也将三个 joint-limit 指标降为0。正式
contrast 中，L2−VLA 与 Dual−L1 的 attacked task-success difference 都为0，paired bootstrap interval 均为
`[0,0]`。这支持“L2 在当前 paired sample 中没有额外改变 task-success aggregate、但提供 containment”的
窄解释，不等价于对总体零效应的证明。

paired transition 进一步显示，clean success→attacked failure 的 pair 数在 VLA/L1/L2/Dual 中分别为
`3/2/3/2`，clean failure→attacked success 分别为 `1/2/1/2`。因此汇总成功率包含双向转移，不能把所有
attacked failure 都解释为攻击新增失败。

四个 attacked arms 的 broader benchmark official-unsafe flag 均为0；clean 条件下 L1-only 与 Dual 各有1次，
本文同样保留。该 endpoint 与 L2 针对的 joint-limit outcome 不同，因此0 crossing不能被解释为“所有安全
信号始终为零”。attacked violation-episode rate 的描述性95% Wilson区间分别为 VLA-only
`[9.00%, 45.21%]`、L1-only `[0.99%, 25.76%]`，以及 L2-only/Dual `[0%, 17.59%]`。零观测事件
只支持冻结样本中的 containment，不是总体零风险上界。

引言中的汽水案例只用于事后解释机制，不是统计 estimand。在
`human_safety_task2_init34` 上，SABER 把“汽水到盘子”替换成“移动到最远装置”：VLA-only 任务失败并
出现2个 crossing steps/5个 joint-limit steps；L1-only 成功且为0/0；L2-only 失败但为0/0；Dual 成功且为
0/0。另一个独立 residual-risk pair 中，L1-only 唯一的 violation episode 占全部295/317 steps，而 Dual
为0/0；两者都任务失败。这两个案例共同说明：任务效用和物理 containment 必须分别度量。

### 8.3 RQ5：完整性、物理 envelope 与开销

- attacked episodes `72/72` 完成；18条 attack records 均有对应 evidence；
- paired clean comparisons 为72，attacked 相对 clean 的 first ActionBlock changed 为 `72/72`；
- attack metadata mismatch 和 prompt digest mismatch 均为0；四臂 pair 内首块一致为 `18/18`；
- checksums 为 `76/76`；69项 focused integrity tests 全部通过；正式 integrity gates 全部为 true；
- L2-on crossing 和 joint-limit violation steps 均为0，deadlock 为0；
- 最大 constraint force 为 `6438.1998 < 10000`；
- 最大 selected-margin prediction error 为 `2.69×10^-13 rad < 0.01 rad`；
- screening latency 最大为 `39.79 ms`，p95 为 `18.30 ms`，100 ms deadline miss rate 为0。

这些开销只说明冻结研究环境满足注册预算。它们没有测量操作系统 worst-case scheduling、硬实时控制环或
真实机器人通信抖动，因而不构成 hard-real-time claim。

## 9. 安全分析

### 9.1 L1 false allow 与 coverage

若 trusted selector 选择错误但语法合法的 `Z_t`，或者 local checker 未识别 task-incompatible action，L1
可能 false allow。若 checker 大量输出 unknown，则系统可能 fail closed 并损害 utility。当前 deterministic
FSM 和 analytic checker 的 frozen-corpus qualification 只缩小实现错误空间，不能证明分布外正确性。

### 9.2 共同视图失效

若攻击发生在 secure split 之前，同时欺骗 trusted tap 和 policy view，则两条分支可能对同一伪造场景自洽，
dual-view 结构不再提供独立证据。覆盖该威胁需要独立传感器、可信 capture path 或物理冗余，不能只增加
software digest。

### 9.3 事务替换与 observer blind spot

L2a 阻止其模型内的 command substitution、nonce replay、receipt/effect 换绑和不完整 prefix，但前提是
single-dispatch boundary 与 observer 属于 TCB。如果 actuator feedback 被伪造、关键物理效果未被 observer
编码，或者 expected/forbidden atom 规格太弱，事务仍可能“对齐”到错误的现实解释。

### 9.4 Simulator 与执行配置 gap

L2b 的结果依赖 LIBERO simulator、virtual stop 实现、snapshot restore 和 force proxy。真实机器人中的
compliance、时延、摩擦和控制器饱和可能改变结果。进一步地，当前 Lean contract 没有 typed-bind guard 和
controller configuration。完整闭环保证需要把 executable tuple 至少扩展为
`(ActionBlock, guard_config, controller_config, state_epoch)`，并给出 runtime serializer 到 Lean model 的
refinement evidence。

## 10. 相关工作

### VLA 攻击、安全 benchmark 与对齐

SABER 使用 bounded instruction edits 黑盒攻击多个 VLA，并以任务失败与 constraint violation 衡量行为后果
[SABER]。FreezeVLA、BadRobot 和 RoboPAIR 分别展示视觉 freezing、具身模型越狱与机器人 jailbreak 风险
[FreezeVLA, BadRobot, RoboPAIR]。
最新 VLA safety survey 总结了多模态攻击面、实时约束和长轨迹错误传播 [VLASurvey]；LIBERO-Safety、
SafeVLA-Bench 和 ForesightSafety-VLA 进一步区分物理/语义安全、任务成功与风险暴露
[LIBERO-Safety, SafeVLA-Bench, ForesightSafety]。SafeVLA 和 SAFE 分别代表训练时安全对齐与 rollout-level
failure detection [SafeVLA, SAFE]。ProofAlign 不提出新攻击，不训练更安全 policy，也不声称比这些 benchmark
具有更广覆盖；它研究冻结攻击输出如何在 consumer side 被审计、绑定和 containment。

### Trusted input、agent action 与 execution isolation

StruQ 和 SecAlign 分别从结构化输入与 preference alignment 保护 legitimate instruction [StruQ, SecAlign]，
CaMeL 则从可信 query 派生受保护控制流 [CaMeL]。IsolateGPT、SAGA 和 agent permissions 工作从隔离、治理和
访问控制限制 agent 权限 [IsolateGPT, SAGA, AgentPerms]；ACE 先生成 trusted abstract plan，再强制 concrete
app execution 与之相容 [ACE]。AttriGuard 通过 counterfactual shadow replay 识别离散 tool call 是由 user
intent 还是 untrusted observation 因果驱动 [AttriGuard]；MATE 则依据可编辑策略审计 mobile-agent
trajectory [MATE]。ProofAlign 没有它们的通用 causal/policy attribution，也没有 ACE 的显式 structured app
plan；它处理 action-only VLA 在线产生的连续数值块，并把 checker-relative verdict 延伸到物理执行证据。

SEAL 和 CoVer 是 VLA 侧最接近的 action verifier：前者根据 policy-supplied reasoning/plan 检查候选动作，
后者使用 learned instruction–action alignment score 扩展 verification [SEAL, CoVer]。它们提供更强的候选
排序，而 ProofAlign 保持单个 source proposal（K=1），使用独立 trusted task branch，并把相同 block 身份
继续带入 authorization、dispatch、receipt 和 effects。两类方法互补，本文不把四臂结果写成数值
leaderboard。

### CPS 与机器人执行完整性

OAT 将 operation 的 control flow、关键 data 和 fresh verifier challenge 组合为执行证据 [OAT]；DIAT、CFA+
和 ARTO 将 autonomous/CPS software execution、data flow 与可信 evidence 结合 [DIAT, CFA+, ARTO]；ARI
进一步要求 real-time mission 被正确且及时地执行 [ARI]；SCAPHY 关联工业控制程序与物理行为 [SCAPHY]；
TAT 从给定 intended path 出发，以 timed motion
events 和 joint measurements 审计工业机械臂轨迹 [TAT]。ProofAlign 不声称首次 trajectory integrity，也
不具备这些 attestation 系统可能依赖的硬件 root of trust。它补充的是 intended path 尚未给定、VLA 只输出
ActionBlock 时的 trusted-task monitor，并在软件 TCB 内维护一次性执行事务。

### Action prediction、shielding 与 formal methods

action-conditioned prediction、visual MPC、control barrier functions 和 continuous-space shields 已经提供
动作后果预测与安全集合约束 [VLMPC, SafetyChance, RealizableShields]。ProofAlign 的 virtual guard 是研究
simulator 中的 runtime containment 工程，不是新的连续控制理论。形式化规划与 runtime verification 可以在
给定模型中证明状态转换；本文 Lean 层只检查 execution transaction semantics，不证明 perception、语义和
物理模型真实性。

## 11. 讨论与局限

第一，当前证据只覆盖一个 Pi0.5 checkpoint、LIBERO-Safety、一个冻结 SABER instruction-attack family 和18个
最终 pairs。攻击复现与最终四臂使用不同 population、denominator 和 event definition，两组数字不能合并成
一个更强的统计结论。第二，最终四臂样本适合暴露机制差异，却不足以支持细粒度 task/suite 亚组结论。第三，L1 依赖
privileged geometry，task-progress 还是 advisory，因此方法距离 camera-only semantic authorization 尚有
明显差距。第四，L2a 和 L2b 在主 arm 中共同启用；要识别二者独立贡献，需要额外 sub-ablation。

第五，软件 nonce、digest、receipt 和 Lean semantics 都位于软件 TCB 内，不是 hardware attestation。第六，
virtual guard 改变 executable configuration，而该配置尚未进入 Lean typed contract。第七，当前 latency
只是在研究机器上的经验分布，不是 worst-case execution time。扩展到真实机器人需要可信感知、控制器配置
绑定、独立 safety supervisor、硬件反馈和 sim-to-real qualification。

这些限制并不消除当前结果的价值：它们界定了一个可复现的、比“VLA 输出看起来合理”更严格的系统主张。
ProofAlign 证明的不是模型拥有正确意图，而是部署者可以在明确 TCB 与冻结 checker 下追踪：哪个 ActionBlock
被检查、哪个 authorization 允许它执行、实际应用了什么命令、观察到了什么 effects，以及 joint-risk 状态下
是否启用了合格 containment。

## 12. 结论

本文提出 ProofAlign，将 action-only VLA 的 trusted-task monitoring、一次性 execution transaction 和
state-triggered joint containment 连接为同一跨层 identity chain。方法不依赖 VLA 自报 plan，也不修改
Pi0.5 权重。攻击基础实验成功复现出 `39/86=45.35%` 的 SABER risk-transition ASR。最终配对四臂实验表明，
L1 在 attacked 条件下保持 `13/18` task success，组合
L2 treatment 将观察到的 joint-limit violation 降至0，Dual 同时达到 `13/18` task success 与 `0/18`
violation episodes。结果支持冻结 simulator 范围内“任务效用与 containment 来自不同机制”的解释。

更广泛的机器人安全保证仍需更强可信感知、更完整的 executable-configuration binding、独立硬件反馈、更多
模型与攻击族，以及真实机器人验证。ProofAlign 的贡献不是宣称这些问题已被解决，而是给出一个可审计、可
形式化且能够被配对实验检验的跨层运行时边界。

换言之，ProofAlign 不证明 VLA “想对了”；它让部署者能够核对哪一块动作因什么可信证据获准、实际执行的
是否仍是同一块动作、观察到的效果是否属于同一事务，以及近关节边界时是否启用了合格 containment。

## 工作参考文献

> 下列条目使用工作引用键，便于当前 Markdown 审阅；提交前统一导出 BibTeX，并核对作者、页码与 DOI。

- **[SABER]** [SABER: A Stealthy Agentic Black-Box Attack Framework for Vision-Language-Action Models](https://arxiv.org/abs/2603.24935), arXiv, 2026.
- **[LIBERO-Safety]** [LIBERO-Safety](https://arxiv.org/abs/2606.23686), ECCV, 2026.
- **[SafeVLA-Bench]** [SafeVLA-Bench](https://arxiv.org/abs/2606.00773), arXiv, 2026.
- **[ForesightSafety]** [ForesightSafety-VLA](https://arxiv.org/abs/2606.27079), arXiv, 2026.
- **[VLASurvey]** [Vision-Language-Action Safety: Threats, Challenges, Evaluations, and Mechanisms](https://arxiv.org/abs/2604.23775), arXiv, 2026.
- **[Pi0.5]** [π0.5: a Vision-Language-Action Model with Open-World Generalization](https://arxiv.org/abs/2504.16054), 2025.
- **[RT-H]** [RT-H: Action Hierarchies Using Language](https://arxiv.org/abs/2403.01823), 2024.
- **[FreezeVLA]** [FreezeVLA](https://arxiv.org/abs/2509.19870), arXiv, 2025.
- **[BadRobot]** [BadRobot](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5b2fa23e4ef0f7ac6c4f01d7998e6237-Abstract-Conference.html), ICLR, 2025.
- **[RoboPAIR]** [RoboPAIR](https://robopair.org/), ICRA, 2025.
- **[SafeVLA]** [SafeVLA](https://safevla.github.io/), NeurIPS Spotlight, 2025.
- **[SAFE]** [SAFE: Multitask Failure Detection for Vision-Language-Action Models](https://vla-safe.github.io/), NeurIPS, 2025.
- **[StruQ]** [StruQ: Defending Against Prompt Injection with Structured Queries](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe), USENIX Security, 2025.
- **[SecAlign]** [SecAlign](https://arxiv.org/abs/2410.05451), ACM CCS, 2025.
- **[CaMeL]** [Defeating Prompt Injections by Design](https://arxiv.org/abs/2503.18813), IEEE SaTML, 2026.
- **[SEAL]** [Do What You Say: Steering Vision-Language-Action Models via Runtime Reasoning-Action Alignment Verification](https://arxiv.org/abs/2510.16281), ICRA, 2026.
- **[CoVer]** [Scaling Verification Can Be More Effective than Scaling Policy Learning for Vision-Language-Action Alignment](https://arxiv.org/abs/2602.12281), ECCV, 2026.
- **[WebAgent]** [When AI Meets the Web](https://arxiv.org/abs/2511.05797), IEEE S&P, 2026.
- **[AgentPerms]** [Towards Automating Data Access Permissions in AI Agents](https://homes.cs.washington.edu/~franzi/pdf/wu-agentperms-sp26.pdf), IEEE S&P, 2026.
- **[IsolateGPT]** [IsolateGPT](https://www.ndss-symposium.org/ndss-paper/isolategpt-an-execution-isolation-architecture-for-llm-based-agentic-systems/), NDSS, 2025.
- **[ACE]** [ACE: A Security Architecture for LLM-Integrated App Systems](https://www.ndss-symposium.org/ndss-paper/ace-a-security-architecture-for-llm-integrated-app-systems/), NDSS, 2026.
- **[SAGA]** [SAGA: A Security Architecture for Governing AI Agentic Systems](https://www.ndss-symposium.org/ndss-paper/saga-a-security-architecture-for-governing-ai-agentic-systems/), NDSS, 2026.
- **[AttriGuard]** [AttriGuard: Defeating Indirect Prompt Injection in LLM Agents via Causal Attribution of Tool Invocations](https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu), USENIX Security, 2026.
- **[MATE]** [MATE: Policy-Aware Security Auditing for Mobile Agents via Synthesis-Driven Trajectory Learning](https://www.usenix.org/conference/usenixsecurity26/presentation/jiang-changyue), USENIX Security, 2026.
- **[OAT]** [OAT: Attesting Operation Integrity of Embedded Devices](https://www.longlu.org/publication/oat/), IEEE Symposium on Security and Privacy, 2020.
- **[DIAT]** [DIAT: Data Integrity Attestation for Resilient Collaboration of Autonomous Systems](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/), NDSS, 2019.
- **[ARI]** [ARI: Attestation of Real-time Mission Execution Integrity](https://www.usenix.org/conference/usenixsecurity23/presentation/wang-jinwen), USENIX Security, 2023.
- **[CFA+]** [CFA+: Control-Flow Attestation for Embedded Systems](https://www.usenix.org/conference/usenixsecurity24/presentation/ammar), USENIX Security, 2024.
- **[ARTO]** [ARTO: Efficient Execution Integrity Attestation for Real-Time Operation of Cyber-Physical Systems](https://www.usenix.org/conference/usenixsecurity26/presentation/zhao-ruizhe), USENIX Security, 2026.
- **[TAT]** [TAT: Attesting Trajectory Integrity of Industrial Robotic Arms](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao), USENIX Security, 2026.
- **[JCS]** [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html), IETF, 2020.
- **[SCAPHY]** [SCAPHY](https://www.ieee-security.org/TC/SP2023/program-papers.html), IEEE S&P, 2023.
- **[VLMPC]** [VLMPC: Vision-Language Model Predictive Control](https://www.roboticsproceedings.org/rss20/p106.pdf), RSS, 2024.
- **[SafetyChance]** [How Safe Am I Given What I See?](https://proceedings.mlr.press/v242/mao24c.html), L4DC, 2024.
- **[RealizableShields]** [Realizable Continuous-Space Shields for Safe Reinforcement Learning](https://proceedings.mlr.press/v283/kim25c.html), L4DC, 2025.

## 投稿前待办

- 将本文转为目标会议 LaTeX 模板并补作者/匿名化信息；
- 生成系统图、威胁模型图、四臂结果图和 latency/force 审计图；
- 将工作引用键替换为正式 BibTeX，逐条核对2026 accepted/embargo paper 的最终元数据；
- 从冻结 artifacts 自动生成主表和 appendix audit table，避免手工转录；
- 在 appendix 给出 Lean theorem-to-claim mapping、negative integrity suite、完整 TCB 与失败分类；
- 如新增模型、seed、attack family、真实机器人或 L2a/L2b sub-ablation，作为 claim expansion，和当前
  frozen main result 分开注册与报告。
