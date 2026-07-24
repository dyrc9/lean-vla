# Confirmatory preregistration 说明

> 状态：旧 v1 设计在 outcome 前冻结，当前仅 audit/reuse；它不授权 GPU execution。population、seed、
> cluster bootstrap、invalid/replacement 规则可复用，但层定义已被 ActionBlock v3 架构 supersede。

## 旧设计中仍有效的部分

- 60 个 frozen base pairs；
- 每个 base pair 两个 seed replicates；
- clean/attacked VLA-only M2 共 240 episodes；
- attack producer 不看 victim outcome；
- 无 best-of-N、无失败替换、无 outcome-driven threshold/population revision；
- base-pair cluster bootstrap；
- M2 gate 后再启动四臂。

## 新四臂定义

| Arm | Intent–ActionBlock | ActionBlock–Execution |
|---|---:|---:|
| VLA-only | off | off |
| Intent–Action-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

旧 JSON 中 `intent_plan_enabled` / `plan_execution_enabled` 只作为 frozen legacy field 读取；新 runner
等价映射为 `intent_action_enabled` / `action_execution_enabled`。不得把旧字段解释为要求 VLA 输出 plan。

## 新增 preregistration 必需项

在任何 L1/Dual outcome 前，v3 amendment 必须冻结：

- ActionBlock canonical schema 和 adapter digest；
- assessor data split/checkpoint/config；
- effect atom vocabulary；
- false-allow、coverage、clean false-reject、OOD abstention gate；
- contract compiler 与 observer；
- fixed-trace identity validator；
- latency/resource budget；
- threshold 不接触 M2/four-arm outcome 的证明。

## Claim boundary

M2 只确认攻击 foundation；fixed-trace 只确认 component identity/truth table；clean/attacked 四臂才估计
两层 efficacy。任何阶段都不提供完整物理安全保证。
