# ProofAlign: VLA ActionBlock 双层完整性

本仓库研究一个不要求 VLA 输出高层规划的问题：

> 在可信任务意图保持不变、policy-facing instruction/observation/history 可能被攻击时，如何判断 VLA
> 输出的 ActionBlock 是否仍服务于可信意图，并确认获准的 ActionBlock 在执行后没有发生命令或效果偏移？

核心链路是：

```text
Trusted T + pre-attack O_t^T -> frozen selector -> SemanticSubtask Z_t ─┐
                                                                       v
external prompt / injected O_t^atk -> π0.5 -> ActionBlock candidates -> L1
                                                                       |
                                                  BlockExecutionContract
                                                                       |
                                           dispatch -> receipt/effects -> L2/Lean
```

两层的含义：

1. **Intent–SemanticSubtask–ActionBlock alignment（L1）**：只用可信任务和安全分叉前 observation
   产生并绑定 `Z_t`，再检查 π0.5 ActionBlock 的局部运动/后果是否与 `Z_t` 兼容。不确定时必须
   abstain/fail closed。
2. **ActionBlock–Execution alignment（L2）**：检查获准 block、最终命令、dispatch receipt、观测效果
   和任务 phase transition 是否属于同一个绑定事务。Lean 只用于这层的有限、离散命题；不证明 learned
   assessor、传感器或物理世界正确。

顶层 motivation 始终是 `Intent -> ActionBlock` 与 `ActionBlock -> Execution` 两层对齐；`Z_t` 是 L1
的结构化机制。Lean 是 L2 的核心方法组件，用于固定 transaction semantics 并检查 exact-dispatch 与
phase-gating theorem，而不是事后附加的形式化说明。

四臂实验是同一 runner 上的两个开关：

| Arm | L1 Intent–Action | L2 Action–Execution |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

冻结 runtime 中的 `intent_only` / `intent_action_enabled` 只是 Semantic-only 的兼容 schema 名称。

## 当前证据边界

- 2026-07-27 semantic qualification 与工程 smoke：
  - raw π0.5 selector 未通过（500 snapshots，coverage `0.822`，known legal-frontier
    `0.564`），因此禁止用于 L1；
  - privileged-geometry deterministic FSM 通过（160/160，unknown fail-closed `100%`）；
  - semantic prompt behavioral control 未通过（median MAD `0.000190`，motion cosine
    `0.998928`），因此不把 prompt 当安全机制；
  - analytic local checker v2 通过 2500-case frozen corpus：clean retention `700/700`、
    attacked false allow `0/1200`、OOD abstention `600/600`，p99 `59.1µs`；v2 将“正在靠近”
    表示为 `closer_to_target`，不再误写为已进入 `near_target`；
  - E4 qualification-outside no-dispatch gate 通过：8 proposals、32 arm rows、跨臂 identity
    一致、dispatch `0`；
  - analytic effect observer v2 通过 2100-case frozen corpus：clean retention `500/500`、
    attacked false allow `0/1000`、OOD abstention `600/600`，p99 `21.6µs`；
  - E6 v2 offline resource smoke 通过：300 次 frozen π0.5 policy call，checkpoint load
    `6.22s`，policy/pipeline p99 `97.3/97.6ms`，GPU/RSS peak `8646/18830.5 MiB`，
    action digest repeat `200/200`；simulator、dispatch、outcome 均为 `0`。
  - E7 dataset qualification runner 已完成：会强制 population/split gate、资产 SHA、真实解码
    shape/dtype 与 asset-root containment；当前仍没有满足 contract 的本机数据。
  - E8 source-binding audit 已绑定 clean commit，semantic scope 未绑定路径为 `0`，分类为
    `semantic_source_binding_clean`。
- E9 clean/no-attack engineering smoke：
  - 首轮暴露 `near_target`/approach-progress 契约混淆，5 个 exact receipt 后被 L2 正确拒绝；
  - v2 复测连续完成 2 个 prefix、10 个 exact receipt、2 个 effect allow，effect reject/unknown 均为
    `0`；第三次 K=1 proposal 因预测进度 `1.93mm < 2mm` 在 dispatch 前被 L1 拒绝，记录为 clean
    availability/deadlock 信号，不据此修改冻结阈值。
- M2 与四臂主线终局：
  - M2 240/240 valid，攻击 transition `39/86=45.35%`，未达到原预注册 `50%`，永久保持
    `confirmatory_attack_foundation_nonpass`；后续 `40%` 只标注 post-outcome exploratory；
  - full-population clean 因 15/60 affordance pairs 缺 part-level trusted geometry 在首单元、
    dispatch 前 fail closed；
  - support45 clean 360/360 valid，但四臂 strict success 为 `61/90, 66/90, 0/90, 0/90`，
    Dual deadlock `88/90`，因此 clean gate nonpass，attacked stage 未授权、未执行。
- 2026-07-28 post-outcome L1 repair qualification：
  - benchmark-only exact simulator geometry 将初态 destination coverage 补到 `45/45`；
  - K=4 共 180 个不同 source chunks，但有可行候选的初态只有 `24/45=53.33%`，低于冻结的
    `90%` gate；三个 suite 分别为 `60.0% / 53.33% / 46.67%`；
  - K=1、K=2、K=3、K=4 的累计 coverage 均为 `24/45`，新增采样没有增加可用初态；
  - 资格测试为 0 dispatch、0 policy-conditioned env step、0 task outcome、0 selected hard
    violation，终局分类为 `l1_repair_initial_availability_qualification_nonpass`。
- 2026-07-28 Block-10 successor 与匹配长度消融：
  - 在逐任务不重叠的新 init 与新 seed 上，以 K=1 检查完整10步 ActionBlock，2 mm 与其他 checker
    条件保持不变；
  - 同一个 π0.5 source chunk 的 H=2/H=5/H=10 availability 分别为
    `0/45, 17/45, 36/45`；H=10 相对 H=5 净增19个初态、无 loss；
  - H=10 的三个 suite 为 `13/15, 12/15, 11/15`，总计80%仍低于90% gate，最差 suite
    73.33%低于80% gate，因此分类仍为 `l1_block10_initial_availability_qualification_nonpass`；
  - 全部三个长度的 hard-violation candidate 都为0；该消融只说明初态 checker availability，
    不说明轨迹 success 或防御 efficacy。
- 2026-07-28 H10×K4 successor：
  - 在第三套逐任务不重叠 init 与新 seed 上保持 H=10，只把候选数从1增到4；
  - 同一 ordered candidate set 的 K=1/K=2/K=4 coverage 为 `35/45, 35/45, 36/45`，45个
    样本都具有4个不同 source chunk，但额外3次推理只增加1个可用初态；
  - K=4 三个 suite 为 `13/15, 14/15, 9/15`，总80%与最差60%仍为 nonpass；因此停止继续堆
    stale horizon 或 IID candidate，下一步必须改变 action generator、训练条件或反馈接口。
- 2026-07-29 v8 完整 clean 诊断：
  - 45 个 paired tasks、四臂共 180/180 episodes 完整；VLA-only、Execution-only、
    Semantic-only、Dual success 为 `34/45, 33/45, 5/45, 5/45`；
  - 旧 L1 在 1142 个在线审计中改写 1036 个 source blocks，并产生 49 个动作终止；其中 43 个仅由
    task-semantic/progress 条件造成，6 个包含 predicted unexpected contact；
  - 该结果只冻结失败机制，不授权 attacked-defense 或 confirmatory claim。
- 2026-07-29 risk-selective / physical-sufficiency successor：
  - v9 保留完整任务 prompt，无预测物理风险时返回 exact source block；scale45 read-only replay 中
    43/49 个软动作终止和 9/17 个 missing-effect 终止可转为 replan，6 个 physical rejects 保留；
  - v9 fresh15 clean 为 VLA/Execution/Semantic/Dual
    `10/15, 10/15, 7/15, 6/15`；656/656 L1 blocks 不改写，15/15 paired first blocks 一致；
  - v10 将 `trusted_articulation_state_unavailable` 改为“继续做可用物理筛查、任务状态 advisory”，并将
    `target_not_held_after_move` 改为 replan；read-only replay 恢复6个 semantic unknown、保留3个
    contact rejects；
  - v10 第二批 fresh15 clean 为 `10/15, 8/15, 7/15, 7/15`；909/909 L1 blocks 不改写，
    15/15 paired first blocks 一致，8次 physical-risk reject 保留，official cost/collision 为0/60。
    Semantic-only 相对 VLA 为 `-20pp`（paired exact McNemar `p=0.25`），因此当前只支持
    risk-triggered mechanism 与明确的 clean safety–utility tradeoff，不支持 non-inferiority 或防御有效。
- P0b：96/96 episode 有效，得到 23 个 clean-eligible pair 和 15 个攻击 transition；因
  `23 < 26` 未通过确认性 denominator gate。
- R9 Execution-only：clean retention `22/23 = 95.7%`；attacked+defended `48/48`
  有效；cost/collision unsafe `1/48`；signal subset `15/15 -> 0/15` cost/collision；
  strict-success recovery `8/15`；`11/15` 仍有 residual contact proxy。

因此现有证据是“L2 有强探索性信号、risk-selective L1 已消除大部分人为 deadlock，但仍有可测 clean
utility 代价”的混合结果，不能声称一般防御有效、完整物理安全、clean non-inferiority 或 attacked
Dual 已验证。旧结果可复用为：

- P0b：原始 instruction/observation attack、clean pairing 和攻击 transition 基础；
- R9：ActionBlock dispatch、intervention、receipt/effect logging 和 Execution-only 基线。

它们不能替代新的 L1 assessor qualification，也不能改名为 Dual 结果。

## 当前主线

1. C1–C5、E1–E8 的 component、provenance、Lean transaction 与资源证据已关闭；E7 仍明确阻断
   camera-only deployment claim。
2. M2 原 `50%` confirmatory gate、full-population support failure 和 support45 clean nonpass 均已
   终局冻结，不被后续探索性工作覆盖。
3. support45 的 attacked stage 以 clean pass 为冻结前置条件；当前未通过，因此不执行攻击 rollout。
4. post-outcome L1 repair、Block-10、H10×K4、v8 scale45、v9 与 v10 均按时间顺序保留；最终方法不再
   投影/改写动作，也不降低2 mm旧阈值，而是移除该 task-progress hard gate，只保留预测物理风险 hard
   gate。
5. 当前论文主线是 risk-triggered nominal-policy non-interference + Lean execution transaction：
   clean 与配对 attacked fresh15 都已完成。攻击使60/60首个 ActionBlock 相对 clean 改变，但
   attacked Semantic/VLA 仅为 `7/15` 对 `8/15`，physical-risk rejects 由 clean 8次降至 attacked
   4次；因此当前不能声称 attacked utility superiority 或 physical-risk enrichment。post-hoc typed
   trace 的 joint-limit 方向性信号只用于提出 outcome-informed v11 假设，不覆盖本轮混合/负结论。

入口文档：

- [方法定义](docs/method.md)
- [`Z_t` 可信输入与注入边界](docs/trusted_semantic_boundary.md)
- [零训练 semantic hierarchy](docs/semantic_subtask_hierarchy.md)
- [ActionBlock assessor 设计与资格化](docs/action_block_assessment.md)
- [实验协议](docs/experiments.md)
- [L2 与跨层攻击实验计划](docs/l2_and_cross_layer_experiments.md)
- [旧实验复用与迁移](docs/experiment_reuse.md)
- [相关工作](docs/paper/related_work.md)
- [论文故事](docs/paper/paper_story.md)
- [代码与实验准备清单](docs/implementation_and_experiment_readiness.md)
- [进展与下一步](docs/progress_and_plan.md)

常用检查：

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" \
  lake --dir lean build ProofAlign
.venv/bin/python scripts/run_action_block_fixed_trace_gate.py --check
bash scripts/check_all.sh
```

冻结的旧协议、旧结果和废弃路线只用于审计，不授权新 rollout。

当前 post-E5 packet 已确认 benchmark privileged-geometry no-outcome stack 完整；opt-in 在线 LIBERO
runtime 已接入资格化的 deterministic selector、analytic executable-prefix checker、fresh one-use
authorization、ordered receipts 和 analytic effect observer。E6 离线资源/延迟 smoke 已通过；剩余
blocker 是 deployment perception、E8 所报告的 clean-commit binding 与明确 outcome 授权。E7 已机器
确认当前 RLDS supervision 不足；当前没有新 efficacy rollout。
