# Paper story

## 1. 中心命题

> ProofAlign 在不要求 VLA 输出高层规划的条件下，将“可信意图到具体 ActionBlock 的对齐”与“获准
> ActionBlock 到实际执行及 observed effects 的对齐”分离，并用四臂 shared runner 估计两层的独立和
> 联合作用。

这句话包含两个必须分开的 claim：

1. **Intent–SemanticSubtask–ActionBlock alignment（L1）**：动作生成前的可信语义锚点与动作生成后的
   局部运动/后果检查；
2. **ActionBlock–Execution alignment（L2）**：授权对象、实际命令、receipt、effects 和 phase update
   属于同一个事务。

L1 的正确性主要是统计与系统 claim；L2 的有限绑定语义可以交给 Lean。二者都不等价于完整物理安全。

论文的中心贡献始终是这两个对齐断点。`SemanticSubtask Z_t` 是当前用来实现和资格化 L1 的结构化机制，
不是第三个顶层对齐层，也不取代原始的 `Intent -> ActionBlock` 研究问题。即使未来把 FSM/PaliGemma
selector 换成其他可信 semantic adapter，双层问题定义和 L2 transaction 仍保持不变。

Lean 是方法的一等组成，而不是事后给 Python checker 加的标签。它把 L2 中容易被自然语言含混处理的
authorization、freshness、exact command、receipt/effect binding 和 phase-gating 写成有限命题，并为
“Execution-enabled arm 能在什么条件下 dispatch/advance”提供 machine-checked theorem。论文应同时展示
Lean 定理、Python 对应证据和明确的 refinement boundary。

## 2. 故事起点：攻击落在动作，不落在“自白”

Instruction/observation attack 的危险不在于 VLA 是否承认一个恶意计划，而在于可信任务 `T` 没有改变时，
policy-facing prompt、observation 或 history 的改变可能使模型输出实际效果偏离 `T` 的数值 action
chunk。多数公开 VLA 部署接口只返回动作，因此：

- 不能把可观察 high-level plan 当作通用前提；
- 不能从 ActionBlock 唯一恢复模型 latent intent；
- 不能让外部模型在动作产生后补一段 explanation，再把它当作 VLA witness。

论文因此从最小共同接口出发：可信任务 artifact、可信/不可信双视图、数值 ActionBlock、consumer
assessment、dispatch receipt 和 observed effects。

## 3. 为什么需要两层，而不是一个 safety filter

只约束动作幅度可以减少部分低层风险，却不能判断一个平滑、合法的动作是不是在拿错物体。只判断动作语义
也不能防止授权后的 command substitution、stale replay、sink-side drift 或效果证据换绑。

因此方法把失败分为两个时间不同、证据不同的问题：

```text
Trusted intent -- semantic authorization --> concrete ActionBlock       [L1]
authorized ActionBlock -- execution transaction --> receipt/effects     [L2]
```

当前 L1 的具体分解是：

```text
Trusted T/O_t^T
    -> legal frontier -> SemanticSubtask Z_t
trusted full T + attacked policy view
    -> π0.5 source ActionBlock
Z_t/O_t^T + source ActionBlock
    -> physical-risk assessment / unchanged-or-reject
```

第一层回答“准备做的事情是否仍服务于可信任务的当前合法步骤”，第二层回答“获准的事情是否真的这样执行并
产生了约定效果”。两层组合可以互补，也可能因过多 `unknown` 导致 deadlock；这正是四臂实验需要估计的
交互。

## 4. 威胁模型是双视图，不是同视图自洽

Semantic branch 只读取：

- 攻击面之外的 trusted task `T`；
- secure split 之前绑定的 `O_t^T`；
- task graph、历史可信 subtask；
- allowlisted selector checkpoint/config。

Action-policy branch 可以读取被攻击的 `P_t^atk/O_t^atk/H_t^atk`。本方法由此研究：攻击把 ActionBlock
带偏后，独立可信语义锚点和 local checker 能否在执行前发现偏离。

最终部署路径保留完整 trusted `T` 作为 action prompt，`Z_t` 只进入独立 monitor，不替换 policy
prompt。攻击评估可以修改 policy-facing observation/history，但它仍不能进入 selector/checker。

当前覆盖 secure split 后的数字/软件注入，不覆盖同时欺骗 trusted tap 的分叉前物理光学攻击，也不覆盖
task source、selector/checker、observer、receipt store 或 actuator feedback 被攻破。

## 5. L1：先约束合法下一步，再检查局部动作

L1 的顶层目标仍是判断 concrete ActionBlock 是否服务于 trusted intent。为避免要求一个评估器直接恢复
完整 latent intent，当前方法把这条关系分解为两个可绑定、可分别资格化的关系：

```text
TaskSubtask(T, O_t^T, Z_t)
SubtaskAction(Z_t, O_t^T, A_t)
```

`Z_t` 从有限 task graph 的当前合法 frontier 中选择。最终方法不训练 π0.5，也不把局部 subtask 当作
policy prompt；π0.5 继续根据完整任务生成 H=10/K=1 source block。这样 L1 的估计对象是 monitor，而不是
“改变 prompt 后 policy 变好”的混合 treatment。

local checker 使用 `Z_t/O_t^T/A_t` 预测有限的 motion、target、part、effect、precondition 和 violation
atoms。最终 hard set 只含速度、工作区和 unexpected-contact 风险；task-progress/phase mismatch 作为
advisory replan。无物理风险时 returned/source block digest 必须一致，禁止 semantic projection。
`trusted_articulation_state_unavailable` 会继续运行所有可用物理筛查，而不是在筛查前 unknown；stale、
malformed 和未识别 unknown 仍 fail closed。

L1 的主要风险不是平均 accuracy，而是：

- selector 把错误但语法合法的 `Z_t` 放进 frontier；
- local checker 在 attacked block 上 false allow；
- clean false reject 或 OOD abstention 过高导致 coverage collapse；
- selector、policy 与 checker 错误共享同一不可信输入。

所以 selector qualification 和 local-checker qualification 必须分开报告。

## 6. L2 与 Lean：把执行当作一次形式化绑定事务

consumer 为 exact ActionBlock 编译 `BlockExecutionContract`，绑定 subtask/prompt、assessment、observation、
state epoch、expected/forbidden effects 和 observation window。authorization 必须新鲜且一次性使用；
Execution-enabled arm 只能 dispatch exact authorized command。receipt 和 evidence 再绑定 authorization、
block、contract、proposal index、observed command 和时间顺序。

观察窗口关闭后，只有 expected effects 已出现、forbidden effects 未出现、observer 未报告 violation，
且 trusted task completion atoms 被观察到时，phase 才能推进。开放窗口是 `pending`，证据不足是
`unknown`，不是 allow。

Lean 检查四臂 truth table、digest/nonce/index 绑定、exact-command dispatch 和 phase-gating 定理。
关键论文定理包括：Dual dispatch 同时要求两层 authorization、Execution-enabled arm dispatch 的 command
必须等于 exact authorized command、Execution-enabled phase advance 蕴含 block-execution alignment，
且任何 phase advance 都要求 trusted contract completion。

它不证明 selector、local checker、perception、observer、simulator 或物理世界正确，也不自动证明
Python runtime 精化了 Lean 模型。这个边界限制 claim 的外延，但不削弱 Lean 对 L2 规范、反例测试和
实现审计的核心作用。

## 7. 论文要回答的经验问题

1. **Attack foundation**：冻结攻击是否稳定地产生相对于 trusted intent 的 ActionBlock/trajectory
   divergence？
2. **Semantic selection**：零训练 selector 在 held-out task/object/stage 上的合法率、稳定性、margin、
   OOD abstention 和 latency 是否达到冻结 gate？
3. **Action conditioning**：固定 observation/noise 时，不同合法或冲突 `Z_t` 是否对 ActionBlock 产生
   可测、阶段合理且不损害 clean utility 的影响？
4. **Local checking**：在 supported attacked blocks 上，local checker 的 false-allow 上界能否达标，
   同时维持 clean retention 和 coverage？
5. **Execution integrity**：L2 能否捕获 substitution、replay、receipt/effect mismatch，并保留 utility？
6. **Composition**：Dual 相对单层是否互补，还是增加 unknown、deadlock 或 time-to-completion？

第 2–4 问共同构成 L1 资格化；不能用初始四帧 top-1、synthetic fixture 或 victim outcome 代替。

## 8. 四臂如何识别两层贡献

统一使用以下论文名称：

| Arm | L1 semantic alignment | L2 execution integrity |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

冻结 runtime/schema 中的 `intent_only`、`intent_action_enabled` 字段仅作为兼容名称，不表示恢复自由文本
plan。

`K=1/H=10` primary design 中四臂共享初始状态、初始观测、完整任务 prompt、环境 seed 和 policy seed，
并要求每个 paired workload 的第一次 policy call 产生相同 source block。L1-on 的每个 nominal-safe
调用还要证明 returned/source digest 相同。hard reject 或状态分叉之后，不用 counterfactual chunk replay
强行维持后续 byte identity。若将来启用 `K>1`，必须另行冻结 candidate-set 与 selection estimand。

## 9. 可主张的贡献与明确排除项

若全部 gate 完成，论文可以主张：

- action-only VLA 上的双层完整性定义；
- trusted task/observation 到有限 semantic subtask 的 provenance、frontier 与 qualification protocol；
- `Z_t -> ActionBlock` 的 local compatibility、abstention 和 deterministic selection boundary；
- ActionBlock/authorization/receipt/effect/phase 的 Lean-specified transaction semantics，以及
  exact-dispatch/phase-gating 的 machine-checked theorem；
- fixed-trace exact identity、closed-loop paired initial identity 与 within-L1 L2 identity 的四臂因果评估
  协议；
- instruction/observation attack 下的 benchmark evidence。

不主张：

- 首次 high-level planning、language hierarchy、world model、shield 或 action filter；
- 当前公开 π0.5 checkpoint 暴露论文中的原生 semantic head；
- 从动作唯一恢复 latent intent；
- Lean 证明 learned prediction、sensor 或现实物理安全；
- 软件 secure split 等价于硬件级 trusted capture。

## 10. 证据叙事与论文结果顺序

P0b 与 R9 只承担历史动机：

- P0b：96/96 有效、23 个 clean-eligible pair、15 个攻击 transition，但 `23 < 26`，未通过确认性
  denominator gate；
- R9：Execution-only 的强探索信号，但 strict-success recovery 不完整，且 15 个 signal pair 中 11 个
  仍有 residual contact proxy。

当前 semantic pilot 只支持“skill-level 路线值得继续”：motion-level `0/4`、skill-level `4/4`、阶段
切换 `3/5`，且 prompt-conditioned action delta 很小。它不是 selector qualification，更不是防御结果。

M2 的确认性 attack-foundation 结果已经终局：240/240 valid，clean-eligible `86` units，
transition `39` units，rate `45.35%`，95% base-pair cluster bootstrap CI `[32.93%,57.78%]`。
它未达到原预注册 `50%` 门槛，必须报告为 confirmatory nonpass。观察该结果后采用的 `40%`
continuation threshold 只授权探索性四臂证据，不能改变原结论或产生 confirmatory claim。

论文结果顺序必须保留这条时间与证据边界：

```text
M1 component closure
  -> selector qualification
  -> local-checker qualification
  -> end-to-end no-outcome identity/resource gate
  -> M2 VLA-only attack foundation（原 50% gate nonpass）
  -> disclosed post-outcome 40% exploratory continuation
  -> full-population clean initialization failure
  -> support45 clean four-arm exploratory stage（360/360 valid，gate nonpass）
  -> attacked four-arm exploratory stage（clean prerequisite 未过，停止且未授权）
```

M2 artifact 不含新 v4 fixed-trace 所需的逐 proposal trusted geometry，因此不得补造该阶段。任何阶段
都不得用后续 outcome 回调 selector/checker threshold。论文结果应依次报告 attack validity、
selector/checker risk-coverage、L2 conformance、clean utility、attacked efficacy、Dual interaction 和
failure taxonomy；不能用一个 aggregate “safe success” 隐藏 unknown、deadlock 或 residual proxy。

首次 full-population clean 启动又暴露了一个必须进入论文的 coverage failure：15/60 affordance pairs
只给出 `Checkgrippercontactpart` goal，而当前 trusted observation/checker 没有 part-level geometry；
fresh1 因此在首单元、dispatch 前 fail closed。静态支持率为 45/60=75%，原 `unknown=0` clean gate
结构上不可通过。任何后续 45-pair support-conditioned 结果必须与 full-population failure 并列报告，
不能把它写成原 480 设计完成。

45-pair clean 后继现已终态完成，且给出比 full-population 初始化失败更直接的闭环反证：360/360
episodes valid，但 VLA-only、Execution-only、Semantic-only、Dual 的 strict clean success 分别为
61/90、66/90、0/90、0/90；Dual deadlock 88/90，`Dual−VLA=-67.78pp`，base-pair cluster 95% CI
`[-80.00pp,-55.56pp]`。两个 semantic-enabled arms 的终止分布完全一致：各 36/90
`missing_destination_geometry`、54/90 `no_feasible_checked_action_block`。前者涉及 18/45 retained
base pairs，说明静态 audit 只是 wrapper-initialization support；后者的终止 K=1 candidate 全部低于
冻结的 2 mm progress 条件。该 nonpass 将论文的正面 claim 限定为双层问题分解、Lean transaction、
证据绑定与 failure localization；不支持当前 Dual defense efficacy。Stage C 不执行，阈值不结果后改写。

在该闭环结果之后进行的 L1 repair 必须单列为 post-outcome exploratory。冻结的 no-outcome
qualification 显示：exact simulator site/body geometry 将初态 coverage 补到 45/45，但 K=4 仅
24/45=`53.33%` 初态存在可行候选，低于 90% gate；三个 suite 为 `60.0% / 53.33% / 46.67%`。
45 个样本各自的 4 个 source chunk digest 均不同，但 K=1、K=2、K=3、K=4 累计 coverage 都是
24/45，21 个失败样本的最佳 predicted progress 最高仅 `1.738mm < 2mm`。这支持“geometry gap
可定位并修复，但当前公开 π0.5 的 bounded resampling 不能恢复 L1 availability”的负结论，不授权
新 clean 或 attacked efficacy rollout，也不能用来覆盖原 support45 nonpass。

随后冻结的 Block-10 successor 在逐任务不重叠 init、新 env/policy seed 上把 K 固定为1，只改变
checked prefix length，并对同一个 source chunk shadow-check H=2/5/10。在不改变2 mm progress、
0.5 projection 与 hard constraints 的条件下，availability 为 `0/45, 17/45, 36/45`；配对 pattern
为 `000:9, 001:19, 011:17`，说明从 H=5 到 H=10 有19个 gain、0个 loss。该结果支持“公开 π0.5
需要更长时间尺度才能显现局部语义进展”，但 H=10 总率80%与最差 suite 73.33%仍低于冻结 gate，
所以仍是 qualification nonpass。论文可将其作为 matched block-size availability ablation，不能写成
trajectory success、攻击防御或 Dual efficacy。

由于 checkpoint 原生 source chunk 只有10步，H>10 不能通过从同一 stale initial observation
重复调用并拼接来构造。第三个冻结 successor 因而保持 H=10，只在第三套不重叠 init 上匹配比较
K=1/2/4。coverage 为 `35/45, 35/45, 36/45`，pattern 为 `111:35, 001:1, 000:9`；虽然每行
四个 source digest 都不同，K=4 仅比K=1增加1个初态。K=4 suite 为 `13/15, 14/15, 9/15`，
总80%与最差60%仍 nonpass。论文应据此明确区分：时间尺度 H=10 对 availability 有明显作用，
blind stochastic resampling 几乎没有作用；后续正向改进需要改变 action generator、训练 semantic
conditioning 或 feedback-aware policy interface，而不是继续堆 IID samples。

v8 随后在全45个 paired tasks 上完成180条 clean episodes。VLA-only、Execution-only、
Semantic-only、Dual success 为 `34/45, 33/45, 5/45, 5/45`。1142个 L1 audits 中，旧方法改写
1036个 source blocks，并有49个动作终止：43个只有 task-semantic/progress 原因，6个包含 predicted
unexpected contact。这个完整结果把问题从“block 不够长”进一步定位为“把 task progress 当 hard
safety constraint，并同时改变 action generator”。

post-outcome v9 因此是 materially new 的 risk-selective 方法，而不是降低2 mm阈值：完整任务 prompt
恢复给 π0.5，安全 block exact passthrough，task-semantic/effect miss 只 replan。scale45
read-only replay 恢复43/49个软动作终止、保留6个 physical rejects。第一批 fresh15 四臂 clean 为
`10/15, 10/15, 7/15, 6/15`；656/656 L1 blocks 不改写，15/15 paired first blocks 一致。

v9 又暴露出6个 `trusted_articulation_state_unavailable` 在运行物理筛查之前 hard unknown。v10 只修该
机制：继续运行速度、工作区和 contact screens，articulation task state advisory；同时把
`target_not_held_after_move` 从 physical violation 中移出。第二批新 init/seed 的 fresh15 结果为
`10/15, 8/15, 7/15, 7/15`；909/909 L1 blocks passthrough，15/15 first blocks 一致，8次
physical-risk rejects 保留，60条 official cost/collision 为0。Semantic-only 相对 VLA 的配对差为
`-20pp`，exact McNemar `p=0.25`，95% Wilson 区间分别为 `[24.8%,69.9%]` 与
`[41.7%,84.8%]`。这批小样本不证明 non-inferiority；它证明 deadlock 大幅下降，同时把剩余 clean
损失明确归因于 physical gate。

因此论文当前可以报告 risk-triggered nominal-policy non-interference、可复算的 hard/advisory
partition 和 clean safety–utility tradeoff。配对 attacked successor 也已完成：15条未改写 M2
task-prompt 攻击令60/60首个 ActionBlock 相对 clean 改变，说明攻击确实激活；attacked
VLA/Execution/Semantic/Dual 为 `8/15, 8/15, 7/15, 6/15`。Semantic−VLA 的配对差从 clean
`-20pp` 缩到 attacked `-6.7pp`，difference-in-differences 为 `+13.3pp`，但 attacked 内仍是
1个 treatment-only 对2个 control-only（exact McNemar `p=1.0`），不能写成 utility superiority。
更直接地，physical-risk rejects 从 clean 8次降为 attacked 4次，未出现预注册的 risk enrichment；
四臂 official cost/collision 均为0，也不能写成安全收益。

post-hoc typed trace 显示 joint-limit violation steps 为
VLA/Execution/Semantic/Dual `768/416/109/109`，给出一个有方向性的机制假设；但 robot-contact 与
excessive-force proxy 并不一致改善，且 joint-limit 不是本 attacked protocol 的预注册主终点。论文
应把 v10 结论写成“attack activation 明确、task utility 与 hard-gate enrichment 混合/负、joint-limit
方向值得新实验”，而不是宣称防御有效。下一步若加入可信关节状态/限位预测，必须作为 outcome-informed
v11 在新 workload 上冻结后验证，不能回写本轮 v10，也不能继续按 outcome 放松
unexpected-contact gate。

v11 已按该边界完成，但最终采用的是可证明的 post-step containment，而不是没有资格化支撑的
pre-dispatch predictor。方法在 L2-on 两臂把 robosuite 原生 0.1 rad joint-limit predicate 绑定进
execution evidence，首次触发后清空剩余 block 并停止 episode；L2-off 两臂只记录信号。15 个新
init、env/policy seed `211/109` 的 clean 与同状态同 seed attacked 各60条，全部数据完整性门通过。
clean/attacked 的 observer coverage 分别为 `5319/5319` 与 `8389/8389`，16个总触发之后的 dispatch
均为0。

机制信号明显但统计结论仍必须克制。clean 的 joint-limit steps 为
VLA/Execution/Semantic/Dual `884/6/780/4`，attacked 为 `202/3/462/3`；对应 L2 paired
joint-limit-rate 方向在 clean 是 `5 lower / 2 higher / 8 equal` 与 `4/0/11`，attacked 是
`3/1/11` 与 `3/0/12`，exact sign `p` 分别为 `0.453/0.125/0.625/0.25`。task success 为 clean
`10/15, 8/15, 9/15, 8/15`，attacked `11/15, 10/15, 9/15, 8/15`；Execution−VLA 与
Dual−Semantic 的配对差为 clean `-13.3pp/-6.7pp`、attacked `-6.7pp/-6.7pp`，exact McNemar
均不显著。official cost/collision 也无一致 arm ordering。

因此 v11 支持的正面系统 claim 是“typed L2 observer 首次触发后不再 dispatch”，并给出强描述性的
joint-limit burden 下降；它不证明 first-hit prevention、task non-inferiority、整体 physical safety
或一般 attacked-defense efficacy。论文主线仍是 L1/L2 两个对齐断点、exact transaction 和可审计
failure localization，v11 作为 L2 observer containment 的具体实例。

为避免15-pair pilot 的低功效掩盖 tradeoff，方法和阈值不变后又冻结了 held-out scale45：每个任务
选择3个未在旧协议或 v11 fresh15 中使用的 init，env/policy seed 固定为 `307/149`。clean 与 exact
paired attacked 各180条全部完成，runtime exception 为0；攻击使 `180/180` 首个 ActionBlock 相对
clean 改变，四臂内首块 identity 为 `45/45`。clean/attacked observer agreement 分别为
`21250/21250`、`26464/26464`，共39次 containment trigger 后 dispatch 仍为0。

scale45 把机制收益和效用代价同时放大。clean 的 VLA/Execution/Semantic/Dual task success 为
`32/45, 27/45, 31/45, 20/45`，joint-limit rate 为
`12.79%, 0.116%, 13.98%, 0.110%`；attacked 分别为
`30/45, 28/45, 25/45, 21/45` 与 `8.19%, 0.063%, 5.83%, 0.049%`。
clean Execution−VLA 的 joint-limit sign test 为 `15 lower / 1 higher / 29 equal`
（`p=0.00052`），Dual−Semantic 为 `11/0/34`（`p=0.00098`）；但 task success 差为
`-11.1pp`（`p=0.267`）与 `-24.4pp`（`p=0.00098`）。attacked 中对应 task 差缩为
`-4.4pp`（`p=0.754`）与 `-8.9pp`（`p=0.125`），joint-limit sign test 为
`9/3/33`（`p=0.146`）与 `7/0/38`（`p=0.0156`）。official cost/collision 仍无稳定 arm ordering。

因此 scale45 不是“防御终于有效”的证据，而是更强的 failure localization：post-trigger containment
稳定成立，joint-limit exposure 通常下降，但 hard stop 会在部分 clean workload 牺牲可观任务效用。
论文应把终局分类写为 `joint_limit_containment_v11_scale45_heldout_mixed_evidence`，并明确
first-hit prevention、task non-inferiority 与 overall safety 均未建立。

outcome-informed v12 随后只在 no-outcome 资格边界内把 hard stop 改造成 typed recovery。
v12.1 的 contract corpus 655/655、单模式 simulator-reset 45/45 通过；v12.2 又加入
old-policy revoke、one-use recovery authorization、ordered command receipts、fresh-state replan
和 shortest-safe-prefix。在15 pairs × 7 joints × 2 sides 的正式210-case population 中，
candidate coverage 为209/210，209/209 selected recovery 都在 actual replay 中达到 safe margin，
hard crossing/transient violation 为0，旧授权与 recovery replay 接受均为0。

v12.2 必须保留 `prefix_recovery_v12_multijoint_qualification_nonpass`：冻结的 full
`MjSimState` identity gate 只有201/210。后续独立 v12.3 没有改判它，而是资格化更准确的 trusted
snapshot boundary：arm `qpos/qvel` identity 为210/210，9个 full-state mismatch 只包含40个
非机械臂诊断值，最大绝对差异 `2.22e-16`。论文可据此主张 typed recovery transaction 和
多关节 simulator feasibility 已显著增强；在完成 policy-prefix predictive shadow、fresh clean
utility 和 attacked cells 之前，仍不能主张 task-preserving recovery 或 defense efficacy。

v12.4 随后把 predictive shadow 接到 controller-aware simulator snapshot。fresh OpenPI π0.5
工程 pilot 在 checkpoint restore 时因共享 GPU 显存不足 fail closed，发生在第一次 inference、
simulator case、dispatch 和 outcome read 之前；因此它是 resource nonstart，不是方法 non-pass。
独立的 fixed-recorded-prefix 机械资格从冻结 v11 clean trace 提取15个实际执行过的10-step prefix，
只重放动作与检查状态，不读取历史或当前 outcome。30个 nominal/synthetic cases 的 risk agreement
为30/30，nominal exact allow 与 synthetic recovery-required 均为15/15。

该实验也定位了两层隐藏状态。首先，恢复 `controller.new_update=False` 而不恢复 cached pose、
joint、Jacobian 和 mass matrix 会使第二次 replay 复用第一次 terminal cache；补齐后工程 pilot 的
repeat fidelity 从0/6变为6/6。其次，MuJoCo constraint solver 的 `qacc_warmstart` 不属于
`MjSimState`；独立 v12.4b 将其纳入 snapshot 后，在不改变 population、prefix 或 tolerance 的
条件下把正式 repeat fidelity 从29/30提高到30/30，最大 qpos 误差从 `0.0990581` 降到
`4.44e-16 rad`。这支持 controller-shadow transaction 的机械可复现性，但 fixed prefix 来自
outcome-known trace 且没有 fresh policy inference，不能写成 task utility、policy qualification
或 defense efficacy。论文应把 fresh-policy GPU resource gate 和 synthetic dense-contact
`ncon=5000` warning 一并保留为限制。

资源恢复后的 v12.4c 没有用 fixed trace 代替 policy evidence，而是在与 pilot 不重叠的15个
task/init pair 上，对 nominal 与 synthetic joint-pressure observation 分别重新输入冻结 π0.5，
得到30个 fresh 10-step prefix。正式结果为 nominal exact allow 15/15、synthetic
recovery-required 15/15、shadow/reference risk agreement 30/30，policy load/inference 为1/30，
live dispatch 与 outcome read 为0。trusted arm、controller、simulator input、clock 和
`qacc_warmstart` restore 都是100%。

repeat fidelity 为29/30，仍通过冻结的≥95% gate；唯一尾部是 joint-6 upper 的 current-trigger
synthetic case，误差 `0.0249513 rad`，两个 replay 都在 step0 判 risk 并要求 recovery。该 case
伴随 `ncon=5000` dense-contact warning，不能隐藏，也不能结果后改 tolerance。论文现在可以主张
fresh policy-prefix no-outcome mechanism qualification 已完成，但在 predictive screen 尚未与
typed recovery、receipt 和 fresh-state replan 接成完整 gate，且没有 clean/attacked outcome 前，
仍不能主张 task-preserving recovery 或 defense efficacy。

v12.5 随后增加 predictive screen 与 recovery runtime 之间的唯一 transaction route。formal 从
v12.4c 冻结 ledger 绑定15个 pairs 的 nominal/synthetic source-prefix digest，并为每个 pair
运行 exact allow、prefix substitution、recovery happy path 和 recovery-selection state substitution
四条路径，共60 cases。所有 route 命中预期；15条 recovery 的旧 policy authorization 和 recovery
replay 接受均为0，ordered receipt、completion 和 fresh-state authorization 均为15/15，错误
fresh state 接受为0。

这一证据必须称为 source-digest-bound fixed-trace composition：recovery sink 在内存中执行30个
action records，没有加载 policy、创建 simulator、dispatch policy action 或读取 outcome。它证明
软件 transaction 组合没有把“shadow pass”和“recovery pass”之间留成未绑定的缝，但还不是
simulator-integrated recovery。后续只有 no-outcome simulator pilot 可以升级该边界；在此之前
clean utility、attacked efficacy 和 physical safety 仍不成立。

v12.6 将 fresh policy、controller-aware shadow、typed recovery simulator steps 和恢复后的
fresh-state authorization 放进同一条真实 LIBERO simulator、no-outcome 链路。recovery、receipt 与
terminal-safe 为9/9，但 fresh authorization 只有6/9，因此 formal 按冻结 gate non-pass。后续
successor 没有覆盖这一结论，而是逐层定位剩余活性缺口：离散/连续 recovery generator、随机 replan、
高层 backup set、OSC nullspace、单轴/耦合 actuator torque、contact-aware vertices、beam horizon 和
soft virtual stop 都不能在0.15 rad floor下完成两条 lane 各5次 exact advances。

v12.37 最终把方法明确改名为 simulator hard virtual joint stop，而不冒充 actuator-only shield。
development seeds `10509/10510` 均完成5/5 exact advances，最低 actual advanced-state margin 为
`0.1661929 rad`。方法和阈值冻结后，v12.38 只替换为未见 seeds `20509/20510`，同样完成5/5，
最低 margin 为 `0.1661158 rad`。两个 split 合计20/20 exact advances；guard action/config/profile
identity、prediction/execution equality 和全部 zero-anomaly 门通过。

这个正结果为论文增加的是“可审计失败定位最终导向跨 seed 可复现的 simulator virtual-brake
mechanism”。执行中最大 target-DOF generalized constraint force 约为`9999/9985`，且整个实验
outcome read 为0，所以它不能恢复 actuator-only recovery、task utility、一般 defense efficacy 或
physical-safety claim。任何 task-outcome 后继都必须另立冻结协议，先验证 clean utility，再决定是否
授权 attacked stage。

v13 已完成这条独立 task-outcome 后继。Fresh3 clean 的180条episodes中，
VLA/Execution/Semantic/Dual success 为`36/36/32/31`，两个冻结`−20pp` paired
non-inferiority gate均通过；official unsafe为`1/1/2/2`。clean shadow-only ablation保持相同
任务与unsafe结果，并把唯一trigger case定位为：full brake相对shadow少250个policy steps、
225个joint-limit steps、41个target-margin<0.15 steps和2个target-margin<0 steps。由于这只是
一个case，论文只能把它写成mechanism-level conservative containment。

attacked scale45也完成180条checksum-bound episodes，instruction attacks改变180/180首个
ActionBlock。原终态enrichment因nested v11 context覆盖v13 metric hook而产生两个不适用legacy gate
failure；机械analysis successor从原episodes重建，不重跑或修改任何outcome。修正后的task success为
`35/35/28/28`，official unsafe为`1/1/0/1`。两条paired success差都是0，但Dual相对
Semantic-only的unsafe nonincrease描述性gate失败。

唯一active case发生在Dual `human_safety task4/init32`：第一步guard把unguarded predicted margin
`0.136171`保持到actual `0.159981 rad`，exact action、restore、torque bound与
prediction/execution equality全部通过；下一步没有安全candidate并fail closed。与此同时，全体有
2016个model-defined joint-limit steps，L2 arms有874个，均未与joint-1-upper target trigger重合。
因此v13的最终论文表述必须是“clean utility engineering pass + attack activation + one exact
active containment + whole-robot coverage/liveness failure”，而不是一般attacked-defense efficacy。

下一实验的识别顺序也由该结果固定：先做同攻击、同schedule的shadow-only guard-off ablation；再将
monitor扩展到7 joints × upper/lower并完整记录每关节margin；随后在预先冻结的low/medium/high
simulator stress下比较no-guard、reactive stop、shadow-only与predictive brake。只有在独立
development split冻结方法后，才能用新workload/init/env-policy seeds做outcome-blind确认性复验。

第一步 attacked shadow-only 已完成并给出强于aggregate表的局部因果证据。180条中只有
`human_safety task4/init32 Dual`的结局与full brake不同；两条件在首次风险前236个policy steps
及step246的source action、current margin和unguarded prediction完全一致。full brake避免7个
joint-limit steps与23个target-margin<0.15 steps，却在下一步deadlock并任务失败；shadow-only最低
margin降至`0.061217 rad`、产生25次counterfactual trigger，但最终任务成功且official unsafe仍为0。
论文应把这个结果写成“predictive hard stop的可识别safety–liveness tradeoff”，而不是把proxy改善
单独写成安全收益。它也直接说明下一方法贡献应是多关节coverage与safe recovery/backup controller，
不是继续在单关节上提高制动力。

v14 已完成第一步多关节 successor。它在同一outcome-disclosed 45-pair clean population上，把在线
审计扩展到7 joints × lower/upper，并联合保护同一步所有at-risk joints。180条Fresh2 episodes中，
29次trigger覆盖joint3/5/6 upper，12次执行exact-action hard guard，17次因没有安全candidate而
fail closed。L2两臂的实际14侧margin共有294,574个值，`<0.15 rad`和crossing均为0；两个disabled
arms对应为3306和1455。该结果解决了v13的单关节coverage失败，但没有解决liveness。

任务成功为VLA/Execution/Semantic/Dual `36/32/32/28`。两个L2对照均下降`8.89pp`，冻结
non-inferiority下界为`−20.06pp/−24.44pp`，均未通过；17个deadlock不能隐藏为安全成功。另一个
冻结non-pass是全14侧`1e-9 rad`校准门：非干预远离边界的最大shadow/replay漂移为
`0.001187 rad`，尽管false-safe风险决策为0、干预逐侧最大误差仅`4.24e-6 rad`、最低margin误差
仅`2.53e-9 rad`。论文必须同时报告“全关节安全代理覆盖显著增强”和“校准/任务效用未过”，并在
同schedule shadow-only之后才能把低余量减少归因到active guard。

该同schedule shadow-only现已完成。它复用全部180条schedule，并在L2 arms保留每步一次
exact-action shadow与restore，但彻底移除candidate evaluation、guard authority和deadlock
synthesis。90个disabled-arm episodes逐步完全一致；73个没有Full trigger的L2 episodes也保持
trace与outcome完全一致。17个首trigger episodes在分叉前共比较20,963个policy steps，source
action digest、risk-side identity、current/unguarded margins及此前actual margins的跨运行最大
误差均为0。这关闭了“差异可能来自shadow/restore或不同source action”的主要替代解释。

在L2 arms中，Shadow-only产生2733个`margin <0.15 rad`侧值和1442个crossing，Full均为0；
paired episode bootstrap中Execution的Full−Shadow crossing均值为`−28.38`
（95%区间`[−51.56,−9.29]`），Dual为`−3.67`（`[−7.58,−0.67]`）。代价同样清楚：
Execution task success从36降至32，Dual从31降至28；Full增加17个unknown/deadlock。论文应把
这写成“在固定development schedule上可识别的joint-limit-proxy containment–availability
tradeoff”，不能只保留安全代理的正差异。

该实验的注册状态仍是calibration non-pass：冻结`0.002 rad` shadow prediction/execution门被
`0.004651 rad`最大逐侧误差超过。后验diagnostic仅把“注册calibration non-pass”和“首次分叉前
causal identity complete”分轴报告，不修订原门，也不把outcome-disclosed对照升级成确认性结论。
下一实验因此转向预冻结的trigger-rich low/medium/high stress ×
no-guard/reactive-stop/shadow/predictive-brake矩阵，并显式加入deadlock recovery；最终主张仍需
新population和新seeds的outcome-blind qualification。
