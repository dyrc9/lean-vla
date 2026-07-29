# v12.2/v12.3 多关节恢复资格实验 checkpoint

> 状态：2026-07-29 terminal。全部实验均为 no-outcome qualification；不加载 VLA、不派发
> policy action、不读取 reward/success/cost/collision。该 checkpoint 不覆盖 v11、v12.1 或
> v12.2 的 non-pass，也不授权 clean/attacked efficacy rollout。

## 1. 本轮优化

本轮沿着 v12.1 暴露的单关节、固定 10 步恢复和 shadow/replay identity 问题，完成了三项改动：

1. 新增 typed recovery runtime：旧 policy authorization 在恢复前撤销；恢复命令使用独立、
   one-use authorization 和逐步 receipt；完成后生成 fresh state epoch，旧授权和 recovery
   authorization 均不可 replay。
2. 将固定 10 步原语改为 shortest-safe-prefix：仍只从已经计算的冻结原语轨迹中选取前缀，不增加
   outcome feedback；选择能达到 safe margin 的最短前缀，减少过度恢复和跨越另一侧限位的风险。
3. 将 MuJoCo snapshot identity 分成完整 `MjSimState` 诊断身份与可信机械臂
   `qpos/qvel` 身份。前者继续完整记录，但只有后者属于当前 recovery transaction 的安全边界。

## 2. 工程 pilot

| 阶段 | Population | Coverage / completion | 主要结果 |
|---|---:|---:|---|
| 固定 H=10 多关节 pilot | 7 joints × 2 sides | 12/14 | joint 1 双侧缺失 |
| shortest-safe-prefix pilot | 7 joints × 2 sides | 14/14 | 前缀长度 2–3 |
| typed actual-replay pilot | 7 joints × 2 sides | 14/14 | 31 recovery steps；receipt/fresh-policy 14/14；旧授权接受 0 |

typed pilot 的最大 shadow/replay 末态机械臂 qpos 误差为 `0.0091053 rad`，最小 replay terminal
margin 为 `0.1562849 rad`。这些 pilot 用于冻结正式协议，不作为最终 population 估计。

## 3. v12.2 多关节正式资格

冻结协议：
`experiments/proofalign_prefix_recovery_v12_multijoint_qualification_protocol.json`。
population 为 15 个与既有 outcome population 隔离的 task/init pair × 7 joints × 2 sides，共
210 个合成注入案例。

| 指标 | 结果 |
|---|---:|
| Valid / baseline trigger | 210/210 |
| Recovery candidate coverage | 209/210 = 99.52% |
| Worst-suite coverage | 98.57% |
| Worst joint-side coverage | 93.33%（joint 1 upper） |
| Selected predicted terminal safe | 209/209 |
| Actual replay terminal safe / completion | 209/209 |
| Hard-limit crossing / transient violation | 0 / 0 |
| Receipt command identity | 100% |
| Old-policy / recovery replay accepted | 0 / 0 |
| Fresh-policy state binding | 100% |
| Shadow/replay within 0.02 rad | 208/209 = 99.52% |
| 最大 shadow/replay qpos 误差 | 0.0355449 rad |
| Selected prefix mean / max | 2.225 / 4 steps |
| Policy load / dispatch / outcome read | 0 / 0 / 0 |

正式分类保持
`prefix_recovery_v12_multijoint_qualification_nonpass`。唯一失败 gate 是完整 simulator snapshot
restore identity：`201/210 = 95.71%`，低于冻结的 100%。9 个失败都发生在每个环境第一次
`joint 0 lower` 注入；它们的可信机械臂状态恢复、实际 recovery completion 和命令身份均通过。

## 4. v12.3 snapshot 边界资格

冻结协议：
`experiments/proofalign_recovery_snapshot_v12_qualification_protocol.json`。它重放 v12.2 已冻结的
selected prefix（唯一 abstention 使用 hold），只验证状态恢复边界，不重新选择候选。

| 指标 | 结果 |
|---|---:|
| Trigger full `MjSimState` bitwise identity | 210/210 |
| Trigger trusted arm qpos/qvel bitwise identity | 210/210 |
| Harness trusted arm qpos/qvel bitwise identity | 210/210 |
| Harness full `MjSimState` bitwise diagnostic | 201/210 |
| 非机械臂差异值数量 | 40 |
| 最大绝对差异 | 2.220446049250313e-16 |
| Probe env steps | 466 |
| Policy load / dispatch / outcome read | 0 / 0 / 0 |

v12.3 分类为 `recovery_snapshot_v12_qualification_pass`。它证明 9 个 full-state mismatch 来自不在
trusted arm boundary 内的机器精度级诊断差异，而不是机械臂 `qpos/qvel` 恢复错误；它不把
v12.2 的原资格分类改写为 pass。

## 5. 当前结论与下一步

当前已有一版明显优于 v12.1 的新结果：覆盖从单一 joint-5 upper 扩到 7 joints × 双侧，正式实验
完成 209/210 个案例，所有被选恢复均实际安全完成，typed authorization/receipt/replay/fresh-state
边界全部通过。剩余主要缺口是 joint-1 upper 的 1/15 coverage 和一个案例超过 0.02 rad 的
shadow/replay 容差。

下一步只授权 no-outcome policy-prefix predictive-shadow qualification：对真实 policy prefix 做
只读风险预测、恢复选择和 fresh replan 边界验证。完成前仍不启动 clean 或 attacked rollout。
