# 当前进展与执行计划

## 最新 checkpoint：2026-07-30 v12.6 simulator-integrated recovery

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
