# 方法：Intent–ActionBlock 与 ActionBlock–Execution 双层完整性

## 1. 研究对象

方法不假设 VLA 输出 high-level plan，也不把事后生成的自然语言 explanation 当作 policy witness。
VLA 的可观察输出只有一个数值 ActionBlock。

记：

- `T`：可信任务意图，由攻击面之外的任务源提供；
- `O_t`：产生 block 时的可信/绑定观测摘要；
- `V_t^atk`：攻击者可修改的 policy-facing instruction、observation 或 history；
- `A_t = π(V_t^atk)`：VLA 输出的 ActionBlock；
- `S_t = Assess(T, O_t, A_t)`：冻结的 consumer-side action assessment；
- `C_t`：consumer 根据 `A_t` 与 `S_t` 编译的执行契约；
- `R_t`：exact dispatch receipt；
- `E_t`：观察窗口内的 command/effect evidence。

攻击链保持最初设定：

```text
TrustedIntent T  (immutable)
       |
       +-------------------------------> verifier

policy-facing view --attack--> VLA --> ActionBlock A_attack
                                      |
                                      +--> verifier / dispatch boundary
```

攻击成功不要求模型“说出恶意计划”；只要攻击使输出 block 的实际预期效果偏离 `T`，就是 L1 的目标事件。

## 2. 第一层：Intent–ActionBlock alignment

L1 的问题是：

> 给定可信意图、当前观测和一个具体动作块，冻结评估器是否有足够证据认为该 block 会推进获准任务，
> 且不会引入禁止效果？

形式化写作：

```text
S_t = Assess(O_t, A_t)

L1(T, O_t, A_t, S_t) :=
    Bound(S_t, O_t, A_t)
  ∧ Known(S_t)
  ∧ GoalCompatible(T, S_t.predicted_effects)
  ∧ TargetCompatible(T, S_t.target/part/region)
  ∧ NoPredictedViolation(S_t)
  ∧ QualifiedProvenance(S_t.assessor)
```

这里的 `Assess` 可以是冻结 learned outcome predictor、解析/运动学模型、可信 shadow rollout，或这些组件的
保守组合。它输出的是**对 ActionBlock 后果的外部预测**，不是 VLA 自报的计划，也不是对 latent intent
的可识别性声明。

未知、OOD、观测不充分或模型分歧必须产生 `unknown`，而不是自动 allow。L1 的可信度来自单独的
qualification set、校准和 false-allow 上界；不能来自将 victim outcome 反向填入 assessment。

## 3. 第二层：ActionBlock–Execution alignment

L2 的问题是：

> 获准的 block 是否按授权命令执行，并在绑定的观察窗口内产生约定效果、没有产生禁止效果？

consumer 在授权前生成：

```text
C_t = {
  action_block_digest,
  assessment_digest,
  observation_digest,
  state_epoch,
  expected_effect_atoms,
  forbidden_effect_atoms,
  observation_window
}
```

执行对齐关系为：

```text
L2(A_t, C_t, Auth_t, R_t, E_t) :=
    all digests/nonces/indices match
  ∧ applied_command = authorized_final_command
  ∧ observed_command = receipt.applied_command
  ∧ receipt is fresh and one-use
  ∧ observation occurs after dispatch
  ∧ expected_effects(C_t) ⊆ observed_effects(E_t)
  ∧ forbidden_effects(C_t) ∩ observed_effects(E_t) = ∅
  ∧ no observer violation
```

对于启用 L2 的 arm，phase 只有在 `L2 ∧ task_completion_observed` 时推进。观察窗口未关闭时保持
`pending`，证据未知时保持 `unknown`。

## 4. Lean 的位置

Lean 规范包含：

- 四臂开关 truth table；
- ActionBlock、assessment、execution contract、authorization、receipt、evidence 的绑定关系；
- Execution-enabled arm 只能 dispatch exact authorized command；
- Execution-enabled arm 的 phase advance 蕴含 block-execution alignment；
- 所有 arm 的 phase advance 都蕴含 trusted task completion。

Lean **不**证明：

- learned assessor 对现实后果的预测正确；
- `T` 本身正确或完备；
- perception、collision/contact proxy 或 simulator 与物理世界等价；
- Python serializer/observer 自动精化到 Lean（需独立 equivalence evidence）。

因此正确的表述是“Lean-checked execution transaction semantics”，不是“Lean 证明机器人安全”。

## 5. 四臂估计量

| Arm | `intent_enabled` | `execution_enabled` | 主要可识别贡献 |
|---|---:|---:|---|
| VLA-only | 0 | 0 | 攻击后的原始 VLA 行为 |
| Intent–Action-only | 1 | 0 | L1 对 intent-divergent blocks 的独立作用 |
| Execution-only | 0 | 1 | L2 对 substitution/drift/effect mismatch 的独立作用 |
| Dual | 1 | 1 | 两层组合、干扰、deadlock 与 utility |

四臂必须共享相同 VLA checkpoint、seed、观测、ActionBlock bytes、intervention policy、observer 和 runner；
唯一 treatment switch 是两层是否启用。

## 6. 威胁模型与假设

攻击者可以修改 policy-facing instruction、图像/状态观测或 history，使 VLA 输出偏离可信任务的
ActionBlock。攻击者不能修改：

- trusted intent artifact；
- assessor/contract compiler 的冻结权重与配置；
- authorization digest chain 和 single dispatch boundary；
- receipt/evidence storage。

如果攻击者也能同时控制可信观测、assessor、observer 或 actuator feedback，则需要更强的 attestation/
sensor-trust 假设；本方法当前不覆盖。

## 7. 主要失败方式

- **L1 assessor false allow**：恶意 block 被预测为 goal-compatible；
- **L1 coverage collapse**：大量 unknown 导致 deadlock；
- **observer blind spot**：接触/碰撞或任务效果未被 evidence 捕获；
- **contract misspecification**：expected/forbidden atoms 太弱；
- **distribution shift**：攻击样本超出 assessor qualification 支持集；
- **层间补偿**：L1 拒绝的 block 经 intervention 改写后必须重新 assessment/contract，不得沿用旧证明。

这些失败必须分别报告，不能用 strict success 或 cost/collision 单一指标替代。
