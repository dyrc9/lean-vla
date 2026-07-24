# 方法：Intent–SemanticSubtask–ActionBlock 与 ActionBlock–Execution 双层完整性

## 1. 研究对象

方法在可信任务与低层 ActionBlock 之间增加受约束的 semantic subtask。它不是事后生成的自然语言
explanation，而是在动作生成前产生、作为显式 policy 输入并与返回 block 绑定的结构化中间层。这里的
“作为输入”是结构事实；它对当前 action head 是否具有足够行为控制力，必须由独立 qualification 测量。

顶层研究问题仍是两层对齐：L1 判断 concrete ActionBlock 是否服务于可信 intent，L2 判断获准
ActionBlock 是否对应实际 dispatch/effects。`Z_t` 是 L1 的内部结构化分解，不是第三个顶层对齐层。

记：

- `T`：可信任务意图，由攻击面之外的任务源提供；
- `O_t^T`：从安全分叉前的 trusted tap 取得并绑定的 semantic observation；
- `P_t^atk/O_t^atk/H_t^atk`：攻击者可修改的 policy-facing prompt、observation 和 history；
- `M_z`：digest/config 均 allowlisted 的冻结 semantic selector；
- `Z_t = M_z(T, O_t^T)`：从可信 task graph frontier 选择的 semantic subtask；
- `A_t = π(P_t^atk, O_t^atk, H_t^atk, Z_t)`：VLA 输出的 ActionBlock；
- `S_t = AssessLocal(Z_t, O_t^T, A_t)`：使用可信观察的局部运动与后果评估；
- `C_t`：consumer 根据 `A_t` 与 `S_t` 编译的执行契约；
- `R_t`：exact dispatch receipt；
- `E_t`：观察窗口内的 command/effect evidence。

攻击链保持最初设定：

```text
TrustedIntent T  (immutable)
       |
       +-------------------------------> verifier

trusted T/O_t^T ------> Z_t ----------+
                                      |
P/O/H policy view --attack-----------> VLA --> ActionBlock A_attack
                                                |
                                                +--> verifier / dispatch boundary
```

攻击成功不要求模型“说出恶意计划”；只要攻击使输出 block 的实际预期效果偏离 `T`，就是 L1 的目标事件。
双视图、TCB 和覆盖边界见 [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

## 2. 第一层：Intent–SemanticSubtask–ActionBlock alignment

L1 的问题是：

> 当前 `Z_t` 是否是可信任务在当前场景中的合法下一步，且以该 `Z_t` 为条件生成的 ActionBlock 是否具有
> 与它兼容的局部运动和后果？

形式化写作：

```text
Z_t = SelectFrozen(T, O_t^T, legal_frontier(T, O_t^T))
S_t = AssessLocal(Z_t, O_t^T, A_t)

L1(T, O_t^T, Z_t, A_t, S_t) :=
    TrustedSemanticProvenance(T, O_t^T, M_z, Z_t)
  ∧ Bound(Z_t, T, O_t^T)
  ∧ LegalFrontier(T, O_t^T, Z_t)
  ∧ PromptBound(Z_t, A_t)
  ∧ Bound(S_t, Z_t, O_t^T, A_t)
  ∧ Known(S_t)
  ∧ LocalMotionCompatible(Z_t, S_t)
  ∧ NoPredictedViolation(S_t)
  ∧ QualifiedProvenance(S_t.assessor)
```

`Z_t` 来自有限 task graph，不允许自由文本越过可信任务约束。第一版优先使用确定性 FSM 或冻结 VLM
constrained selection，不更新 π0.5 权重。`AssessLocal` 优先采用解析/运动学/几何规则；learned outcome
predictor 或 shadow rollout 只作为后续增强。

`TrustedSemanticProvenance` 检查 task source、observation tap、secure split、selector checkpoint 和
config 的 exact allowlist，并绑定 observation/state epoch。它证明来源和绑定符合 TCB 假设，不证明冻结
selector 的语义输出永远正确；后者由资格化结果和 `unknown` 规则支撑。

具体 ActionBlock 采用 generate-then-constrain，但 `Z_t` 必须在 action generation 之前固定：

```text
Z_t fixed
  -> π0.5 proposes K blocks for the same Z_t
  -> check executable prefixes
  -> bounded numeric projection
  -> re-check projected prefixes
  -> deterministic feasible-block selection
```

语义不匹配只能 reject/resample，不能靠 numeric projection 改写，也不能从动作反向选择一个方便的 `Z_t`。
完整选择规则见 [`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)。

未知、OOD、观测不充分、候选分数接近或模型分歧必须产生 `unknown`，而不是自动 allow。完整定义见
[`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)。

## 3. 第二层：ActionBlock–Execution alignment

L2 的问题是：

> 获准的 block 是否按授权命令执行，并在绑定的观察窗口内产生约定效果、没有产生禁止效果？

consumer 在授权前生成：

```text
C_t = {
  action_block_digest,
  semantic_subtask_digest,
  exact_policy_prompt_digest,
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

Lean 是 L2 方法的一等组成：它固定 transaction vocabulary 和允许的 phase transition，并对
exact-dispatch/phase-gating 性质给出 machine-checked theorem，而不是在 Python 实验完成后追加的说明。

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
| Semantic-only | 1 | 0 | L1 对 task/subtask/action 偏离的独立作用 |
| Execution-only | 0 | 1 | L2 对 substitution/drift/effect mismatch 的独立作用 |
| Dual | 1 | 1 | 两层组合、干扰、deadlock 与 utility |

四臂必须共享相同 VLA checkpoint、seed、观测、intervention policy、observer 和 runner。`K=1`
primary 中 exact proposal、assessment 和 execution contract bytes 相同，唯一 treatment switch 是两层
是否启用。冻结 schema 的 `intent_only` 只是 Semantic-only 的兼容值。

若启用 best-of-K，四臂必须共享同一批 ordered candidate bytes 和每候选 assessment；VLA-only arm 使用
预注册的 base candidate，启用 L1 的 arm 才应用冻结过滤/选择规则，不能在不同 arm 中重新采样。此时
最终 ActionBlock/command 的差异属于 treatment mechanism，不能再笼统声称 final bytes 跨臂相同。

## 6. 威胁模型与假设

攻击者可以在 secure split 之后修改 policy-facing prompt、图像/状态观测或 history，使 VLA 输出偏离
可信任务的 ActionBlock。攻击者不能修改：

- trusted intent artifact；
- trusted observation tap 及其安全分叉前帧；
- task graph、semantic selector、local checker/contract compiler 的冻结权重、allowlist 与配置；
- authorization digest chain 和 single dispatch boundary；
- receipt/evidence storage。

部署路径的 action prompt 只由 trusted `T + Z_t` 固定编译，外部 prompt 不进入。攻击评估可以把
external prompt 有意送入 action-policy branch 来测量 L1 检出，但仍禁止其进入 `Z_t` 和 checker。

当前覆盖安全分叉后的数字/软件视觉注入；不覆盖发生在分叉前、同时欺骗 trusted tap 的物理光学攻击。
如果攻击者也能控制可信观测、selector/checker、observer 或 actuator feedback，则需要独立传感器、
capture attestation 或更强的 TCB，本方法当前不覆盖。

## 7. 主要失败方式

- **semantic selector false allow**：选择了错误但语法合法的 `Z_t`；
- **共同失效**：semantic selector 与 action policy 在同一被攻击 view 上产生恶意但自洽的结果；
- **local checker false allow**：动作与 `Z_t` 的局部运动不兼容却被接受；
- **L1 coverage collapse**：大量 unknown 导致 deadlock；
- **observer blind spot**：接触/碰撞或任务效果未被 evidence 捕获；
- **contract misspecification**：expected/forbidden atoms 太弱；
- **distribution shift**：攻击样本超出 assessor qualification 支持集；
- **层间补偿**：L1 拒绝的 block 经 intervention 改写后必须重新 assessment/contract，不得沿用旧证明。

这些失败必须分别报告，不能用 strict success 或 cost/collision 单一指标替代。
