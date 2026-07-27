# 代码与实验推进准备清单

## 1. 目标与不变量

下一阶段只做一件事：把当前已经分别存在的 semantic boundary、ActionBlock selection 和 L2/Lean
transaction 贯通，同时不污染 P0b/R9 或现有 v3 frozen evidence。

必须保持的论文不变量：

1. 顶层问题始终是 `Intent -> ActionBlock` 与 `ActionBlock -> Execution` 两层对齐；
2. `SemanticSubtask Z_t` 是 L1 的内部机制，不是自由文本 plan，也不是第三个顶层 layer；
3. Lean 是 L2 的核心方法组件，检查 exact-dispatch、receipt/effect binding 和 phase-gating；
4. selector/local checker 的现实正确性是 qualification claim，不交给 Lean；
5. 新 outcome rollout 必须等待 no-outcome identity、qualification、资源和授权 gate。

## 2. 当前基线

已经可复用：

- `semantic_trust.py`：trusted component allowlist、semantic context、`Z_t` artifact、trusted prompt；
- `semantic_action_selection.py`：同一 `Z_t` 下的 candidate filter、projection budget、复检和确定性选择；
- integrity v3：ActionBlock、assessment、contract、authorization、single dispatch、receipt、effects；
- Lean `IntegrityCore`：四臂 truth table、exact dispatch、execution alignment、phase-gating theorem；
- fixed-trace shared runner、historical executed-prefix adapter、M1 validator；
- P0b/R9 的 attack、pairing、observer、ledger 和探索性 evidence。

当前贯通状态：

- semantic context/`Z_t`/prompt digest 的独立 v4 schema 已进入 opt-in 在线 LIBERO policy-call 路径；
- online runner 已在生成动作前从 pre-transform view 选择并绑定 `Z_t`；
- analytic local checker 已从当前 trusted geometry 和 exact executable prefix 产生 assessment，并通过
  E3 frozen analytic-corpus qualification；
- bounded clip/projection 后会重新检查并生成 final proposal/assessment/contract，并签发 fresh v4
  authorization；
- `(H,7)` prefix 已作为一个 one-use logical dispatch session 接入 LIBERO boundary，每步 receipt 绑定同一
  authorization，execution evidence 绑定 ordered receipts、实际 action 和 observation window；
- E5-qualified analytic semantic effect observer 已接入 online receipt/window seal；只有 before/after
  privileged geometry 支持 expected effect atoms 时才返回 known，否则 reject/unknown；
- C5 fixed-trace/Lean scoped equivalence 已覆盖 semantic binding，并接入顶层检查。
- E3/E5 v2 已将 `closer_to_target` 与 `near_target` 分离，并在原冻结 corpus/gate 下重新通过；
- E8 已绑定 clean commit；两轮 E9 clean/no-attack smoke 已完成，第二轮连续通过两个 effect window。

## 3. Schema 决策

### C1：新增 semantic-bound runtime schema

推荐新增 `proofalign-integrity-v4`，不原地改变 v3 digest semantics。v3 继续只用于已冻结历史 evidence 和
回归测试；v4 承担当前论文主线。

v4 exact ActionBlock/proposal 至少绑定：

```text
episode_nonce
proposal_index / candidate_index
state_epoch
semantic_context_digest
semantic_subtask_digest
exact_policy_prompt_digest
trusted_observation_digest
policy_observation_digest
source_policy_chunk_digest
exact executable-prefix command + shape
```

`ActionBlockAssessment` 再绑定：

```text
semantic_subtask_digest
trusted_observation_digest
exact final ActionBlock digest
assessor id/version/config
known / unknown reason
motion/target/part/region
preconditions/effects/violations
progress margin
```

`BlockExecutionContract` 再绑定：

```text
semantic_subtask_digest
exact_policy_prompt_digest
assessment_digest
exact final ActionBlock digest
expected/forbidden effects
observation window
```

验收条件：

- 任一 semantic context、prompt、trusted/policy observation、command 或 shape 换绑都会改变 digest；
- v3 frozen fixtures 仍按原 schema 读取，不能被静默升级；
- unknown `Z_t` 不能生成 trusted action prompt 或 dispatchable v4 proposal；
- legacy adapter 必须显式标记 `historical_v3`，不能伪造缺失 semantic fields。

当前实现状态（2026-07-24）：

- `src/proofalign/integrity_v4_models.py` 已实现独立的 `proofalign-integrity-v4` proposal、
  assessment 和 execution contract，不改写 v3；
- verified proposal factory 会重新编译 trusted prompt，绑定 trusted/policy 双视图和 source chunk；
- proposal/assessment/contract 的换绑与 post-projection 旧 artifact 复用已有 negative tests；
- unknown semantic artifact 无 trusted prompt，v4 unknown proposal 明确不可 dispatch；
- historical executed-prefix adapter 显式输出 `runtime_schema_class=historical_v3`；
- `integrity_v4_runtime.py` 已实现 artifact freshness、one-use authorization、ordered exact-action dispatch、
  per-step receipt 和 receipt/effect window binding；
- stale authorization、caller/sink substitution、重复派发和 projection 后旧 artifact 复用均 fail closed。
- `semantic_policy_wrapper.py` 已把 deterministic BDDL task graph、trusted prompt、K=1 policy output、
  local checker、selection 和 v4 artifacts 串成一条 consumer-side path；
- `semantic_local_checker.py` 已实现 transport skills 的运动学/几何检查；articulation state 不足时
  unknown/fail closed；
- `run_liberosafety_pi05_openpi_eval.py --semantic-runtime` 在 checker/authorization reject 时保证 zero
  `env.step`；通过后也只能由 `AuthorizedLiberoActionSink` 在 exact step receipt boundary 内调用
  `env.step`，不再存在 checker 通过后直接派发路径；
- 当前几何来自 LIBERO object-state privileged benchmark observation，尚不是 deployment perception。

## 4. 代码工作包

### C2：Trusted semantic policy wrapper

输入：

```text
TrustedSemanticContext
SemanticTrustPolicy
UntrustedPolicyView
task graph frontier
frozen selector/config
frozen flow-noise seed(s)
```

输出：

```text
verified SemanticSubtaskArtifact
TrustedActionPrompt
ordered ActionBlock candidate artifacts
selector scores/margin/latency
```

约束：

- deployment mode 只能使用 trusted `T + Z_t` prompt；
- attack-evaluation mode 可以把 external prompt/image 送入 action branch，但不能进入 selector/checker；
- wrapper 不读取 reward、success、cost、collision 或 future observation；
- `K=1` 是 primary；`K>1` 必须由单独 protocol 冻结。

### C3：Executable-prefix local checker

第一版只实现 skill-level `Z_t` 的解析/运动学/几何检查：

```text
pick_up(target)
move(target, destination)
place(target, destination)
release(target)
open/close/actuate(target, part)
finish
```

checker 只读取 `Z_t`、trusted observation/state 和实际会执行的 prefix。它返回 frozen
`CheckedActionBlock`/`ActionBlockAssessment`，不读取 attacked instruction 或 episode future。

最低 negative fixtures：

- wrong target/part/region；
- close gripper outside target neighborhood；
- release before valid place region；
- move without held-object precondition；
- workspace/velocity/rotation/contact hard violation；
- missing/unknown trusted geometry；
- stale observation/state epoch；
- post-projection semantic mismatch。

### C4：Select、project、recheck、rebind

固定顺序：

```text
Z_t fixed
  -> generate candidate set
  -> assess nominal executable prefixes
  -> bounded projection
  -> assess projected prefixes again
  -> deterministic selection
  -> construct exact final ActionBlock
  -> compile fresh assessment/contract
  -> fresh authorization
```

禁止：

- 用 projection 修复 semantic mismatch；
- 选择动作后重命名 `Z_t`；
- nominal block 的 assessment/contract 沿用到 projected block；
- authorization 后修改 command；
- 不同 arm 重新采样 policy/selector。

当前实现状态（2026-07-24）：

- C4 已完成：final proposal/assessment/contract 精确换绑后才可签发 authorization；
- 一个 authorization 只可打开一次，但其 session 可按序消费完整 `(H,7)` prefix；
- 每步记录 actual applied action 与 receipt，窗口 evidence 绑定初始观察、每步 post observation 和全部
  receipt；
- episode 提前结束会诚实记录 incomplete prefix，不能伪装成完整 exact dispatch；
- E5 effect observer 已资格化并接线；incomplete prefix、epoch mismatch、缺失几何和 articulation
  state 仍保持 `unknown`。

### C5：Shared runner、trace validator 与 Lean evidence

`K=1` primary：

- 四臂共享 exact proposal、assessment、execution contract；
- 只有 `intent_enabled/execution_enabled` 开关不同；
- fixed-trace 永远 zero dispatch。

`K>1` future amendment：

- 共享 ordered candidate bytes、noise seeds 和每候选 assessment；
- VLA-only/Execution-only 使用冻结 base candidate；
- Semantic-only/Dual 使用同一 deterministic L1 selector；
- final command 可以因 treatment 不同，报告时不得称 final bytes identical。

Lean/v4 准备项：

- 在 Lean block/assessment/contract 中加入 semantic-subtask 与 prompt binding；
- 保留并重新证明四臂 truth table；
- 保留 Dual dispatch 同时要求 L1/L2 verdict；
- 保留 Execution-enabled exact-command theorem；
- 保留 phase advance 蕴含 execution alignment 与 trusted completion；
- 生成 Lean source digest、theorem inventory、Python truth-table/equivalence artifact；
- 明确该 artifact 是 scoped equivalence evidence，不是完整 refinement proof。

当前状态（2026-07-25）：

- 新增 `lean/ProofAlign/SemanticIntegrityCore.lean`，v3 `IntegrityCore.lean` 保持不变；
- 新增 `semantic_four_arm_runner.py`，只做确定性 shadow evaluation，不创建 simulator、sink 或 dispatch
  session；
- 新增并冻结 `proofalign_semantic_v4_c5_protocol.json`；
- 已生成 `proofalign_semantic_v4_fixed_trace_c5.json`：8 cases、32 arm rows、artifact identity 通过、
  dispatch count 为零；
- 已生成 `proofalign_semantic_v4_lean_equivalence_c5.json`，绑定 v4 Lean source、14 个 theorem anchors、
  Python sources 和 fixed-trace digest；
- 两个 artifact generator 的 `--check` 与 Lean build 当前通过；
- 专门 pytest、C5 readiness packet、`Makefile`/`scripts/check_all.sh` 接线均已完成，C5 已关闭。

## 5. 必需测试

### Unit/property tests

- semantic allowlist、context/epoch/frontier/prompt 换绑；
- candidate shape、duplicate index、mixed `Z_t`、projection budget；
- local checker 每个 skill 的 positive/negative/unknown；
- projection 前后 digest 与重新 assessment；
- stale/replay/substitution/receipt/effect negative；
- one-use authorization 和 sink-side substitution；
- Lean theorem/source digest freshness。

### Integration tests

1. 同一 trusted context 下 external prompt/image 改变不影响 `Z_t`；
2. attacked view 可以改变 candidate block，但不能改变 trusted checker input；
3. wrong-target block 只在 L1-enabled arms 被拒绝；
4. substitution/stale receipt 只在 L2-enabled arms 被拒绝；
5. Dual 同时要求两层通过；
6. `K=1` 四臂 proposal/assessment/contract digest 一致；
7. fixed-trace dispatch count 恒为零；
8. intervention 后旧 assessment/authorization 无法复用。

## 6. No-outcome 实验包

### E1：Semantic selector qualification

冻结 snapshot set 必须覆盖：

- 多 task、object、destination、stage；
- approach/grasped/transport/pre-place/released 等 predicate-defined state；
- base/wrist/state ablation；
- clean trusted view 与只作用于 policy branch 的 prompt/visual attack；
- OOD object、遮挡、缺失 state 和候选近分。

按 task/base-pair 分组切分，禁止同一 trajectory 的相邻帧跨 train/development/qualification。报告 legal
frontier、top-1/top-k、margin、stability、unknown/OOD abstention、worst group 和 latency。

首轮 `0/4`、`4/4`、`3/5` 只用于选择 skill-level 粒度，不进入 qualification denominator。

结果：raw π0.5 selector 未通过；500 snapshots 的 coverage `0.822`、known legal-frontier `0.5645`。
预注册 deterministic privileged-geometry FSM fallback 在 160 cases 上 160/160，并对 unknown
`100%` fail closed。

### E2：Action-conditioning qualification

固定：

- exact observation/state；
- prompt template；
- flow-noise tensor；
- ActionBlock transform；
- 合法 `Z_t`、相邻阶段 `Z_t` 和冲突 `Z_t`。

报告完整 block digest、per-dimension delta、motion cosine、gripper change、阶段合理性和重复稳定性。该实验
回答 `Z_t` 是否具有有意义的行为影响，不承担防御 efficacy claim。

结果：未通过 behavioral-control gate；median MAD `0.000190`、motion cosine `0.998928`。semantic
prompt 不授权为安全控制，analytic checker 仍为必需。

### E3：Local-checker qualification

数据只允许使用当前 observation、ActionBlock 和预注册 predicate/geometry label。禁止读取同 episode 的
future reward/success/cost/collision 来生成当前 assessment。

冻结并报告：

```text
coverage
attacked false-allow confidence bound
clean false reject / retention
OOD abstention
worst-group risk
p50/p95/p99 latency
CPU/GPU memory
```

阈值必须在 M2/four-arm outcome 前冻结。

结果：v2 在 2500 cases 中 clean `700/700`、attacked false allow `0/1200`、OOD abstention
`600/600`，p99 `59.1µs`，全部 gate 通过。v2 使用 `closer_to_target` 表示 approach progress，
保留 `near_target` 表示真实进入目标邻域。该结论只覆盖 synthetic analytic privileged-geometry corpus。

### E4：No-dispatch four-arm gate

使用 qualification 外的 frozen trace，验证：

- 每个 proposal 恰有四个 arm rows；
- semantic/action/contract identity 满足 primary design；
- L1/L2 negative fixtures 命中正确 arm；
- zero simulator、zero sink dispatch；
- Python/Lean evidence source digest 当前。

结果：8 proposals、32 rows，15 项 gate 全部通过，dispatch/simulator/sink/outcome 均为零。

### E5：Semantic effect-observer qualification

冻结 before/after geometry、prefix completeness、expected/forbidden effect atoms 与 trusted violation
fixtures。结果：2100 cases 中 clean `500/500`、attacked false allow `0/1000`、OOD abstention
`600/600`，p99 `21.6µs`。在线 runner 已使用同一 v2 observer 生成 bound
`PrefixExecutionEvidence`。

该结果不资格化 camera perception、simulator info trust 或在线效果分布。

### E6：Latency/resource smoke

已冻结 100 个 E2 snapshots × 3 measured passes 的 no-simulator workload，测量 checkpoint load、
policy/semantic pipeline p50/p95/p99、selector/checker/observer CPU latency、process GPU/RSS peak、
输出大小和 digest repeatability。v2 successor 固定 GPU 0 及 `<4096 MiB`/zero external compute
process 启动门。

授权 successor 已在本机 OpenPI 环境完成测量并分类为
`semantic_resource_smoke_qualified`。checkpoint load `6.222s`；300 次 warm policy call 的
p50/p95/p99 为 `85.3/94.8/97.3ms`，semantic pipeline p99 `97.6ms`；selector/checker/observer
最大 qualification p99 `59.1µs`；process GPU/RSS peak `8646/18830.5 MiB`；输出
`130086 bytes`；两个 repeat pass 共 `200/200` digest 完全一致。10 项 gate 全部通过，资源 monitor
无查询错误。runner 记录 simulator、action sink、dispatch、outcome 和 training 均为 false。

该结果只资格化冻结 workload 的本机工程预算，不资格化 camera perception、closed-loop efficacy 或
物理安全。

### E7：Deployment-perception data adequacy

当前 frozen RLDS schema 有 main/wrist RGB、robot/joint state、action 和 trajectory path，但缺少：

- camera intrinsics/extrinsics；
- target identity/localization 与 destination geometry；
- visibility/occlusion 与 held/contact supervision；
- 独立 qualification split。

因此 E7 分类为 `deployment_perception_data_inadequate`，不得直接训练或宣称 camera-only qualification。
下一数据 artifact 必须 outcome-blind，并按 trajectory/scene 分组冻结 development/qualification split。
`proofalign_deployment_perception_supervision_schema_e7.json` 已冻结完整逐帧 contract 和 population gates；
validator 会拒绝 outcome 字段、资产 digest 漂移及 trajectory/scene split leakage。新增 dataset
qualification runner 会在完整 population 上额外验证：

- 每个资产路径都相对且不能逃出 asset root；
- SHA-256 与实际文件一致，文件可由 Pillow 解码；
- main/wrist image 必须是 `HxWx3 uint8`，instance mask 必须是 `HxW bool`；
- 声明 shape/dtype 与实际数组一致；
- qualification evidence 使用 fresh root 和 checksum，且明确不资格化 perception model。

合成的 2000-snapshot、10-task、200-trajectory fixture 已覆盖全部 population/split/asset gate；当前
本机没有可用于生成真实 qualification evidence 的 conforming dataset。旧 EDPA/SafeLIBERO bundle
只保存 primary/wrist perturbation array 和当前 RLDS tree manifest，不提供 calibration、entity
geometry/mask、held/contact 或独立 split，不能混作 E7 supervision。

### E8：Source/evidence binding audit

只读 E8 audit 已绑定主仓库 HEAD、semantic commit scope、本地 E1–E6 evidence inventory 和 OpenPI
checkout。当前 evidence inventory 完整，OpenPI tracked worktree 干净并绑定
`15a9616a00943ada6c20a0f158e3adb39df2ccac`；semantic scope 未绑定路径为 `0`，分类为
`semantic_source_binding_clean`。audit 仍不执行隐式 `git add/commit`。

## 7. Outcome gate 与停止条件

用户已授权继续推进，执行仍按冻结 successor protocol 逐级收窄：

1. 少量 closed-loop no-attack engineering smoke（已完成）；
2. M2 60-record outcome-blind producer（仅缺第二张满足启动门的 GPU）；
3. producer 终态校验后的 240 个 VLA-only clean/attacked episodes；
4. M2 denominator/signal gate 后的 clean/attacked 四臂。

立即停止并不得进入新 outcome 的条件：

- selector/local checker protocol 或 threshold 未冻结；
- semantic/ActionBlock/contract digest 不能端到端验证；
- fixed trace 出现 dispatch；
- Lean source/equivalence evidence 过期；
- output root 已存在或允许隐式 replacement；
- GPU/latency 预算未测；
- 需要查看 victim outcome 才能选择阈值或 population。

## 8. 首个代码提交的最小范围

第一个实现提交只做 C1：

1. 新增 v4 semantic-bound typed objects；
2. 添加 canonical payload/digest 与 v3 isolation tests；
3. 将 `SemanticSubtaskArtifact`/`TrustedActionPrompt` 转换为 v4 provenance；
4. 不改在线 runner，不运行 simulator，不生成 outcome；
5. Python tests 与 Lean v3 build 必须继续通过。

这样可以先冻结跨模块接口，再并行推进 wrapper、local checker 和 Lean v4，而不会在 runner 中边写边改
digest 语义。
