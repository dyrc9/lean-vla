# 论文就绪度评估

> 2026-07-29 更新：本页原 support45 评估保留为历史诊断；最新 outcome checkpoint 已推进到
> v11 unchanged-method held-out scale45。终局结果和不可覆盖边界见
> [`../v11_terminal_checkpoint.md`](../v11_terminal_checkpoint.md)，后继优化见
> [`../v12_recoverable_alignment_plan.md`](../v12_recoverable_alignment_plan.md)。v12 首轮
> no-outcome 资格结果见
> [`../v12_qualification_checkpoint.md`](../v12_qualification_checkpoint.md)，多关节 typed
> recovery 后继见
> [`../v12_recovery_successor_checkpoint.md`](../v12_recovery_successor_checkpoint.md)，controller
> shadow 后继见
> [`../v12_policy_prefix_shadow_checkpoint.md`](../v12_policy_prefix_shadow_checkpoint.md)，simulator
> integrated non-pass 与结果后优化见
> [`../v12_simulator_integrated_recovery_checkpoint.md`](../v12_simulator_integrated_recovery_checkpoint.md)。

| 模块 | 就绪度 | 证据/缺口 |
|---|---|---|
| Threat model | 高 | 沿用原始可信 intent + attacked policy view |
| 双层问题定义 | 高 | Intent→ActionBlock 与 ActionBlock→Execution 的 estimand 已稳定 |
| Trusted semantic boundary | 中高 | context/allowlist/prompt/double-view binding 已接入 opt-in online path；尚无硬件级 trusted tap |
| Semantic selector | benchmark 中高 / deployment 低 | raw π0.5 未通过；deterministic privileged-geometry FSM 160/160，通过 unknown fail-closed |
| Action conditioning | 低 | E2 未通过，semantic prompt 不作为独立 safety control |
| Local ActionBlock checker | benchmark 中高 / deployment 低 | E3 v2 analytic corpus 通过；approach progress 与 near-target 已分离；camera perception supervision 尚不足 |
| ActionBlock runtime schema | 高 | semantic-bound v4 proposal/assessment/contract/authorization/receipt/evidence 已端到端贯通 |
| Action–Execution checker | 中高 | Python tests + Lean semantic core + scoped equivalence；仍无完整 Python refinement 或现实世界证明 |
| Four-arm fixed trace | 高（no-dispatch） | C5/E4 共覆盖 8 proposals × 4 arms，identity gate 通过且 zero dispatch |
| Observer adequacy | benchmark 中高 / deployment 低 | E5 v2 analytic observer 通过并在线接线；camera/contact attestation 尚未资格化 |
| Resource readiness | 高（冻结本机 workload） | E6 v2 10 项 gate 通过，policy/pipeline p99 约 97 ms |
| Source/evidence binding | 已关闭 | E8 clean commit binding 完整，未绑定 semantic scope path 为 0 |
| Closed-loop no-attack smoke | 工程链路通过、活性风险待量化 | 2 个 effect-allow prefix、10 个 exact receipts；随后 K=1 proposal 被 L1 fail-closed |
| M2 confirmatory foundation | 终局 nonpass | 240/240 valid；39/86 transition=`45.35%`，95% cluster CI `[32.93%,57.78%]`；原 50% gate 未通过 |
| Four-arm v4 full population | 结构性不可执行/不可通过 | fresh1 首单元在 dispatch 前 fail closed；15/60 affordance pairs 缺少可信 part geometry，而 clean gate 要求 0 unknown |
| Support-conditioned successor | clean 终局 nonpass | 360/360 valid；VLA-only 61/90、Execution-only 66/90、Semantic-only/Dual 0/90 strict success；Dual deadlock 88/90，attacked 未授权 |
| Risk-selective L1 v10 | mixed/negative | exact passthrough 消除大部分人为动作改写；clean/attacked fresh15 未建立 non-inferiority 或 safety efficacy |
| Typed L2 containment v11 | mechanism pass / efficacy mixed | fresh15 与 held-out scale45 均为 trigger 后旧 policy dispatch 0；scale45 joint-limit burden 显著下降，但 clean Dual−Semantic-only task success `−24.4pp` |
| Recoverable L2 v12.1 | no-outcome preflight pass / efficacy 未测 | 655-case contract gate 与45-pair simulator-reset recovery gate 通过；只覆盖 joint-5 upper-limit，未加载策略或读取 outcome |
| Recoverable L2 v12.2/v12.3 | mechanism strengthened / efficacy 未测 | typed runtime 10/10；多关节210-case覆盖209，actual recovery 209/209；v12.2因full-state identity 201/210保持non-pass，v12.3 trusted-arm identity 210/210通过 |
| Policy-prefix shadow v12.4 | fresh no-outcome mechanism pass / efficacy 未测 | fixed-prefix warm-start 后 repeat 30/30；fresh π0.5 formal 为30次 inference、risk agreement 30/30、nominal allow 15/15、synthetic recovery-required 15/15，repeat 29/30；dispatch/outcome 为0 |
| Integrated recovery v12.5 | fixed-trace composition pass / simulator integration 未测 | 60/60 routes；exact allow 与两类 substitution boundary通过，typed recovery receipt/completion/fresh-state authorization 15/15；policy/simulator/outcome为0 |
| Simulator-integrated recovery v12.6 | mechanism mostly pass / liveness non-pass | 18/18 valid，recovery/receipt/terminal safe 9/9；恢复后 fresh authorization 6/9，formal non-pass。后继 policy-aware 单前缀关闭2/3 known outliers；最后一个 outlier 的156个两阶段组合中65个 recovery-safe，但 seed10509 全部 block；dispatch/outcome为0 |
| Deployment | 未就绪 | E7 缺少7类 perception supervision；所有正向结果仍限于 privileged simulator geometry |

## 2026-07-29 终局判断

v11 scale45 clean/attacked 各180条完整。任务成功率为：

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 32/45 | 27/45 | 31/45 | 20/45 |
| Attacked | 30/45 | 28/45 | 25/45 | 21/45 |

joint-limit step rate 为：

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 12.794% | 0.116% | 13.980% | 0.110% |
| Attacked | 8.194% | 0.063% | 5.826% | 0.049% |

当前论文足以形成“形式化 transaction integrity + auditable failure localization + containment–utility
tradeoff”的完整系统论文；不足以形成“通用 defense efficacy、first-hit prevention 或完整物理安全”
的强正面论文。v12 若要恢复正面 efficacy claim，必须通过新版本 sparse L1、predictive L2 和 typed
recovery 的独立资格与 fresh gate，不能把 v11 改判。

v12.2/v12.3 已把这条无 outcome 证据从单一 joint-5 upper 扩到7 joints ×双侧：正式210-case
population 覆盖209个，209/209 selected recovery 都在 actual replay 中安全完成，typed
authorization/receipt/replay/fresh-state 边界通过。v12.2 的 full-state identity 201/210 按原 gate
保持 non-pass；v12.3 另行证明 trusted arm `qpos/qvel` identity 210/210，剩余差异是最大
`2.22e-16` 的非机械臂诊断状态。它显著增强恢复机制证据，但没有 policy-prefix、clean utility 或
attacked efficacy，因此不改变上述论文强度判断。

v12.4a/v12.4b 先关闭了 controller-aware shadow 的机械复现缺口：固定的10-step policy prefix 在15个
nominal 与15个 synthetic joint-pressure case 上均给出绑定决策和30/30 risk agreement；
`qacc_warmstart` 后继将 repeat fidelity 从29/30提高到30/30，最大 qpos 误差从
`0.0990581` 降到 `4.44e-16 rad`。v12.4c 随后在资源恢复后完成独立 fresh π0.5 qualification：
30个 observation 各做一次 fresh inference，nominal allow 15/15、synthetic recovery-required
15/15、risk agreement 30/30，repeat fidelity 29/30，所有 trusted restore gate 100%，dispatch
和 outcome read 为0。唯一尾部处于 current-trigger dense-contact synthetic dynamics，两个 replay
仍一致要求 recovery。该结果增强的是 simulator/controller/policy-prefix mechanism，不是 clean
utility、task-preserving recovery 或 attacked efficacy；“完整系统论文、尚非强正面 efficacy
论文”的判断不变。

v12.5 进一步把 fresh screen evidence 与 typed recovery transaction 接成单一 fixed-trace route：
15个 nominal exact authorizations、15个 prefix substitutions、15个 recovery happy paths 和15个
selection-state substitutions 全部符合预期；旧 policy authorization、recovery replay 和 substituted
fresh state 接受均为0。该结果关闭的是 source-digest-bound software composition，使用 in-memory
sink 且不创建 simulator，因此仍不能表述为实际 task-preserving recovery。它让论文的 transaction
integrity 证据更完整，但不改变 efficacy 强度判断。

v12.6 把上述链路放进真实 LIBERO simulator state transition，但继续丢弃所有 outcome。正式9-pair
population 中 nominal allow 9/9，synthetic recovery open/completion/receipt/terminal safe 均9/9，
active MuJoCo warning、joint crossing、policy dispatch 和 outcome read 均为0；恢复后新 prefix
只有6/9 `allow_exact`，其余3个被预测屏幕正确地 `block_replan`，因此按冻结 gate 判 non-pass。
结果后的统一 margin sweep 和每点8次 bounded replan 都未消除全部 outlier。这使论文多了一条
有价值的系统负结果：state-safe recovery 不等于 next-policy-safe recovery；下一版需要
policy-aware candidate objective，而不能降低 gate 或把 block 当作成功。结果后的 policy-aware
branch screen 已在 shortest/all-safe-prefix 两阶段为3个 outlier 中的2个找到双-seed安全候选；
最后一个 case 在冻结13原语×H10库的65个 safe prefixes 中仍为0，进一步把剩余缺口定位为
recovery generator 容量，而非 margin、seed retry 或候选排序。继续扩展的156个两阶段组合中
65个通过原 recovery safety，但在 seed10509 下仍全部 `block_replan`；最好 post-policy
margin 只从单前缀的 `−0.01246` 改善到 `−0.01194 rad`。这进一步排除了简单串联离散原语，
下一步需要诊断具体 joint/direction 后再构造连续或 joint-space generator。随后164个局部连续
blend 全部 recovery-safe，却同样在 seed10509 下 block；最好值仅到 `−0.01187 rad`，而且
164/164 limiting atoms 都是 joint-1 upper。这排除了局部笛卡尔插值，支持下一步做
joint-1-targeted、仍受全局 recovery gate 约束的序列搜索。该 beam 后继把 joint-1 terminal
margin 推到 `0.27944 rad`，96/96 retained trajectories 均 recovery-safe，但 fresh policy
仍全部 block；endpoint 与 post-policy margin 相关仅 `−0.135`。因此剩余缺口已从 recovery
generator 转移到闭环控制时域：需要逐 action safety/replan，而不是更远的 open-loop retreat。
一步 receding-horizon 后继进一步验证了这一点：两条独立 seed lane 都在原 H1 gate 下安全推进
3步，而完整H10始终 block；第4轮 H1 才 fail closed。该结果把零步活性提高到3步，但未通过
预注册5-cycle gate，仍是机制性局部改善而非 task utility 或 efficacy。第4轮再做每 lane
8次 bounded fresh H1 replan 仍为16/16 reject，排除了单一 seed 偶然性，并把下一设计点明确为
predictive `block_replan` 后的显式 recovery escalation。
显式 escalation 原型确实在第4轮触发，但原13原语从约0.1546 rad 的当前 margin 出发无法找到
满足额外0.02 rad terminal gain 的候选，selection/execution 为0/2并安全停止。这说明路由方向
合理但动态恢复库仍不足；后续需把 joint-targeted generator 接入 escalation，而不是降门。
接入后的 adaptive beam 在首个 safe-state escalation 上仍无 recovery-terminal node 并终态
fail closed，说明瓶颈并非只在 generator，而是 `block_replan` 状态与 near-limit recovery
的额外0.02 rad gain contract 类型不匹配。后继需独立的 safe bridge/shield contract。
full-scale safe-bridge 后继又显示 H1 推进3步后，13/13下一原语单步都会 crossing；说明H1
离散 horizon 没有保留制动余量。下一控制设计应使用 H2 预测、H1 执行，而不是在临界状态补救。
H2/H1 后继确实更早在约0.2728 rad 停止，但122个缩放 bridge 仍全部违反 recovery-style
5 mrad transient-loss floor；最好下一步约0.1570 rad，仍高于trigger但不满足该专用 contract。
因此下一论文迭代需把 bridge/brake 形式化为独立类型，不能把 recovery 条件直接复用或事后放宽。

该独立类型现已冻结为 `absolute-safe H2 bridge` 工程协议：bridge 必须保持绝对
`0.15 rad` safe margin、零 crossing，并在精确重放后的终点让同一 fresh policy prefix 再次通过
H2；只执行其首个 action。near-limit recovery 的 `+0.02/0.005 rad` 合同不变且不被 bridge
冒充。预注册正结果门为两条 result-informed lane 各完成5个 control cycles 且所有 warning、
dispatch、typed recovery、outcome read 为0；即使通过，也必须在冻结方法后做未见 seed 复验，
才能从机制性改善升级为较可信的闭环工程证据，仍不能直接称 task utility 或物理安全。

首轮 absolute-safe H2 结果仍为 non-pass，但提供了更细的因果分解：122/122个候选都满足
独立 `0.15 rad` bridge floor 并完成 post-H2 screen，证明失败不再来自 recovery-style
transient gate；然而122/122 policy screens 仍 block，最好 margin 为 `−0.015518 rad`，
且61种动作的单步终点都集中在约 `0.1545–0.1549 rad`。因此瓶颈是 H2 stop 后只剩一个
controller-lag step，而非候选合法性。下一轮应在不改阈值的前提下使用 H3 提前制动和有界
controller-aware bridge sequence。该轮已预注册为 maximum depth 3、beam width 96、最多192个
post-H3 candidates，并只加入 blocked prefix 的8个反向缩放动作；仍需双 lane 5-cycle 与未见
seed 复验才能形成正向证据。

H3 sequence 终态依然 non-pass：两条 lane 各推进1步；每条 lane 有4418个安全两步扩展，但
第三步6624/6624违反0.15 floor，合计256个 post-H3 screens 全部 block，最好 margin 仅改善到
`−0.013973 rad`。这进一步把失败定位到 OSC 累积 goal/controller lag，而不是高层候选数量。
下一轮应验证显式 controller-goal reset brake：只重绑低层 goal 到当前位姿，不清零 qvel/qpos，
随后仍由0.15 floor、零 crossing 和 exact H3 gate约束。若其双-lane 5-cycle 通过，仍需冻结后
用未见 seeds 复验。

controller-goal reset 本身仍没有让122个 post-H3 screens 中任何一个通过，最好 margin 为
`−0.013713 rad`；但122/122 reset+一步候选均物理安全，说明 reset 的价值在逐步制动，而不是
一次性改变三步 policy 语义。下一工程协议应采用 reset-guarded exact H1：H3 block 时仅在 reset
controller 上验证并执行原 prefix 的首个 exact action，随后立即 fresh H3 replan。这样测试的是
“预测提前触发 + 低层逐步制动 + exact action identity”，不是用保守替代动作制造表面成功。

该 exact-H1 successor 将活性提高到每条 lane 3/5：4次 fallback execution 的 action identity
4/4、预测/执行误差0，但第3步后只剩约 `0.15456 rad`，下一 exact action 被0.15 floor拒绝。
因此下一设计点不是放宽 floor，而是验证 control-invariant backup set：exact action 终点必须仍有
至少一个安全 reset+backup；否则先执行单独记账的 reserve action并 fresh replan。最终正结果仍
以5个 exact policy advances计，不把 reserve action计作 policy success。

一步 backup viability 进一步阻止了不可恢复的第3个 exact action，但只达到2/5：每条 lane 的
首个 reserve 虽保持约 `0.15669 rad`，其终点 backup set 已为空。这个负结果说明 control
invariant 不能只检查“存在下一步”，还要检查下一步之后仍可继续。下一轮冻结为 two-step backup
certificate，并对 exact 与 reserve 使用同一判据；仍不改变0.15 floor或把 reserve算成 policy
success。

two-step certificate 进一步给出空不变集证据：初始有56个 viable reserve candidates，但执行
最佳 `negative_z` 后 viable set 变为0；exact fallback 也没有 two-step viable endpoint。
因此继续在高层61动作上加深 backup horizon不会恢复活性。下一合理干预层是 OSC nullspace target：
只把 joint-1 内部目标向安全侧偏移，仍执行相同 policy action bytes，并保持0.15 floor与 fresh
H3；这直接针对已反复出现的 joint-1 upper limiting atom。

首次 nullspace 运行只暴露了落盘实现问题：case 返回后 controller target 的 NumPy array 无法
JSON serialization，ledger 为空且 outcome 未读，因此不报告效果。允许的后继仅做 list 转换并在
新目录机械重放同一冻结协议，不能借此改 offset 或 gate。

机械 replay 表明 nullspace offset 本身无效：4次 exact fallback 都选择0.05 rad并复现一致，但
第4 cycle 的0.05–0.50 rad候选全部 crossing，各档 terminal margin 几乎没有分离。这支持把干预
从任务 nullspace 移到显式 joint-velocity damping torque；新 brake 必须作用域仅限一个 exact
action、裁剪 actuator limits、保持配置前 qpos/qvel identity，并继续使用0.15 floor与 fresh H3。

该 scoped brake 已实现并通过13个 H2/H3/receding 定向测试；冻结 gain 为2/5/10/20/40/80。
每个控制子步显式记录 damping direction 与 torque clipping，实验结果尚未生成，因此这一实现
目前仍只是待验证方法，不进入论文效果结论。

冻结实验结果仍为双 lane 3/5。其价值是排除了“增益不够”：第4 cycle 开始 qvel 已约
`+5.47 rad/s`，此后25/25 substeps 的 torque 对所有 gain 都饱和在 `−80`，仍发生 crossing。
因此论文方法若要恢复活性，必须表述为提前保持可制动性的 joint-limit velocity envelope，而不是
事后阻尼。后继仍保持 exact source action bytes，但在进入不可制动状态前约束 joint-1 正速度。

v12.25 已将这一判断编码为双重 gate：单步位置 floor 与终点 velocity envelope 必须同时成立，
并在七档冻结 slope 中选择最大可行值。相关15个定向测试通过；正式双 lane 结果尚未生成。

冻结结果为双 lane 2/5。它没有形成正结果，但给出了新的控制结论：slope0 在速度转正后连续约
18个 substeps 打满 `−80`，终点仍为 `+0.305 rad/s`，所以反应式 envelope 启动过晚。下一方法
必须从被拦动作的第一个 substep 预制动，并以终点 toward-limit qvel≤0作为可继续性条件。

v12.26 已实现四档 full-action actuator-bound fraction，并通过17个相关定向测试。该方法仍只
是待验证 engineering pilot；在双 lane 结果和未见 seeds 复验完成前不提升论文结论。

冻结结果降为1/5：full joint-1 `−80` 从substep0施加仍以约`+0.305 rad/s`结束，各 fraction
差异极小。这排除了单轴反应时机问题，指向多关节/constraint coupling；下一方法应以 inverse
mass row 做最小干预的 coupled torque shield，同时保留 exact action bytes 与双重安全 gate。

v12.27 coupled shield 已实现并通过19个相关定向测试；每个子步都能审计 actuator-box vertex
确实降低 inverse-mass toward-acceleration term。实验结果生成前仍不计作正证据。

冻结结果仍为1/5，但 full blend 将 qvel 从约`+0.305`降至`+0.205 rad/s`，证明耦合控制方向
有效而 free-dynamics authority不足。下一步以64个实际 actuator vertices 的 restored shadow
直接纳入 contact response，再用相同位置/终点速度门筛选。

v12.28 contact-aware 64-vertex runner 已通过21个相关定向测试；结果生成前仍不计正证据。

冻结结果为1/5，但 vertex25 将 qvel 降至约`+0.169`且 margin 保持约0.2757。terminal qvel≤0
不是原五步安全定义的一部分；后继仅移除这一过强代理门，仍以每步真实 contact shadow的0.15
floor和fresh H3约束全部 advances。

v12.29 独立 runner 已通过22个相关定向测试；实验结果尚未生成，不提前计入正证据。

冻结结果为3/5：vertex25→vertex9安全推进两步且最低margin约0.2003，随后64/64候选为空。
因此 contact-aware control有局部效果，剩余缺口是选择规则未维护下一步viability；后继增加
第二个source-policy action上的vertex successor存在性门，不消费该预测动作。

v12.30 两步viability runner 已通过23个相关定向测试；双 lane 结果尚未生成。

冻结结果为2/5：第一步有64个safe successors，fresh下一状态却不存在two-step viable首步。
这说明局部successor count不是长程控制不变量；后继以width64、depth4 beam直接覆盖剩余cycles，
仍只执行首步并fresh replan。

v12.31 full-remaining-horizon beam runner 已通过24个相关定向测试；正式结果尚未生成。

冻结结果证明 extreme-vertex library到depth3已无路径：前两层仍有数千安全扩展，第三层
0/4096。下一版不再加深horizon，而把跨lane top16 contact patterns各与nominal torque做四档
插值，在不增加每层64分支的前提下测试平滑控制是否形成四步安全序列。

v12.32 smooth-mode beam已完成实现和23个相关定向测试。它只改变低层controller torque，
不改变source-policy action bytes、0.15 floor、width64/depth4或fresh-replan规则；正式双lane
结果尚未生成，因此当前论文结论仍维持negative efficacy与failure-localization边界。

正式结果仍为1/5：depth2的4096个expansions全部safe，但margin-ranked width64在depth3没有
safe expansion，且最佳模式仍是fraction1.0极值控制。16512条边审计完整且无runtime异常。
因此当前只证明“单目标margin retention”失败，不能声称全部平滑depth2状态不可达。v12.33将用
同一宽度做margin/terminal-velocity各半的冻结diverse frontier；在其结果前不提升论文结论。

v12.33实现与25个相关定向测试已完成；它不增加beam width、controller modes或预测horizon，
只增加可审计的frontier diversity。正式结果前仍视为未验证方法。

正式结果仍为1/5，且depth2的全部4096个safe endpoint的最低toward velocity已达约
`4.329 rad/s`；最低速度和最高margin都来自full vertex9→vertex9，velocity-diverse剪枝未恢复
任何depth3分支。该负结果进一步排除beam ranking，下一验证对象是exact action内部的两阶段
多关节torque schedule；在其双lane与未见seed结果前，论文结论不变。

v12.34两阶段`8×8=64` schedule runner已实现并通过27个相关定向测试；动作、floor、beam与
fresh-replan门均未改变。正式双lane结果前仍只是待验证controller parameterization。

正式结果仍为1/5，depth2最低toward velocity约`4.32974–4.32987 rad/s`，与constant vertex9
无实质差异；所以当前actuator-only simple schedules已穷尽。下一实验是明确分开的simulator
virtual joint-stop机制，预注册4个大于0.15 floor的guard margins并审计constraint/range restore。
即使得到正结果，也只能作为虚拟机械刹车的shadow机制证据，不能回填actuator-only或物理安全claim。

v12.35实现和29个相关定向测试已完成；它拒绝任何起点已在临时guard之外的candidate，并保留
exact action与原controller torque。正式结果及冻结后未见seed复验前不提升结论。

首次运行只暴露audit-layer fail-closed：200个OSC raw torques在robosuite robot层裁剪前被误标
为actual bound violation，guard效果尚未进入排序。v12.36仅按已核对的`SingleArm.control`
downstream clipping语义重放同一方法，并修正depth计数时点；不得把该工程错误当成正负效果。

v12.36机械replay实现与31个相关定向测试已完成，所有guard与效果门逐值不变。正式结果前论文
结论保持不变。

v12.36有效结果仍为1/5，但virtual stop把depth2最低toward velocity从约4.329降到2.521 rad/s；
default soft limit在0.22 guard下允许终点margin降到约0.1772，因此depth3仍为空。v12.37只冻结
更硬且满足timestep安全下限的joint-limit solref/solimp并审计恢复；即使通过也仅是simulator
virtual-brake机制证据。

v12.37实现与33个相关定向测试已完成，历史soft profile路径不变。正式结果前论文结论不变。

known-seed正式结果首次通过预注册活性门：`10509/10510`均5/5 exact advances，最低actual
advanced margin `0.16619 rad`，6/6 guard action identity和预测/执行一致性、160/160配置identity
及全部zero-anomaly门通过。该正结果来自高刚度virtual joint stop，执行中最大target-DOF
constraint force约9999，不能回填actuator-only、task utility或物理安全claim。方法现冻结，
必须在未见`20509/20510`复验后才能称为稳定simulator机制证据。

v12.38未见seed runner已实现并通过34个相关定向测试；它只替换seed并独立重算全部门。正式结果前
仍只报告known-seed正结果。

frozen held-out结果也通过：`20509/20510`均5/5，最低actual advanced margin `0.16612 rad`，
6/6 guard exact action identity、160/160 config identity、0 prediction/execution error和全部
zero-anomaly门成立。development与held-out合计4条lane、20/20 exact advances；两个split的
最低margin分别为0.16619/0.16612。最大target-DOF constraint force分别约9999/9985，说明正结果
依赖高刚度simulator stop。

这足以形成论文中的“可审计闭环失败定位最终导向一个跨seed可复现virtual-brake机制”的正向
engineering result，增强系统论文完整性；仍不足以声称actuator-only recovery、task utility、
一般defense efficacy或physical safety。若新增task-outcome实验，必须另行冻结protocol，不能回读
本轮no-outcome ledger。


论文主故事仍是两层对齐，而不是 SemanticSubtask 本身。当前最重要的科学风险集中在 L1：

1. deterministic privileged-geometry FSM 和 analytic checker 的支持集能否覆盖 closed-loop clean trajectory；
2. E2 已表明 `Z_t` prompt 本身几乎不控制动作，因此 L1 主要依赖 post-generation checker；
3. 离线 finite-corpus 的零 false allow 能否外推到新的 M2 attacked ActionBlocks；
4. online effect observer 是否因 evidence unknown/reject 导致 deadlock；
5. camera-only deployment perception 数据和独立 split 尚未到位。

如果 selector/checker 支持集太窄，Dual 会 deadlock；如果阈值太松，攻击 block 会 false allow。如果
`Z_t` 对 action head 几乎没有行为影响，它仍可作为 verifier anchor，但不能被表述为有效的 hierarchical
control。

当前最短可发表路径：

1. 保留 M2 原 50% terminal nonpass，并在正文/附录披露 40% 是 outcome-informed continuation；
2. 报告 fresh1 零 dispatch/零有效 ledger 的 semantic-support fail-closed，不隐藏 full-population coverage failure；
3. 报告 support45 clean 的完整 nonpass：360/360 valid，Dual 0/90 strict success、88/90 deadlock，
   `Dual−VLA=-67.78pp`，cluster 95% CI `[-80.00pp,-55.56pp]`；
4. 把 18/45 pair 的初始 `missing_destination_geometry` 与其余路径最终 K=1/2 mm reject 分开报告，
   并更正“45-pair supported”为“45-pair wrapper-initializable”；
5. attacked stage 因 clean prerequisite 未过而停止，不再追加当前协议 rollout，也不结果后降低 checker
   threshold；
6. 论文转为“可审计双层体系 + coverage/availability failure taxonomy”的诚实系统论文主线；若未来恢复
   efficacy claim，先用独立 split 重做 L1 closed-loop qualification 并另行冻结新协议；
7. 保持 E7 camera/deployment perception 与 MuJoCo `ncon=5000` warning 为明确 limitation，分别报告
   utility、coverage、unknown、deadlock 和 simulator diagnostics，不扩大到 physical safety。

当前已经执行这一路线回退：论文使用“双层对齐 + deterministic privileged-geometry task-FSM +
analytic checker”的窄版本。raw π0.5 selector 与 semantic prompt control 的失败应作为结果如实报告，
不能为了保留 learned hierarchy 叙事而放宽 gate。support45 clean 进一步证明当前窄版本尚不能支撑
positive defense-efficacy claim；可保留的核心贡献是问题分解、形式化 transaction、证据绑定协议和
闭环失败定位，而不是 Dual 优于 baseline。
