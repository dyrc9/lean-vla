# ActionBlock 后果评估器：设计与资格化

## 1. 为什么不需要高层规划输出

当前 π0.5-LIBERO/OpenPI 接口返回数值 action chunk。这不是方法缺陷，而是本项目要保护的原生边界：

```text
(trusted intent, current observation, concrete ActionBlock)
                           |
                           v
                predicted task-relevant effects
```

模型是否在内部形成离散计划不可识别，也不是核心 estimand。RT-H、π0.5 的 semantic subtask 或未来
支持 joint text/action 的模型，可以额外提供解释或辅助特征，但没有它们 L1 仍然定义良好。

## 2. Assessor 的输出

`ActionBlockAssessment` 必须在 block 产生后生成，并绑定：

- episode nonce、proposal index；
- ActionBlock digest；
- observation digest、state epoch；
- assessor id/version/kind 和生成时间。

它只输出有限、可评估的字段：

- `predicted_skill`；
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

### B. Learned outcome predictor

输入 `O_t` 与 `A_t`，预测 block 末端状态、对象/夹爪关系、接触风险和 task-progress atoms。可以用
state-space dynamics、latent world model 或 action-conditioned video predictor。它最接近 L1 的目标，
但必须单独处理 calibration、OOD 和 domain shift。

### C. Trusted shadow rollout

在独立 simulator/digital twin 中执行 block，抽取效果。它提供清晰的 counterfactual semantics，但存在
sim-to-real/sim-to-benchmark mismatch，且 latency 较高。

### D. 保守组合

第一版建议：

```text
analytic hard constraints
      ∧ calibrated learned outcome predictor
      ∧ disagreement/OOD abstention
```

shadow rollout 用于离线 qualification 和困难样本审计；不应在没有资源预算的情况下成为默认 online path。

## 4. 推荐的第一版 LIBERO assessor

对每个 7-DoF action chunk：

1. 解析 chunk 的末端位移、旋转、gripper 开合和长度；
2. 从当前 observation/state 提取 task object、part、robot/object relation；
3. 预测窗口末端的有限 atoms，例如 `approach:mug`、`grasp:mug`、`release:mug`、
   `contact:fixture`、`workspace_exit`；
4. 将可信 intent 编译为允许 target/part/region 和所需 progress atoms；
5. 对不支持的对象、严重遮挡、模型分歧或过长 chunk 返回 `unknown`。

注意：`predicted_skill` 是 consumer 对动作后果的分类，不是 VLA 输出的 plan。

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

## 8. 可选显式 plan 扩展

若未来 policy 原生输出并因果使用 language motion/subtask，可将其作为额外观测：

```text
optional policy plan -> cross-check with ActionBlockAssessment
```

这可提升解释性或提供新的攻击面，但不得改变核心两层定义，也不得把外部 assessor 生成的标签冒充 policy
plan。

## 9. 当前工程状态

`action_block_trace_adapter.py` 已能从 victim episode 中按 `policy_call_index` 分组实际消费的 raw actions，
输出 exact executed-prefix ActionBlocks，并保留原 policy chunk digest 作为 provenance。它明确不读取
reward、success、cost、collision 或 future observation，也不重建未执行的 chunk tail。

因此当前未完成项已缩小为 assessor 本身与资格化阈值，而不是 ActionBlock 抽取。
