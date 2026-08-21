# 相关工作与论文定位

文献核查截止：**2026-08-18**。会议归属优先以官方 proceedings/program 为准；尚未正式发表的工作明确标为
arXiv。USENIX Security 2026 已于 8 月 12--14 日举行，AttriGuard、MATE、ARTO、TAT 和 Agentic AI SoK 的
正式 proceedings PDF 均已公开；下文对 TAT 的定位已经按正式正文、而不是会议前摘要复核。

## 1. 结论先行：论文应主张跨层绑定，而不是单点首创

ProofAlign 的相邻文献已经分别覆盖了以下问题：

- VLA jailbreak、指令扰动、视觉攻击和安全 benchmark 已经证明模型会产生有害或失效行为；
- LLM/agent 安全文献已经研究 trusted/untrusted input separation、用户意图到 tool call 的归因、权限和
  execution isolation；
- robotics/CPS security 已经研究 control/data-flow attestation、工业控制物理行为关联和机器人 trajectory
  integrity；
- robot learning 已经研究 failure detection、safety alignment、shielding 和 action-conditioned prediction。

因此，论文不能把“首次检查意图”“首次做 action filter”“首次做执行完整性”或“首次做机器人轨迹审计”
作为顶层新颖性。当前最窄、也最能被实验支持的定位是：

> 面向不暴露可信高层计划的 action-only VLA，ProofAlign 在 consumer side 维护攻击面之外的可信任务/观察
> 视图，对一个 **exact ActionBlock** 做 trusted-task monitoring 与 checker-relative authorization，再将
> 获准对象绑定到一次性 authorization、实际 dispatch、receipt 和 observed physical effects；L1 与组合
> L2 treatment 的作用由同一 task/init/seed 的四臂闭环实验比较。

这个定位有两个顶层 gap，其中 realization gap 再拆成两个证据来源不同的子机制：

```text
trusted task / observation -> ActionBlock audit / relative authorization [L1]
authorized ActionBlock -> dispatch / receipt / observed effects         [L2a]
risk state -> guarded execution / joint-limit containment                [L2b]
```

论文的新意来自这条完整 identity chain 在 VLA 物理闭环中的组合，而不是其中任一组件单独存在。

本轮安全四大筛查以官方 accepted/program/proceedings 为主，范围和最接近工作如下：

| Venue | 最新可核查批次 | 与本文最接近的工作 | 对叙事的约束 |
|---|---|---|---|
| IEEE S&P | [2026 accepted papers](https://www.ieee-security.org/TC/SP2026/accepted-papers.html) | Agent data permissions；When AI Meets the Web | 不能把数据授权或 trusted/untrusted content separation 当作首创 |
| USENIX Security | [2026 technical sessions](https://www.usenix.org/conference/usenixsecurity26/technical-sessions) | AttriGuard；MATE；ARTO；TAT | 正式论文已公开；不能泛称首次 intent→action/policy attribution、execution integrity 或 trajectory integrity |
| ACM CCS | 2025 proceedings/DOI | SecAlign | 不能把 prompt/data alignment 或模型级 prompt-injection defense 当作本文新意 |
| NDSS | [2026 accepted papers](https://www.ndss-symposium.org/ndss2026/accepted-papers/) | ACE；SAGA；另参考 IsolateGPT 2025 | 不能声称首次分离 trusted planning 与 execution，或首次做 agent isolation/governance |

截至 `2026-08-18`，CCS 2026 尚无可用正式 proceedings；USENIX Security 2026 的相关正式正文已经公开。
在本轮官方目录与已公开正文中未发现
与 `trusted task -> exact continuous ActionBlock -> physical dispatch/effects` 完全同构的 VLA 系统；这是
基于所核查目录的文献筛查结论，不是穷尽性“全球首个”证明。

## 2. VLA 与具身模型攻击：说明物理后果，但不提供运行时闭环

[SABER](https://arxiv.org/abs/2603.24935)（作者主页称已被 IROS 2026 接收；当前参考文献仍按 arXiv 官方元数据著录）使用 bounded instruction edits 对六类 VLA 做
black-box attack，并以 task failure、动作长度和 constraint violation 衡量机器人行为后果。它是本文冻结
攻击记录的直接来源，也支持“攻击是否改变最终执行”而不是“模型是否输出恶意解释”的问题设定。

[FreezeVLA](https://arxiv.org/abs/2509.19870)（arXiv 2025）通过视觉输入诱发 action freezing；
[BadRobot](https://proceedings.iclr.cc/paper_files/paper/2025/hash/5b2fa23e4ef0f7ac6c4f01d7998e6237-Abstract-Conference.html)
（ICLR 2025）和 [RoboPAIR](https://robopair.org/)（ICRA 2025）展示 embodied LLM jailbreak 可以转化为
物理世界中的有害动作。这些工作共同表明攻击面跨越 language、vision 和 interaction history，而且文本拒绝
或无害 explanation 不能替代对实际命令的检查。

这些攻击工作主要回答“怎样使模型偏离”和“偏离造成什么 outcome”。ProofAlign 不提出新的攻击算法；它将
SABER 当作冻结外部攻击源，研究在 trusted task artifact 不变时，consumer 能否对攻击后的数值动作建立
pre-dispatch authorization 和 post-dispatch evidence chain。

## 3. VLA safety benchmark、训练时对齐与失败监控

[Vision-Language-Action Safety: Threats, Challenges, Evaluations, and Mechanisms](https://arxiv.org/abs/2604.23775)
（arXiv 2026 survey）将 VLA 风险整理为训练时/推理时攻击与训练时/运行时防御，并把不可逆物理后果、
多模态攻击面、实时约束和长轨迹错误传播列为 VLA 区别于纯 LLM 安全的核心挑战。它也将 unified runtime
safety architecture 列为开放问题；ProofAlign 是这个大方向中的一个窄实例，而不是覆盖该 survey 全部威胁。

[LIBERO-Safety](https://arxiv.org/abs/2606.23686)（已被 ECCV 2026 接收；当前可访问版本为 arXiv）同时覆盖物理与语义安全，并指出更丰富的安全
数据与 task success 之间仍存在 trajectory synthesis/semantic misalignment 瓶颈。
[SafeVLA-Bench](https://arxiv.org/abs/2606.00773)（arXiv 2026）用 task-aware Signal Temporal Logic
区分 success、succ-but-unsafe 和 violation severity；
[ForesightSafety-VLA](https://arxiv.org/abs/2606.27079)（arXiv 2026）进一步把 instruction、perception 和
physical-interaction 风险分开，并报告累计风险与暴露时间。这些工作直接支持本文同时报告 task success、
violation episode、risk steps、deadlock 和 latency，而不是只给一个成功率。

[SafeVLA](https://proceedings.neurips.cc/paper_files/paper/2025/hash/e185c7be603426028c32ae1003a59d78-Abstract-Conference.html)（NeurIPS 2025）通过 constrained learning 改善 VLA 的训练时
安全对齐；[SAFE](https://proceedings.neurips.cc/paper_files/paper/2025/hash/392d0d05e2f514063e6ce6f8b370834c-Abstract-Conference.html)（NeurIPS 2025）从 VLA hidden features 预测跨任务失败，并以
conformal prediction 校准报警时间。它们分别代表 policy-level alignment 和 rollout-level failure detection。

ProofAlign 与这一组工作的边界是：

- benchmark 给出 endpoint specification，但不会自动形成在线授权；
- training-time alignment 改变或增强 policy，本项目保持 Pi0.5 参数不变；
- failure detector 可以触发 stop/backtrack，但其分数本身不绑定 authoritative task、exact executable bytes
  或 dispatch receipt；
- ProofAlign 当前也不声称比这些方法具有更广的 attack coverage 或真实机器人泛化。

## 4. Action-only VLA 与语义层级：结构不等于可信来源

[OpenVLA](https://proceedings.mlr.press/v270/kim25c.html) 预测 tokenized actions 并解码为连续动作；
[Diffusion Policy](https://arxiv.org/abs/2303.04137) 直接生成 receding-horizon 动作序列。这类最低共同接口
不保证部署者能读取离散高层计划，所以依赖模型自报 plan 或 chain-of-thought 的 verifier 不是通用方案。

[Pi0.5](https://arxiv.org/abs/2504.16054)（CoRL 2025 Oral）在论文系统中使用 high-level semantic prediction、object detection
和 low-level action 等混合训练信号；[RT-H](https://www.roboticsproceedings.org/rss20/p049.html)（RSS 2024）显式预测 language motion
再条件化动作。它们证明 semantic/action hierarchy 可以提供结构与干预接口，但 policy 内部产生的 semantic
output 仍与 policy 共享攻击面。

ProofAlign 因此不主张首次提出 language hierarchy。其 `SemanticSubtask Z_t` 来自 consumer-side、冻结且
allowlisted 的有限 task graph/selector，只进入独立 monitor，不被当作 VLA latent intent 的观测值。当前公开
`pi05_libero` 路径只返回数值动作；论文不能从 Pi0.5 论文中的训练信号反推本地 checkpoint 暴露可信 semantic
API。

## 5. 安全四大中的 LLM/agent security：最接近 L1 的数字世界邻居

安全四大近年的工作正在从 input filtering 转向 trust separation、action attribution、permissions 和
execution isolation：

- [SoK: Attack and Defense Landscape of Agentic AI Systems](https://www.usenix.org/conference/usenixsecurity26/presentation/kim-juhee-agentic)
  （USENIX Security 2026）系统整理 agent design、attack landscape 与 defense mechanism，说明本文应把
  contribution 落在具体 system object 和 threat model，而不是把“agent security”本身当作新问题；
- [Formalizing and Benchmarking Prompt Injection Attacks and Defenses](https://www.usenix.org/conference/usenixsecurity24/presentation/liu-yupei)
  （USENIX Security 2024）系统化 prompt-injection threat/evaluation；
- [StruQ](https://www.usenix.org/conference/usenixsecurity25/presentation/chen-sizhe)（USENIX Security 2025）
  用 structured queries 分离 instruction 与 data channel；
- [SecAlign](https://arxiv.org/abs/2410.05451)（ACM CCS 2025，DOI
  `10.1145/3719027.3744836`）通过 preference optimization 让模型偏向执行 legitimate instruction；
- [IsolateGPT](https://www.ndss-symposium.org/ndss-paper/isolategpt-an-execution-isolation-architecture-for-llm-based-agentic-systems/)
  （NDSS 2025）为 LLM app 生态设计
  execution isolation，限制不可信 app 间交互；
- [ACE](https://www.ndss-symposium.org/ndss-paper/ace-a-security-architecture-for-llm-integrated-app-systems/)
  （NDSS 2026）先用可信信息生成 abstract execution plan，再将其具体化为 app plan，并在执行期强制
  data/capability barriers 与计划一致性；
- [SAGA](https://www.ndss-symposium.org/ndss-paper/saga-a-security-architecture-for-governing-ai-agentic-systems/)
  （NDSS 2026）进一步以身份、策略和 cryptographic access tokens 支持多 agent 的用户侧治理；
- [Towards Automating Data Access Permissions in AI Agents](https://homes.cs.washington.edu/~franzi/pdf/wu-agentperms-sp26.pdf)
  （IEEE S&P 2026）研究 agent 代表用户访问数据时的 permission decision；
- [When AI Meets the Web](https://arxiv.org/abs/2511.05797)（IEEE S&P 2026）表明 chatbot plugin 会因
  conversation-history integrity 缺失以及 trusted/untrusted web content 混合而放大 prompt injection；
- [AttriGuard](https://www.usenix.org/conference/usenixsecurity26/presentation/he-yu)（USENIX Security 2026）
  已把防御单位推进到 tool invocation，通过 counterfactual shadow replay 判断一个 action 是由 user intent
  支持，还是由 untrusted observation 因果驱动。
- [MATE](https://www.usenix.org/conference/usenixsecurity26/presentation/jiang-changyue)（USENIX Security 2026）
  使用可编辑自然语言策略审计移动智能体的 task instruction 与 execution trajectory，说明本文不能把
  policy-conditioned trajectory auditing 本身作为首创。

AttriGuard 与 MATE 对论文定位尤其关键：ProofAlign 不能笼统声称“首次把 user intent/policy 与 action 或
trajectory 对齐”。差异应写在 system object 和 evidence 上：AttriGuard 归因离散 tool call，MATE 学习审计
移动智能体轨迹，而 ProofAlign 面向高频连续数值 ActionBlock，并把授权对象继续绑定到 actuator dispatch、
receipt、joint-side margins 和 observed effects。反过来，ProofAlign 当前既没有 AttriGuard 的通用
counterfactual causal attribution，也没有 MATE 的跨应用 learned policy auditor，不应暗示具备。

同理，StruQ/SecAlign 的 prompt/data separation 支持 dual-view 思路，但它们主要保护模型输入/输出行为；
IsolateGPT、SAGA 和 agent permissions 支持 least privilege、治理与 trusted scaffold，却不判断机器人动作
是否推进指定 object/region，也不验证物理执行是否与授权 bytes 一致。ACE 更接近本文的两阶段结构，因此
ProofAlign 也不能声称首次把 trusted planning 与 execution integrity 分离；区别在于 ACE 有显式 structured
app plan 和离散 tool execution，而 action-only VLA 不暴露可信 plan。ProofAlign 由 consumer 为连续数值
ActionBlock 建立授权，并继续绑定 simulator 中的 actuator command 和 physical effects。

## 6. 安全四大中的 CPS/robot execution integrity：最接近 L2 的系统邻居

机器人和 CPS 安全已经长期研究从软件执行到物理状态的完整性：

- [An Experimental Security Analysis of an Industrial Robot Controller](https://www.ieee-security.org/TC/SP2017/papers/20.pdf)
  （IEEE S&P 2017）系统展示工业机器人控制器的软件攻击面及物理后果；
- [DIAT](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/)
  （NDSS 2019）把自主系统交换的数据与其生成/处理软件的 control-flow attestation 绑定；
- [SCAPHY](https://www.ieee-security.org/TC/SP2023/program-papers.html)（IEEE S&P 2023）关联 SCADA 与 physical
  behavior 来检测现代 ICS attack；
- [CFA+](https://www.usenix.org/conference/usenixsecurity24/presentation/ammar)（USENIX Security 2024）将
  control-flow prevention 与可信 runtime evidence 结合；
- [ARTO](https://www.usenix.org/conference/usenixsecurity26/technical-sessions)（USENIX Security 2026）面向
  real-time CPS 组合 control-flow attestation 与 data-flow protection；
- [TAT](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao)（USENIX Security 2026，
  pp. 3439--3457）明确定义工业机械臂 trajectory integrity。它对受保护的任务程序做静态分析，并在受控
  离线运行中生成 Timed Motion Event Graph 与事件级参考轨迹；运行时由 TEE 保护 event/control/data-flow
  证据，并用旁路采集的原始电机编码器读数重建 actual trajectory。

TAT 直接占据“机器人轨迹完整性”这一表述，因此 ProofAlign 不应声称首次提出 trajectory integrity 或首次把
joint measurements 纳入 attestation。更准确的区分是：TAT 从预编程任务及其受控测试所得参考 profiles
出发，验证工业臂的实际运动是否符合事件级时空语义；ProofAlign 研究的前置问题是，当自然语言条件下的 VLA
在线生成数值 ActionBlock 时，哪个 exact block 获得可信任务授权，以及授权后系统如何把同一 identity
延伸到执行与 effects。TAT 主要生成执行后的远程 attestation evidence，ProofAlign 则在执行前进行 dispatch
mediation；两者是可组合的上下层，而不是互斥替代。

ProofAlign 当前也不具备 TAT/DIAT/CFA+ 的硬件 root of trust、旁路 encoder evidence 或远程 attestation 保证。其 digest、nonce、
receipt 和 Lean semantics 是软件 TCB 内的 transaction-integrity mechanism；论文必须把这一点作为安全边界，
不能用 `attestation` 一词暗示硬件支持。

## 7. Action-conditioned prediction、shielding 与 runtime assurance

L1 的 local checker 与 action-conditioned prediction/model-based control 相邻：

- [Unsupervised Learning for Physical Interaction through Video Prediction](https://arxiv.org/abs/1605.07157)
  学习 action-conditioned visual futures；
- [Deep Visual Foresight](https://research.google/pubs/deep-visual-foresight-for-planning-robot-motion/)
  将视觉未来预测与 MPC 结合；
- [VLMPC](https://www.roboticsproceedings.org/rss20/p106.pdf) 为候选动作预测未来帧并按视觉/语义成本选择；
- [How safe am I given what I see?](https://proceedings.mlr.press/v242/mao24c.html) 研究视觉控制系统的校准
  safety-chance prediction；
- [Model-Based Runtime Monitoring with Interactive Imitation Learning](https://arxiv.org/abs/2310.17552)
  结合未来预测、OOD 和 failure detection 做 runtime monitoring。

连续控制 safety filter/shield 的代表工作包括
[A Learnable Safety Measure](https://proceedings.mlr.press/v100/heim20a.html)、
[Measurement-Robust Control Barrier Functions](https://proceedings.mlr.press/v155/dean21a.html)、
[Realizable Continuous-Space Shields](https://proceedings.mlr.press/v283/kim25c.html) 和
[Adaptive Shielding with HJ Reachability](https://proceedings.mlr.press/v283/lu25a.html)。

这些工作支持 `Assess(O, A) -> predicted outcome/risk` 以及动作约束的技术可行性，但 safety-set
compatibility 不等于 trusted-task compatibility。ProofAlign 的组合纪律是：authoritative task/target 必须
来自 trusted branch；assessment 必须绑定 exact executable prefix；任何改变 command 的 intervention 都会使
旧 assessment/authorization 失效，并要求重新检查和授权。task-progress mismatch 在当前实现中是 advisory，
而 hard-risk atoms 才触发当前 block 的拒绝；这是 checker-relative system transaction rule，不是完整语义
判定，也不是新的连续控制理论。

## 8. Formal methods 与 proof-carrying control

形式化规划、runtime verification、temporal-logic shields 和 proof-carrying control 能在给定模型与规范中
证明离散或连续性质。ProofAlign 借用 fail-closed 与 proof-carrying transaction 的思想，但 Lean claim 必须
保持窄化：

- Lean 不解析自然语言 intent，也不选择 `Z_t`；
- Lean 不证明 selector、checker、perception 或 observer 对现实正确；
- Lean 检查 ActionBlock、assessment、contract、authorization、exact command、receipt、evidence 和
  phase update 的有限关系；
- Python runtime/serializer 到 Lean model 的 refinement 仍是未完成边界；
- 物理结论仍受 sensor trust、observer completeness、simulator mismatch 和软件 TCB 假设限制。

正确用语是 **Lean-checked execution transaction semantics**，而不是 “formally verified robot safety”。

## 9. 横向比较

| Work family | Trusted task 与 untrusted view 分离 | Intent/task→action | Exact command identity | Receipt/effect binding | Physical trajectory/constraint | Formal or attested mechanism |
|---|---:|---:|---:|---:|---:|---:|
| VLA attacks / benchmarks | evaluation-dependent | outcome only | no | post-hoc trace | measured | no |
| VLA alignment / failure detection | not inherent | learned score/alignment | usually no | no | predicted/measured | statistical |
| StruQ / SecAlign | prompt–data separation | legitimate instruction→response | no | no | no | model/system claim |
| AttriGuard | control-attenuated dual view | user intent→tool call | tool-call level | no physical receipt | no | causal runtime test |
| IsolateGPT / SAGA / agent permissions | trusted scaffold | capability/data access | capability level | digital execution isolation | no | isolation/access control |
| ACE | trusted abstract plan | abstract→concrete app plan | structured app-call level | digital plan/execution binding | no | static analysis + barriers |
| DIAT / CFA+ / ARTO | trusted verifier/model | not natural-language task | software/data-flow level | attestation evidence | CPS-dependent | hardware/software attestation |
| TAT | protected task program | offline event-level reference profiles | motion-event level | TEE-protected event evidence + bypass joint measurements | yes | trajectory attestation |
| ProofAlign L1 | required | trusted-task monitor；progress advisory | exact block digest | feeds L2 | hard local-risk gates | statistical/system claim |
| ProofAlign L2a | inherits L1 binding | no new semantic truth | exact authorized command | required | no standalone containment claim | Lean-checked finite semantics |
| ProofAlign L2b | inherits L1 binding | no new semantic truth | source command retained | runtime guard/margin evidence | joint-margin/force envelope | simulator-qualified system claim |

表格不表示每篇工作都只有一个能力，而是说明 ProofAlign 的 estimand：两层必须共享同一 ActionBlock identity，
并通过四臂设计分别估计 L1、L2 和组合效果。

## 10. 论文中可用与不可用的新颖性表述

可以使用：

> ProofAlign 是一个面向 action-only VLA 的跨层 reference monitor：它用攻击面之外的 trusted task/
> observation 对 exact ActionBlock 做 checker-relative monitoring/authorization，并把获准对象延伸到
> nonce-bound dispatch、receipt 和 observed physical effects；配对四臂实验比较 L1 的任务效用与组合 L2
> treatment 的 joint-limit containment。

不应使用：

- “首次将用户意图与 agent action 对齐”（AttriGuard 等已覆盖相邻命题）；
- “首次把可信计划与不可信执行分离”（ACE 已对 LLM app system 给出直接先例）；
- “首次提出机器人 trajectory integrity”（TAT 已直接提出）；
- “首次用形式化方法保证机器人安全”（本文 Lean claim 和物理 TCB 均不足）；
- “首次用 shadow rollout/action filter 保证 VLA 安全”（prediction、MPC、shielding 文献均已有）；
- “对任意 VLA 攻击有效”或“真实机器人安全”（当前仅有冻结 SABER 与 LIBERO-Safety simulator evidence）。

## 11. 安全四大筛查对投稿叙事的直接影响

截至核查日，在上述已检查的安全四大正式或 accepted papers 中，没有发现与本文完全同构的
`trusted task -> exact continuous ActionBlock -> dispatch/receipt/effects` 双层 VLA 闭环；但相邻组件已经
非常拥挤。投稿叙事因此应采用以下顺序：

1. 先用 SABER 和最终 VLA outcome 说明 **prompt integrity failure 会变成 physical execution failure**；
2. 再定义 authorization gap 与 realization gap，而不是泛称“VLA 不安全”；
3. 将 AttriGuard/StruQ/ACE/IsolateGPT 放在 L1 的数字 agent 邻域，将 TAT/ARTO/DIAT 放在 L2 的 CPS 邻域；
4. 把 novelty 放在跨层 identity chain、action-only applicability 和配对四臂机制归因；主表只识别 L1 与
   `L2a+L2b` 整体，不能进一步声称 L2a/L2b 的独立因果效应；
5. 用 `13/18` task success 与 `0/18` violation episodes 支撑冻结范围内的组合结果，不扩大为一般安全保证。

这也是正式 Introduction、Related Work 和 Discussion 应共享的主线。
