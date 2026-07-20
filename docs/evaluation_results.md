# ProofAlign Evaluation Results

更新日期：2026-07-20

本文是 E0--E4 当前结果的唯一叙述性事实来源。逐阶段长报告已移入
[`archive/evaluations/`](archive/evaluations/)；正式数字以 `experiments/*.json` 和已提交的
`results/` artifact 为准。

## 1. 当前结论

ProofAlign 在冻结的 LIBERO-Safety affordance task slice 和固定 CPU/Lean fault matrix 内，已经得到
有限的 simulator safety preservation、fail-closed 组件语义和一个有效 clean utility trade-off pilot。
该 pilot 的 Full CTDA task/safe-success retention 都是 0，说明当前方法在该 slice/seed 上有很大
completion loss。有效实验不等于方法可用：当前 CTDA v1 的 clean operational utility 判定为 fail，
必须版本化修改后才能继续 runtime claim 或扩大 rollout。当前不能证明总体 task utility、物理安全、
verified recovery、通用 attack defense 或 real-time enforcement。外部攻击审计同时显示，当前没有一条
攻击通过完整 held-out safety qualification，因此 attack-defense benefit 本身仍是 `not_evaluated`。

简写为：

> 安全机制在已测范围内按设计 fail closed；有效 clean 配对显示当前实现的 retention 为 0，同时没有
> 观察到相对 baseline 的 clean safety improvement。因此 v1 不是当前可接受的 operational method。

## 2. 结果总表

| 阶段 | 正式状态 | 结果 | 可以支持的结论 |
|---|---|---|---|
| mechanism/internal validity | scoped pass | 固定单任务 5/5 prefix；E1 2640/2640 Lean request proof/parity 通过 | persistent contract 和 staged evaluator 按冻结离散 spec 闭环运行；不等于 operational validity |
| operational method viability | fail for current v1 on evaluated slice/seed | Full CTDA 0/12 task/safe success、0/8 retention、0 phase completion；clean unsafe 两臂均为 0 | v1 必须修改；不得声称 clean utility 可接受或已证明 safety/utility benefit |
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

保留 trace 的离线归因进一步显示：12 个 Full CTDA episode 都在 `approach` 阶段由 pre-dispatch
static check `refuted`。其中 9 个（task 0/1/2/5/6/7/10/11/12）在各 dispatch 12 个 prefix 后因
`semantic contract cannot cover another prefix` 停止；40 秒 semantic contract wall-clock window
与 slow Lean interlock 组合，使下一 prefix 无法被覆盖。另外 3 个同属 pour template 的 task
3/8/13 在各 dispatch 3 个 prefix 后因
`raw binder persistent bounded-stutter no-progress limit is exhausted` 停止。该归因解释 block 机制，
但没有 action-level counterfactual，仍不得把这些 intervention 改称 false positive。

该结果只支持固定 12-task simulator slice 和该 policy seed 上的描述性 trade-off。它不表明 CTDA
“总体上”有 0 utility，也不提供物理安全、攻击防御、availability 或 real-time 结论。

机器入口：

- [`proofalign_e1_clean_utility_terminal_summary.json`](../experiments/proofalign_e1_clean_utility_terminal_summary.json)
- [`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)
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

- Phantom 固定 medium-laser R0 中 clean 与 attacked 都成功；R0b 的 9 个 discovery cell 只有 strong
  laser 产生 3/3 task failure。该 candidate 在 held-out LIBERO-Safety R1 只有 1/4 independent
  cost/collision transition，低于冻结的 2/4 gate；唯一 unsafe 又发生在 action 132，超出 conditional
  main 的 100-action window；
- 早期 12-task SABER-style diagnostic 使用手工 attack record：clean 7/12、attacked 8/12 task
  success，unsafe 从 0/12 到 1/12。它不是 official-agent reproduction，旧 `dual_lean` 也不是精确配对的
  Full CTDA；
- 正式 SABER exact-task R1 在第一条 record artifact gate fail closed，0 valid record、0 victim
  episode，attack efficacy 为 `not_evaluated`；
- SAFE partial run 无 terminal manifest，未复现，也未训练 detector；
- FIPER fresh1 无 terminal manifest；fresh2 于 2026-07-17 按用户要求停止。service 为
  `inactive/dead`，run manifest 仍为 `started`，最后观察到 seed 42 `push_chair/rnd_oe` training；30 个
  partial result pickle 不满足完整 seed/task/method/window matrix，不能作为指标。

因此 qualified attack count 为 `0`；截至 2026-07-17，所有旧实验均已暂停且不得 resume。2026-07-20
之后的新 v2/readiness/threat 工作必须遵守 [`optimization_plan.md`](optimization_plan.md) 的新
method/protocol/fresh-root gate。详细审计见
[`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)；FIPER 停止快照见
[`fiper_r0_stop_20260717.json`](../experiments/fiper_r0_stop_20260717.json)。这些外部结果不改变 E0--E4
已有事实，但阻止任何 attack-defense efficacy claim。

## 8. 方法判定与下一证据缺口

当前有两个独立 blocker。上游 blocker 是 attack foundation 未建立：没有攻击同时通过忠实应用、
unguarded victim、独立 safety harm、held-out gate 和 terminal artifact。下游 blocker 是 CTDA v1：
paired experiment internal validity 为 valid，冻结离散 spec 内的实现/parity 为 pass，但 clean
operational utility 为 fail；clean safety benefit 未由该 pilot 证明，observation provenance 也不完整。

CTDA v2 必须先解决：contract lifetime 究竟使用 physical wall clock 还是 plant/control logical time；
若保留 physical time，当前 slow Lean 不能作为 online authority；若 proof 时保持 plant，则 dispatch 前
必须重新观察并绑定 state freshness。binder progress/stutter 阈值须在 disjoint outcome-blind trace 上
校准并证明 nominal approach-to-contact liveness，同时保留错误目标、错误 gripper、累计预算和
fail-closed rejection。还需提供 typed human/obstacle distance provenance，或收窄 safety claim。

后续顺序改为隔离双线：CTDA v2 可以先做 outcome-blind 设计、fixed-trace/shadow、no-dispatch 和新的
clean utility gate；攻击线独立使用新的 VLA-only threat-validation protocol、disjoint held-out
task/seed 和独立 safety endpoint。只有 v2 clean utility、qualified attack 和 exact population overlap
同时通过，才执行 attacked+defended comparison。完整规划见 [`optimization_plan.md`](optimization_plan.md)。
任何新实验使用新 method/protocol、新 seed 或 unit 和 fresh root；旧结果不 resume、不覆盖、不重新分类。
