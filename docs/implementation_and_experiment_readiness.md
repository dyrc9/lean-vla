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

尚未贯通：

- semantic context/`Z_t`/prompt digest 尚未进入 integrity transaction；
- online LIBERO runner 尚未在生成动作前选择并绑定 `Z_t`；
- local checker 尚未从真实 trusted observation 和 executable prefix 产生 qualified assessment；
- projection/intervention 后的重新 assessment/contract/authorization 尚未形成一条在线路径；
- fixed-trace/Lean equivalence artifact 尚未覆盖 semantic binding。

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

### E2：Action-conditioning qualification

固定：

- exact observation/state；
- prompt template；
- flow-noise tensor；
- ActionBlock transform；
- 合法 `Z_t`、相邻阶段 `Z_t` 和冲突 `Z_t`。

报告完整 block digest、per-dimension delta、motion cosine、gripper change、阶段合理性和重复稳定性。该实验
回答 `Z_t` 是否具有有意义的行为影响，不承担防御 efficacy claim。

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

### E4：No-dispatch four-arm gate

使用 qualification 外的 frozen trace，验证：

- 每个 proposal 恰有四个 arm rows；
- semantic/action/contract identity 满足 primary design；
- L1/L2 negative fixtures 命中正确 arm；
- zero simulator、zero sink dispatch；
- Python/Lean evidence source digest 当前。

## 7. Outcome gate 与停止条件

完成 C1–C5、E1–E4 后，仍需用户/负责人明确授权才可运行：

1. 少量 closed-loop no-attack engineering smoke；
2. M2 的 240 个 VLA-only clean/attacked episodes；
3. M2 denominator/signal gate 后的 clean/attacked 四臂。

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
