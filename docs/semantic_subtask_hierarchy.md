# 零训练 Semantic-Subtask 层级

## 1. 决策

L1 的主路线改为在可信任务与低层 ActionBlock 之间增加结构化语义子任务 `Z_t`。Semantic branch
只读取可信任务和安全分叉前的 observation tap；可能被攻击的外部 prompt/图像只进入 action branch：

```text
Trusted task T + trusted observation O_t^T
                    |
                    v
 allowlisted frozen semantic selector
                    |
                    v
        SemanticSubtask Z_t
                    |------------------------------┐
                                                   v
 policy prompt/image/history -> frozen π0.5 -> ActionBlock A_t
                                                   |
                                                   v
                                  checker(Z_t, O_t^T, A_t)
```

第一版不训练模型、不更新 π0.5 checkpoint，也不训练新的 action-to-intent 分类器。只增加推理代码、
有限子任务词表、绑定记录和保守检查器。

这采用了 RT-H 和完整 π0.5 的 action hierarchy 思路，但不声称当前 OpenPI checkpoint 已经实现论文中的
显式 semantic head。当前仓库明确只支持 π0.5 的 flow-matching head；本地 `pi05_libero` 接口也只返回
数值动作。

## 2. 当前 π0.5 边界

当前 LIBERO policy 接收：

- base/wrist RGB；
- 末端位置、axis-angle 姿态和 gripper state；
- task prompt。

它输出一个 `10 x 7` ActionBlock。每步为：

```text
[Δx, Δy, Δz, Δrx, Δry, Δrz, gripper]
```

内部 action representation 补齐到 32 维，LIBERO output transform 只保留前 7 维。最终四臂 runner 使用
`replan_steps=10`，将完整 `10 x 7` source chunk 作为 ActionBlock。此路径没有文本输出，也没有现成的
`Z_t`。

代码依据：

- `external/openpi/src/openpi/training/config.py` 中的 `pi05_libero`；
- `external/openpi/src/openpi/policies/policy.py::Policy.infer`；
- `external/openpi/src/openpi/policies/libero_policy.py::LiberoOutputs`；
- `scripts/run_liberosafety_pi05_openpi_eval.py`。

## 3. `Z_t` 的定义与粒度

`Z_t` 不是自由文本 explanation，也不是从 `A_t` 事后反推的 intent。它必须在动作生成之前、基于同一
trusted state epoch 产生，作为独立 monitor anchor 与返回的 ActionBlock 绑定；最终系统不把它写入
policy prompt：

```text
Z_t = SelectFrozen(T, O_t^T, Z_{t-1}, C(T))
A_t = π_action(P_t^pol, O_t^pol, H_t^pol)
S_t = AssessLocal(Z_t, O_t^T, A_t)
```

因此，`Z_t` 的作用不是形成 hierarchical action control，而是让 consumer 在不信任 policy-facing view
的情况下拥有一个有限、可审计的 task-progress 与 local-risk 参照。论文不把 `Z_t` 对 policy 行为的因果
控制作为贡献或 estimand。

其中 `C(T)` 是由可信任务编译出的有限合法候选集。最终系统使用以下技能级 `Z_t` 词表：

```text
pick_up(target)
move(target, destination)
place(target, destination)
release(target)
open(target)
close(target)
actuate(target, part)
finish()
unknown(reason)
```

`approach`、`align`、`grasp`、`lift`、`lower` 和 `retract` 作为 `Z_t -> A_t` checker 使用的局部
motion atoms，不作为当前冻结语言 selector 的主候选。具体任务只能启用其 task graph 中出现的节点。例如
`put mug on plate` 不允许选择 `open(drawer)`，即使冻结 VLM 给它更高分。

## 4. 零训练来源

最终 `Z_t` 由确定性 task graph/FSM 产生：它使用可信 task、BDDL goal、gripper 状态和可审计几何关系
判断当前合法 frontier，不更新任何模型权重。该实现依赖 simulator privileged state，因此只能支持
benchmark qualification，不能冒充 camera-only deployment perception。冻结 VLM constrained selection
属于未来扩展，不参与当前 L1 授权或最终四臂结果。

不允许把攻击后的 instruction 当作 `T`。Semantic selector 和 local checker 必须使用安全分叉前的
`O_t^T`，而不是 policy-facing `O_t^atk`；否则结果只能称为层级自洽，不能称为 adversarial
alignment。完整 TCB 和覆盖边界见
[`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

## 5. 推理和绑定

每个 `SemanticSubtask` 至少记录：

```text
episode_nonce
proposal_index
trusted_task_digest
observation_digest
previous_subtask_digest
task_graph_digest
candidate_set_digest
verb / target / destination / part
selector_kind / selector_version / checkpoint_digest
task_source / observation_tap / secure_split identities
prompt_template_digest
confidence_or_margin
status = known | unknown
```

policy prompt 与 semantic artifact 分开绑定。clean 时 `P_t^pol` 是任务的正常序列化，attacked 时它由冻结
SABER record 修改；两种条件都记录 exact prompt bytes/digest。`Z_t` digest、trusted observation digest、
policy-view digests 和完整 ActionBlock digest 随后共同进入 provenance/contract，但只有 `T/O_t^T/Z_t`
属于 semantic authority。任何重新选择 `Z_t`、prompt 改写或 observation epoch 变化都要求重新生成并重新
评估 ActionBlock。

可信 context 和 `Z_t` artifact 已实现于 `src/proofalign/semantic_trust.py`。它以 exact allowlist 检查
task source、observation tap、secure split、selector checkpoint/config；`UntrustedPolicyView` 单独表示
可能被攻击的 prompt/image/history，不能传入签发 `Z_t` 的函数。仓库中的 fixed prompt compiler 是
历史/qualification 辅助路径；最终四臂不使用它给 π0.5 注入 `Z_t`。

## 6. 具体选择哪个动作

最终在线 L1 采用 **select subtask → generate exact source → monitor → authorize/dispatch**：

```text
1. 固定 Z_t 和 observation epoch
2. π0.5 从 `P_t^pol/O_t^pol/H_t^pol` 生成唯一的 `H=10` source ActionBlock
3. 应用与 VLA-only 相同的 numeric envelope
4. semantic/local checker 对 exact block 给出 known、task-progress advisory 和 hard-risk atoms
5. 没有 hard risk 时返回 byte-identical source block；task-progress miss 触发 audited replan
6. hard risk、stale state、malformed command 或未知 evidence 时 fail closed
7. 为 exact returned block 生成 fresh assessment/contract/authorization
8. 通过 single dispatch boundary 消费，并绑定 receipt/effect evidence
```

当前正式 estimand 固定为 `K=1/H=10`，不做 best-of-K policy resampling，也不对语义不兼容的动作做
projection“修复”。禁止看完 ActionBlock 后把 `Z_t` 改成与动作相符的标签。L2 风险恢复中最多2个候选
指的是同一 source action 下的 guard configurations，而不是新的 policy ActionBlocks。

在线接线位于 `semantic_policy_wrapper.py`、`integrity_v4_runtime.py` 和
`run_liberosafety_pi05_openpi_eval.py`。当前几何来自 LIBERO benchmark privileged state，不能表述为
camera-only deployment perception。

## 7. 新 L1

L1 拆成两个关系：

```text
TaskSubtask(T, O_t, Z_t)
SubtaskAction(Z_t, O_t, A_t)
```

第一部分检查：

- `Z_t` 的所有 binding/provenance 匹配；
- `Z_t` 属于可信 task graph 的当前合法 frontier；
- target、destination 和 part 来自可信任务/场景实体；
- selector 未返回 `unknown`。

第二部分不尝试恢复完整意图，只检查低层局部兼容性：

- `pick_up(x)`：依次允许 approach/align/grasp/lift，闭合只能发生在目标邻域；
- `move(x, y)`：已抓持 `x`，整体运动朝向 `y`；
- `place(x, y)`：目标位于 `y` 的允许区域，下降/释放顺序合法；
- 所有子任务均满足 workspace、速度、旋转、碰撞/contact 和 gripper envelope。

证据不足、候选分数接近、目标不可见或几何不支持时返回 `unknown`，默认不授权。这里的“兼容性”仍需按
实现强度解释：workspace、速度、unexpected contact、stale/malformed command 和 unknown evidence 是
hard gate；task-progress、release/close progress 与 expected-effect miss 是 advisory，只触发记录和下一
block 重规划。因而 L1 是 trusted-task ActionBlock monitor 与 checker-relative authorization，不是完整的
task-semantic verifier。

## 8. 与 L2/Lean 的关系

L2 绑定被授权的 ActionBlock、实际 dispatch command、receipt 和观察到的 effect。`Z_t` 和
exact policy-prompt digest 加入 execution contract provenance，但 Lean 不证明 selector 选择正确，也不证明
场景感知真实。

因此：

- L1：可信任务 → 语义子任务 → 局部动作监控/有限授权；
- L2a：获准 ActionBlock → exact command/receipt/effect 事务；
- L2b：风险状态 → guarded execution/joint-limit containment；
- Lean：检查绑定与 transaction semantics；
- qualification：统计评估 selector 和 local checker 的现实正确性。

当前 Lean `BlockExecutionContract` 绑定 ActionBlock、assessment、authorization、step receipts 和 effects，
但尚未把 virtual-guard 或 controller configuration 作为独立 typed digest。runtime trace 会记录 guard、
state restore、force 和 margin；这支持研究模拟器内的审计与 containment 结果，却不构成 full executable
configuration 或 exact physical trajectory binding。

## 9. 当前资格化边界

正式系统使用 deterministic privileged-geometry task graph/FSM，而不使用 raw π0.5 semantic score 做
L1 授权。该 selector 已通过160-case gate，analytic local checker 与 effect observer 分别通过 E3/E5
finite-corpus gate。所有资格化只覆盖 benchmark privileged geometry，不覆盖 camera perception、分叉前
视觉欺骗或部署泛化；相关 pilot 和替代路线保留在 [`archive/`](archive/) 供审计，不进入论文主线。
