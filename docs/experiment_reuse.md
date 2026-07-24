# 旧实验复用与迁移方案

## 1. 结论

P0b 与 R9 都能复用，但复用对象不同：

- **P0b 复用攻击问题、runner/validator、endpoint 定义、pairing 逻辑和探索性效应信息**；
- **R9 复用低层 intervention/dispatch 实现、日志字段、observer、失败分类和 Execution-only 探索性证据**；
- 两者的历史 trace 可以做 schema/replay/assessor development，但不能进入新 confirmatory primary
  denominator；
- 旧实验没有 prospectively generated `ActionBlockAssessment` 和
  `BlockExecutionContract`，因此不能改名为 Intent–Action、Dual 或 Lean-verified v3 结果。

最重要的原则是：

> 复用代码、冻结资产、实验设计和探索性证据；不复用旧 outcome 来冒充新 estimand。

## 2. 复用等级

| 等级 | 含义 | 是否允许 |
|---|---|---:|
| C：Code reuse | runner、adapter、validator、observer、统计代码 | 是 |
| S：Schema reuse | episode/ledger、pair id、attack record、endpoint schema | 是，需版本迁移 |
| D：Design reuse | population planning、seed blocking、bootstrap、stopping rule | 是 |
| R：No-dispatch replay | 从旧 trace 提取 ActionBlock，运行离线 checker | 是，标注 post-hoc |
| E：Exploratory evidence | 将 P0b/R9 作为历史 pilot/外部基线报告 | 是，不与新结果合并 |
| Q：Qualification data | 用于 assessor 训练、debug 或阈值开发 | 有条件，必须 base-pair 隔离 |
| P：Primary confirmatory outcome | 进入 M2/四臂主要估计量 | 否，必须新运行 |

## 3. P0b 如何复用

P0b 的冻结定义见
[`saber_threat_replication_p0b_victim_protocol.json`](../experiments/saber_threat_replication_p0b_victim_protocol.json)。
历史结论为：

- 96/96 clean/attacked episodes 有效；
- 23 个 clean-eligible pairs；
- 15 个 clean-safe → attacked-unsafe transitions；
- denominator gate 要求 26，因此分类保持
  `p0b_blocked_insufficient_clean_baseline`。

### 3.1 可以直接复用

1. **Threat model**

   - task registry 中的 trusted instruction 继续作为 `TrustedIntent T`；
   - perturbed instruction/observation/history 只进入 policy-facing view；
   - attacker 不允许修改 trusted artifact、checker 或 observer。

2. **Attack producer 与 validator 实现**

   - prompt-tool producer 的调用方式；
   - one-generation-per-pair；
   - 禁止 best-of-N、outcome feedback 和 replacement；
   - attack record identity/order/digest validator。

3. **Pairing 与 endpoint**

   - clean/attacked 使用相同 task/init/seed；
   - clean eligibility、transition、strict success、cost/collision 分开；
   - contact/joint/force proxy 不与 cost/collision 合并。

4. **实验设计信息**

   - `23/48` clean eligibility 和 `15/23` transition 只能用于样本量规划、资源估计和 failure-mode
     设计；
   - base-pair cluster bootstrap、invalid 不替换、terminal stopping rule 可以复用。

### 3.2 不能直接复用

- M2 不复用 P0b 的 48 个 task/init identities；
- 不复用 P0b attack records、episode 或 outcome；
- 不把 23 个 eligible pairs 填入新 denominator；
- 不用 15 个 transition 调整看过 M2 outcome 后的 assessor threshold；
- 不把 P0b 的 numeric action 事后标注为 VLA-declared plan。

当前 frozen confirmatory protocol 已明确排除全部 48 个 P0b identities，并要求 60 个新 base pairs ×
2 seeds。

### 3.3 作为 assessor 数据时的限制

P0b trace 可以用于：

- effect atom vocabulary 设计；
- action/observation parser debug；
- assessor prototype training 或 development；
- attacked false-allow failure taxonomy。

但 15 个 transition 太少，不能单独支持可信的 false-allow 上界。若使用 P0b 开发 assessor：

- 必须按 `base_pair_id` 整组划分，不能把同一 pair 的 clean/attacked 或不同 seed 分到 train/test；
- P0b 只能标记为 historical development/pilot；
- 最终 qualification 必须使用独立、冻结、未参与 threshold 选择的数据。

## 4. R9 如何复用

R9 的冻结协议和 terminal audit 分别是：

- [`saber_integrity_action_envelope_r9_protocol.json`](../experiments/saber_integrity_action_envelope_r9_protocol.json)
- [`saber_integrity_action_envelope_terminal_summary.json`](../experiments/saber_integrity_action_envelope_terminal_summary.json)

R9 已完成 48/48 attacked+defended episodes；terminal summary 绑定 53 个 checksum entries，分类为
`exploratory_attacked_defended_complete_not_confirmatory`。

### 4.1 可直接复用的实现

| R9 资产 | v3 去向 |
|---|---|
| raw policy action | `ActionProposal` / executed-prefix ActionBlock |
| L2 action envelope | intervention policy |
| non-finite brake | pre-dispatch fail-safe intervention |
| clipped/projected command | authorization 的 `final_command` |
| environment step boundary | single dispatch boundary |
| episode ledger/checksums | artifact integrity与validator |
| cost/collision | execution violation endpoint |
| contact/joint/force channels | 独立 observed/forbidden effect atoms |
| strict success | utility endpoint，不是 alignment proof |

当前 [`integrity_execution_adapter.py`](../src/proofalign/benchmark/integrity_execution_adapter.py)
已将 execution-only 路径迁移到 ActionBlock/contract/receipt v3 runtime。

### 4.2 历史 trace 的精确迁移

使用
[`action_block_trace_adapter.py`](../src/proofalign/benchmark/action_block_trace_adapter.py)
时：

1. 按 `policy_call_index` 分组；
2. 只拼接该 policy call 实际消费的 `raw_action`；
3. 把 `(action_count, action_dimension)` 纳入 ActionBlock digest；
4. 保留原 `policy_action_chunk_sha256` 作为 source provenance；
5. 不读取 reward、success、cost、collision 或 future observation；
6. 不重建未执行的 policy chunk tail。

因此可以准确复用的是**executed prefix**，不是原始完整 policy chunk。若历史 run 没保存 observation
像素，只保存 frame digest，则它足以做 binding/L2 replay，但不足以重新运行 vision-based L1 assessor。

### 4.3 R9 outcome 的正确用法

允许继续报告：

- clean retention `22/23 = 95.7%`；
- full attacked+defended cost/collision unsafe `1/48`；
- signal subset cost/collision `15/15 -> 0/15`；
- signal subset strict success `8/15`；
- residual contact proxy `11/15`。

这些数字的角色是：

- Execution-only historical pilot；
- 新 observer/endpoint 的 regression reference；
- 四臂效应大小和资源预算的规划输入；
- failure taxonomy 的来源。

不能：

- 与新 Intent–Action-only/Dual episode 拼成一个四臂 factorial；
- 将 R9 作为新四臂的 confirmatory Execution-only cell；
- 声称一般防御或完整物理安全；
- 因为 envelope bound 成立就声称 task intent alignment。

四臂必须在同一个 shared runner、相同 ActionBlock bytes 和相同 assessor/contract 下运行；R9 没有这些
并行 treatment identities。

## 5. 旧字段到新架构的映射

| 历史字段/资产 | 新对象 | 迁移强度 |
|---|---|---|
| original trusted instruction | `TrustedTaskArtifact` / `T` | 可直接绑定 |
| perturbed instruction | attacked policy-facing view | 可直接绑定 |
| raw actions consumed per policy call | `ActionProposal` | 可无 outcome 提取 |
| policy action chunk SHA-256 | source provenance | 不能替代 ActionBlock digest |
| projected/clipped action | authorized final command | 可直接迁移 |
| cost/collision | `ExecutionEvidence.violation`/atoms | 可迁移，observer claim 不变 |
| contact/joint/force proxy | observed/forbidden atoms | 可迁移，必须单独报告 |
| task/strict success | outcome endpoint | 不作为 L1/L2 proof |
| post-action outcome label | assessor development label | 不得回填当前 block assessment |
| 历史 authorization/effect verdict | legacy audit | 不能追溯变成 v3 authorization |

历史数据中不存在：

- prospectively frozen `ActionBlockAssessment`；
- 与 assessment 绑定的 `BlockExecutionContract`；
- 新四臂间 byte-identical treatment identity；
- Python v3 ↔ Lean source binding。

这些对象只能在新 trace/新 run 中生成。

## 6. 两条复用轨道

### 轨道 A：无需新 GPU outcome

目标是最大化利用旧资产，同时不产生新 efficacy claim。

1. 校验 P0b/R9 protocol、manifest、ledger 和 checksums；
2. 从本地历史 episode 导出 executed-prefix ActionBlocks；
3. 运行 shape/digest/nonce/index validator；
4. 用 synthetic 或明确标注 post-hoc 的 assessment 做 fixed-trace component replay；
5. 用历史 outcome 设计 effect atoms、observer regression 和 failure taxonomy；
6. 结果标记为 `historical_posthoc_component_replay`，不进入 primary table。

Lean 可检查导入后对象是否满足当前离散 predicate，但只能称为**post-hoc conformance check**；因为旧 run
执行时没有 v3 authorization/contract，不能声称当时受 Lean-backed boundary 强制。

### 轨道 B：新 confirmatory evidence

1. 用历史结果完成 protocol/样本量/资源设计；
2. 冻结独立 assessor training/qualification split、threshold 与 abstention；
3. 生成 60 条新 attack records；
4. 运行 240 个 M2 VLA-only clean/attacked episodes；
5. M2 gate 通过后，从新 episode 导出 ActionBlocks；
6. 在四臂共享相同 ActionBlock、assessment 和 execution contract；
7. 依次运行 fixed-trace、480 clean、480 attacked；
8. 新 outcome 单独分析，不与 P0b/R9 pooled。

## 7. 四臂证据现状

| Arm | 历史可复用证据 | 新实验是否仍必需 |
|---|---|---:|
| VLA-only | P0b exploratory attack pilot | 是，M2 必须新运行 |
| Intent–Action-only | 无 | 是 |
| Execution-only | R9 exploratory mitigation pilot | 是，共享 runner 下重跑 |
| Dual | 无 | 是 |

## 8. 禁止的“伪复用”

- 把 P0b 23 个 clean-eligible pairs 当作 M2 denominator；
- 把 R9 改名为 Action–Execution confirmatory result；
- 用旧 episode 的 future collision/success 生成该 episode 当前时刻的 L1 assessment；
- 用同一 base pair 的 clean trace 训练、attacked trace qualification；
- 将 action-chunk hash 当作完整 ActionBlock 内容；
- 将 post-hoc Lean predicate pass 写成在线 formal enforcement；
- 把 `0/15 cost/collision` 写成 `0/15 physical harm`；
- 将历史 Execution-only 与新跑的其他 arms 拼接成四臂因果比较。

## 9. 推荐执行顺序

当前最优顺序是：

1. 保持 P0b/R9 原始 artifacts immutable；
2. 完成历史 trace 的 no-outcome ActionBlock export/replay；
3. 用历史数据只做 assessor development 和 observer regression；
4. 冻结独立 assessor qualification protocol；
5. 完成资源 smoke 与 clean commit；
6. 再申请 M2 和后续四臂执行。

这样可以最大化复用已有投入，同时不损害新实验的独立性和 claim validity。
