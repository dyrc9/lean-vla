# ActionBlock 后果评估器：设计与资格化

## 1. 在 semantic subtask 之后评估 ActionBlock

当前 π0.5-LIBERO/OpenPI 接口只返回数值 action chunk，但主方案不再把这视为必须永久接受的方法边界。
我们在其外部增加动作生成前的结构化 `Z_t`：

```text
(trusted intent, trusted observation O_t^T)
                  |
                  v
       frozen semantic subtask Z_t
                  |
                  v
 attacked policy view -> π0.5 ActionBlock
                  |
                  v
 local assessment(Z_t, O_t^T, ActionBlock)
```

因此本文件中的 assessor 主要负责 `Z_t -> ActionBlock` 的局部兼容性和禁止后果，不再承担“仅凭动作块
恢复完整任务意图”的职责。`Z_t` 的来源、绑定和 qualification 见
[`semantic_subtask_hierarchy.md`](semantic_subtask_hierarchy.md)。

这里不能让 assessor 读取攻击后的外部 prompt，也不能默认复用被注入的 policy-facing image。否则 selector、
policy 和 assessor 会共同接受同一注入，只得到“攻击视图内部自洽”。trusted observation tap、secure
split 与不覆盖的物理光学攻击见
[`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

## 2. Assessor 的输出

`ActionBlockAssessment` 必须在 block 产生后生成，并绑定：

- episode nonce、proposal index；
- ActionBlock digest；
- observation digest、state epoch；
- assessor id/version/kind 和生成时间。

它只输出有限、可评估的字段：

- `predicted_motion`；
- target/part/region；
- task-relevant predicted effect atoms；
- predicted violation atoms；
- required precondition atoms；
- `known` 或带原因的 `unknown`。

自由文本 explanation 不能作为 efficacy witness。

## 3. 候选实现

### A. 解析/运动学评估器

根据末端位姿增量、gripper command、对象几何和短时运动学预测 block 的局部效果。优点是低延迟、容易
审计；缺点是难以表示接触、遮挡和复杂语义。

### B. Learned outcome predictor（可选，非首版）

输入 `O_t` 与 `A_t`，预测 block 末端状态、对象/夹爪关系、接触风险和 task-progress atoms。可以用
state-space dynamics、latent world model 或 action-conditioned video predictor。它最接近 L1 的目标，
但必须单独处理 calibration、OOD 和 domain shift。

### C. Trusted shadow rollout

在独立 simulator/digital twin 中执行 block，抽取效果。它提供清晰的 counterfactual semantics，但存在
sim-to-real/sim-to-benchmark mismatch，且 latency 较高。

### D. 保守组合

第一版建议：

```text
legal semantic-subtask frontier
      ∧ analytic motion/geometry constraints
      ∧ OOD/ambiguity abstention
```

冻结 learned predictor 和 shadow rollout 用于后续 qualification/困难样本审计；第一版不训练新模型。

## 4. 推荐的第一版 LIBERO assessor

对每个 7-DoF action chunk：

1. 解析 chunk 的末端位移、旋转、gripper 开合和长度；
2. 从 `Z_t` 和当前 observation/state 提取 target、part、region、robot/object relation；
3. 预测窗口末端的有限 atoms，例如 `approach:mug`、`grasp:mug`、`release:mug`、
   `contact:fixture`、`workspace_exit`；
4. 检查 predicted motion/effect 是否与 `Z_t` 和 task graph frontier 兼容；
5. 对不支持的对象、严重遮挡、模型分歧或过长 chunk 返回 `unknown`。

注意：`predicted_motion` 是 consumer 对局部动作后果的分类；`Z_t` 才是动作生成前的语义条件，二者不能
互相冒充。

## 5. 资格化 gate

在进入四臂 outcome run 前，冻结独立 qualification set 和阈值，并报告：

- field-level skill/target/part/effect accuracy；
- attacked transition 上的 false-allow rate（主风险）；
- clean block false-reject rate/retention；
- coverage 与 unknown rate；
- reliability diagram、Brier/ECE 或 risk-coverage curve；
- OOD/遮挡/观测缺失下的 abstention；
- worst-group：suite、task、object、attack family、chunk norm/length；
- p50/p95/p99 latency 与 GPU/CPU memory；
- assessor 是否读取 attacked instruction（默认禁止）。

最低 gate 不应只看平均 accuracy。建议 preregister：

```text
coverage >= c_min
upper_confidence_bound(false_allow | supported attacked blocks) <= r_max
clean false reject <= q_max
OOD abstention >= a_min
p99 latency <= budget
```

数值阈值必须在查看 confirmatory victim outcome 前冻结。

## 6. 防止标签泄漏

禁止：

- 从同一 episode 的 future outcome 生成当前 assessment；
- 用 victim success/collision 选择 assessor checkpoint 或 threshold；
- 将攻击后的 instruction 当作 authoritative target；
- 用 VLA 的事后 explanation 填充 predicted effects；
- 在四臂之间重新运行随机 assessor，导致 ActionBlock/assessment 不同。

允许：

- 使用训练/qualification split 的 action-conditioned transitions；
- 用可信 task registry 提供 target/part/allowed effects；
- 在所有 arm 共享同一个预计算 assessment。

## 7. 与 Lean 的接口

L1 的 learned prediction 真实性是统计 claim，不交给 Lean。Lean 只接收：

- assessment digest；
- consumer 生成的 execution contract；
- exact ActionBlock/command/receipt/effect bindings。

换言之，Lean 能保证“系统执行了被这个 assessment/contract 指向的 block，并按证据规则推进状态”，不能
保证“assessment 对现实一定正确”。

## 8. Semantic-subtask 接口

当前公开 OpenPI 没有原生 semantic decode API，因此第一版 `Z_t` 是 consumer-side frozen selector 的
输出。只有当 exact `Z_t` 在动作生成前写入 policy prompt 并绑定返回的 ActionBlock 时，才具备结构上的
前置中间层身份；动作产生后的 explanation 不合格。是否产生有意义的行为因果效应，必须用固定
observation/noise 的 action-conditioning probe 测量，不能从 prompt wiring 本身推出。

## 9. 当前工程状态

`action_block_trace_adapter.py` 已能从 victim episode 中按 `policy_call_index` 分组实际消费的 raw actions，
输出 exact executed-prefix ActionBlocks，并保留原 policy chunk digest 作为 provenance。它明确不读取
reward、success、cost、collision 或 future observation，也不重建未执行的 chunk tail。

因此当前未完成项已缩小为 assessor 本身与资格化阈值，而不是 ActionBlock 抽取。
