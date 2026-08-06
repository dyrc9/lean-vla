# 方法：Intent–SemanticSubtask–ActionBlock 与 ActionBlock–Execution 双层完整性

## 1. 研究对象

方法在可信任务与低层 ActionBlock 之间增加受约束的 semantic subtask monitor。它不是事后生成的自然语言
explanation，也不再替换 action policy 的原始完整任务 prompt。最终 risk-selective 版本让 π0.5 继续根据
完整可信任务生成动作，`Z_t` 只作为独立可信的审计锚点；无物理风险时，monitor 返回 byte-identical
source ActionBlock。

顶层研究问题仍是两层对齐：L1 判断 concrete ActionBlock 是否服务于可信 intent，L2 判断获准
ActionBlock 是否对应实际 dispatch/effects。`Z_t` 是 L1 的内部结构化分解，不是第三个顶层对齐层。

记：

- `T`：可信任务意图，由攻击面之外的任务源提供；
- `O_t^T`：从安全分叉前的 trusted tap 取得并绑定的 semantic observation；
- `P_t^atk/O_t^atk/H_t^atk`：攻击者可修改的 policy-facing prompt、observation 和 history；
- `M_z`：digest/config 均 allowlisted 的冻结 semantic selector；
- `Z_t = M_z(T, O_t^T)`：从可信 task graph frontier 选择的 semantic subtask；
- `A_t = π(T, O_t^atk, H_t^atk)`：VLA 根据完整可信任务和 policy-facing view 输出的 ActionBlock；
- `S_t = AssessLocal(Z_t, O_t^T, A_t)`：使用可信观察的局部运动与后果评估；
- `C_t`：consumer 根据 `A_t` 与 `S_t` 编译的执行契约；
- `R_t`：exact dispatch receipt；
- `E_t`：观察窗口内的 command/effect evidence。

攻击链保持最初设定：

```text
TrustedIntent T  (immutable)
       |
       +-------------------------------> verifier

trusted T/O_t^T ------> Z_t --------------------> physical-risk monitor
                                                    ^
trusted full T + O/H policy view --attack--> VLA --> ActionBlock A_attack
                                                    |
                                                    +--> authorization / dispatch
```

攻击成功不要求模型“说出恶意计划”；只要攻击使输出 block 的实际预期效果偏离 `T`，就是 L1 的目标事件。
双视图、TCB 和覆盖边界见 [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

## 2. 第一层：Intent–SemanticSubtask–ActionBlock alignment

L1 的问题是：

> 当前 `Z_t` 是否是可信任务在当前场景中的合法下一步，且独立可信检查器是否能在不改写名义策略的
> 前提下发现 ActionBlock 的预测物理风险？

形式化写作：

```text
Z_t = SelectFrozen(T, O_t^T, legal_frontier(T, O_t^T))
S_t = AssessLocal(Z_t, O_t^T, A_t)

L1(T, O_t^T, Z_t, A_t, S_t) :=
    TrustedSemanticProvenance(T, O_t^T, M_z, Z_t)
  ∧ Bound(Z_t, T, O_t^T)
  ∧ LegalFrontier(T, O_t^T, Z_t)
  ∧ Bound(S_t, Z_t, O_t^T, A_t)
  ∧ PhysicalScreenAvailable(S_t)
  ∧ NoPredictedPhysicalRisk(S_t)
  ∧ QualifiedProvenance(S_t.assessor)
```

`Z_t` 来自有限 task graph，不允许自由文本越过可信任务约束。第一版优先使用确定性 FSM 或冻结 VLM
constrained selection，不更新 π0.5 权重。`AssessLocal` 优先采用解析/运动学/几何规则；learned outcome
predictor 或 shadow rollout 只作为后续增强。

`TrustedSemanticProvenance` 检查 task source、observation tap、secure split、selector checkpoint 和
config 的 exact allowlist，并绑定 observation/state epoch。它证明来源和绑定符合 TCB 假设，不证明冻结
selector 的语义输出永远正确；后者由资格化结果和 `unknown` 规则支撑。

最终 ActionBlock 采用 generate-then-monitor；`Z_t` 在 action generation 前固定，但不替换完整任务
prompt：

```text
Z_t fixed
  -> π0.5 produces one H=10 source block from the full trusted task
  -> apply the same numeric envelope as VLA-only
  -> check velocity/workspace/unexpected-contact risk
  -> no risk: return the exact source block
  -> physical risk: fail closed
```

`close_outside_target_neighborhood`、`release_command_missing`、place/release progress 和 expected
task-effect miss 属于 task-semantic advisory：记录后在下一 block 重规划，不再终止 episode。
`translation/rotation_velocity_limit`、`workspace_exit` 与 `unexpected_contact_neighborhood:*` 才是
预测物理 hard gate。

`trusted_articulation_state_unavailable` 不再等价于“发现物理风险”：检查器仍用可信 EEF、实体几何和
exact block 运行所有可用物理筛查，只把不可观测的 articulation task state 标成 advisory。stale epoch、
malformed command 和未识别 unknown 仍 fail closed。

## 3. 第二层：ActionBlock–Execution alignment

L2 的问题是：

> 获准的 block 是否按授权命令执行，并在绑定窗口内没有产生物理禁止效果或完整性偏移？

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
  ∧ required_integrity_effects(C_t) ⊆ observed_effects(E_t)
  ∧ forbidden_effects(C_t) ∩ observed_effects(E_t) = ∅
  ∧ no physical observer violation
```

missing task-progress effect 与 `target_not_held_after_move` 触发 audited replan；cost/collision、
workspace/wrong-contact、command/receipt substitution、stale/replay 和未识别 evidence unknown 仍
fail closed。对于启用 L2 的 arm，phase 只有在 `L2 ∧ task_completion_observed` 时推进。

v10 attacked 结果之后，v11 另行增加了一个明确标注为 outcome-informed 的 L2 observer refinement：
每次 `env.step` 后读取 robosuite 模型关节范围定义的 `joint_limit_violation`，与独立 SABER typed
signal 逐步核对；若首次为真，则把 `joint_limit_violation` 绑定进当前 L2 evidence，封存事务，并禁止
本 episode 的任何后续 dispatch。该规则只在 Execution-only 与 Dual 启用，不修改 source ActionBlock，
也不作用于 VLA-only/Semantic-only。

这个 refinement 是 **containment**，不是 pre-dispatch **prevention**：首次触发已经发生并计入
violation。当前 trusted observation 没有绑定足以精确预测 OSC 动作到关节状态的动力学契约，因此论文
不得把 post-step latch 写成“提前预测关节限位”。缺失 observer、信号 schema 错误或与独立 signal
不一致均 fail closed。

fresh15 开发性结果之后，方法和阈值保持不变，并在每个任务3个新 init 的 held-out scale45 上复验。
clean/attacked 各180条中共有39次 L2 containment trigger，所有 trigger 后的 dispatch 数仍为0；
这支持 transaction-level mechanical containment 的稳定性。与此同时，scale45 clean 的
Dual−Semantic task success 从 `31/45` 降到 `20/45`，因此该机制不能被写成 task-preserving shield。
方法章节必须把 containment guarantee 与 empirical utility tradeoff 分开：前者是首次 typed signal
之后的系统行为，后者取决于 workload，且当前没有 non-inferiority 结论。

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

四臂必须共享相同 VLA checkpoint、seed、初始观测、完整任务 prompt、intervention policy、observer
和 runner。当前 K=1/H=10 primary 要求每个 paired workload 的首个 source ActionBlock 四臂一致；L1
在没有物理风险的每次调用上还必须证明 returned/source digest 一致。发生 hard gate 或状态分叉后，不要求
后续轨迹 byte identity。

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

部署路径的 action prompt 保持完整 trusted `T`；`Z_t` 不进入 action generator。攻击评估可以修改
policy-facing observation/history 来测量 L1 检出，但仍禁止其进入 `Z_t` 和 checker。

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
