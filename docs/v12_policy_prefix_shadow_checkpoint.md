# v12.4a/v12.4b policy-prefix shadow checkpoint

> 状态：2026-07-29 terminal。该 checkpoint 只覆盖 no-outcome、fixed-recorded-prefix
> controller-shadow mechanics；不覆盖 fresh policy inference、clean utility、attacked efficacy、
> deployment perception 或物理安全，也不授权 clean/attacked rollout。

## 1. fresh-policy 工程启动为何停止

原计划是在独立 reset state 上加载冻结 OpenPI π0.5，并对每个 nominal / synthetic-pressure
observation 生成 fresh 10-step prefix。资源预检选择 policy GPU1、EGL GPU0；checkpoint restore
在第一次 policy inference 前因显存不足 fail closed：

| 指标 | 结果 |
|---|---:|
| Policy GPU preflight used / total | 25,428 / 49,140 MiB |
| 失败阶段 | checkpoint restore |
| Policy inference | 0 |
| Simulator case | 0 |
| Live dispatch / outcome read | 0 / 0 |

终态分类为 `policy_prefix_shadow_v12_policy_load_resource_nonstart`。该结果只说明当前共享 GPU
资源不足，不是方法 non-pass。失败 manifest 被保留，fresh-policy qualification 在资源 gate
重新满足前不启动。

## 2. fixed-prefix 机械资格边界

为了继续验证 controller snapshot，而不伪装成 fresh-policy 证据，v12.4a 从冻结的 v11 clean
VLA-only trace 中机械提取第一次实际传给 `env.step` 的10个动作：

- formal 为15个 prefix，pilot 为另外3个 prefix；
- population 是 outcome-known，但提取和本轮 runner 不读取 reward、done、task success、cost、
  collision 或 terminal classification；
- 每个 prefix 在独立 reset 的 nominal state 和一个 synthetic joint-pressure state 上各做两次
  read-only shadow，共30个正式案例、600个 shadow steps；
- policy load/inference、live policy dispatch、recovery dispatch 和 outcome read 全部为0。

该边界只回答：给定已经存在的 exact policy prefix，pre-dispatch simulator shadow 能否在恢复
controller/simulator 状态后稳定复现和做绑定决策。

## 3. pilot 定位与修复

第一版 snapshot 已包含 `MjSimState`、controller goal、simulator input 和 environment clock，但把
`controller.new_update=False` 恢复后，没有同步恢复 cached pose / joint / Jacobian / mass matrix。
第二次 replay 的第一个 control substep 因此复用了第一次 replay 的 terminal cache。

| Pilot | Cases | Repeat ≤0.02 rad | 最大误差 |
|---|---:|---:|---:|
| 初始 controller snapshot | 6 | 0/6 | 0.0894145 rad |
| 加入完整 controller cache | 6 | 6/6 | 2.78e-17 rad |

完整 controller cache 包括 pose、orientation、velocity、joint state、Jacobian、mass matrix、torque、
initial references 和 action scaling state。两个 pilot 都不读取 outcome。

## 4. v12.4a 正式结果

冻结协议：
`experiments/proofalign_fixed_policy_prefix_shadow_v12_qualification_protocol.json`。

| 指标 | 结果 |
|---|---:|
| Valid cases | 30/30 |
| Nominal exact allow | 15/15 |
| Worst-suite nominal allow | 5/5 |
| Synthetic current trigger | 15/15 |
| Synthetic recovery-required | 15/15 |
| Shadow/reference risk agreement | 30/30 |
| Trusted arm / controller / input / clock restore | 100% / 100% / 100% / 100% |
| Repeat trajectory ≤0.02 rad | 29/30 |
| 最大 repeat qpos 误差 | 0.0990581 rad |
| Exact allow identity | 100% |
| Blocked prefix 被授权 | 0 |
| Policy load / inference / live dispatch / outcome read | 0 / 0 / 0 / 0 |

v12.4a 通过预先冻结的 `≥95%` repeat-fidelity gate，分类为
`fixed_policy_prefix_shadow_v12_qualification_pass`。唯一尾部是
`obstacle_avoidance_human_task4_init17` 的 joint-1 upper synthetic case；两次 replay 风险判断一致，
但都进入 dense contact/limit dynamics，轨迹相差0.0991 rad。

## 5. v12.4b warm-start 后继

MuJoCo iterative constraint solver 会使用 `sim.data.qacc_warmstart`，而它不属于 `MjSimState`。
v12.4b 只增加这一 snapshot field，不改变 prefix、population、trigger margin、0.02 rad tolerance
或其他 controller state。结果-informed outlier pilot 先将同一案例的最大误差降到0，随后重新冻结并
运行同一30-case population。

冻结协议：
`experiments/proofalign_warmstart_policy_prefix_shadow_v12_qualification_protocol.json`。

| 指标 | v12.4a | v12.4b |
|---|---:|---:|
| Repeat trajectory ≤0.02 rad | 29/30 | 30/30 |
| 最大 repeat qpos 误差 | 0.0990581 | 4.44e-16 rad |
| `qacc_warmstart` restore | 未绑定 | 100% |
| Nominal exact allow | 15/15 | 15/15 |
| Synthetic recovery-required | 15/15 | 15/15 |
| Risk agreement | 30/30 | 30/30 |

v12.4b 分类为 `warmstart_policy_prefix_shadow_v12_qualification_pass`。full simulator-state bitwise
identity 仍为93.33%，最大非机械臂差异仍只有 `2.22e-16`；trusted arm、controller、simulator
input、clock 和 warm-start identity 全部为100%。

## 6. 当前结论与下一步

controller-aware fixed-prefix shadow mechanics 已关闭：exact prefix 的 allow/block 决策可绑定，
30/30 重复轨迹达到容差，合成当前风险全部进入 recovery-required，且没有 live dispatch 或 outcome
泄漏。

但论文仍不能声称 fresh policy-prefix qualification 完成，因为：

1. fixed prefixes 来自 outcome-known 历史 trace；
2. injected observation 没有重新输入 π0.5；
3. fresh checkpoint load 因共享 GPU 显存不足尚未启动；
4. synthetic injection 多次出现 MuJoCo `ncon=5000` warning；
5. 本轮没有实际 recovery、fresh replan 或任务 outcome。

下一步保持 no-outcome：等待独占/足量 GPU 后，运行已实现的 fresh-policy protocol；要求 policy
checkpoint load、30次 fresh inference、controller-aware shadow 和 typed recovery/fresh-state
transaction 同时通过。此前不生成 clean 或 attacked 协议。
