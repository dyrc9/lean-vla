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
                    |
                    v
  attacked prompt/image -> frozen π0.5
                    |
                    v
          ActionBlock A_t
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

内部 action representation 补齐到 32 维，LIBERO output transform 只保留前 7 维。当前 runner 每次执行
前 `replan_steps=5` 步后重新调用 policy。此路径没有文本输出，也没有现成的 `Z_t`。

代码依据：

- `external/openpi/src/openpi/training/config.py` 中的 `pi05_libero`；
- `external/openpi/src/openpi/policies/policy.py::Policy.infer`；
- `external/openpi/src/openpi/policies/libero_policy.py::LiberoOutputs`；
- `scripts/run_liberosafety_pi05_openpi_eval.py`。

## 3. `Z_t` 的定义与粒度

`Z_t` 不是自由文本 explanation，也不是从 `A_t` 事后反推的 intent。它必须在动作生成之前产生，作为
policy 的显式输入并与返回 ActionBlock 绑定：

```text
Z_t = SelectFrozen(T, O_t, Z_{t-1}, C(T))
A_t = π_action(O_t, Prompt(T, Z_t))
```

这里“显式输入”不等于已经证明有效控制：固定 observation/noise 后，不同 `Z_t` 是否产生足够且阶段合理的
ActionBlock 差异，必须作为独立 action-conditioning qualification 报告。若行为影响不足，`Z_t` 仍可作为
local checker 的 trusted verifier anchor，但不能声称形成了可靠 hierarchical control。

其中 `C(T)` 是由可信任务编译出的有限合法候选集。GPU pilot 表明，当前冻结 checkpoint 对 π0.5
风格的**技能级**标签有信号，但不适合直接选择 RT-H 风格的低层 motion 标签。因此第一版 `Z_t` 词表为：

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

`Z_t` 的来源按优先级分为两种，二者都不更新权重：

1. **确定性 task graph/FSM**：由可信 task、BDDL goal、gripper 状态和可审计几何关系判断当前合法
   frontier。它适合 benchmark qualification，但使用 simulator privileged state 时必须单独标注，不能
   冒充可部署视觉结果。
2. **冻结 VLM constrained selection**：从合法 frontier 中选择一个结构化候选。优先探测当前 π0.5
   checkpoint 内的 PaliGemma；若该公开 checkpoint 的语言能力不可用，再评估独立冻结 VLM。

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

动作 prompt 使用固定模板：

```text
Task: <trusted task>
Current semantic subtask: <canonical Z_t>
```

随后必须把 exact prompt bytes、`Z_t` digest、observation digest 和返回的完整 ActionBlock digest 一起记录。
任何重新选择 `Z_t`、prompt 改写或 observation epoch 变化都要求重新生成 ActionBlock。

可信 context 和 `Z_t` artifact 已实现于 `src/proofalign/semantic_trust.py`。它以 exact allowlist 检查
task source、observation tap、secure split、selector checkpoint/config；`UntrustedPolicyView` 单独表示
可能被攻击的 prompt/image/history，不能传入签发 `Z_t` 的函数。固定 prompt 编译器只使用 trusted
`T + Z_t`。

## 6. 具体选择哪个动作

当前 `run_liberosafety_pi05_openpi_eval.py` 的实际行为仍是：

```text
π0.5 生成一个 10 x 7 chunk
        |
逐步 clip 到 [-1, 1]
        |
执行前 5 步
        |
重新观察并生成下一块
```

它尚未集成 `Z_t` 或 semantic checker。目标方法采用 **select subtask → propose actions → constrain/select**：

```text
1. 固定 Z_t 和 observation epoch
2. π0.5 用同一 Z_t 提议 K 个 ActionBlocks
3. 只取每个 chunk 将实际执行的前 H=5 步作为 executable prefix
4. semantic/local checker 对每个 prefix 给出 known、progress margin 和 violations
5. numeric envelope 只允许小幅投影
6. 对投影后的 prefix 再做 semantic check
7. 从可行集合选择一个并绑定 exact final bytes
```

第一版 baseline 使用 `K=1`；`K>1` 是不训练的 best-of-K 扩展，通过不同且预先记录的 flow-noise seeds
得到候选。所有候选必须绑定同一个 `Z_t`。禁止看完 ActionBlock 后把 `Z_t` 改成与动作相符的标签。

可行集合为：

```text
Q_t = {
  k |
      known_k
    ∧ semantic_compatible(Z_t, A_t^k)
    ∧ no_hard_violation(A_t^k)
    ∧ projection_l2(A_t^k, Â_t^k) <= δ
    ∧ semantic_compatible(Z_t, Â_t^k)
    ∧ progress_margin(Â_t^k) >= m
}
```

若 `Q_t` 非空，采用固定的 lexicographic rule：

1. progress margin 更大；
2. numeric projection 更小；
3. ActionBlock 更平滑；
4. candidate index 更小，作为确定性 tie-break。

若 `Q_t` 为空，返回 `unknown/reject`，保持、刹停或重新观察；不能把语义错误通过 numeric projection
“修复”，也不能临时选择另一个 `Z_t` 为原动作辩护。选中的是投影并复检后的 exact executable prefix，
不是原始 10 步 chunk；原 chunk digest 只保留为 provenance。

该纯选择边界实现于 `src/proofalign/semantic_action_selection.py`。它不实现 perception 或几何评分，只保证
候选共享同一 `Z_t` 且与传入的 trusted `SemanticSubtaskArtifact.artifact_digest` 完全一致，并保证过滤
顺序、投影预算、复检和确定性选择规则。

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

证据不足、候选分数接近、目标不可见或几何不支持时返回 `unknown`，默认不授权。

## 8. 与 L2/Lean 的关系

L2 保持不变：它绑定被授权的 ActionBlock、实际 dispatch command、receipt 和观察到的 effect。`Z_t` 和
exact prompt digest 加入 execution contract provenance，但 Lean 不证明冻结 VLM 选择正确，也不证明
场景感知真实。

因此：

- L1：可信任务 → 语义子任务 → 局部动作兼容；
- L2：授权 ActionBlock → 实际执行/effect；
- Lean：检查绑定与 transaction semantics；
- qualification：统计评估 selector 和 local checker 的现实正确性。

## 9. 首轮可行性 probe

首轮只评估零训练可行性，不做 confirmatory outcome rollout：

1. 固定 checkpoint、候选词表、prompt 模板和随机种子；
2. 在少量干净 LIBERO observation/task 上运行 frozen selector；
3. 保存完整候选分数、top-1、margin、文本输出（若有）、latency 和失败原因；
4. 检查候选合法率、阶段合理性、重复运行稳定性和 `unknown`；
5. 再比较轻微视觉扰动/指令攻击下，可信 semantic view 是否保持稳定。

首轮结果只能回答“当前冻结 checkpoint 是否值得继续”，不能证明防御有效。若 PaliGemma 不能可靠选择
`Z_t`，顺序是：确定性 FSM → 独立冻结 VLM → 最后才讨论小规模 LoRA；不会自动进入训练。

首轮实际结果见 [`semantic_subtask_pilot.md`](semantic_subtask_pilot.md)。当前决策是把冻结 PaliGemma
分数作为 proposal/ranking 特征，而不是授权依据；task graph/FSM 和 local checker 保持权威。
