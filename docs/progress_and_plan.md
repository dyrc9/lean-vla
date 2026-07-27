# 当前进展与执行计划

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
- 当前只授权 480-episode clean four-arm Stage B；
- attacked Stage C 仍未授权，必须等 clean terminal gate 后另行绑定；
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
- 用户已明确授权新的 support-conditioned fresh2。协议、360-row schedule/analysis、runner 与 one-shot
  launcher 已冻结并通过全量门禁；当前 launcher 等待两张不同且各 `<1024 MiB` 的 GPU，尚未创建
  fresh2 output root。它不能称为 fresh1 重试或 full-population 结果。

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

剩余 blocker：

1. 等待两张 `<1024 MiB` GPU；launcher 完整 preflight 后启动 45-pair/360-episode clean fresh2；
2. 禁止复用已失败 fresh1，禁止跳过 fresh2 的首个 invalid 停止规则；
3. support-conditioned clean gate 通过后，才可另行授权同一支持集上的 attacked stage；
4. 所有结果保持 exploratory 标签，不得回写原 50% M2 nonpass；
5. E9 暴露的 K=1 clean availability/deadlock 风险进入报告，不反向修改冻结阈值；
6. E7 perception 数据仍阻断 camera-only deployment claim，但不阻断明确标注 privileged geometry 的
   benchmark 论文主线。

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

1. **M2 terminal evidence**：producer 已完成，victim 正在授权 fresh root 中运行；完成前不读取中间
   outcome，也不启动依赖其结果的四臂 rollout；
2. **closed-loop clean availability**：E9 v2 的前两个 prefix 均 effect-allow，第三个 K=1 proposal
   被 L1 在 dispatch 前拒绝；作为 deadlock/utility 信号进入后续报告，不反向调冻结阈值。
3. **Deployment perception qualification data**：E7 已证明当前 RLDS 缺少 7 类必要监督；这是
   camera-only deployment claim blocker，不是 privileged-geometry benchmark 主线的先决 gate。

E8 已绑定 clean commit，semantic scope 未绑定路径为 `0`。E7 仍是 deployment claim blocker，但不阻止
明确标注 privileged geometry 的 benchmark M2。

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

### M2：240 episode

60-record outcome-blind producer 与 240-episode victim 均已终态完成。M2 rate 为 45.35%，原 50%
confirmatory gate nonpass；结果后 40% exploratory continuation 的 full-population fresh1 又因
semantic support coverage 在首单元 dispatch 前 fail closed。当前等待是否授权 45-pair
support-conditioned fresh2。

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
  -> support-conditioned clean 360 episodes（已授权；launcher 等待两张合格 GPU）
  -> clean terminal gate
  -> support-conditioned attacked 360 episodes（须 clean pass + 新授权）
```

当前继续使用预先资格化的 deterministic task-FSM L1。40% 只改变是否继续收集探索性四臂证据，
不得用 M2/four-arm outcome 反向调整 selector/checker/effect observer，也不得把原 M2 改判为 pass。

## 8. M2 后的 published-attack-grounded successor

M2 producer/victim 的 240-episode population、stopping rule、原 50% gate 和终局 artifact 保持不变。
原 gate 已 terminal nonpass；新的 40% 决策仅开启明确标注的 exploratory clean outcome。完整 successor 见
[《L2 与跨层攻击实验计划》](l2_and_cross_layer_experiments.md)。

论文主线与次要 stress study 现在明确分开：

1. 论文事实链是 M2 confirmatory nonpass → disclosed 40% post-outcome exploratory continuation →
   clean four-arm gate →（若 clean pass）separately authorized attacked four-arm；
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
7. terminal analysis 使用完整 population、保守 missing/invalid、base-pair cluster bootstrap、exact
   McNemar 和 Holm；40% threshold change 必须始终披露为 outcome-driven exploratory decision。

Evidence naming 固定为：

- SABER：L1 benchmark；
- source `S_u` transfer：externally grounded operator-transfer L2 case study；
- ROS replay：只有 online capture/transport gate 通过后才是 adapted replay case study；
- feedback FDIA：当前只报告 `interface_not_supported`；
- SABER × source operator：cross-layer composition study；
- wrong digest/receipt/effect/phase：formal negative suite。

这项 successor 不授权修改历史 frozen artifact，也不授权把 L2 case-study 结果称为标准化 benchmark、
一般物理安全或完整硬件 attestation。
