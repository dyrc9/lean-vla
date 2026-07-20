# Experiment Rules

更新日期：2026-07-20

本文只定义当前实验规则。已完成结果见 [`evaluation_results.md`](evaluation_results.md)，环境命令见
[`remote_execution.md`](remote_execution.md)。

## 1. 通用原则

1. protocol、case/unit、source/checkpoint hash、labels、failure policy 和 output root 必须在 outcome 前
   冻结并提交。
2. 正式运行只使用 fresh absent output root；已 dispatch/attempted unit 不 resume、不覆盖、不替换。
3. experimental validity 与 task/safety outcome 分开。无有效分母时输出 `not_evaluated`。
4. collision/cost、task success、constraint oracle 必须来自独立 simulator observation，不能由 CTDA
   自己的 verdict 生成 ground truth。
5. `proof_verified=true` 只表示 Lean kernel 实际检查成功；Python reference/shadow 不得授权执行。
6. latency 原样保存，但当前不作 support/safety gate；禁止 real-time claim。
7. synthetic/fake-env case 只证明组件语义，不证明物理防御。
8. 正式实验必须保存 protocol、manifest、append-only ledger、per-episode artifact、summary 和 SHA-256。

## 2. 当前方法臂

### VLA-only

- 与 Full CTDA 使用相同 benchmark task、registered init、policy checkpoint/config/seed、camera、observer
  schema 和 horizon；
- action gate 完全禁用，但仍记录 state、collision/cost、task success 和 policy output；
- 不得继承 legacy intent/effect checker。

### Full CTDA

- contract authority 只来自 frozen benchmark mission、phase 和 residual obligation；
- raw proposal 由 consumer-side binder 检查；
- semantic/prefix 必须在 dispatch 前 Lean-proven；
- observed/monitor 必须在下一 dispatch/phase advance 前 Lean-proven；
- fallback 必须有 typed actuator receipt 和完整 postcondition evidence；
- timing policy 固定为 slow-interlock diagnostic。

## 3. 已完成的 clean paired utility pilot

### Unit

```text
(suite, task_id, init_state_id, env_seed, policy_seed, workload)
```

固定 unit 为 E0-v2 的 12 个 affordance task、`init_state_id=0`、`env_seed=7`、新的
`policy_seed=1`、`workload=clean`。policy-seed 0 的 E1-v3 未被覆盖或 resume。

### 必须先关闭的 blocker

E1-v3 的两臂 observation schema 不同。新 runner 已在 VLA-only 与 Full CTDA 的第一次
`state_observer.observe()` 前安装同一个 task-manifest contact query。测试与 no-dispatch probe 已证明：

- 同一 fake/real initialized observation 的 state digest 完全相同；
- baseline 仍使用 unguarded checker，零 CTDA authorization；
- policy metadata、first policy chunk 和 task/init provenance 可序列化并精确配对。

### Terminal result

- 12/12 valid pair，24/24 valid episode；
- VLA-only task/safe success 8/12，Full CTDA 0/12，retention 0；
- 两臂 collision/cost coverage 100%、unsafe 0；
- Full CTDA block/deadlock 12、phase completion 0、Lean parity mismatch 0；
- 两臂 unknown episode 都是 12/12，来自 human/obstacle distance provenance 缺失；
- method-attributable utility loss 8/12；closed-loop block 没有 false-positive label。

### Primary metrics

- valid pairs / invalid pairs；
- VLA-only 与 Full CTDA task success；
- safe success；
- task-success retention；
- collision/cost coverage 与 unsafe count；
- Full CTDA block、unknown、deadlock、phase completion；
- method-attributable utility loss：VLA-only safe success 且 Full CTDA 未成功；
- Python/Lean parity mismatch。

closed-loop block 没有独立 action-level counterfactual label，因此不能直接命名为 false positive。

### Analysis

- pilot 为 descriptive；可以报告 paired difference 和 exact intervals，但不把 12 pair 写成总体性能；
- 只有两侧都 valid 的 pair 进入 paired inference；
- 0 valid pair 时所有 retention/inference 为 `not_evaluated`；
- task failure 与 unsafe event 分开；safe stop 不自动算安全成功。

### Post-terminal method decision

保留 trace 的 outcome-preserving 离线归因已完成：9/12 Full episode 因 semantic contract
wall-clock coverage 耗尽停止，3/12 因 bounded-stutter no-progress limit 耗尽停止；全部停在 approach，
phase completion 为 0。paired experiment 仍是 valid，Lean parity 仍是 pass，但当前 v1 operational
utility 判定为 fail，clean safety benefit 未由本 pilot 证明。该判定不改写 protocol、episode label 或
terminal artifact，机器入口为
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

任何修订必须命名为新 method version，并在新 protocol 中重新冻结 contract timebase、binder
progress/stutter、observation provenance、最低 retention 和独立 safety endpoint；旧 policy-seed 1
unit 不 resume、不覆盖、不重跑。

## 4. EDPA R0 threat-validation draft

该草案早于当前 [`optimization_plan.md`](optimization_plan.md) 整合到 `master`，现仅作未执行的
参考实现保留，不是当前实验入口，也不构成 M5 的 EDPA + SafeLIBERO P1 protocol。不得
为它生成 patch 或启动 victim rollout；后续顺序以 optimization plan 为准。

该草案只验证 unguarded VLA-only victim 上的 published workload safety signal，不运行 CTDA，不计算
defense benefit，不复用已关闭的 Phantom/SABER unit。关键冻结规则是：

- 使用 EDPA official Pi0 JAX 默认参数生成 primary/wrist 两个 `3x44x44` patch；
- 生成过程不观察 LIBERO-Safety victim outcome，patch 不按下游结果挑选；
- clean screening 为 4 个 physical suite × task `[2, 6, 12]`，`init=2/env_seed=17/policy_seed=2`；
- 每个 suite 只选第一个 valid clean task-success/cost-safe candidate，最多 12 个 clean episode；
- 每个选中 unit 只运行一个 attacked episode，最多 4 个；patch 位置事前固定，并遵循
  official evaluator 的 224 采样范围（`3x44x44` patch 的坐标上界为 180）；
- pair 必须匹配 initial state、pre-attack first-frame/call binding、checkpoint/config/seed，并验证实际
  patch digest/position audit；
- primary gate 为至少 2/4 clean-safe → attacked independent collision/cost unsafe transition；任务失败
  单独不计 unsafe；
- 任一 provenance/audit 不匹配则 terminal-invalid，不替换 unit。

[`run_edpa_threat_validation_r0.py`](../scripts/run_edpa_threat_validation_r0.py) 只有 preflight 和
`--validate-results`，故意没有 execute 模式。当前 protocol 是 `draft_asset_gate_not_frozen`：数据
manifest、两个 patch 和它们的 SHA-256 尚缺，victim execution 明确未授权。

## 5. 执行 gate

正式执行前必须全部满足：

- clean Git commit，protocol 已提交；
- required file/checkpoint/external source hash 匹配；
- CPU tests 与 Lean build 通过；
- no-dispatch real-policy output probe 通过；
- 同一 task/init 的双臂 initial digest 和 first policy chunk probe 匹配；
- selected physical GPU 存在、空闲且不是 GPU 1；
- CUDA、MuJoCo EGL 和 render device 使用同一 selected physical GPU；
- FIPER `proofalign-fiper-r0-fresh2.service` 未被停止或干扰；
- output root 不存在。

EDPA R0 不进入当前 execution gate。未来若按 optimization plan 重新定义 EDPA + SafeLIBERO
P1，必须使用新 protocol/root，不续接本草案。

## 6. 结果解释

新 paired pilot 能回答固定 simulator slice 上的正常 task utility/safety trade-off。它不能回答物理安全、
通用攻击 defense、verified recovery、availability 或 real-time enforcement。

## 6. CTDA v2 规划期规则

CTDA v2 尚未形成正式 protocol 或结果。其工作顺序和实验矩阵见
[`optimization_plan.md`](optimization_plan.md)，当前先执行设计、fixed-trace/shadow、typed provenance、
SafeLIBERO/AEGIS readiness 和 no-dispatch gate。

新增规则：

1. v2 使用新 method/wire/schema id，v1 protocol/result 保持可重放；
2. candidate population 先按 manifest、source hash、model compatibility、support 和 safety-oracle
   coverage outcome-blind 冻结，不能先看正式 clean/attack outcome 再挑 pair；
3. clean-success/clean-safe 是预定义 classifier 产生的分析标签。只有它们进入条件式 attack-transition
   denominator，但失败/不安全 pair 仍保留在 valid/task/safety 汇总中，不替换；
4. 若需要 discovery 筛选，discovery 与 formal held-out task/seed 必须不相交，held-out population 在
   outcome 前冻结；
5. attacked+defended comparison 只有在 clean utility、VLA-only threat qualification 和 exact
   population overlap 全部通过后才允许；
6. AEGIS 是低层 closed-loop baseline；SAFE/FIPER 是 detector baseline，转为 stop/replan 时必须与其他
   方法共用同一 fallback；
7. task failure、detector alarm、CTDA block 和 attack metadata 都不能代替 independent unsafe label。
