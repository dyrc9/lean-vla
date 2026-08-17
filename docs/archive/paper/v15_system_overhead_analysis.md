# v15.3 task-rollout systems overhead

该表由冻结 clean/attacked episode 逐文件校验 SHA 后重算，属于 checksum-bound
post-hoc 描述分析，不修改任何注册结论。

| Condition | Arm | Screens | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | 50 ms miss | 100 ms miss |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| clean | execution_only | 6016 | 15.67 | 39.30 | 54.31 | 65.92 | 104/6016 | 0/6016 |
| clean | dual | 5785 | 16.00 | 36.72 | 48.12 | 79.00 | 47/5785 | 0/5785 |
| attacked | execution_only | 7305 | 17.19 | 33.50 | 50.19 | 68.80 | 85/7305 | 0/7305 |
| attacked | dual | 6522 | 16.95 | 29.94 | 36.46 | 51.89 | 1/6522 | 0/6522 |

| Condition | Arm | Untriggered | Standard | Recovery | Deadlock | Shadow steps / screen (mean) | Candidates / screen (mean) |
|---|---|---:|---:|---:|---:|---:|---:|
| clean | execution_only | 5495 | 8 | 512 | 1 | 1.17 | 0.52 |
| clean | dual | 5561 | 17 | 207 | 0 | 1.08 | 0.23 |
| attacked | execution_only | 7193 | 6 | 106 | 0 | 1.03 | 0.09 |
| attacked | dual | 6504 | 3 | 15 | 0 | 1.01 | 0.02 |

## 解释边界

This artifact is a checksum-bound post-hoc descriptive analysis of the frozen clean and attacked task rollouts. It supports research-simulator screening-cost, deadline-miss, intervention-category, candidate-count, and shadow-step reporting. The four arms follow different trajectories, so cross-arm wall-time differences are not causal overhead estimates. The 50 ms result is diagnostic; the registered task protocols use a 100 ms screening budget. This artifact does not change the attacked qualification nonpass and does not establish hard real-time, hardware, arbitrary-attack, actuator-authority, or physical-safety claims.

尤其是：50 ms 是控制周期诊断，不是注册通过门；注册 task protocol 的 screening budget 是 100 ms。不同 arm 的任务轨迹和长度不同，因此不能把 cross-arm wall time 差直接解释为因果 overhead。
