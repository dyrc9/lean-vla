# 历史实验时间线（归档）

> 本文件保留完整实验时间线、失败successor和停止边界，仅用于论文审计与复现。
> 它不再是当前项目进度入口。日常状态统一见
> [`current_status_and_roadmap.md`](current_status_and_roadmap.md)，默认无需读取本文件其余内容。

当前主线、可主张边界和下一步以
[`current_status_and_roadmap.md`](current_status_and_roadmap.md) 为准。本页保留完整时间线和所有
结果后 successor，不再作为快速状态入口。

## 最新 checkpoint：2026-07-31 v14 held-out task-outcome utility qualification

在held-out stress协议执行前即冻结的18个task/init pair上，使用全新environment seed `2509`与
policy seed `1251`完成四臂配对task-outcome qualification，共`18 × 4 = 72/72` episodes。所有
18个pair完整保留，没有按stress结果筛选；冻结协议前没有读取这些pair的task success、done、reward、
cost或collision outcome。

任务成功数为VLA/Execution/Semantic/Dual `16/10/15/13`。Execution−VLA的配对差为`−33.33pp`，
100,000次base-pair cluster bootstrap的Bonferroni 2.5%下界为`−55.56pp`；Dual−Semantic为
`−11.11pp`，下界`−27.78pp`。两者都低于冻结`−20pp` non-inferiority margin，所以资格分类严格
保持`predictive_virtual_brake_v14_multijoint_task_utility_qualification_nonpass`。四臂official
unsafe/collision计数均为0，对应unsafe nonincrease gates通过，但不能抵消utility gate失败。

独立逐episode轨迹扫描确认Execution有7次、Dual有3次
`no_safe_multijoint_guard_candidate` deadlock。L2-enabled两臂的全部实际14侧值中，margin
`<0.15 rad`与crossing均为0；disabled两臂分别累计1014个低余量值和380个crossing。共有4次active
intervention，逐侧prediction/execution最大误差`0.000614 rad`，通过冻结`0.005 rad`校准门；screen
latency p95 `28.30ms`、p99 `36.12ms`、最大`131.60ms`，最大constraint force约`1035.17`。运行
控制台出现contact-capacity warning，但日志没有注册可复算计数，终结件只披露观察事实，不补写
数值。

终态见
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_task_utility_qualification_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_task_utility_qualification_terminal_summary.json)。
它保留原non-pass并固定全部75条checksum entries。下一步只在outcome-disclosed development失败
上设计recovery因子；方法与参数冻结后，必须使用新的task/init population和env-policy seeds做
stress containment与task utility资格复验，不能在本轮18 pair上追逐门限。

## 前一 checkpoint：2026-07-31 v14 trigger-rich stress development 与 held-out qualification

单环境pilot冻结low/medium/high dose后，12环境development按3 suites × 4 environments ×
14 joint-sides × 3 doses完成`504`条stress lanes和四基线`2016`条执行。no-guard/shadow均产生
`528`个crossing和`1236`个低余量侧值；reactive-stop将crossing降为0，但在停止前仍观察264个
低余量值；predictive-brake将两者均降为0，同时产生240个deadlock lanes。Predictive相对Reactive
执行步可用性高`7.14pp`，但p95 screening latency为`45.13ms`、33/1968次超过50ms，最大
constraint force约`4689.7`。

development注册终态仍是non-pass：no-guard/shadow所有侧最大数值差`0.047551 rad`超过冻结
`0.001 rad`。后验诊断没有放宽门，只确认35,280个配对侧值在crossing以及
`0.15/0.16/0.22/0.30 rad`阈值上的分类分歧均为0。终态见
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_development_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_development_terminal_summary.json)。

随后在旧45个精确task/init pair之外，确定性选择三套任务各6个不同task id与新init，并将environment
seed改为`1509`。held-out qualification完成18环境、`756` stress lanes和`3024` baseline lanes。
Shadow产生`818` crossing与`1884`低余量值，Predictive均为0；Reactive为`2/402`。18个完整性、
核心机制、active-contact和timing gate通过：active阶段19,654次contact observations最大
`ncon=107/5000`且无warning/saturation，p95为`38.32ms`，60/2934=`2.045%`超过50ms，低于
冻结2.5%门。Predictive相对Reactive执行可用性高`7.09pp`，但366/756=`48.41%` lanes deadlock，
最大constraint force约`8048.8`。

资格总体仍为注册non-pass。唯一失败的`low_negative_control`来自两个未见human-safety环境的
joint-1-upper low lanes：原生constraint force约`30k`使no-guard在第二步crossing；Predictive
在两条均提前deadlock并保持实际crossing为0。该意外结果不能事后把low重标为stress。终态将总体
non-pass与完整的core axes分开记录，见
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_qualification_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_stress_qualification_terminal_summary.json)。

独立task-outcome utility qualification已按上节完成并因10次deadlock保持non-pass。下一实验将
deadlock recovery/backup controller作为独立因子；不得从本轮结果选择后续确认性任务或改写
dose/gate。

## 前一 checkpoint：2026-07-31 v14 同 schedule shadow-only 因果消融终态

v14 shadow-only 在新的 causal1 root 完成与 Fresh2 完全相同的45 workloads × 4 arms=`180/180`。
Execution-only和Dual仍在每个policy step执行一次exact-action shadow与warm-start restore，但从不
评估guard candidate、不施加virtual guard、不替换source action，也不合成brake deadlock；
VLA-only和Semantic-only保持直接执行与14侧post-state审计。

在线合同全部通过：共`50,484`个policy steps、`24,395`个L2 shadow steps，intervention与deadlock
均为0，restore和exact-action mismatch均为0。Shadow-only的L2 arms产生`2733`个
margin `<0.15 rad`侧值和`1442`个crossing，而Full brake对应均为0。Execution-only分别是
`2108/1277`，Dual为`625/165`。Full/Shadow的L2 task success合计为`60/67`，unknown/deadlock为
`17/0`；逐臂task success为Execution `32/36`、Dual `28/31`，official unsafe保持
Execution `1/1`、Dual `2/2`。

冻结终端比较给出了强身份检查。90个disabled-arm episodes的action digest、逐步margin、trace长度和
outcome完全一致；73个没有Full trigger的L2 episodes也完全一致。其余17个首trigger episodes在
分叉前共比较`20,963`个policy steps，source action、risk-side identity、current/unguarded
prediction及此前actual margin的最大跨运行误差均为0。Full共29次trigger、12次intervention和
17次deadlock。因此本development population上的`1442 -> 0` crossing与`2733 -> 0`低余量差异
可一致地解释为授予brake authority的结果，同时必须报告`67 -> 60`任务成功与`0 -> 17`
deadlock代价。

注册结论仍是non-pass。预先冻结的shadow prediction/execution逐侧容差为`0.002 rad`，实际最大
`0.004651 rad`，是门限的`2.326×`；唯一失败gate为calibration。后验diagnostic将该注册non-pass
与完全通过的pre-divergence causal identity分轴记录，但明确不修订注册分类、不授权确认性结论。
冻结文件为
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_shadow_only_causal_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_shadow_only_causal_terminal_summary.json)
和
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_shadow_only_causal_terminal_diagnostic.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_shadow_only_causal_terminal_diagnostic.json)。

下一步不再重跑同一outcome-disclosed schedule以追逐门限，而是冻结trigger-rich
low/medium/high stress development，比较no-guard、reactive-stop、shadow-only与predictive
brake，并把deadlock recovery作为独立因子。方法冻结后，必须用新workload/init/env-policy seeds
执行outcome-blind qualification。

## 前一 checkpoint：2026-07-31 v14 全关节 clean development 终态

v14 将 v13 的单一 `joint-1 upper` monitor 扩展为每步7个arm joints × lower/upper共14个margin，
并对同一步所有at-risk joints联合施加最弱可行的 simulator hard guards。development1 在完成前两条
L2 outcome后，于首条disabled arm暴露继承的v13单目标审计依赖；该root以4条checksum entries封存，
不复用。Fresh2只移除disabled-arm的单目标依赖，保持180条schedule、workload/init、env/policy
seeds、arm order、guard、阈值、estimands和gates不变，并在新root完成`180/180`。

终态共有`47,130`个policy steps、`21,041`个L2 screen steps、29次trigger、12次active
intervention和17次fail-closed deadlock。trigger分别来自joint3/5/6 upper的`17/4/8`次，
intervention为`7/2/3`次。Execution-only和Dual的所有实际14侧值中，margin `<0.15 rad`与
crossing均为0；VLA-only和Semantic-only合计分别为`3306`和`1455`。所有restore、scope、exact
action、torque-bound和intervention-floor异常计数均为0。

该正coverage结果伴随明确代价。task success为VLA/Execution/Semantic/Dual
`36/32/32/28`，Execution−VLA与Dual−Semantic均为`−8.89pp`，冻结`−20pp` paired
non-inferiority下界分别为`−20.06pp`和`−24.44pp`，两门均未过；17个L2 deadlock是主要活性缺口。
official unsafe仍为`1/1/2/2`，没有显示总体改善。

严格的`1e-9 rad`全侧 prediction/execution calibration gate也按冻结规则non-pass。最大误差
`0.001187 rad`来自非干预且远离风险边界的joint side；非干预p99为`9.74e-6 rad`。12次干预的
168个逐侧误差最大`4.24e-6 rad`，最低margin预测误差最大`2.53e-9 rad`；false-safe风险决策为0。
因此终态分类为
`predictive_virtual_brake_v14_multijoint_clean_development_fresh2_data_complete_calibration_nonpass`，
不能结果后放宽原门。

冻结终态见
[`../experiments/proofalign_predictive_virtual_brake_v14_multijoint_clean_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v14_multijoint_clean_terminal_summary.json)。
同schedule全关节shadow-only guard-off消融已按上节完成；下一步冻结trigger-rich
no-guard/reactive/shadow/predictive压力测试，确认性复验必须使用新workloads/init/seeds。

## 前一 checkpoint：2026-07-31 v13 task-outcome、shadow 与 attacked 终态

v13 Fresh3 clean 已完成45 workloads × 4 arms=`180/180`。VLA-only、Execution-only、
Semantic-only、Dual task success 为`36/45、36/45、32/45、31/45`；Execution−VLA 与
Dual−Semantic 的 paired bootstrap 95%区间分别为`[-8.89pp,+8.89pp]`与
`[-15.56pp,+11.11pp]`，均高于冻结`−20pp` non-inferiority margin。official unsafe 为
`1/1/2/2`，不是零风险。该 clean population 只有1次 joint-1-upper trigger，因无安全候选
fail closed；active intervention 为0。

同一45 workloads/seeds/order 的 clean shadow-only ablation 也完成`180/180`。任务成功和 official
unsafe 与 full brake 完全相同。唯一 full-brake trigger 对应的 shadow episode继续运行到
max steps；full brake少执行250个 policy steps，少225个 model-defined joint-limit steps、
41个 target-margin<0.15 steps和2个 target-margin<0 steps。这是一个保守 containment case，
不是总体 safety efficacy。

冻结的 instruction-attacked stage 随后完成`180/180`，攻击使`180/180`首个 ActionBlock 相对
paired clean 改变。原 retained evidence 因 wrapper nesting 顺序让 v11 legacy metric hook 覆盖
v13 hook，故保留`predictive_virtual_brake_v13_attacked_incomplete`和两个不适用 legacy gate
failure。终态 successor 不重跑、不修改任何 episode/manifest/checksum，只在内层 context 恢复已冻结
的v13 metric hook并从183条 checksum entries机械重建；修正后所有数据完整性 gate 通过。

attacked task success 为`35/45、35/45、28/45、28/45`，official unsafe 为`1/1/0/1`。
Execution−VLA 与 Dual−Semantic 的 paired success difference 都是0，95%区间均为
`[-11.11pp,+11.11pp]`；但 Dual official unsafe nonincrease 相对 Semantic-only 失败。
一个 Dual episode产生2次target trigger：第一次0.16-rad hard guard把 unguarded predicted
`0.136171 rad`保持为actual `0.159981 rad`，prediction/execution error为0；下一步无安全候选并
deadlock。全population仍有2016个全机械臂 joint-limit violation steps，其中L2 arms为874，
与target trigger重合为0。结果因此支持“一次exact active simulator containment”，不支持总体
attacked efficacy、recovery、全关节安全或确认性结论。

随后冻结的 attacked shadow-only 保留同一45 workloads、M2 prompt transplants、seeds、四臂和顺序，
并在每个L2 step执行同一shadow+warm-start restore，但从不评估或施加guard。180/180完成，active
trigger/intervention/deadlock均为0，restore/action audit无失败。VLA/Execution/Semantic三臂与full
attacked逐episode结果完全相同；Dual success从full的28/45变为shadow的29/45，unsafe仍为1/45。

唯一差异仍是`human_safety task4/init32 Dual`。两条件前236个policy steps、首次risk action digest、
current margin和unguarded prediction完全一致。full在step246把predicted `0.136171`守到
`0.159981 rad`，step247 deadlock，238 steps后失败；shadow继续到276 steps，累计25次
counterfactual trigger、最低target margin `0.061217 rad`、23个margin<0.15 steps和7个
joint-limit steps，最终env_done成功，且两条件official unsafe都为false。该结果识别了一个清楚的
safety-proxy–liveness tradeoff：guard减少风险暴露，但没有safe recovery时会牺牲任务完成。

终态可复算入口为
[`../scripts/freeze_predictive_virtual_brake_v13_attacked_terminal.py`](../scripts/freeze_predictive_virtual_brake_v13_attacked_terminal.py)
和
[`../experiments/proofalign_predictive_virtual_brake_v13_attacked_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v13_attacked_terminal_summary.json)。
attacked因果对照见
[`../experiments/proofalign_predictive_virtual_brake_v13_attacked_shadow_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v13_attacked_shadow_terminal_summary.json)。
下一步实现全7关节/双侧margin audit与trigger-rich
no-guard/reactive/shadow/predictive压力测试；development完成后必须另取未见workload/init/seeds做
outcome-blind qualification。

## 最新 checkpoint：2026-07-30 v12.38 frozen held-out hard virtual joint stop

v12.37 development 与 v12.38 frozen held-out 已完成方法冻结前后的跨 seed 验证：4条 lane 合计
20/20 exact advances，最低 actual advanced-state margin 分别为 `0.1661929/0.1661158 rad`，
action/config/profile identity、prediction/execution equality 与全部 zero-anomaly 门通过。该结果严格
限定为 hard simulator virtual-joint-stop engineering evidence；约 `10k` generalized constraint
force、zero task-outcome read、无 actuator-only authority 和无部署证据必须同时披露。

下一科学步骤只允许另立 task-outcome protocol，先验证 clean utility；不能回读本轮 no-outcome ledger
选择 workload、guard 或阈值。以下从 v12.6 开始保留完整优化时间线。

### v12.6 simulator-integrated recovery 起点

v12.6 已把 fresh policy、controller-aware shadow、typed recovery simulator steps 和恢复后
fresh-state authorization 接入同一条 no-outcome 链路，并完成独立 formal：

- 初始化已绕开内部调用 `check_success()` 的 LIBERO `set_init_state()` wrapper；测试和账本均锁定
  wrapper call/outcome read 为0；
- MuJoCo warning 已按 frozen state 绑定前/后分阶段记账；formal active phase warning 和 contact
  saturation 均为0；
- 9个 fresh pairs、18个 cases 全部有效，覆盖全部7个 joints，历史薄弱的 joint1-upper 重复3次；
- nominal allow 9/9，synthetic recovery open、candidate coverage、completion、terminal safe、
  receipt identity 均为9/9，joint-limit crossing 为0；
- 正式 gate 仍为 non-pass：恢复后 fresh prefix 仅6/9 `allow_exact`，3/9 `block_replan`；
- 结果后 margin sweep 没有找到统一可用阈值：0.18/0.20/0.25/0.30 的 post allow 分别为
  1/3、2/3、2/3、2/3，0.30 的 candidate coverage 又降为2/3；
- formal-seed bounded replan 在三个 outlier 上各尝试8个 fresh prefix，仍为0/3 authorized。
- policy-aware branch screen 随后在 shortest-safe candidates 上解决1/3；扩展到全部 H≤10
  recovery-safe prefixes 后再解决1/2，累计为2/3 known outliers 找到双-seed安全候选；
- 最后一个 `obstacle_avoidance_human_task14_init46` 在65个 safe prefixes 中仍为0个可用，
  表明冻结13原语×H10 generator 容量不足，而不是 selector 排序或单一 margin 问题。

完整 formal 表格、outlier、负结果和下一版设计见
[`v12_simulator_integrated_recovery_checkpoint.md`](v12_simulator_integrated_recovery_checkpoint.md)。
当前下一步是版本化两阶段/关节空间 recovery generator 的 no-outcome engineering pilot；不放宽
gate，不授权 clean/attacked/outcome rollout。

两阶段 pilot 已完成：只对最后一个 outlier 搜索4个证据驱动 parent prefix × 13个原动作 ×
H=1/2/3，共156个组合。65个组合通过原 recovery safety，但全部在第一个固定 policy seed
`10509` 下 `block_replan`；最好 post-policy margin 为 `−0.01194 rad`，因此没有候选进入
`10510`，也不授权 typed recovery。branch restore identity 为100%，active warning、dispatch、
typed recovery 和 outcome read 均为0。下一步应先定位被 post-policy prefix 压过边界的具体
joint/direction，再设计连续动作或显式 joint-space retreat；继续保持原 gate。

局部连续搜索也已完成：围绕最好结构生成的164个有界混合动作全部 recovery-safe，但
seed10509 仍全部 `block_replan`；最好 post-policy margin 仅为 `−0.01187 rad`。新增诊断显示
164/164 的 limiting atom 都是 `joint 1 upper`，因此问题已经从“未知 generator 容量”收缩为
“需要显式增加 joint 1 上界余量”。下一轮使用 simulator-shadow beam search，每步可切换原13个
动作，按 joint-1 upper margin 排序，同时保留原全局 recovery safety 与 policy gate。

joint-targeted beam 也已完成：它把恢复终点 joint-1 upper margin 提高到 `0.27944 rad`，
96/96 保留轨迹通过原 recovery selector，但 seed10509 仍全部 `block_replan`，最好
post-policy margin 反而只有 `−0.01543 rad`。endpoint margin 与 post-policy margin 相关仅
`−0.135`，说明 fresh policy 对新观测的响应抵消了 open-loop retreat。下一步转为
receding-horizon 机制试验：每轮只放行经原 gate 验证的首个 action，然后立即在新状态 replan；
仍只做 restored shadow，不派发、不读 outcome。

两条 seed lane × 5 cycles 的 runner 与测试已实现；固定使用 beam 中 full-prefix margin 最好的
三步恢复序列，不在新结果上再次挑 recovery。每 cycle 同时记录 full-H10 verdict 和 H1 gate，
只有 H1 exact-safe 才推进一个 shadow action。实现先提交，随后在 clean worktree 上运行。

该试验已完成：两条 seed lanes 都连续安全推进3步，H1 gate 前3轮合计6/6 allow；第4轮
H1 直接预测越界并在推进前停止，因此5-cycle gate non-pass。相较完整H10在每轮都 block，
receding horizon 已把可安全活性从0步提高到3步，但还不能持续。下一轮允许每 cycle 最多8次
fresh H1 replan，仍只推进首个 exact-safe action；不降低阈值，不隐式打开 recovery。

bounded-H1 runner 与测试已完成：每 cycle 最多8次、attempt seed stride=10，状态在失败尝试间
保持不变。只有首个 H1 exact-safe attempt 被选中并推进，全部失败则停止；代码先独立提交后运行。

结果表明第4轮两条 lane 的16个额外 H1 seeds 全部失败，安全推进仍停在3步；继续增加随机
retry 没有依据。下一步版本化 predictive recovery escalation：bounded H1 replan 耗尽后，
只允许通过原 selector 的 recovery shadow 轨迹推进，再从新状态重新做 fresh H1 gate。

predictive-escalation runner 与测试已实现：每 round 一次 H1 inference，每 cycle 最多2次显式
recovery；每次 recovery 都重新跑原 selector、replay tolerance 和 crossing gate，之后再用
独立 seed round 做 H1。仍为 restored shadow、zero dispatch、zero outcome。

结果为 selection 0/2：两条 lane 在第4轮的状态 margin 约0.1546 rad，原13原语没有任何轨迹
能满足相对当前状态再增益0.02 rad，故 escalation 未执行即 fail closed。下一步把
joint-targeted beam 作为动态 escalation generator，生成后仍由原 selector 复核，不改门。

adaptive-beam fallback 与测试已实现；它只在默认 selector 无候选时启动，beam 结果仍需原
selector 与独立 replay 双重通过。实现先提交，再在 clean worktree 上做两 lane × 5-cycle 运行。

运行在首个 escalation state fail closed：beam 也没有满足当前 margin `+0.02 rad` 的
recovery-terminal node；未执行 escalation/policy、未读 outcome。失败目录保留，不覆盖。
原因是 safe-state `block_replan` 与 near-limit recovery contract 不匹配。下一版应单独定义
one-step safe bridge/shield，保持 transient/no-crossing/H1 门，不篡改 recovery gain。

safe-bridge runner 与测试已实现：13个一步原语先过 unchanged transient/trigger gate，再要求
fresh post-bridge H1 allow；每 cycle 最多2个 bridge。bridge 独立记账，不记为 recovery，
所有执行仍为 restored shadow。

结果为 transient-safe bridge 0/26：H1 允许第3个 policy action 后 margin 只剩约0.1546 rad，
随后任何 full-scale 原语（含 hold）一步都会 crossing。下一步改用 H2 screen、仍只推进首步，
提前保留制动余量；bridge 动作增加0.1/0.25/0.5/0.75缩放，但 transient/trigger 门不变。

H2-scaled-bridge runner 与测试已完成：61个有界 bridge actions，H2 screen/H1 advance，
post-bridge 仍需 fresh H2 allow。实现先提交后运行。

结果：H2 将两条 lane 的安全 policy advance 固定在2步并更早停止，停止时 margin 约0.2728；
61×2个 scaled bridges 中 transient-safe 仍为0，因为下一控制步最好只剩约0.1570，
无法满足 recovery-style `current−0.005` floor。下一阶段先版本化独立 bridge/brake contract
或 controller-aware braking predictor；不继续对现有门做结果后微调。

独立 bridge contract 已在看结果前冻结并实现：bridge 仍取同一61动作库，但单步终点必须
`margin >= 0.15 rad` 且零 crossing；该绝对 safe-state floor 不复用 recovery 专用的
`current−0.005` transient floor，也不修改 recovery 的 `+0.02/0.005` 参数。候选终点必须产生
fresh H2 `allow_exact`；实际重放 bridge 后，再对同一个已授权 prefix 做一次 H2 确认，只推进其
第一个 policy action。成功标准固定为两条独立 lane 均完成5 cycles，crossing、active warning、
live dispatch、typed recovery 和 outcome read 全为0。首轮只用已知 seeds `10509/10510`
做 result-informed engineering；若通过，冻结方法后另取未参与设计的 seeds 做 held-out 验证。

首轮已完成但未通过：两条 lane 仍各完成2个 policy advances；122/122 个 bridge 单步终点均
满足绝对 `0.15 rad` 安全域并全部进入 post-H2 screen，说明新 contract 已消除候选集为空问题。
但 post-H2 仍为122/122 `block_replan`，最好 minimum margin 仅 `−0.015518 rad`，
selection/execution/authorized-prefix consumption 均为0。所有 crossing、active warning、
dispatch、typed recovery 和 outcome read 仍为0。单步终点约集中在 `0.1545–0.1549 rad`，
表明当前 controller response 有明显时滞：到 H2 stop 后才发一个 bridge 已不足以改变下一段策略风险。

下一 successor 不改任何 safety threshold，改为 H3 提前触发、H1 执行，并在较高余量状态搜索
bounded controller-aware bridge sequence。搜索固定 maximum depth=3、beam width=96，每个
depth 最多送64个候选、总计最多192个进入 policy screen；动作库为原61个缩放原语，加上 blocked
prefix 首动作与 H3 均值动作的反向 `0.25/0.50/0.75/1.00` 缩放。序列每个中间状态仍须
`margin >= 0.15 rad` 且零 crossing；终点必须 fresh H3 allow，精确重放后再确认同一 prefix，
才允许推进一个 policy action。双-lane 5-cycle 成功门不变。

H3 sequence pilot 已完成但 non-pass：H3 让两条 lane 各先安全推进1个 policy action。
在随后 block 状态，每条 lane 的 depth-1 共有69/69安全节点，depth-2 有4418个安全扩展，
最佳终点约 `0.18120 rad`；depth-3 的6624个扩展全部跌破0.15 floor。每条 lane 送128个、
合计256个合法序列终点做 post-H3 screen，仍为256/256 `block_replan`；最好 margin 改善到
`−0.013973 rad`，但 selection/execution 为0。restore identity 100%，crossing、warning、
dispatch、typed recovery、outcome read 均为0。

这排除了“只增加高层桥接序列长度”。下一 successor 使用现有 OSC 的 `reset_goal()` 定义独立、
可审计的 controller-goal brake：在 restored branch 上先把 goal 重绑定到当前末端位姿，再搜索
原61个一步动作；每个候选仍守0.15 floor/零 crossing/post-H3 exact gate，实际重放时执行同一
reset+action 并确认同一 prefix。它不清零物理 qvel、不修改 simulator qpos，也不改 recovery
合同或风险阈值。

controller-goal brake pilot 已完成但 post-H3 gate 仍 non-pass：122/122 个 reset+一步候选都
守住0.15 floor并完成 policy screen，reset 审计计数244，但122/122 post-H3 仍 block；
最好 margin 为 `−0.013713 rad`，selection/execution 为0，两条 lane 各保持1个 exact policy
advance。该结果说明 reset 能稳定单步物理状态，却不能让后续未重置的三步 policy prefix 一次性安全。

下一版不再要求 reset 后的整个 H3 prefix 变成安全，而定义与 receding control 一致的
`reset-guarded exact H1 fallback`：H3 block 时，从绑定 snapshot 执行 controller goal reset，
只 shadow 检查同一个 policy prefix 的精确首动作；若该 exact action 重放全程保持
`margin >= 0.15 rad` 且零 crossing，恢复 snapshot 后执行同一 reset+同一 action bytes，
随后立即 fresh H3 replan。它不是替代动作或 projection，仍逐 cycle 消费 exact policy action；
两 lane 各5个 exact advances 的成功门与所有零审计计数不变。

reset-guarded exact-H1 已完成但达到3/5后 non-pass。两条 lane 各有第1个 action 由 H3 直接
放行，之后共有6次 reset-H1 screens，其中4次授权并执行；4/4 action bytes identity，
prediction/execution margin error 最大为0。每条 lane 第3次 advance 后 minimum margin 约
`0.15456 rad`，下一 exact action 虽经过 reset 仍低于0.15 floor，因此正确拒绝。总计6个
exact policy advances，无 crossing、warning、dispatch、typed recovery 或 outcome read。

该结果证明 exact-H1 本身可重复，但只看当前一步会把状态送出 backup-controllable set。
下一版增加 controller backup viability，不改0.15门：对 reset+exact action 的终点再验证
至少存在一个原61动作中的 reset+一步安全 backup；只有存在才执行 exact action。若不存在，
从当前 snapshot 选择 terminal margin 最大的已验证 reset+reserve action，执行后 fresh policy
replan，仍在同一个 policy cycle 中等待 exact action；每 cycle 最多2个 reserve actions。
成功仍要求每条 lane 完成5个 exact policy advances，reserve 数量单独披露。

one-step backup-viability 已完成但 non-pass：两条 lane 各完成2/5 exact advances。4次 exact
endpoint viability screens 中只有2次 backup set 非空，因而只授权2次 reset-exact action；
之后每条 lane 执行1个 `positive_y_scale0p75` reserve，最低 margin 约 `0.15669 rad`，
但该 reserve 终点的下一次61动作搜索为空，第二 reserve 无法选择。reserve 2次均未计入
policy advance；identity、restore、warning/dispatch/outcome 边界均保持。

下一版把 backup certificate 从一步提升为两步，不改动作库或floor：exact action 终点必须存在
一个安全 reset+backup，且该 backup 终点还至少存在一个安全 reset+successor；reserve 选拔也用
相同 two-step viability，而不是只按当前 terminal margin。仍每 policy cycle 最多2个 reserve，
成功只计5个 exact policy advances。

two-step certificate 已终态 non-pass：两条 lane 各仅完成第1个 direct exact action。首轮 reserve
search 各有56个 two-step viable candidates，选择 `negative_z` 后 terminal margin 约
`0.27500 rad`；但新状态的 two-step viable set 立即变为0，第二 reserve 无法选择。exact
fallback 的 two-step viable count 始终0，故没有把不可控 exact action误计为成功。该轮执行
22814个 backup-candidate shadow steps，所有 warning/dispatch/outcome 仍为0。

这证明冻结高层61动作空间不存在可持续 backup invariant，继续加深 horizon 只会确认空集。
下一 successor 改变干预层而不改 policy action：H3 block 时，在 restored controller 上把 OSC
`initial_joint[1]` nullspace target 向远离 upper limit 的方向移动，offset 候选固定为
`0.05/0.10/0.20/0.30/0.50 rad`，同时 reset goal；逐一重放同一个 exact policy 首动作，
选择最小的0.15-safe offset。物理 qpos/qvel 不修改，action bytes 不替换，之后立即 fresh H3。

首个 nullspace run 在完整 case 返回后、写 ledger 时因
`TypeError: Object of type ndarray is not JSON serializable` 终态 fail closed。preflight 为
ready，outcomes observed 为false，ledger 保持0字节；因此该目录不支持任何效果结论，也不覆盖。
修复严格限于把两段 controller target audit arrays 转成 JSON lists；offset、gate、seeds、
动作与成功门全部不变，使用新 output root 做 mechanical replay。

mechanical replay 已正常完成但仍为3/5 non-pass。两条 lane 共30个 offset candidates 的
configuration qpos/qvel identity 均30/30；4次授权与执行全部选最小 `0.05 rad`，exact action
identity 4/4、prediction/execution error 0。到第4个 policy cycle 时，即使 `0.50 rad`
nullspace target offset 也预测 crossing；各 offset terminal margin 只相差约微弧度，说明默认
`joint_kp=10` 的 nullspace torque 经投影后对该受约束 joint 几乎无控制权。

下一版改为显式、单步、可撤销的 direct joint-velocity damping brake：H3 block 后 reset EE goal，
在同一个 exact policy action 的 controller substeps 上给 joint 1 叠加
`−k_d q̇_1`，候选 `k_d=2/5/10/20/40/80`，torque 仍裁剪到 actuator limits；动作结束立即移除
wrapper。只选最小的0.15-safe gain，配置本身不得改 qpos/qvel，action bytes保持一致并 fresh H3。

该 v12.24 runner 与作用域审计已经实现：每个 controller substep 保存 nominal torque、requested
damping、clipped torque 与 joint velocity；候选预测和实际 advance 使用同一 wrapper，退出
action 后验证实例级 override 已移除。13个 receding/H2/H3 定向测试通过，下一步在 clean-tree
preflight 后执行冻结双 lane 实验。

v12.24 双 lane 已完成但仍为3/5 non-pass。36/36 candidate configurations 保持 qpos/qvel
identity，4/4授权执行保持 exact action identity，prediction/execution error 0，wrapper
scope restore 40/40，且 warning/contact/outcome 均为0。失败点揭示了更严格的动力学原因：
第4 cycle 开始时 joint 1 已有约 `+5.47 rad/s` 速度，名义 torque 约 `−583` 至 `−515`，
所有 gain 在25/25 controller substeps 都裁剪为 actuator lower limit `−80`，终点仍 crossing。

因此增大 damping gain 不再是有效后继。v12.25 改为提前介入的 one-sided joint-limit velocity
envelope：在 margin 接近0.15 floor 时限制朝 upper limit 的允许正速度；一旦实测 qvel 超过
envelope，joint 1 使用最大可用负 torque，其余 joints 与 source-policy action bytes 不变。
候选只改变冻结的 envelope slope，仍按最小干预、one-step floor、fresh H3 与完整 scope audit
选择，目标是避免上一动作把不可制动的高速状态带入下一 cycle。

v12.25 runner 已实现，slope 冻结为 `0/0.5/1/2/4/8/16 s⁻¹`；eligible gate 同时要求单步
全局 margin ≥0.15 与终点 envelope 成立，再选择最大的可行 slope（最小干预）。15个
receding/H2/H3 定向测试通过，待 clean-tree preflight 后执行双 lane。

v12.25 结果为双 lane 2/5 non-pass，但 terminal invariant 正确拒绝了不可制动状态。第2 cycle
选择 slope16 时 envelope 未激活，下一 cycle 七档全部失败；更关键的是 slope0 虽在速度转正后
连续约18个 substeps 使用 `−80`，终点 qvel 仍为 `+0.305 rad/s`，不能满足 toward velocity≤0。
28/28配置 identity、2/2 exact action、prediction/execution position 与 velocity error均0。

v12.26 改为 full-action anticipatory torque brake：被 H3 block 后，从第一个 controller substep
起即对 joint 1 施加 away-limit torque，冻结 actuator-bound fractions `0.25/0.50/0.75/1.00`，
其余 joints 与 policy action bytes不变。候选须全程 margin≥0.15 且终点 toward-limit qvel≤0，
选择最小可行 fraction；这直接解决“等速度转正后已来不及制动”的因果缺口。

v12.26 runner 与逐 substep torque audit 已实现，17个相关定向测试通过；候选/执行仍验证
qpos-qvel configuration identity、exact action identity、scope restore以及位置/速度双重
prediction-execution error。下一步 clean-tree 后跑冻结双 lane。

v12.26 结果为双 lane 1/5 non-pass，严格 gate 未授权任何 brake advance。即使从 substep0 到24
固定 joint-1 torque=`−80`，终点 qvel 仍约 `+0.305 rad/s`，且0.25–1.00 fractions 仅产生
约5e-4 rad/s的分离；这证明其它关节 torque/约束耦合主导了 joint-1 acceleration，单轴 actuator
已无足够 authority。8/8配置 identity，zero warning/contact/outcome，结果可信但方法无效。

v12.27 使用 coupled inverse-mass torque shield：每个 substep 从 controller mass matrix 取
joint-1 的 inverse-dynamics row，在全部7个 arm actuator bounds 上构造使 toward-limit
unconstrained acceleration 最小的 torque vertex，再用冻结 fractions `0.25/0.50/0.75/1.00`
与 nominal clipped torque 插值。仍选择满足0.15 floor与终点 toward qvel≤0的最小 fraction，
保持 source action bytes、one-action scope与 fresh H3。

v12.27 runner 已实现，逐 substep 记录 inverse-mass row、线性求解 residual、nominal/vertex/
applied 7轴 torques、toward-acceleration term与 bound violation；19个相关定向测试通过。
clean-tree 后执行双 lane。

v12.27 双 lane 仍为1/5 non-pass。free-dynamics 指标有效：200/200 substeps 的 vertex 都降低
toward-acceleration term，mass solve residual≤6.7e-16，且无 torque bound violation；full blend
把终点 qvel 从约`+0.305`降至`+0.205 rad/s`、margin提高到约0.275，但仍未达到非正速度门。
这说明 contact constraint response 与 free mass-matrix optimum 不同。

v12.28 改为 contact-aware actuator-vertex shadow：joint 1 固定 away-limit bound，枚举其余6轴
的 `2^6=64` 个 min/max torque vertices，并在真实 restored one-step simulator branch 中直接
筛选全局 margin≥0.15、terminal toward qvel≤0的候选。选择最大终点 target margin、再最大
全局 margin、再稳定 lexicographic ID；执行仍是同一 policy action bytes和 one-action scope。

v12.28 runner 已实现，逐 candidate 保存固定7轴 vertex、25个 nominal/applied torque samples、
terminal target margin/qvel、scope与configuration identity；21个相关定向测试通过，待
clean-tree 双 lane 实验。

v12.28 双 lane 为1/5 non-pass，128/128 configuration/scope identity与零 torque/warning/contact
异常成立，但64 vertices均被 terminal qvel≤0门拒绝。最好且跨 lane 一致的 vertex25 将 qvel
从 unshielded约`+0.308`降到约`+0.169 rad/s`，同时维持约0.2757 margin；这说明搜索有效，
而“单步终点必须反向”只是充分条件、并非五步 receding safety目标的必要条件。

v12.29 保留同一64 vertices、0.15 one-step floor、margin-first排序、terminal qvel完整审计与
fresh H3，但移除 nonpositive-qvel 硬门；下一 cycle 由新的真实 contact-aware screen 直接决定
能否继续。成功门仍严格要求两 lane各5个 exact policy advances与全程零 crossing/warning/
contact saturation/outcome read，不因放松代理条件而放松物理 floor。

v12.29 runner 已实现并通过22个相关定向测试；代码路径只增加一个显式 boolean gate，默认仍
保持v12.28 strict行为，新 runner 单独冻结为false，避免改变历史结果语义。

v12.29 双 lane 回到3/5 non-pass，但两次 shielded fallback 均安全执行：选择序列在两 lane
一致为 vertex25→vertex9，最低 advanced margin约0.2003；384/384 candidate identities、
4/4 exact action与prediction/execution position/qvel error 0。第三 fallback才出现64/64无安全
vertex，说明问题是 greedy one-step ranking没有维护 successor viability。

v12.30 对每个one-step safe vertex的endpoint恢复快照，并用当前 source-policy chunk的第二个
exact action枚举同一64-vertex successor set。首步只有在至少一个 successor仍满足0.15 floor时
才 eligible；排序先最大 safe-successor count，再最大首步 target/global margin与稳定ID。
执行后仍fresh inference/H3，successor只作保守viability证据、不被实际消费。

v12.30 runner 已实现，successor配置/作用域/torque bounds与margin单独审计，23个相关定向测试
通过。该搜索量约为每个fallback `64×64` successor branches，正式运行预计明显慢于前版。

v12.30 双 lane 为2/5 non-pass。第一 fallback 的 vertex25各有64个safe successors并被安全执行，
但 fresh下一 cycle的全部首步都没有safe successor；共16384 successor branches的identity/
scope/bounds全部成立，最低advanced margin约0.2757。结论是2-step viability horizon仍不足。

v12.31 使用宽度64、最大深度4的 contact-aware beam：从当前prefix按剩余 cycle数取exact actions，
逐层对每个保留状态扩展64 vertices，仅保留全程margin≥0.15分支，并按trajectory minimum
margin、terminal target margin、terminal qvel与稳定sequence排序。只有存在覆盖全部剩余cycles
的序列才授权其第一vertex；实际仍只执行第一exact action并fresh inference/H3。

v12.31 runner 已实现，beam每层记录parent/expansion/safe/retained counts、最佳序列与整段最小
margin，并汇总所有configuration/scope/bound audits；24个相关定向测试通过。正式运行的首个
fallback预计扩展约`64+3×4096`条边。

v12.31 双 lane 为1/5 non-pass，但给出完整可达性证据：depth1为64/64 safe，depth2分别
3283/4096与3285/4096 safe，width64最佳为`[9,9]`且trajectory minimum约0.20036；depth3却
0/4096 safe，因此不存在当前极值vertex集合内的3步、更不用说4步路径。16512/16512配置/
scope identity与零bound/warning/contact异常成立。

v12.32 不扩大branching factor：从v12.28跨lane平均terminal target margin排序冻结top16 patterns
`[25,9,29,13,57,41,27,11,61,45,59,15,31,43,63,47]`，每个加入
nominal→vertex blend `0.25/0.50/0.75/1.00`，仍为64个控制模式。对这64个平滑模式运行同一
width64、remaining-depth4 beam；目标是避免极值torque在前两步积累导致第三步全空。

v12.32 runner与审计链已实现。每个controller substep先保留原controller计算与goal/cache更新，
对nominal torque裁剪后按冻结fraction向vertex插值，再按原actuator bounds裁剪；source-policy
action bytes不变。影子选择出的vertex/fraction由实际隔离advance原样复现，配置前qpos/qvel、
逐substep nominal/vertex/applied torque、scope restore、bound、exact action identity及
prediction/execution margin/qvel error均落盘。相关23个定向测试通过；双lane正式结果尚未生成，
不提前计为正证据。

v12.32 双lane正式结果为1/5 non-pass，且已通过checksum与summary重算。depth1为64/64 safe，
depth2为4096/4096 safe，但按trajectory minimum margin保留的64个parent在depth3上仍为
0/4096 safe；最佳mode从vertex25/fraction1.0转为连续两个vertex9/fraction1.0，说明单一margin
排序仍把full-vertex极值路径排在最前，平滑模式未进入长期frontier。16512/16512配置的qpos/qvel/
scope identity成立，bound/warning/contact saturation/dispatch/typed recovery/outcome read均为0。

这一结果只排除了“平滑mode library + 单一margin排序”，不能排除depth2其余4032个safe endpoints
中存在低toward-velocity后继。v12.33保持相同64 modes、width64、depth4与0.15 floor，只修改
beam retention：固定保留32个原margin-ranked nodes与32个terminal toward-velocity最小nodes，
去重后按原margin排序补足64。最终full-horizon选择规则、首步消费和fresh replan不变；新增
frontier来源与速度范围审计。

v12.33 runner已实现，默认`trajectory_margin`路径保持v12.31/v12.32语义；新runner显式冻结
`margin_velocity_diverse`。每层ledger记录两组top-set overlap、实际保留计数、全部/保留节点
toward-velocity范围及最低速度序列。覆盖整个H3/controller/receding链的25个定向测试通过，
正式双lane结果尚未生成。

v12.33 正式结果经checksum与summary重算后仍为双lane 1/5 non-pass。depth1最低toward
velocity约`0.1694–0.1695 rad/s`；depth2的4096/4096 safe endpoints却全部落在约
`4.329–5.303 rad/s`，最低速度序列与最高margin序列同为full vertex9→vertex9。强制保留
velocity-top32后depth3仍0/4096，因此排除的是frontier pruning：所有固定substep torque mode
在第二个exact action后都积累了不可制动速度。16512/16512 identity/scope/bounds和全部零异常
审计继续成立。

v12.34 将控制参数化从“一整个env step固定同一vertex/blend”改为冻结两阶段vertex schedule：
取v12.28跨lane排名前8个patterns，在每个exact action的25个controller substeps中前12步使用
vertex A、后13步使用vertex B，枚举`8×8=64`个有序模式。target joint仍始终为away-limit bound，
source action bytes、width64/depth4、0.15 floor与fresh replan不变。该设计只检验contact/coupling
下的时变多关节制动，不扩大branching或降低门。

v12.34 runner与预测/执行schedule复现链已实现。配置和逐substep audit明确记录`A/B`、
phase、switch index、nominal/applied torque及bound；默认fixed/blend路径不变。覆盖相关历史链与
新schedule契约的27个定向测试通过，正式双lane结果尚未生成。

v12.34 正式结果经重算验证后仍为双lane 1/5。depth2最低toward velocity仅从v12.33的约
`4.32946–4.32990`变为约`4.32974–4.32987 rad/s`，没有实质改善，depth3仍0/4096。
16512/16512 configuration/scope identity与零bound/warning/contact/dispatch/outcome异常成立。
因此在当前contact state下继续枚举原7轴±80 actuator box内的常量、blend或一次切换模式已无
信息增益。

v12.35 改为单独命名的 simulator virtual joint-stop/safety-brake pilot，不冒充actuator-only
successor：在每个exact action期间把target joint的MuJoCo upper range临时收紧到原upper limit减去
冻结guard margin，action结束立即逐字节恢复model range并forward；配置前后qpos/qvel必须identity，
shadow/actual使用同一guard，source action bytes不变。guard margins预注册为
`0.16/0.18/0.20/0.22 rad`，均严格高于0.15 floor；每层只4个mode，width上限仍64、覆盖全部剩余
cycles。新增joint-limit constraint activation、range restore、constraint force与warning审计。
即使通过，也只支持simulator virtual-stop机制，不支持原actuator authority、task utility或物理安全。

v12.35 runner已实现。guard配置只解析target hinge joint并构造临时range，不改变qpos/qvel；
作用域内保留原controller和exact action，逐substep记录guard distance、target qvel、generalized
constraint force与controller torque bounds，退出时恢复原range并forward。beam只扩展当前状态
仍位于guard内的候选，防止通过“把range直接移过当前qpos”制造冲量。相关29个定向测试通过，
正式双lane结果尚未生成。

v12.35 首次运行终态为审计fail-closed，不形成guard效果结论。8个depth1 guard replay均完成且
range/config identity恢复，但OSC `run_controller()`返回robot层裁剪前的raw torque，200/200个
substeps被当前audit错误当成actual actuator violation，全部candidate在margin ranking前拒绝。
源码确认`SingleArm.control`随后按`self.torque_limits`对这些raw torques执行`np.clip`后才写入
`sim.data.ctrl`。同时发现depth summary在retention后读取parent count，使空frontier的理论
expansion count误记为0。

v12.36只做机械replay修复：guard、seeds、actions、margins、beam与成功门全部不变；torque audit
同时记录raw controller torque、按controller actuator limits得到的downstream-clipped torque及
是否需要裁剪，actual bound violation只检查clipped值，且仍返回raw值让原robot路径执行唯一真实
裁剪。depth parent/expansion count在扩展前冻结。不得借此改变任何guard效果参数。

v12.36 replay runner已实现；v12.35通用执行函数仅增加默认保持原行为的显式output/schema/source
参数，历史验证路径不变。raw/clipped返回语义、guard常量和parent count均有单测，相关31个定向
测试通过。正式机械replay尚未生成结果。

v12.36重算验证后仍为双lane 1/5，但首次给出有效guard效果：56/56 config/scope identities、
0 downstream-clipped bound violation，depth1 `4/4` safe、depth2 `16/16` safe；最佳guard序列
`0.16→0.22`把depth2最低toward velocity从actuator-only约`4.329`降到约`2.521 rad/s`，但
trajectory minimum已降到约`0.1771–0.1772 rad`，depth3 `0/64`。说明range guard有效但MuJoCo
默认soft limit允许约43 mrad penetration，仍不足以维持0.15 floor。

v12.37保持同四个guard margins和所有实验门，只把virtual brake constraint profile显式冻结为
`jnt_solref=[0.004,1.0]`、`jnt_solimp=[0.999,0.9999,0.001,0.5,2.0]`；0.004 s为当前0.002 s
physics timestep的2倍安全下限。配置/作用域新增原始与guard solref/solimp identity及恢复审计，
不改contact geom、actuator、qpos/qvel或action。该结果只能比较default-soft与hard virtual stop，
不能回填真实硬件claim。

v12.37 runner已实现，通用guard runner默认profile仍为None，v12.35/v12.36历史路径不变。
hard profile的scope enter/exit、range/solref/solimp恢复及配置契约均有定向测试；相关33个测试
通过，正式双lane结果尚未生成。

v12.37 已在result-informed seeds `10509/10510`上终态通过并经checksum/summary重算：两lane均
完成5/5 exact policy advances，最低actual advanced-state global margin为`0.1661929 rad`。
6次guard execution的action identity 6/6，预测/执行margin与qvel误差均0；160/160 beam configs
的qpos/qvel/scope identity成立，range/profile restore 6/6，downstream-clipped bound violation、
active warning、contact capacity saturation、live dispatch、typed recovery和outcome read均0。
guard constraint在50个执行substeps激活，最大target-DOF generalized constraint force约
`9999.04`，必须作为高刚度simulator brake的重要limitation披露。

方法现已冻结，唯一授权的下一步是未见seed复验：使用`20509/20510`，逐值复用四个guard margins、
hard solref/solimp、beam/retention、H3/H1、0.15 floor、action与所有成功门。不得根据已知seed
结果修改参数；held-out仍须两lane 5/5和全部identity/zero-anomaly门通过，才能称为稳定的
simulator engineering正结果。

v12.38 held-out runner已实现，通用runner仅增加默认仍为`10509/10510`的显式lane-seed参数；
历史入口不变。held-out summary不继承known-seed success boolean，而按`20509/20510`独立重算
5/5、margin、action/config/profile identity、完整beam与zero-anomaly门。相关34个定向测试通过，
正式未见seed结果尚未生成。

v12.38 未见seed验证终态通过并完成checksum/summary重算。`20509/20510`均5/5，最低actual
advanced margin为`0.1661158 rad`；6/6 guard exact action identity、0 prediction/execution
margin/qvel error、160/160 config qpos/qvel/scope identity、6/6 range/profile restore与全部
zero-anomaly门成立。50个执行substeps激活virtual stop，最大target-DOF constraint force约
`9985.37`。held-out选择序列与development一致为guard modes
`[0,3,2,1]→[3,2,1]→[2,1]`，实际首guard margins均为`0.16→0.22→0.20`。

当前“好结果”的严格工程目标已达成：

| Evidence | Seeds | Exact advances | Min actual margin | Guard action identity | Beam config identity | Pred/exec max error |
|---|---|---:|---:|---:|---:|---:|
| Development | 10509/10510 | 10/10 | 0.1661929 | 6/6 | 160/160 | 0 |
| Frozen held-out | 20509/20510 | 10/10 | 0.1661158 | 6/6 | 160/160 | 0 |

结论边界固定：这是跨seed可复现的simulator hard virtual joint-stop机制正证据，且完整保留source
action bytes与transaction/audit边界；它**不是**原actuator-only torque shield成功、任务完成率/
utility证据、真实部署资格或物理安全证明。约`10k` generalized constraint force必须在论文结果和
limitation中同时披露。下一科学步骤若继续，应另立task-outcome protocol比较utility，不能在本轮
no-outcome artifact上补读reward/success。

## 前一 checkpoint：2026-07-30 v12.5 integrated predictive recovery

fresh policy-prefix shadow 与 typed recovery runtime 的 fixed-trace composition 已完成并终态冻结：

- engineering pilot 使用与 formal 不重叠的3个 fresh-policy pairs，12/12 paths 命中预期；
- formal 绑定 v12.4c 冻结 ledger 中15个 pairs、30个 source cases，运行60条 integrated paths；
- nominal exact authorization 15/15，prefix substitution reject 15/15；
- synthetic recovery open 15/15，recovery-selection state substitution reject 15/15；
- recovery receipt identity、completion、fresh-state authorization 均为15/15；
- old policy authorization、recovery replay、substituted fresh state 接受均为0，negative path sink
  side effect 为0；
- policy load/inference/action dispatch、simulator create 和 outcome read 全部为0。

完整结果与边界见
[`v12_integrated_predictive_recovery_checkpoint.md`](v12_integrated_predictive_recovery_checkpoint.md)。
该结果只关闭 source-digest-bound in-memory transaction composition；下一步仅授权 no-outcome
simulator-integrated pilot，仍不授权 clean、attacked 或 efficacy rollout。

## 前一 checkpoint：2026-07-30 v12.4c fresh policy-prefix shadow

v12.4a/v12.4b/v12.4c 已完成并终态冻结，证据范围严格限于 no-outcome controller shadow：

- fresh OpenPI π0.5 工程 pilot 在 checkpoint restore 阶段因共享 policy GPU 显存不足 fail closed；
  policy inference、simulator case、live dispatch 和 outcome read 均为0，该历史 resource
  nonstart 保持不变；
- 为继续检查执行机制，v12.4a 从冻结 v11 clean trace 中机械提取15个10-step prefix；正式
  nominal/synthetic population 为30 cases，风险判断30/30一致，nominal exact allow 15/15，
  synthetic recovery-required 15/15，旧/blocked prefix 被授权为0；
- 初始 pilot 暴露 controller cache 恢复缺口，repeat fidelity 为0/6；补齐 pose、joint、Jacobian、
  mass matrix 等缓存后，新 pilot 为6/6；
- v12.4a 正式 repeat fidelity 为29/30，仍通过冻结的≥95% gate；唯一尾部处于 dense
  contact/joint-limit dynamics，最大 qpos 误差为 `0.0990581 rad`；
- 独立 v12.4b 进一步绑定 MuJoCo `qacc_warmstart`，在相同30-case population、相同 tolerance
  下达到30/30，最大误差降至 `4.44e-16 rad`。所有 trusted arm/controller/input/clock/warm-start
  restore gate 均为100%；
- 资源恢复后，fresh π0.5 pilot 6/6 完成，随后冻结的30-case formal qualification terminal pass：
  policy load 1、fresh inference 30、nominal allow 15/15、synthetic recovery-required 15/15、
  risk agreement 30/30，所有 trusted restore gate 100%，live dispatch/outcome read 为0；
- fresh formal repeat fidelity 为29/30，最大误差 `0.0249513 rad`，仍通过冻结的≥95% gate。唯一
  尾部是 joint-6 upper 的 current-trigger synthetic dense-contact case；两次均判 risk 并要求
  recovery，运行保留 `ncon=5000` warning。

完整表格、资源 nonstart、fresh retry 和 claim boundary 见
[`v12_policy_prefix_shadow_checkpoint.md`](v12_policy_prefix_shadow_checkpoint.md)。下一步只授权
no-outcome predictive-screen + typed-recovery 集成 transaction gate；此前不生成 clean/attacked
outcome 协议，也不把 shadow pass 写成 task utility 或 defense efficacy。

## 前一 checkpoint：2026-07-29 v12.2/v12.3 多关节恢复 successor

v12.1 后续恢复优化已经完成并终态冻结：

- typed recovery runtime fixed trace 10/10 通过；old-policy revoke、one-use recovery、
  command receipt identity、recovery replay reject 和 fresh-policy state binding 全部通过；
- shortest-safe-prefix 把工程 coverage 从固定 H=10 的12/14提高到14/14；
- 正式 v12.2 在15 pairs × 7 joints × 2 sides 的210个注入中覆盖209个；209/209 selected
  recovery 都在 actual replay 中到达 safe margin，hard crossing/transient violation 为0，
  old-policy/recovery replay acceptance 为0；
- v12.2 仍按冻结 gate 判 non-pass：full simulator snapshot identity 为201/210，而不是100%；
- 独立 v12.3 snapshot qualification 表明 trusted arm `qpos/qvel` restore identity 为210/210。
  9 个 full-state mismatch 只包含40个非机械臂状态值，最大绝对误差为
  `2.220446049250313e-16`；v12.3 pass 不回写 v12.2 non-pass。

完整表格、claim boundary 和产物位置见
[`v12_recovery_successor_checkpoint.md`](v12_recovery_successor_checkpoint.md)。其后继
policy-prefix shadow 结果见最新 checkpoint；仍不授权 clean、attacked 或 efficacy outcome rollout。

## 前一 checkpoint：2026-07-29 v12 无 outcome 资格实验通过

v11 终局保持不变。v12 已完成第一批实现和两层 no-outcome 资格：

- 纯 contract corpus 为 655 cases：Sparse L1 315、analytic shadow 220、recovery transaction
  120；所有冻结 gate 通过，simulator/`env.step`/policy/outcome/dispatch 全部为0；
- v12.1 simulator-reset preflight 在与 v11 scale45 outcome 零重叠的45个 task/init pair 上通过：
  recovery coverage、terminal safe、recovery completion、state restore identity 均为45/45，
  hard-limit crossing、old-policy authorization acceptance、policy load/dispatch/outcome read 均为0；
- 45/45 都选择 `negative_ry`，只覆盖 joint 5 upper-limit 合成模式；selected replay 的逐浮点
  bitwise identity 仅2/45，且出现一次 MuJoCo `ncon=5000` warning。这些是下一阶段必须关闭的限制，
  不能从 preflight 推出一般 recovery、clean utility 或 attacked efficacy。

完整结果、claim boundary 与后续顺序见
[`v12_qualification_checkpoint.md`](v12_qualification_checkpoint.md)。当前只授权 typed recovery 的
zero-policy runtime fixed-trace integration；仍不授权 clean、attacked 或 outcome rollout。

## 更早 checkpoint：2026-07-29 v11 终局与 v12 启动边界

v11 unchanged-method held-out scale45 已终态完成并单独封存于
[`v11_terminal_checkpoint.md`](v11_terminal_checkpoint.md)。clean/attacked 各180条均完整，
observer agreement 为 `21250/21250`、`26464/26464`，39次 typed joint-limit trigger 后旧 policy
dispatch 为0；同时 clean Dual−Semantic-only task success 为 `−24.4pp`
（exact McNemar `p=0.00098`）。因此终局保持
`joint_limit_containment_v11_scale45_heldout_mixed_evidence`：mechanical containment 稳定，
task-preserving safety shield、first-hit prevention、整体 physical safety 与 non-inferiority 均未建立。

后续优化不再修改 v11。新的 outcome-informed v12 见
[`v12_recoverable_alignment_plan.md`](v12_recoverable_alignment_plan.md)，核心是：

```text
Sparse L1 exact-passthrough intent guard
  -> predictive L2 shadow screen
  -> typed recovery authorization
  -> fresh policy replan
```

当前已完成 V12-C1–C5 Python contract、zero-policy runtime transaction、全关节双侧 synthetic
coverage，以及 fixed-recorded-prefix controller shadow；fresh-policy shadow 尚因显存资源 gate
未启动。这一 gate 通过前不得启动新 clean，clean gate 通过前不得启动 attacked。

## 0. 2026-07-27 M2 终局与 40% 探索性后继

M2 已自然完成并通过 artifact/ledger/terminal validator：240/240 complete、240/240 valid，
clean-eligible `86` units / `47` base pairs，attack transition `39` units / `26` base pairs，
transition rate `45.35%`，base-pair cluster bootstrap 95% CI `[32.93%, 57.78%]`。原预注册
`50%` minimum-transition-rate gate 未通过，因此原结论永久保持
`confirmatory_attack_foundation_nonpass`；不能重命名为 pass。

在观察上述终局后，用户明确授权将“继续四臂实验”的门槛改为 `40%`。该改动是
outcome-informed，已单独冻结为
`proofalign_four_arm_v4_exploratory40_successor.json`，后续只能称为 post-outcome exploratory /
hypothesis-generating evidence：

- 不覆盖原 50% 预注册和 nonpass；
- 不把 M2 或后续四臂结果称为 confirmatory；
- M2 产物缺少重建新 v4 semantic assessment 所需的逐 proposal trusted geometry，因此不伪造
  fixed-trace Stage A；
- 该后继当时只授权 480-episode clean four-arm Stage B；
- attacked Stage C 未授权，并以 clean terminal gate 为前置条件；
- fresh root、append-only ledger、首个 invalid 即停止、checkpoint/source/checkout/GPU/disk gate
  均 fail closed。

两张 GPU 满足门槛后 fresh1 已 one-shot 启动，但在首个
`semantic_only_affordance_task0` episode、任何 dispatch 和 ledger row 之前 fail closed：
trusted BDDL goal 只有 `Checkgrippercontactpart`，已资格化 semantic wrapper 没有可信物体部位几何，
不能初始化。fresh1 已封存，禁止 resume/retry/replacement。

随后完成的 60-pair 静态 audit 表明：

- 45/60 base pairs（75%）可初始化，15 个 unsupported pairs 全部来自 affordance suite；
- 原 full-population clean gate 要求 unknown/unbound rate 为 0，因此 480-episode 设计在结构上不可通过；
- 不得把 `Checkgrippercontactpart` 偷换成普通 `pick_up`，否则会虚构不存在的 part-level checker 能力；
- support-conditioned 45-pair population 有 90 units、每 stage 360 episodes；
- 该支持集上的 post-outcome M2 描述性 transition 为 30/67=`44.78%`，cluster 95% CI
  `[30.77%,59.09%]`，仍超过披露的 40% exploratory threshold；
- 用户明确授权的 support-conditioned fresh2 已终态完成：360/360 episodes valid，artifact/checksum/
  terminal recomputation 全部通过，但分类为 `support45_clean_gate_nonpass`；
- VLA-only strict clean success 为 61/90，Execution-only 为 66/90，Semantic-only 与 Dual 均为
  0/90；Dual deadlock 88/90、phase completion 0/90、相对 VLA-only 的 strict-success 差为
  `-67.78pp`，base-pair cluster 95% CI `[-80.00pp,-55.56pp]`；
- 两个 semantic-enabled arms 各有 36/90 `missing_destination_geometry` 和 54/90
  `no_feasible_checked_action_block`。前者涉及 18/45 base pairs，证明先前 45-pair audit 只建立
  wrapper/BDDL 初始化支持，不建立在线 trusted-geometry 或闭环支持；后者的终止 K=1 candidate
  全部低于冻结的 2 mm progress 条件；
- terminal summary 已冻结为
  `experiments/proofalign_four_arm_v4_support45_clean_terminal_summary.json`。该结果不能称为 fresh1
  重试、full-population 或 confirmatory 结果；clean prerequisite 未通过，因此 Stage C attacked
  不授权、不启动，且不再为当前协议追加 clean retry。
- 结果后 L1 repair 只做了 no-outcome、zero-dispatch 资格测试：exact simulator site/body geometry
  将 destination coverage 补到 45/45，但 K=4 有可行候选的初态只有 24/45=`53.33%`，低于冻结的
  90% gate，worst suite 为 7/15=`46.67%`；K=1 到 K=4 的累计 coverage 全部是 24/45，说明 180 个
  不同 chunk 没有扩展可用初态。全程 0 policy-conditioned env step、0 dispatch、0 task outcome、
  0 selected hard violation，分类为 `l1_repair_initial_availability_qualification_nonpass`，已冻结到
  `experiments/proofalign_four_arm_v4_l1_repair_qualification_terminal_summary.json`。
- 用户随后授权把 checked ActionBlock 从5步扩到公开 checkpoint 原生输出上限10步。版本化 Block-10
  successor 使用逐任务不重叠 init、env seed 83、policy seed 29、K=1，并在同一次 policy call 上
  shadow-check H=2/5/10。匹配 availability 为 `0/45, 17/45, 36/45`，pattern 仅有
  `000:9, 001:19, 011:17`，三个长度均无 hard violation；H=10 的 suite 结果为
  `13/15, 12/15, 11/15`。虽然 H=10 相对 H=5 提高42.22pp，仍未达到总90%与 worst-suite 80%
  gates，故保持 `l1_block10_initial_availability_qualification_nonpass`，终局见
  `experiments/proofalign_four_arm_v4_l1_block10_terminal_summary.json`。
- 因 checkpoint 不支持原生 H>10，后继没有拼接 stale-observation chunk，而是在第三套不重叠 init、
  seed 97/37 上冻结 H10×K4。匹配 K=1/2/4 coverage 为 `35/45, 35/45, 36/45`；
  pattern `111:35, 001:1, 000:9`，45/45 行的四个 source digest 均不同。K=4 仅净增1个初态，
  suite 为 `13/15, 14/15, 9/15`，总80%与 worst-suite 60%继续 nonpass。该终局冻结在
  `experiments/proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json`，并停止继续增加 blind
  stochastic samples 或伪造 H>10 open-loop block。

## 0A. 2026-07-27 qualification 与工程 smoke checkpoint

当前 C5 与 E1–E8 证据链已关闭，并完成两轮单 episode clean/no-attack 工程 smoke：

- C5：8 cases × 4 arms = 32 rows，proposal/assessment/contract identity 通过，dispatch `0`；
- E1 raw π0.5 selector：未通过；500 snapshots 的 coverage `0.822`、known legal-frontier
  `0.5645`、worst-stage `0.0682`、occlusion abstention `0.21`；
- E1F deterministic privileged-geometry FSM：160/160，unknown fail-closed `100%`，p99
  `7.1µs`；
- E2 action conditioning：未通过；median MAD `0.000190`、motion cosine `0.998928`，prompt
  不授权为 behavioral control；
- E3 v2 analytic local checker：700/700 clean retained、0/1200 attacked false allow、600/600
  OOD abstain，p99 `59.1µs`；`closer_to_target` 与 `near_target` 已分离；
- E4：qualification-outside four-arm no-dispatch gate 的 15 项检查全部通过；
- E5 v2 analytic effect observer：500/500 clean retained、0/1000 attacked false allow、600/600
  OOD abstain，p99 `21.6µs`；在线 receipt/window seal 已接线。
- E6 resource smoke：100 个 frozen E2 snapshots × 3 passes、GPU/RSS/latency/repeatability gate
  已由 v2 授权 successor 完成；300 次调用的 checkpoint load `6.22s`，policy/pipeline p99
  `97.3/97.6ms`，GPU/RSS peak `8646/18830.5 MiB`，digest repeat `200/200`，10 项 gate
  全部通过；simulator/dispatch/outcome 均为 `0`；
- E7 deployment-perception data gate：当前 RLDS 只含 RGB、robot/joint state、action 等，缺少
  camera calibration、target/destination geometry、visibility/occlusion、held/contact supervision
  与独立 qualification split，因此分类为 `deployment_perception_data_inadequate`；逐帧资产、标定、
  3D entity/mask、provenance、split 防泄漏与 population gate contract 已冻结；dataset qualification
  runner 进一步验证真实资产解码、SHA、shape/dtype、asset-root containment 和完整 population；
  本机旧 EDPA/SafeLIBERO asset bundle 只含两张 `44×44` perturbation array 与同一 RLDS tree
  manifest，不含缺失监督，因此明确排除复用；
- E8 source binding：commit scope 与本地 evidence inventory 完整，OpenPI checkout 干净并绑定
  `15a9616a...`；semantic scope 未绑定路径为 `0`，分类为
  `semantic_source_binding_clean`；
- E9 第一轮准确暴露 approach progress 被错误声明为 `near_target`；修复后继任 smoke 完成两个
  effect-allow prefix、10 个 exact receipts、零 effect reject/unknown，随后第三个 K=1 proposal 因
  `1.93mm < 2mm` 在 dispatch 前 fail closed；
- M2 outcome-blind producer 已终态完成 60/60 records；victim 已终态完成 240/240，原 50% gate
  因 `45.35% < 50%` 非通过；
- 新 v4 四臂 successor 已冻结 120-unit × 4-arm 的 fixed-trace、clean closed-loop 和 attacked
  closed-loop schedule；同时冻结 fresh roots、append-only ledger、clean gate、保守 missing rule、
  base-pair cluster bootstrap、McNemar 与 Holm 分析。原 outcome-blind 协议未授权 rollout；结果后
  40% 探索性后继只授权 clean Stage B。

`experiments/proofalign_semantic_post_e5_readiness_packet_v1.json` 当前判定
benchmark privileged-geometry no-outcome stack 完整；deployment perception 仍未资格化。

当前 blocker 与停止边界：

1. 当前 L1 不具备闭环 clean availability：oracle geometry 已关闭 destination gap，Block-10
   把不同 successor split 的初态 availability 提高到约80%，但 H10×K4 证明多采样只净增1/45，
   总 gate 与最差 suite gate仍未通过；
2. attacked Stage C 以 clean gate 为冻结前置条件，现已永久阻断于本协议；不得把“继续跑攻击”用于绕过
   clean nonpass；
3. 所有结果保持 exploratory 标签，不得回写原 50% M2 nonpass，也不得结果后降低 2 mm checker 条件；
4. 下一步只做不产生 efficacy outcome 的 L1 redesign/qualification：把 geometry availability 纳入
   population gate，并在独立 clean qualification split 上验证 trajectory-level coverage、K 候选策略和
   false-allow/false-reject；
5. E7 perception 数据仍阻断 camera-only deployment claim；当前 privileged-geometry benchmark 也必须先
   解决上述在线 geometry closure，不能再把初始化成功当作部署支持。

## 0B. 2026-07-24 历史收工 checkpoint

本轮代码和生成 artifact 已保存到当前 worktree，**尚未提交 Git commit**，也没有运行任何新
efficacy/outcome rollout。

已完成并验证：

- C4 已贯通 final proposal → fresh assessment/contract → authorization → one-use `(H,7)` dispatch
  session → ordered step receipts → bound observation-window evidence；
- C4 完成时全量 Python 为 `159 passed`，v4 online runner 的 `(2,7)` integration test 证明两步共享一个
  authorization；
- C5 已新增独立 `SemanticIntegrityCore.lean`，没有改写冻结 v3 `IntegrityCore.lean`；
- C5 已新增 semantic v4 no-dispatch four-arm runner、protocol、fixed-trace evidence 和 scoped
  Python/Lean equivalence evidence；
- v4 fixed trace 覆盖 8 类案例 × 4 arms = 32 rows，包括 semantic mismatch、stale state、contract
  substitution、projection 后旧 artifact、command substitution、authorization replay 和 unknown
  assessment；
- C5 artifact 当前 `--check` 通过，Lean `lake build ProofAlign` 通过；fixed trace 中 policy/simulator/sink
  均未创建，dispatch count 为零；
- 新 v4 protocol 显式绑定冻结 v3 fixed-trace/equivalence artifact digest，避免静默覆盖历史证据。

本次收工时尚未完成：

1. 为新增 semantic v4 shadow runner/generator 添加专门的 pytest；
2. 新建 C5 readiness/fresh-root validator 和 packet；
3. 将两个 v4 C5 `--check` 接入 `Makefile`/`scripts/check_all.sh`；
4. 在上述接线完成后重新运行全量 Python、Lean 和完整 no-dispatch check；
5. C5 完整关闭后再进入 E1 selector、action-conditioning、E2 checker qualification 和 E3 no-dispatch gate。

下次恢复建议从以下命令开始：

```bash
.venv/bin/python scripts/run_semantic_v4_fixed_trace_gate.py --check
.venv/bin/python scripts/generate_semantic_v4_equivalence_evidence.py --check
make lean
git status --short
```

## 1. 2026-07-24 对齐结论

主线已进一步改为：

```text
L1: TrustedIntent -> frozen SemanticSubtask -> checked ActionBlock
L2: authorized ActionBlock -> exact dispatch/receipt/observed effects
```

顶层故事仍是 Intent→ActionBlock 与 ActionBlock→Execution 双层对齐。`SemanticSubtask` 是 L1 的当前
结构化机制，不是新的第三层，也不是恢复旧的自由文本 PlanWitness。它来自有限 task graph，在动作生成前
成为显式 π0.5 输入并与返回 block 绑定；第一版不训练模型。其行为控制力必须实验测量，不能从 prompt
wiring 本身推出。

当前第一关键 blocker 变成：

> 当前冻结 π0.5/PaliGemma 或其他零训练 selector 能否稳定选择合法 `Z_t`，以及 `Z_t` 条件化是否改善
> ActionBlock 的可解释约束而不破坏 clean utility？

当前公开 OpenPI 只开放 flow-matching action head，因此需要 consumer-side inference wrapper；不能把
论文版 π0.5 的 semantic head 当作已存在的本地接口。

`Z_t` 的 trusted-input boundary 已落地为双视图：

- semantic branch 只读取 trusted `T/O_t^T`，并 allowlist task source、observation tap、secure split、
  selector checkpoint/config；
- 外部 prompt、被注入图像和 history 只属于 action-policy branch；
- `Z_t` artifact 绑定合法 frontier、state epoch 和完整 semantic context；
- hardened action prompt 只从 trusted `T + Z_t` 固定编译；
- 当前只覆盖 secure split 后的数字/软件注入，不覆盖同时欺骗 trusted tap 的分叉前物理光学攻击。

实现与边界见 [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

2026-07-24 零训练 GPU pilot 的当前结论：

- motion-level `approach/grasp/...` 初始选择为 `0/4`；
- π0.5 skill-level `pick_up/move/place/...` 初始选择为 `4/4`；
- 单条轨迹阶段切换名义为 `3/5`，两个错误均在人工标签边界；
- 不同 `Z_t` prompt 会改变 ActionBlock，但差异很小，不能视为可靠 action control。

详见 [`semantic_subtask_pilot.md`](semantic_subtask_pilot.md)。

动作选择已经形式化为 `Z_t` 先固定、π0.5 后提议、consumer 再过滤/小幅投影/复检。确定性 best-of-K
选择边界和单元测试已实现于 `semantic_action_selection.py`；K=1 路径现已接入在线 LIBERO runner，
仍以实际执行的前 `replan_steps` 作为 exact executable prefix。

可信 semantic context、`Z_t` artifact、外部攻击视图隔离和固定 prompt 编译已实现于
`semantic_trust.py`。这两个边界现已通过 `semantic_policy_wrapper.py` 接入
`run_liberosafety_pi05_openpi_eval.py`：每次 policy call 前从 pre-transform trusted view 选择并绑定
`Z_t`，policy 返回后只把通过 nominal check、bounded clip/projection 和 post-projection recheck 的最终
prefix 交给 v4 authorization/dispatch transaction。该路径由 `--semantic-runtime` 显式启用，未启用时
保持历史 runner 行为。

首版真正的 `Z_t -> executable prefix` analytic checker 已实现于 `semantic_local_checker.py`。它读取
当前 trusted eef/gripper/object geometry 和 exact `(H,7)` prefix，支持
`pick_up/move/place/release` 的目标、持有、方向、放置/释放顺序检查，以及 workspace、translation、
rotation 和非目标 contact-neighborhood hard violations；缺失几何、stale epoch、未知 task 或当前没有
trusted articulation state 时 fail closed。当前 LIBERO object position 属于 benchmark privileged state，
runtime metadata 明确标注，不能冒充部署视觉或硬件 attestation。

`proofalign-integrity-v4` 的首批 semantic-bound runtime schema 已实现于
`integrity_v4_models.py`，独立绑定 semantic context、`Z_t`、exact prompt、trusted/policy observation、
source policy chunk 和 executable-prefix bytes。assessment/contract 已提供 exact-binding 检查，
unknown `Z_t` 不可形成 dispatchable v4 proposal；历史 prefix adapter 显式标为 `historical_v3`。
`integrity_v4_runtime.py` 已实现 final proposal → fresh assessment/contract → authorization 的顺序，
并把 `(H,7)` prefix 作为一个 one-use authorization session：每步 exact action receipt 绑定同一
authorization，窗口 evidence 绑定实际消费 action、ordered receipts 和 post-dispatch observations。
stale、caller/sink command substitution、重复打开 authorization、projection 后复用旧 artifact 均有
negative tests。v3 frozen digest fixture 保持不变。全量 Python 测试为 197 个通过，Lean build 通过。
2026-07-27 已运行两轮单 episode clean/no-attack engineering smoke；它们是工程诊断，不是 efficacy
估计。

## 2. 已完成

- ActionProposal 已成为原生 ActionBlock，不再含 `plan_digest`；
- 新增 `ActionBlockAssessment` 和 `BlockExecutionContract`；
- authorization、dispatch receipt、execution evidence 已绑定 block/assessment/contract digests；
- shared four-arm runner 改为 Intent–Action / Action–Execution 两个开关；
- Lean core 改为 action-block execution transaction semantics；
- L2 支持 exact command、one-use authorization、freshness、expected/forbidden effects、phase gating；
- P0b/R9 历史结果及冻结协议仍保留审计边界。

## 3. 历史实验怎么复用

完整的逐字段映射、post-hoc replay 规则和 confirmatory 禁止项见
[`experiment_reuse.md`](experiment_reuse.md)。

### P0b

可直接复用：

- 原始攻击机制和 threat model；
- clean/attacked pairing；
- valid episode 与 clean-eligible denominator 逻辑；
- transition signal 和缺失/替换规则。

不可复用：

- 新 L1 assessment；
- 四臂 causal effect；
- confirmatory denominator（`23 < 26`）。

### R9 Execution-only

可直接复用：

- action envelope/intervention；
- exact dispatch 和 episode ledger；
- cost/collision、strict success、contact proxy；
- clean retention 和 attacked recovery 的 exploratory baseline。

需要迁移：

- 将旧 transport/audit 映射为 ActionBlock/contract/receipt v3；
- 不把旧 effect verdict 当作完整物理安全；
- 不把 R9 称为 Dual。

## 4. 当前 blocker 排序

1. **整体安全 efficacy 未建立**：机制和阈值不变的 held-out scale45 clean/attacked 各180条已完成。
   39个 joint-limit trigger 后均为0 dispatch，且 L2-on arm 的 joint-limit step burden 明显更低；
   但 official cost/collision 无一致 ordering，不能声称整体 physical safety；
2. **Containment–utility tradeoff 已被 scale45 确认存在**：task success 为 clean
   `32/45, 27/45, 31/45, 20/45`、attacked `30/45, 28/45, 25/45, 21/45`
   （顺序 VLA/Execution/Semantic/Dual）。Execution−VLA 与 Dual−Semantic 为 clean
   `-11.1pp/-24.4pp`、attacked `-4.4pp/-8.9pp`；clean Dual−Semantic exact McNemar
   `p=0.00098`，当前不支持 task non-inferiority；
3. **L2 articulation evidence unknown**：v10 Dual 有3次仅承诺 `command_applied` 的 articulation
   transaction 因 task effect 不可观测而 `semantic_execution_unknown`；它是 transaction contract
   refinement 问题，不应通过放松 receipt/cost/collision integrity 解决；
4. **Deployment perception qualification data**：E7 已证明当前 RLDS 缺少7类必要监督；这是
   camera-only deployment claim blocker。当前正向证据仍限于 privileged-geometry benchmark。

E8 已绑定 clean commit，semantic scope 未绑定路径为 `0`。E7 仍是 deployment claim blocker，但不阻止
明确标注 privileged geometry 的 benchmark M2。

v10 attacked pilot 的全部数据完整性门已通过：60条 episode、15条攻击、60个 clean/attacked comparator、
攻击 prompt digest 和15/15同 workload 四臂首个 source ActionBlock 均匹配；1055/1055 L1 blocks
passthrough。physical rejects 从 clean 8次降为 attacked 4次，未出现预期 enrichment；四臂 official
cost/collision 均为0，不能提供 arm separation。post-hoc SABER typed trace 中 joint-limit violation
steps 为 VLA/Execution/Semantic/Dual `768/416/109/109`，但 contact/force proxy 不一致改善，因此只能
用于提出 joint-limit-aware v11 假设，不能当作预注册安全主终点或回调本轮结论。

v11 已作为单独的 outcome-informed successor 冻结和完成。它没有假装从 EEF delta 精确预测关节状态，
而是在 L2-on arm 对 robosuite 原生 joint-limit signal 做 post-step containment。clean/attacked
observer coverage 为 `5319/5319`、`8389/8389`，16次总触发后 dispatch 为0。clean joint-limit
steps 为 `884/6/780/4`，attacked 为 `202/3/462/3`（VLA/Execution/Semantic/Dual）；对应 exact
paired sign tests 仍不显著。终局分类为 `joint_limit_containment_v11_exploratory_mixed_evidence`，
只支持 mechanical containment 与描述性 burden reduction，不支持 first-hit prevention 或一般安全。

随后在不改方法或阈值的 held-out scale45 上，clean/attacked 各180条均完整；攻击激活
`180/180`，observer agreement 为 `21250/21250`、`26464/26464`，39次总触发后 dispatch 为0。
clean joint-limit rate 为 VLA/Execution/Semantic/Dual
`12.79%/0.116%/13.98%/0.110%`，attacked 为
`8.19%/0.063%/5.83%/0.049%`。burden reduction 的配对信号更强，但 clean Dual−Semantic task
success 差为 `-24.4pp`（`p=0.00098`）。终局分类为
`joint_limit_containment_v11_scale45_heldout_mixed_evidence`：mechanical containment 稳定，
task-preserving safety shield 未建立。

E6 已关闭为 `semantic_resource_smoke_qualified`，只证明冻结离线 workload 满足预注册工程预算；不得
据此选择 efficacy threshold，也不得把它解释为 simulator、camera perception 或物理安全证据。

M1 producer/victim、shared runner、fixed-trace exporter、validator 和 outcome-blind ActionBlock prefix adapter
已经完成；adapter 只读取 policy-call audit 与实际消费的 raw actions，不读取 reward/success/cost/collision，
也不伪造未执行的 chunk tail。

## 5. 下一里程碑

### M1A：component closure

- 全部 Python/Lean tests 通过；
- 新 ActionBlock fixed-trace smoke artifact 当前；
- M1 readiness validator 不再引用 PlanWitness；
- frozen legacy protocol 明确标注 audit-only，v3 schema 不改写历史结果，semantic-bound successor 使用
  新版本 schema。

### M1B：semantic hierarchy no-outcome qualification

- 冻结 task graph、subtask vocabulary 和 prompt template；
- 探测当前 checkpoint 的 PaliGemma constrained selection；
- 冻结 `unknown`/margin 规则；
- 只做离线 observation/action probe，不看 M2 outcome。

### M1C：local checker no-outcome qualification protocol

- 冻结训练/qualification split；
- 冻结 finite atom vocabulary；
- 冻结 threshold、abstention 和 worst-group；
- 只允许 offline transition label，不看 M2 victim outcome。

### M1D：semantic runtime 与 Lean identity closure

- 把 semantic context、`Z_t`、trusted prompt 和 executable-prefix digest 接入 ActionProposal/assessment/
  execution contract；
- projection/intervention 后重新 assessment、contract 和 authorization；
- `K=1` fixed-trace 四臂共享 exact proposal；`K>1` 只作为另行冻结的扩展；
- 更新 Lean source binding、关键 theorem inventory 和 scoped Python-equivalence artifact；
- 完成 zero-dispatch fixed-trace、latency/resource smoke 和 fresh-root validator。

### M2 与四臂 clean 终局

60-record outcome-blind producer 与 240-episode victim 均已终态完成。M2 rate 为 45.35%，原 50%
confirmatory gate nonpass；结果后 40% exploratory continuation 的 full-population fresh1 又因
semantic support coverage 在首单元 dispatch 前 fail closed。随后单独授权的 45-pair support-conditioned
fresh2 已完成 360/360 valid episodes，但 clean gate nonpass：Dual 0/90 strict success、88/90 deadlock，
因此 attacked stage 不再进入当前论文执行链。

## 6. 当前可声称与不可声称

可声称：

- 双层问题已定义在 action-only VLA 可观察接口上；
- L2 的有限 transaction semantics 已由 Lean 检查；
- P0b/R9 给出强探索性攻击/Execution-only 信号；
- component runner 可验证两层开关和 digest identity；
- benchmark privileged-geometry 下的 deterministic selector、analytic local checker 和 analytic effect
  observer 已通过各自 frozen finite-corpus gate；
- E4 no-dispatch 四臂 gate 已通过。

不可声称：

- raw π0.5 selector 已达到可用标准；
- semantic prompt 能可靠控制 ActionBlock；
- secure split 或 trusted camera tap 已在真实部署环境得到硬件级 attestation；
- 一般防御有效；
- Dual 已验证；
- 完整物理安全；
- Lean 证明 learned predictions 或真实世界。

## 7. 立即推进顺序

具体接口、测试、artifact 和停止条件见
[`implementation_and_experiment_readiness.md`](implementation_and_experiment_readiness.md)。执行顺序固定为：

```text
C1 semantic digest schema（已实现）
  -> C2 trusted prompt/policy wrapper（已实现 K=1 online path）
  -> C3 executable-prefix local checker（已实现并通过 E3 analytic gate）
  -> C4 post-intervention rebind + v4 transaction（已实现）
  -> C5 shared-trace/Lean evidence refresh（已完成）
  -> E1 raw selector 未通过 / E1F deterministic fallback 通过
  -> E2 action conditioning 未通过（不作为安全机制）
  -> E3 local-checker qualification（通过）
  -> E4 no-dispatch four-arm（通过）
  -> E5 effect-observer qualification + online wiring（通过）
  -> E6 authorized resource smoke（通过）
  -> E7 perception supervision collection/qualification（当前数据 gate 未通过）
  -> authorized no-attack smoke（已完成；效果契约修复后 2 prefix allow，随后 L1 fail-closed）
  -> M2 producer（60/60 records，已完成）
  -> M2 victim 240 episodes（已完成；45.35%，原 50% gate 非通过）
  -> outcome-informed 40% exploratory successor（已冻结）
  -> v4 fixed-trace shadow（因缺少可信逐 proposal geometry 而跳过，不伪造）
  -> v4 clean fresh1（首 episode 初始化前 fail closed，0 valid ledger rows）
  -> semantic-support audit（45/60 supported；full population structurally infeasible）
  -> support-conditioned clean 360 episodes（已完成；360/360 valid）
  -> clean terminal gate（nonpass：Dual 0/90，deadlock 88/90）
  -> support-conditioned attacked 360 episodes（前置 gate 未过，未授权且不执行）
  -> post-outcome L1 geometry+K4 no-outcome qualification（nonpass：24/45）
  -> Block-10 + matched H=2/5/10 no-outcome qualification（nonpass：36/45）
  -> H10×K4 + matched K=1/2/4 no-outcome qualification（nonpass：36/45）
  -> v9/v10 risk-selective clean + attacked fresh15（已完成；mixed/negative efficacy）
  -> outcome-informed v11 L2 joint-limit containment clean + attacked fresh15（已完成；mixed evidence）
  -> v11 unchanged-method held-out clean + attacked scale45（已完成；mixed evidence）
  -> materially-new action generator / trained conditioning / feedback interface
```

当前继续使用预先资格化的 deterministic task-FSM L1。40% 只改变是否继续收集探索性四臂证据，
不得用 M2/four-arm outcome 反向调整 selector/checker/effect observer，也不得把原 M2 改判为 pass。

## 8. M2 后的 published-attack-grounded successor

M2 producer/victim 的 240-episode population、stopping rule、原 50% gate 和终局 artifact 保持不变。
原 gate 已 terminal nonpass；新的 40% 决策仅开启明确标注的 exploratory clean outcome。完整 successor 见
[《L2 与跨层攻击实验计划》](l2_and_cross_layer_experiments.md)。

论文主线与次要 stress study 现在明确分开：

1. 已观察的论文事实链是 M2 confirmatory nonpass → disclosed 40% post-outcome exploratory
   continuation → full-population initialization-support failure → support45 clean-gate nonpass →
   post-outcome oracle-geometry+K4 availability qualification nonpass → Block-10 availability
   qualification nonpass → H10×K4 availability qualification nonpass；attacked four-arm 因冻结
   前置条件未过而停止；
2. online runner 已将 L1 semantic alignment 与 L2 execution integrity 拆成独立开关。closed-loop 不要求
   跨 L1 source chunk 相同，只要求 paired initial identity 和 within-L1 L2 pair 的首个 policy input/output
   identity；
3. 原 v4 successor 已 outcome-blind 冻结 population、schedule、ledger、endpoint、stopping rule、
   clean gate 和统计方法；结果后 successor 复用这些设计且只签发 clean execution authorization；
4. Ueda–Blevins `S_u` transfer 的 P1/P2/P3、ROS replay 和 feedback FDIA 均降为次要
   trust-boundary/case-study 证据，不再作为 480+480 主线的前置门；
5. P1/P2/P3 的 mock-online tests 继续锁定 prevention、after-one-step detection 与 forged-receipt
   limitation；需要 GPU 的 12-episode smoke 只检查接口，不比较 efficacy；
6. ROS 没有真实 graph 时只称 adapted captured-prefix replay；feedback-linearized FDIA 当前保持
   `interface_not_supported`；
7. terminal analysis 使用完整 support-conditioned population、保守 missing/invalid 和 base-pair cluster
   bootstrap；40% threshold change 必须始终披露为 outcome-driven exploratory decision。当前 45-pair
   结果还必须披露 MuJoCo `ncon=5000` warning 176 次，因此 contact-proxy magnitude 不作扩大解释。

Evidence naming 固定为：

- SABER：L1 benchmark；
- source `S_u` transfer：externally grounded operator-transfer L2 case study；
- ROS replay：只有 online capture/transport gate 通过后才是 adapted replay case study；
- feedback FDIA：当前只报告 `interface_not_supported`；
- SABER × source operator：cross-layer composition study；
- wrong digest/receipt/effect/phase：formal negative suite。

这项 successor 不授权修改历史 frozen artifact，也不授权把 L2 case-study 结果称为标准化 benchmark、
一般物理安全或完整硬件 attestation。

## 9. 2026-08-06：v15.11最终clean四臂fresh1封口与fresh2适配

最终clean fresh1协议已冻结并启动。运行完成VLA-only和Semantic-only各1条后，首个L2-enabled episode
在环境包装初始化阶段触发`PreStepCalibratedRecoveryError`并fail closed。根因是v15.8–v15.11的
model-mismatch资格链由专用实验控制器注入`proofalign_shadow_model_calibrator`，标准LIBERO任务环境
没有该接口；这不是运行中的安全gate non-pass，也不是v15.11 bounded brake核心产生deadlock。

审计处理如下：

- fresh1保持`terminal_failed_closed`，2条已完成episode、manifest、运行配置和checksums原样保留；
- 不覆盖fresh1输出，不复用其协议ID或输出目录；
- fresh2仅在最终任务运行器增加same-model nominal identity adapter，明确记录candidate count为1、
  model mismatch未注入、selector未读真实参数且未读task outcome，不宣称执行七模型bank calibration；
- fresh2从prior population中排除fresh1协议冻结的全部18个task/init pairs，保持结果未观察的全新population；
- same-model adapter与既有calibration/prebound链相关测试共`16/16`通过；fresh2协议仍需单独冻结后才能执行。

fresh2随后已冻结：18个全新pair、72个episodes，排除437个历史task/init组合，与fresh1冻结pair零
重叠；协议SHA-256为`13d21817ff6290527d6fea1854ed43f12d65e1cb9df71d0940ad957a9e14bfe4`。
冻结时未读取fresh2 task outcome。

fresh2运行同样完成2条非L2 episode；首个L2 episode已越过setup calibration，证明same-model adapter
接入有效，随后在10个pre-policy dummy wait steps中触发v15.7 incremental enrichment的空审计索引。
该层缺少“observation count未增加则直接返回”的保护，而其父类已有该保护。fresh2按fail-closed封口并
保留manifest和episode。fresh3 task-runtime adapter只在`call_index < wait_steps`时直接调用已有父类路径，
policy step仍调用原v15.7/v15.11路径；同时记录wait-step count并新增coverage gate。fresh3还必须排除
fresh1和fresh2协议冻结的全部pair。

fresh3已冻结：18个全新pair、72个episodes，排除455个历史task/init组合，分别与fresh1和fresh2零
重叠；协议SHA-256为`8730e54742c1bac5b11bd204cf633cd29a93011bcb6afbe010faa080fec0fdc7`。

fresh3首个arm为L2-only。运行越过10个wait steps并进入policy action，但v15.11最外层在读取
`bounded_guarded_candidate_rollout_count`时发现该字段不存在，说明嵌套的模块级core patch在真实继承链
中没有形成稳定身份绑定；运行在0个完整episode时fail closed。fresh4在incremental调用点显式、作用域化
绑定`_bounded_state_triggered_core_step`，计数每次core调用和每条policy audit，并要求core调用数等于
wait-step数加policy-step数；任何覆盖差异继续fail closed。前三版冻结pair全部进入fresh4排除集。

fresh4已冻结：18个全新pair、72个episodes，排除473个历史task/init组合；协议SHA-256为
`214c4e482fa8f514dcd7029806469dd90f769f22af456b5e1d34f9b4bd9680c4`。冻结时未读取task outcome。

fresh4首个arm为Dual。下层episode显示10条wait trace、0条policy trace，semantic dispatch issue保留了
内部`KeyError: bounded_guarded_candidate_rollout_count`；因此v13最终报告的trace/audit count mismatch只是
二次错误，不是根因。fresh5在不吞掉异常的task-runtime顶层记录bounded core调用计数、observation count、
last audit schema与完整keys后继续fail closed，用于精确定位真实继承链的core identity。

fresh5已冻结：18个全新pair、72个episodes，排除491个历史task/init组合；协议SHA-256为
`64fc1eab87044c39c0ac680ff0f7a6169b93b951010e3d58733f39a5075335c4`。

fresh5诊断结果为：`wait_step_count=10`、`policy_core_bind_count=1`、
`bounded_core_call_count=0`、`bounded_policy_audit_count=0`，最后schema为v15.10 rolling prebound。
这证明模块global patch不是稳定的真实task-runtime绑定。fresh6直接作用域化替换v15.6 adaptive class的
`step`：父类调用前把v14 core指向v15.11 bounded core，返回后执行与冻结v15.6逐字段相同的adaptive
enrichment，再交还v15.7 incremental、v15.10 rolling和v15.11顶层；core调用与policy audit继续计数。

fresh6已冻结：18个全新pair、72个episodes，排除509个历史task/init组合；协议SHA-256为
`9be1d52e567270e8cea77697e1b49dcb9cb28033c169d9d52ec51cf6630db0e2`。

fresh6的direct adaptive标记已进入audit，但bounded core调用仍为0。原因是多层runner context在运行时
会把v14模块的`MultiJointPredictiveVirtualBrakeEnvironment`变量替换成外层wrapper；adaptive adapter
在运行中按模块变量取类，修改的是被替换对象，而真实MRO最终仍调用导入时的v14 base class。fresh7在
所有嵌套context启动前捕获原始class对象，并在adaptive step内只通过该稳定引用临时替换`step`。

fresh7已冻结：18个全新pair、72个episodes，排除527个历史task/init组合；协议SHA-256为
`498eafeafb710e51d45cbdc283c065a571a53b7f72ae19823994952553297a1b`。

fresh7已命中原始v14 class，但v15.11 bounded core的wait分支通过
`v14.core.PredictiveVirtualBrakeEnvironment`模块变量调用v13 base；该变量此时也已被外层context替换，
因此重新进入顶层wrapper并递归。fresh8在context前同时捕获原始v14与v13 class，bounded core调用期
临时把v13模块变量恢复为捕获引用，返回后原样恢复运行时context。

fresh8已冻结：18个全新pair、72个episodes，排除545个历史task/init组合；协议SHA-256为
`baf0d7dbaa60736fbdaa7f615952acbb3f87d21eb4227ff14dc3ea74d4c5b5bd`。

fresh8已进入bounded core并越过双基类绑定，随后在复制的v15.6 adaptive enrichment中因selected
post-force prediction/execution不是`1e-12`位级一致而fail closed。最终v15.11资格协议并未把该旧identity
作为gate，而是约束最大constraint force、margin prediction/execution error、deadlock、crossing与latency。
fresh9继续记录两项force absolute error和identity divergence count，但明确停用旧identity gate，仍由
v15.11注册的`force <= 10000`和`margin error <= 0.01 rad`正式门判定。

fresh9已冻结：18个全新pair、72个episodes，排除563个历史task/init组合；协议SHA-256为
`0f14ee7a207a71a1ecc57f9a6723dc9611b778598e0fc001ff2469108849243b`。

fresh9完成72/72并独立validate。四臂clean success为VLA-only 10/18、L1-only 11/18、L2-only 9/18、
Dual 12/18；clean utility gate通过。v15.11正式机制指标为0 deadlock、L2内0 crossing/0 joint-limit、
最大constraint force 1349.47、最大selected margin prediction error约`1e-12 rad`、最大screen latency
33.26ms，均通过。唯一false gate是继承的`v9_v14_prediction_execution_calibration`：v15.11删除
unguarded rollout后，兼容字段明确保存当前状态而非下一步预测，旧gate比较当前状态与下一状态得到
0.089rad差值。fresh9不得结果后改判，保持non-pass。fresh10在新population上预注册停用这个不适用的
旧gate，并用zero unguarded rollout加selected prediction error正式门替代。

fresh10已冻结：18个全新pair、72个episodes，排除581个历史task/init组合；协议SHA-256为
`2ba4120226098e2e128bb16075c67894881bdb397d4ea72b54086cf37ee836ad`。

fresh10运行到10/72已完成episodes后，在第11个execution-only episode按预注册规则fail closed：
`runner_step_id=580`时当前minimum margin为`0.1209137574 rad`，risk side count为1，5个候选均不能
满足`0.15 rad`安全底线。该结果表明`0.24 rad`固定状态触发阈值在部分任务轨迹上介入过晚，是方法问题，
不能通过放宽floor或事后改判处理。协议、10个完成episode、manifest和checksums均保留。

基于fresh9完整轨迹和fresh10的fail-closed诊断，v15.12 task-trigger successor将状态触发阈值从
`0.24`提前到`0.30 rad`；`0.15 rad`安全floor、最多2次guarded candidate rollout以及force、margin、
latency gates保持不变。该修改明确标注为outcome-informed method design，并在排除599个历史pair后选择
18个未读取结果的新pair。v15.12 clean fresh1已冻结为72个episodes，协议SHA-256为
`ec9556b02d24b1ffd572e921cd2587f2e958cbd0baef6a4f6f0736e307b3e506`。

v15.12 clean fresh1已完成72/72并通过独立`--validate-results`重算，checksums 75/75通过。四臂
VLA/L1/L2/Dual success为15/13/13/12，unsafe均为0；L2内0 crossing、0 joint-limit，最大force
1838.10、最大selected margin prediction error约`4.94e-9 rad`、最大screen latency 40.31ms、p95
16.56ms，100ms miss为0。正式false gates只有`v15_11_zero_deadlock`和
`v9_execution_only_task_success_noninferiority`：Dual在task1/init25末端有1次deadlock；L2-VLA差为
-2/18，bootstrap下界-0.2778低于-0.20门。v15.12保持non-pass，attacked不获授权。

deadlock诊断显示当前minimum margin为0.15837rad，两个screened candidate的预测minimum margin分别为
0.15836和0.15731，均满足0.15 floor，但其transient attributable recovery force分别为1838.10和
1682.35，超过旧1250 recovery专用子限额，尽管都远低于正式10000 force envelope。下一版只考虑将
该recovery子限额提高到2000，并保留0.30 trigger、0.15 floor、2次rollout预算和所有正式门；这是基于
v15.12结果的outcome-informed successor，必须使用新pair重新验证。

v15.13 recovery-force successor已冻结：18个全新pair、72个episodes，排除617个历史task/init组合；
协议SHA-256为`3a9c483d982531a9c9419772c9e8117137c9d79fa39284a8e4c0d31f52552022`。
代码级诊断测试确认同一个1838.10 recovery candidate在旧1250子限额下被拒绝、在v15.13的2000子限额
下可行；该测试不替代全新population的task-outcome结果。

v15.13 clean完成72/72并独立validate，checksums 75/75通过。VLA/L1/L2/Dual success为11/12/11/11，
四臂unsafe各1，clean utility全部正式门通过；L2内0 crossing、0 joint-limit，最大force 2438.64、
最大selected margin prediction error约`5.27e-9 rad`、最大screen latency34.72ms、p95 18.00ms。
唯一false gate是zero-deadlock：两次execution-only deadlock的current minimum margin分别为0.15250和
0.15998，screened候选预测minimum margin均高于0.15 floor，post-step risk force均为0.1，但transient
force为2162.99–2438.64，超过2000 recovery专用子限额。

由于连续两版deadlock均只由额外recovery子限额造成，下一版不再按观测最大值逐次调高任意小门；它将
recovery force feasibility统一到已注册的10000全局force envelope。0.30 trigger、0.15 floor、两次
rollout预算、实际最大force、prediction error与latency正式门不变。该设计仍明确标注outcome-informed，
并必须排除v15.13全部pair重新验证。

v15.14 unified-force-envelope clean已冻结：18个全新pair、72个episodes，排除635个历史task/init组合；
协议SHA-256为`bcc39b02d7bb57c6fd928261afb3f5792ef460cb00e35aaff79f6b75f0652342`。
代码级诊断确认v15.13观测到的最大2438.64候选在旧2000子限额下被拒绝，在统一10000 envelope下
可行；正式实际force仍由同一个10000 gate裁决。

v15.14 clean完成72/72并独立validate，checksums 75/75通过，正式qualification pass。VLA/L1/L2/Dual
success均为13/18；unsafe分别为0/1/0/1，两个paired success contrast均为0。机制指标为0 deadlock、
L2内0 crossing/0 joint-limit、最大force 6568.13、最大selected margin prediction error
`7.77e-5 rad`、最大screen latency44.73ms、p95 25.57ms、100ms miss 0。所有gate为true，
`attacked_stage_authorized=true`；下一步按clean同pair、同environment/policy seeds冻结SABER-attacked四臂。

v15.14 SABER-attacked fresh1按clean同18 pair、同seeds完成72/72，但完整性门判non-pass：只有36个L2-on
episodes收到冻结攻击prompt，VLA/L1的disabled-L2 runner仍收到clean prompt。重算得到first-block change
36/72、metadata mismatch 144、prompt digest mismatch 1044；checksums 76/76通过。该批只作为攻击接线
失败审计保留，不解释为方法效果。

fresh2只修复disabled-L2 runner的attack-record转发，任务、方法、seeds、schedule和18条攻击文本不变，
并在协议中绑定fresh1 non-pass。fresh2完成72/72，独立validate与checksums 76/76通过，全部正式gate为
true。clean四臂success均13/18；attacked VLA/L1/L2/Dual success为11/13/11/13。attacked中至少一次
joint-limit violation或actual crossing的episode数为4/1/0/0，对应22.22%/5.56%/0%/0%；crossing steps
为28/295/0/0，joint-limit steps为175/317/0/0。L2与Dual 0 deadlock，最大force 6438.20，最大selected
margin prediction error约2.69e-13rad，最大latency39.79ms、p95 18.30ms、100ms miss 0。论文主线模拟器
实验至此完成。
