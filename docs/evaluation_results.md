# ProofAlign Evaluation Results

更新日期：2026-07-17

本文是 E0--E4 当前结果的唯一叙述性事实来源。逐阶段长报告已移入
[`archive/evaluations/`](archive/evaluations/)；正式数字以 `experiments/*.json` 和已提交的
`results/` artifact 为准。

## 1. 当前结论

ProofAlign 在冻结的 LIBERO-Safety affordance task slice 和固定 CPU/Lean fault matrix 内，已经得到
有限的 simulator safety preservation、fail-closed 组件语义和一个有效 clean utility trade-off pilot。
该 pilot 的 Full CTDA task/safe-success retention 都是 0，说明当前方法在该 slice/seed 上有很大
completion loss。当前不能证明总体 task utility、物理安全、verified recovery、通用 attack defense
或 real-time enforcement。

简写为：

> 安全机制在已测范围内按设计拒绝不充分授权；有效 clean 配对显示当前实现以 0 retention 换取这种
> 保守行为，completion trade-off 很大。

## 2. 结果总表

| 阶段 | 正式状态 | 结果 | 可以支持的结论 |
|---|---|---|---|
| method validity | pass | 固定单任务 5/5 prefix，16 个唯一 Lean request proof/parity 通过 | persistent contract 和 staged evaluator 能闭环运行 |
| E0 support | complete | `12 supported / 63 unsupported` | 非实时支持范围固定为 affordance task `0,1,2,3,5,6,7,8,10,11,12,13` 的 init 0 |
| E1 clean utility | complete, scoped pilot | seed-1 新 pilot 12/12 valid pair；VLA-only 8/12、Full CTDA 0/12 task/safe success | 固定 simulator slice/seed 上 retention 0、method-attributable utility loss 8/12 |
| E3 clean safety | complete | 12/12 valid preserved；117/117 dispatch 有完整负 collision/cost；0 hard-invariant failure | 固定 clean simulator slice 上 observed safety preserved |
| E3 post-dispatch | complete, primary unknown | 0 contained / 0 failed / 12 unknown | 行为上全部 fail closed 并 zero-hold，但冻结 labeler 的 receipt schema gap 阻止正式 containment claim |
| E4 robustness | complete | v2 36/36 pass；1 control + 35 fault | 固定 CPU/Lean 组件故障矩阵内 fail closed |
| timing | negative | Lean 单 stage 约 0.9--1.3 s；历史 100 ms/50 ms gate 有 miss | 只能表述为 slow-interlock/offline audit |

## 3. E0：支持范围

E0 v1 的严格支持集合为 `0/75`。v2 增加 exact BDDL-bound manifest、独立 contact-part observer、
registered-init 和 typed zero-hold fallback safety qualification。时间性能被明确移出支持分类后，最终
固定 12 个 supported unit：

```text
suite: affordance
task_id: 0,1,2,3,5,6,7,8,10,11,12,13
init_state_id: 0
env_seed: 7
```

task 4/9/14 因跨 seed 初态 digest 不一致而排除。其余 suite/task 不在当前 compiler 和 fallback
支持范围。机器入口：

- [`proofalign_e0_protocol_v2.json`](../experiments/proofalign_e0_protocol_v2.json)
- [`proofalign_e0_v2_gate_decision.json`](../experiments/proofalign_e0_v2_gate_decision.json)
- [`proofalign_e0_v2_fallback_audit_summary.json`](../experiments/proofalign_e0_v2_fallback_audit_summary.json)

## 4. E1：clean utility trade-off

### 旧 terminal-invalid runs

- v1：physical CUDA/EGL 绑定错误，environment construction 前失败；
- v2：真实 policy output 的 nested metadata 在 dispatch 前被旧 serializer 拒绝；
- v3：24 个 episode 均写出，但 Full CTDA arm 在初态 observer 中安装 contact query，VLA-only arm
  没有，导致 12/12 pair 的 initial-state digest schema 不一致。

v3 中 VLA-only `7/12` task success 和 Full CTDA `0/12` 只是无效配对 artifact 内的诊断值，不能计算
retention，也不能解释为正式 completion trade-off。已 dispatch 的 policy-seed 0 pair 不得覆盖或当作
同一实验重跑。

### 新 policy-seed 1 pilot

独立 protocol/runner 在两臂第一次 state digest 前安装相同的 task-manifest contact query，并把实际
OpenPI RNG 固定为新 `policy_seed=1`。启动前 12/12 pair 的 initial digest、E0 frozen digest 和 first
policy chunk 均匹配，24/24 probe arm 的 `env.step_count=0`。唯一 fresh run 得到：

- 12/12 valid pair，24/24 valid episode，0 excluded；
- VLA-only task success `8/12`，safe success `8/12`；
- Full CTDA task success `0/12`，safe success `0/12`；
- task-success retention `0/8 = 0`，safe-success retention `0/8 = 0`；paired difference 为
  `-8/12 = -0.667`，冻结 bootstrap 95% interval `[-0.917, -0.417]`；
- method-attributable utility loss `8/12`；
- VLA-only collision/cost coverage `3129/3129`，Full CTDA `117/117`，observed unsafe 都是 0；
- Full CTDA `12` 个 block episode、`12` deadlock、`0` phase completion；2640/2640 Lean artifact
  proof-verified 且 Python/Lean parity match；
- 两臂各 `12/12` episode unknown，原因都是缺少 human-hand 与 obstacle distance provenance。
  experimental validity、task/safe success、unsafe 和 unknown 是分开的冻结标签，因此 unknown 不会
  后验改成 invalid，也不会抹去按 collision/cost 规则计算的 safe success；
- closed-loop block 没有独立 action-level counterfactual label，只报告 intervention，不报告 false
  positive rate。

该结果只支持固定 12-task simulator slice 和该 policy seed 上的描述性 trade-off。它不表明 CTDA
“总体上”有 0 utility，也不提供物理安全、攻击防御、availability 或 real-time 结论。

机器入口：

- [`proofalign_e1_clean_utility_terminal_summary.json`](../experiments/proofalign_e1_clean_utility_terminal_summary.json)
- [`proofalign_e1_clean_utility_protocol.json`](../experiments/proofalign_e1_clean_utility_protocol.json)
- `results/proofalign_e1_clean_utility_seed1_20260717/`
- [`proofalign_e1_v3_terminal_invalid_summary.json`](../experiments/proofalign_e1_v3_terminal_invalid_summary.json)
- `results/proofalign_e1_clean_pilot_v3_20260717/`

## 5. E3：安全性

### Clean simulator safety

12/12 record valid 且 `safety=preserved`：

- 117/117 policy dispatch 有完整 collision/cost observation，均为负；
- 117 个 hard-invariant sample 全部为 true；
- 12 次 block 均发生在 pre-dispatch，phase advance 为 0；
- Lean proof 与 Python parity 无失败；
- task success 为 0/12，但这是未配对的 utility 诊断；
- fresh run 没有在线 fallback，fallback 仅由此前 12 unit × 3 seed 的 36/36 zero-hold safety
  repetitions 支持。

机器入口：

- [`proofalign_e3_safety_terminal_summary.json`](../experiments/proofalign_e3_safety_terminal_summary.json)
- `results/proofalign_e3_safety_20260717/`

### Post-dispatch observation failure

12/12 episode 都在一次真实、静态授权 dispatch 后遇到一次 collision/cost observation blackout；实际
行为均为 monitor `unknown`、phase 保持 `approach`、`replan`、exact zero-hold，以及恢复后的完整负
oracle/postcondition。冻结 primary labeler 要求 typed receipt schema 中不存在的顶层
`integrity_verified`，所以正式结果必须保持 `12 unknown`。后验 12/12 typed receipt integrity pass
只解释 schema gap，不升级分类或授权重跑。

机器入口：

- [`proofalign_e3_postdispatch_terminal_summary.json`](../experiments/proofalign_e3_postdispatch_terminal_summary.json)
- [`proofalign_e3_postdispatch_receipt_audit.json`](../experiments/proofalign_e3_postdispatch_receipt_audit.json)

## 6. E4：fail-closed robustness

v1 runner 在第三个 case 写记录时因 float timeout 与 wire serializer 不兼容而 terminal-invalid；partial
root 原样保留。v2 amendment 只把该值记录为整数纳秒，未改变 case、预期 verdict、classifier、
pytest nodeid 或被测实现。

v2 正式结果：

- 36/36 case pass；
- 1/1 real-Lean control；
- 35/35 fault case fail closed；
- 覆盖 Lean unavailable/timeout、checker/request/shadow/artifact、19 个 wire fault 和 10 个
  fake-env/runtime transaction/fallback contract；
- 174 个 manifest entry 独立重算无 missing/size/hash mismatch。

机器入口：

- [`proofalign_e4_robustness_terminal_summary.json`](../experiments/proofalign_e4_robustness_terminal_summary.json)
- [`proofalign_e4_robustness_protocol_v2.json`](../experiments/proofalign_e4_robustness_protocol_v2.json)
- `results/proofalign_e4_robustness_v2_20260717/`

## 7. 外部线

- Phantom R0b 找到 camera workload signal，但 held-out R1 只有 1/4 independent cost/collision
  transition，低于冻结的 2/4 gate，停止；
- SABER R1 在第一个 record artifact gate fail closed，未运行 victim，停止；
- SAFE partial run 无 terminal manifest，未复现；
- FIPER fresh1 无 terminal manifest；fresh2 当前由 `proofalign-fiper-r0-fresh2.service` 在 GPU 1
  后台运行，只有 terminal manifest/validator 全通过才能记为 reproduced。

这些外部结果不改变 E0--E4 自身结论。

## 8. 下一证据缺口

优先解释新 clean pilot 的 completion loss：从 retained trace 区分 raw binder block、persistent
no-progress、observation provenance unknown 与 phase progression 的贡献。该分析不能把 closed-loop
block 后验命名为 false positive；独立 action-level counterfactual 需要新冻结的 fixed-trace protocol。
在理解 0 retention 前不扩大 task/seed 范围，也不把该 simulator pilot 推广为总体或物理安全证明。
