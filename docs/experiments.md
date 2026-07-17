# Experiment Rules

更新日期：2026-07-17

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

## 3. 下一 clean paired pilot

### Unit

```text
(suite, task_id, init_state_id, env_seed, policy_seed, workload)
```

固定候选：E0-v2 的 12 个 affordance task、`init_state_id=0`、`env_seed=7`、新的
`policy_seed=1`、`workload=clean`。policy-seed 0 已被 E1-v3 使用，不得覆盖。

### 必须先关闭的 blocker

E1-v3 的两臂 observation schema 不同。新 runner 必须在 VLA-only 与 Full CTDA 的第一次
`state_observer.observe()` 前安装同一个 task-manifest contact query。测试必须同时证明：

- 同一 fake/real initialized observation 的 state digest 完全相同；
- baseline 仍使用 unguarded checker，零 CTDA authorization；
- policy metadata、first policy chunk 和 task/init provenance 可序列化并精确配对。

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

## 4. 执行 gate

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

## 5. 结果解释

新 paired pilot 能回答固定 simulator slice 上的正常 task utility/safety trade-off。它不能回答物理安全、
通用攻击 defense、verified recovery、availability 或 real-time enforcement。
