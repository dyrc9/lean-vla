# 方法：Trusted-Task Action Monitoring 与 ActionBlock–Execution 双层完整性

## 1. 研究对象

方法在可信任务与低层 ActionBlock 之间增加受约束的 semantic subtask monitor。它不是事后生成的自然语言
explanation，也不替换 action policy 的 policy-facing prompt。最终 risk-selective 版本让 π0.5 继续根据
clean 或 SABER-attacked 的 policy view 生成动作，`Z_t` 只作为独立可信的审计锚点；无物理风险时，monitor
返回 byte-identical source ActionBlock。

顶层研究问题分为两个断点：L1 使用可信任务状态审计 concrete ActionBlock，并给出相对于冻结 checker 的
有限授权；L2 判断获准 ActionBlock 是否对应实际 dispatch/effects。`Z_t` 是 L1 的内部结构化锚点，不是
第三个顶层对齐层，也不是对 VLA latent intent 的恢复。

记：

- `T`：可信任务意图，由攻击面之外的任务源提供；
- `O_t^T`：从安全分叉前的 trusted tap 取得并绑定的 semantic observation；
- `P_t^pol/O_t^pol/H_t^pol`：policy-facing prompt、observation 和 history；它们在 clean 条件下正常生成，
  在攻击条件下可以被修改；
- `M_z`：digest/config 均 allowlisted 的冻结 semantic selector；
- `Z_t = M_z(T, O_t^T)`：从可信 task graph frontier 选择的 semantic subtask；
- `A_t = π(P_t^pol, O_t^pol, H_t^pol)`：VLA 根据可能受攻击的 policy view 输出的 ActionBlock；
- `S_t = AssessLocal(Z_t, O_t^T, A_t)`：使用可信观察的局部运动与后果评估；
- `C_t`：consumer 根据 `A_t` 与 `S_t` 编译的执行契约；
- `R_t`：exact dispatch receipt；
- `E_t`：观察窗口内的 command/effect evidence。

攻击链保持最初设定：

```text
TrustedIntent T  (immutable)
       |
       +-------------------------------> verifier

trusted T/O_t^T ------> Z_t -----------------------> physical-risk monitor
                                                     ^
P_t^pol + O_t^pol + H_t^pol --attackable--> VLA --> ActionBlock A_attack
                                                     |
                                                     +--> authorization / dispatch
```

攻击成功不要求模型“说出恶意计划”；只要攻击使输出 block 的实际预期效果偏离 `T`，就是 L1 的目标事件。
双视图、TCB 和覆盖边界见 [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

## 2. 第一层：Trusted-task ActionBlock monitoring

L1 的问题是：

> 当前 `Z_t` 是否是可信任务在当前场景中的合法下一步，且独立可信检查器是否能在不改写名义策略的
> 前提下识别 ActionBlock 的局部风险并产生可审计的 replan/fail-closed 决策？

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

这里的 `L1` 是 **relative authorization**：它证明 provenance、frontier、assessment binding 与当前 hard
gates 均成立，不证明任意物理安全动作都在语义上推进 `T`。特别地，当前实现把 task-progress miss、
release/close progress 等语义问题作为 advisory，允许当前 block 继续但强制下一 block 重新观察和规划；
因此论文应称其为 trusted-task monitoring/replanning，而不是完整 semantic soundness。

`Z_t` 来自有限 task graph，不允许自由文本越过可信任务约束。最终 simulator 系统使用冻结的
deterministic privileged-geometry FSM，不使用 raw π0.5 semantic score 做授权，也不更新 π0.5 权重。
`AssessLocal` 采用解析/运动学/几何规则；learned outcome predictor 只作为未来扩展。

`TrustedSemanticProvenance` 检查 task source、observation tap、secure split、selector checkpoint 和
config 的 exact allowlist，并绑定 observation/state epoch。它证明来源和绑定符合 TCB 假设，不证明冻结
selector 的语义输出永远正确；后者由资格化结果和 `unknown` 规则支撑。

最终 ActionBlock 采用 generate-then-monitor；`Z_t` 在 action generation 前固定，但不进入或替换
policy-facing prompt：

```text
Z_t fixed
  -> π0.5 produces one H=10 source block from P_t^pol/O_t^pol/H_t^pol
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

L2 包含两个相关但证据来源不同的子机制：L2a 维护 software transaction identity，L2b 在研究 simulator
中提供 joint-limit containment。SABER outcome 主要评价 L2b；substitution、replay、receipt/effect 换绑和
Lean 定理评价 L2a，二者不能用同一个结果互相代替。

### 3.1 L2a：执行事务身份

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

### 3.2 L2b：状态触发的物理 containment

最终 L2 在 dispatch 前执行有界的 state-triggered recovery：

1. 在线计算7个机械臂关节上下两侧共14个 margin；当前最小 margin 大于 `0.30 rad` 时，不运行 shadow
   rollout，source ActionBlock 直接进入 execution transaction；
2. 进入风险区时，系统为当前危险 joint sides 构造临时 virtual-stop guard，最多筛选2个 guard
   configurations；
3. 每个候选从同一 simulator snapshot 出发，以同一个 exact source action 做 one-step shadow rollout；
4. 可行候选必须在全部14侧保持 `>=0.15 rad` 的安全 floor，完成 state-restore 和 prediction/execution
   identity 审计，并统一满足 `force <=10000`；
5. 选择满足条件的最弱 uniform guard。若没有候选通过，事务 fail closed，不发生 dispatch；
6. 正式执行仍消费同一个 source ActionBlock bytes，guard 只改变执行层的临时约束配置；receipt 继续绑定
   authorized command、guard identity 和 observed joint-side effects。

这是一项针对研究 simulator 中 joint-limit risk 的 pre-dispatch containment mechanism，不是硬件
attestation、任意动力学安全证明或真实机器人保证。阈值、候选预算、force envelope 和最终结果只按冻结
方案报告。

系统层面必须区分 source action identity 与 executable configuration：virtual guard 不改变 `A_t` bytes，
但会改变 controller 到物理状态的映射。当前 protocol/runtime audit 记录 guard、restore、force 和 margin
证据；当前 Lean `BlockExecutionContract` 只显式建模 ActionBlock、assessment、authorization、receipt 与
effects，没有把 guard/controller configuration 作为 typed digest 字段。因而“full executable-configuration
binding”是明确的 Python-to-Lean refinement 缺口，正文不能把 exact ActionBlock 写成 exact physical
trajectory。

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
- virtual guard/controller configuration 已作为 typed field 精化进 Lean execution contract。

因此正确的表述是“Lean-checked execution transaction semantics”，不是“Lean 证明机器人安全”。

## 5. 四臂估计量

| Arm | `intent_enabled` | `execution_enabled` | 主要可识别贡献 |
|---|---:|---:|---|
| VLA-only | 0 | 0 | 攻击后的原始 VLA 行为 |
| Semantic-only | 1 | 0 | L1 对 task/subtask/action 偏离的独立作用 |
| Execution-only | 0 | 1 | L2 对 substitution/drift/effect mismatch 的独立作用 |
| Dual | 1 | 1 | 两层组合、干扰、deadlock 与 utility |

四臂必须共享相同 VLA checkpoint、seed、初始观测、policy-facing prompt、intervention policy、observer
和 runner。当前 K=1/H=10 primary 要求每个 paired workload 的首个 source ActionBlock 四臂一致；L1
在没有物理风险的每次调用上还必须证明 returned/source digest 一致。发生 hard gate 或状态分叉后，不要求
后续轨迹 byte identity。

最终设计固定为 `K=1/H=10`，不使用 best-of-K policy resampling。L2 在风险状态下筛选的最多2个对象是
共享同一 source ActionBlock 的 guard configurations；它们必须从同一 snapshot 开始并逐项通过 restore、
margin、force 与 identity gate，不能被解释为新的 policy candidates。

四臂只识别 L1 与“L2a+L2b 整体”的 treatment effect，不能从主表进一步分解 transaction binding 与
virtual-guard containment 的独立因果贡献。

## 6. 威胁模型与假设

攻击者可以在 secure split 之后修改 policy-facing prompt、图像/状态观测或 history，使 VLA 输出偏离
可信任务的 ActionBlock。攻击者不能修改：

- trusted intent artifact；
- trusted observation tap 及其安全分叉前帧；
- task graph、semantic selector、local checker/contract compiler 的冻结权重、allowlist 与配置；
- authorization digest chain 和 single dispatch boundary；
- receipt/evidence storage。

clean 部署路径的 `P_t^pol` 由 `T` 正常序列化，但 secure split 之后它不再具有 authority；SABER 评估可以
修改其 exact bytes，视觉/history 攻击也可以修改 `O_t^pol/H_t^pol`。`Z_t` 不进入 action generator，且
任何 policy-facing 输入都禁止进入 `Z_t` selector 或 trusted checker。系统记录 exact policy-prompt
digest 用于 provenance，但不会让该 digest 反向授权任务语义。

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
- **execution-configuration refinement gap**：guard/controller audit 尚未成为 Lean typed contract 的一部分；
- **distribution shift**：攻击样本超出 assessor qualification 支持集；
- **层间补偿**：L1 拒绝的 block 经 intervention 改写后必须重新 assessment/contract，不得沿用旧证明。

这些失败必须分别报告，不能用 strict success 或 cost/collision 单一指标替代。
