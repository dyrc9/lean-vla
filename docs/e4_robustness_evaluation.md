# E4 Fail-Closed Robustness Evaluation

更新日期：2026-07-17

## 结论

E4 的安全鲁棒性部分已完成。正式 v2 矩阵记录 `36/36` case，包含 `1/1` 真实 Lean 正常对照和
`35/35` frozen fault case；全部满足事前固定的 fail-closed 或 control 断言。因此，可以声称：

> 在这套固定的 CPU/Lean 组件故障矩阵内，ProofAlign 的 verifier、wire binding、shadow gate、
> fake-env transaction 和 typed fallback receipt 路径表现为 fail closed。

这个结论不是物理安全、verified recovery、attack defense、实时性、可用性或任务完成度结论。

## 冻结范围与结果

| 层 | case 数 | 结果 | 实际约束 |
|---|---:|---:|---|
| real-Lean control | 1 | 1 pass | 正常 semantic request 必须 kernel proven 且 Python/Lean parity match |
| verifier failure | 2 | 2 pass | Lean 不可用或 replay timeout 时 proof=false、verdict=inconsistent、不得授权 |
| binding/gate/artifact | 4 | 4 pass | checker digest、canonical request id、shadow authorization、retained digest mutation |
| Lean wire faults | 19 | 19 pass | spec/nonce/state/monitor/contract/proposal/command/timebase/stale/replay、observed receipt/command/provenance/timestamp、monitor violation/rollback/cross-episode/provenance/missing completion |
| exact runtime contracts | 10 | 10 pass | unavailable/tampered pre-stage 零 fake-env dispatch，observed/monitor failure 零 phase advance，receipt tamper、unsafe/missing fallback evidence 均不得建立 success |

19 个 wire fault 都由真实 Lean replay 检查。负例的 `proof_verified=true` 表示 Lean 证明了拒绝、
`inconsistent`、`violated` 或 `safe_pending` verdict，并不表示动作获准。static fault 必须
`result.proven=false`；monitor fault 必须不能得到 `complete`。

10 个 runtime contract 是固定 pytest nodeid，而不是只检查日志文本。其中四个直接断言 fake-env
零派发或 phase 保持，六个断言 typed fallback receipt/postcondition 的完整性和失败闭合。

## v1 terminal-invalid 与 v2 amendment

第一次冻结执行没有终态矩阵。v1 runner 在写第三个 case 时把 `0.05` 秒诊断参数交给禁止浮点数的
CTDA wire serializer，因而在结果记录阶段异常退出：只形成 2 条 record，正式结论为
`not_established_no_terminal_matrix`。partial root 已原样保留，既未覆盖也未解释 case outcome。

v2 在新提交和新 output root 中重新冻结。它从 v1 原样继承全部 36 个 case、预期 verdict、pytest
nodeid、分类器、被测实现和“timing 非 gate”规则；唯一修改是把结果记录里的 timeout 从浮点秒改为
整数纳秒。v1 失败记录见
[`proofalign_e4_robustness_v1_failure.json`](../experiments/proofalign_e4_robustness_v1_failure.json)，
v2 amendment 见
[`proofalign_e4_robustness_protocol_v2.json`](../experiments/proofalign_e4_robustness_protocol_v2.json)。

## Artifact 与复核

正式结果目录为 `results/proofalign_e4_robustness_v2_20260717`。独立重算得到：

- 36 个唯一 record，全部 `passed=true`；
- manifest 174 个条目，missing/size/hash mismatch 为 0；
- manifest SHA-256：`70c436c5779a0abd527b3783192bd365d30fc1695bd97d46263955e2d84f042b`；
- records SHA-256：`6b0b6d107b0a731bd57a9cf0a9738997a015b7f0ca1bcdcebfb5ccb7a2bdfb25`；
- summary SHA-256：`5b6e7529e0d06a8dacfd11c20afcc29ecdbb6f499f8da06925ff5fc543278bd1`。

机器终态摘要见
[`proofalign_e4_robustness_terminal_summary.json`](../experiments/proofalign_e4_robustness_terminal_summary.json)。

## Claim boundary

本实验能回答“列出的组件故障出现时，当前实现是否拒绝授权、不推进 phase 或拒绝建立 fallback
success”。它不能回答：

- 未列入矩阵的新 fault、恶意进程、OS/硬件故障或密钥/producer compromise；
- 真实机器人或连续动力学是否安全；
- observation blackout 后是否完成物理恢复；
- 发布攻击 workload 上是否有 defense efficacy；
- 系统是否满足 control deadline 或具备高 availability；
- Full CTDA 是否保留任务完成度。

用户已明确允许先略过时间性能，因此 E4 本轮不设 latency gate。此前 Lean 单 stage 约
`0.9--1.3 s` 的负结果继续有效，系统仍只能按 slow-interlock/offline audit 表述。
