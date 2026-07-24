# Confirmatory preregistration 说明

> 状态：旧 v1 设计在 outcome 前冻结，当前仅 audit/reuse；它不授权 GPU execution。population、seed、
> cluster bootstrap、invalid/replacement 规则可复用，但层定义已被 ActionBlock v3 及当前
> semantic-bound successor 架构 supersede。

## 旧设计中仍有效的部分

- 60 个 frozen base pairs；
- 每个 base pair 两个 seed replicates；
- clean/attacked VLA-only M2 共 240 episodes；
- attack producer 不看 victim outcome；
- 无 best-of-N、无失败替换、无 outcome-driven threshold/population revision；
- base-pair cluster bootstrap；
- M2 gate 后再启动四臂。

## 新四臂定义

| Arm | Intent–SemanticSubtask–ActionBlock | ActionBlock–Execution |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

旧 JSON 中 `intent_plan_enabled` / `plan_execution_enabled` 只作为 frozen legacy field 读取；新 runner
等价映射为 `intent_action_enabled` / `action_execution_enabled`，`intent_only` 也继续作为 schema arm
值。不得把这些兼容字段解释为要求 VLA 输出自由文本 plan。

## 新增 preregistration 必需项

在任何 L1/Dual outcome 前，semantic-bound amendment（推荐新建 v4、保持 v3 evidence immutable）必须
冻结：

- trusted task source、observation tap、secure split allowlist；
- task graph、skill-level `Z_t` vocabulary、prompt template 和 selector/config digest；
- selector qualification snapshot split、unknown/margin/OOD gate；
- ActionBlock canonical schema 和 adapter digest；
- local-checker data split、implementation/config 与 threshold；
- fixed observation/noise 的 action-conditioning probe；
- effect atom vocabulary；
- false-allow、coverage、clean false-reject、OOD abstention gate；
- contract compiler 与 observer；
- fixed-trace identity validator；
- Lean source digest、关键 theorem 和 scoped Python-equivalence evidence；
- latency/resource budget；
- threshold 不接触 M2/four-arm outcome 的证明。

`K=1` 是 primary design：四臂共享 exact proposal bytes。任何 `K>1` amendment 必须另外冻结 ordered
candidate set、每候选 assessment、base candidate index 和 deterministic L1 selection rule；不得继续
声称四臂 final command byte-identical。

## Claim boundary

M2 只确认攻击 foundation；fixed-trace 只确认 component identity/truth table；clean/attacked 四臂才估计
两层 efficacy。任何阶段都不提供完整物理安全保证。
