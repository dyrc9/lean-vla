# Project Status

更新日期：2026-07-20

## 当前状态

当前所有实验、simulator/GPU rollout 和外部 baseline execution 均暂停。用户已授权并完成
`proofalign-integrity-v1` 本地最小原型施工；它只有 in-memory no-action sink、unit tests 和 Lean build，
不产生实验 outcome。VLA-only 发布攻击复现与 threat qualification 仍是恢复实验后的第一优先级。
既有 CTDA、Ed25519、typed geometry 和 AEGIS CBF/QP 结果继续作为冻结历史保留。

方法方向已经收缩为“两关系、两不变量、三 transaction”和 VLA-only/Intent-only/Execution-only/Dual
四臂消融。现有 CTDA v2 certificate/rebind/六阶段 wire 是可 replay 的历史原型，不再预设为下一版公开
架构。最小 core 已实现，但 fixed-trace、clean/attack runner 与实验矩阵仍 deferred/unauthorized。

| 工作线 | 状态 | 当前结论 | 下一步 |
|---|---|---|---|
| minimal integrity prototype | local implementation complete | 五组件、三 transaction、四臂 switch、28 个 focused unit、Lean core 已接通；无 online wire/refinement/simulator | 保持 no-action；只做本地测试与代码审计，不产生 outcome |
| CTDA v1/v2 | frozen/history | v1 clean utility 不合格；v2 core/wire 与 no-action 基础结果已保存但不再定义下一架构 | 不运行、不扩展、不接入新 prototype |
| E0 support | complete | 12 个 affordance/init0 non-real-time supported unit | 新实验不得越过支持范围，除非先做新 support audit |
| E1 utility | scoped pilot complete | policy-seed 1 的新 pilot 为 12/12 valid pair；VLA-only 8/12、Full CTDA 0/12 task/safe success，retention 0 | 负结果和归因已保存；不扩写总体结论或重跑旧 unit |
| E3 safety | scoped evidence complete | clean 12/12 preserved；post-dispatch 行为 fail closed，但正式 primary 12 unknown | 不改写旧分类；新的独立 challenge 才能增加 containment 证据 |
| E4 robustness | complete | 35/35 frozen fault case fail closed | 只保留 scoped component claim |
| timing | negative/deferred | Lean 0.9--1.3 s/stage，不满足实时控制 | 不优化，不恢复 real-time claim |
| attack foundation | paused / next experiment | Phantom held-out 仅 1/4；旧 SABER exact-task R1 为 0 record/0 victim，qualified attack count 为 0 | 当前不执行；恢复后从 fresh SABER protocol/root 和 immutable producer gate 继续 |
| safety foundation | frozen/deferred | R0--R3、state r1、OpenRegion、signed geometry/CBF 均通过；所有新增 gate 的 `env.step/dispatch=0` | 不继续 perception、budget、recovery 或 CTDA support 工作 |
| external baselines | frozen/deferred | AEGIS 只有 no-action core；SAFE partial、FIPER stopped | 不运行 AEGIS/SAFE/FIPER；当前只运行 unguarded VLA-only victim |

完整数字见 [`evaluation_results.md`](evaluation_results.md)。

## 方法 validity 判定

“实验有效”和“方法可用”必须分开：

- 新 E1 paired experiment 是有效的，12/12 pair 配对与 artifact validation 均通过；
- 2640/2640 Lean proof/parity 通过，说明实现执行了冻结的离散 spec，但不验证阈值、state abstraction
  或 utility 本身；
- 当前 CTDA v1 的 clean operational utility 判定为 **fail on the evaluated slice/seed**：baseline 的
  8 个 safe completion 一个也未保留，Full CTDA 0 phase completion；
- 该 clean pilot 两臂 observed unsafe 都是 0，因而没有显示可补偿 completion loss 的 clean safety
  benefit；两种距离 provenance 又在 24/24 episode 缺失；
- 总判定是 **v1 不具备 operational claim readiness，必须修改**，而不是把有效负结果改称
  terminal-invalid，也不是声称 CTDA 在所有分布上都无效。

机器可读判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

## 当前可以写

- 在固定 simulator task slice 上，Full CTDA clean safety observation 为 12/12 preserved；
- 在固定 CPU/Lean fault matrix 上，35/35 fault case fail closed；
- 在冻结 v2 wire R0 corpus 上，6/6 stage、21/21 Python/Lean verdict parity 通过；这只证明 normalized
  payload 判定一致；
- 在冻结 drawer 50-init R2 上，exact official joint source、finite range、strict predicate agreement 均为
  50/50，且禁止操作计数为 0；50 个值全为 `0.0 m`/closed，只支持 initial negative-class claim；
- 在冻结 adapter R0 上，6/6 fake/adversarial case 覆盖 progress attestation、post-filter binding、stale/
  cross-state rejection 和 recovery ledger non-refund，AST/运行禁止操作计数均为 0；issuer 仅为 test TCB；
- 在冻结 strict-threshold R0 上，五个直接注入 qpos 的请求/读回和官方/reference predicate 为 5/5，
  精确 `-0.14 m` 为 closed；这不构成自然 transition evidence；
- 在冻结 crypto-evidence R0 上，Ed25519 exact producer/version 身份、tamper、wrong-key、revocation 和
  signed progress integration 为 11/11；仅使用 ephemeral test key，不证明生产密钥安全；
- 在冻结 AEGIS CBF/filter R0 上，9/9 unit 及 5/5 CVXPY/OSQP fixture parity 通过，最大误差
  `4.44e-16`；签名 full-result tamper 在 authorization 前 hard-block，dispatch 为 0；
- 在冻结 AEGIS geometry R0 上，8/8 unit 及 4/4 官方 `compute_h_coeffs_3d` parity 通过，最大误差
  `1.53e-16`；几何 payload/signature/freshness/source/causality 异常均在系数推导前失败；
- Lean unavailable/timeout、关键 binding tamper 和 typed fallback evidence 不足时，当前实现不会静默
  回退到 Python 授权；
- 当前系统是 slow-interlock/offline prototype。
- `proofalign-integrity-v1` 已实现独立 Python minimal core 和 `ProofAlign.IntegrityCore` Lean model；二者
  尚无 machine-checked refinement，且只有 in-memory no-action sink。
- 在固定 12-task/init0/env7/policy-seed1 simulator slice 上，VLA-only 为 8/12 task/safe
  success，Full CTDA 为 0/12，task/safe-success retention 都是 0；两臂 collision/cost
  coverage 为 100%、observed unsafe 为 0。

## 当前不能写

- 该 12-task/policy-seed1 结果可推广到总体 task distribution 或其他 policy seed；
- post-dispatch containment 已正式建立；
- 对发布攻击有总体 defense efficacy；
- physical/hardware/continuous-dynamics safety；
- verified recovery、availability 或 real-time enforcement。
- 当前已经复现了足以支持 ProofAlign defense claim 的发布攻击。

## 已完成 clean utility 主任务

新 clean paired utility pilot 已完成并封存：

1. 24/24 episode、12/12 pair valid，双臂 initial digest、first policy chunk、checkpoint/config/camera/
   init/seed binding 匹配；
2. VLA-only 仍为 `UnguardedObservationChecker`，trace 中无 CTDA record；Full CTDA 使用
   `ctda-lean-kernel` 与 `slow-interlock-diagnostic-v1`；
3. VLA-only 8/12 task/safe success，Full CTDA 0/12；8 个 pair 构成 method-attributable utility
   loss；
4. Full CTDA 为 12 block、12 deadlock、0 phase completion；没有独立 action counterfactual，故不称
   false positive；
5. 两臂均为 12/12 episode unknown，因为 human/obstacle distance provenance 缺失；这与冻结的
   task/safe-success 标签正交，不改写为 invalid；
6. retained trace 归因完成：9/12 因 40 秒 semantic contract wall-clock window 无法再覆盖一个
   prefix，3/12 因 persistent bounded-stutter no-progress limit 在 3 个 prefix 后耗尽；12/12 都在
   approach 阶段 pre-dispatch refuted；
7. CTDA v2 原型曾把 proof latency 与 semantic lease 分离，并加入 rebind/progress ledger；retained trace
   只证明 9/3 归因可读和该原型不复刻旧 blocker，不构成 counterfactual dispatch/retention。后续不直接
   延续这套六阶段设计，而是先重冻最小三 transaction 架构；任何新 rollout 仍须新 method id、protocol、
   disjoint unit/seed 或明确的新实验单位和 fresh root。

机器结果见
[`proofalign_e1_clean_utility_terminal_summary.json`](../experiments/proofalign_e1_clean_utility_terminal_summary.json)，
后续边界见 [`roadmap.md`](roadmap.md)。

## 实验暂停；下一实验仍为 VLA-only 攻击复现

完整执行规划见 [`optimization_plan.md`](optimization_plan.md)。下面的执行链当前暂停，不运行；恢复
实验时仍从该链开始，不跳到 CTDA、AEGIS 或 attacked+defended：

1. 在新 protocol、clean commit 和 fresh absent root 上修复 official SABER constraint-violation producer；
2. 生成并验证 immutable official attack record/transcript/hash；producer gate 未通过时不启动 victim；
3. gate 通过后直接运行同 task/init/seed/checkpoint 的 unguarded VLA-only clean/attacked pair；
4. 使用独立 collision/force/joint-limit/action-magnitude oracle 判定 clean-safe→attacked-unsafe；
5. 保存 terminal manifest、append-only ledger、episode artifact 和 SHA-256；
6. SABER terminal blocked/failed 后才按独立 fresh protocol 转 EDPA + SafeLIBERO，不按 outcome 调 patch；
7. VLA-only threat qualification 结束后停止，不自动进入 CTDA、AEGIS 或 attacked+defended comparison。

实验暂停期间禁止运行 `ctda_v2_*` audit/probe、ProofAlign clean pilot、CTDA shadow/fixed-trace outcome、
AEGIS closed-loop、SAFE/FIPER 或任何自研 method arm。允许
`tests/test_integrity_prototype.py`、其他本地 unit regression 和 `lake build ProofAlign`；它们不得连接
simulator/GPU 或创建 outcome root。

安全基础机器入口为
[`safelibero_aegis_readiness_protocol.json`](../experiments/safelibero_aegis_readiness_protocol.json) 和
[`safelibero_aegis_readiness_summary.json`](../experiments/safelibero_aegis_readiness_summary.json)，只读入口为
`scripts/safelibero_aegis_readiness.py`。runtime R1 入口为
[`safelibero_aegis_runtime_protocol.json`](../experiments/safelibero_aegis_runtime_protocol.json)、
[`safelibero_aegis_runtime_summary.json`](../experiments/safelibero_aegis_runtime_summary.json) 和
`scripts/safelibero_aegis_runtime_preflight.py`；R2/R3 终态分别见
[`safelibero_aegis_model_load_summary.json`](../experiments/safelibero_aegis_model_load_summary.json) 与
[`safelibero_aegis_scene_summary.json`](../experiments/safelibero_aegis_scene_summary.json)。这些 gate 都不授权
rollout。全量 state gate 同时保留 r0
[`state_coverage_summary.json`](../experiments/ctda_v2_safelibero_state_coverage_summary.json) 的 1250/1600
负结果和 r1
[`state_coverage_summary_r1.json`](../experiments/ctda_v2_safelibero_state_coverage_summary_r1.json) 的
1600/1600 通过结果；两者 `env.step=0`。
OpenRegion gate 的 terminal 入口为
[`open_region_coverage_summary_r2.json`](../experiments/ctda_v2_open_region_coverage_summary_r2.json)：50/50
source/range/predicate agreement、`env.step=0`，但全部 joint value 为 `0.0 m`/closed，不能解释为 online
transition coverage。
AEGIS no-action producer 链的机器终态为
[`ctda_v2_aegis_cbf_filter_summary.json`](../experiments/ctda_v2_aegis_cbf_filter_summary.json) 与
[`ctda_v2_aegis_cbf_geometry_summary.json`](../experiments/ctda_v2_aegis_cbf_geometry_summary.json)；对应
summary SHA-256 分别为 `25507c261168b172888f588d3f75cd633e8faa593f0059e4f3099821b9f22a7c` 和
`205f16277ee9b661d6b46008f4a2bbe031c3201d4c38fa9609261f8b30daf90e`。它们均不授权 rollout。

攻击证据审计的正式结论仍是 `0` 条 workload 通过完整 qualification：

1. Phantom 固定 R0 的 medium laser 确实改变 20/20 policy frame，但 clean/attack 都成功；
2. R0b discovery 只有 strong laser 产生 3/3 task failure，held-out LIBERO-Safety R1 最终只有 1/4
   clean-safe → attacked-unsafe，低于 2/4 gate；
3. 早期 SABER-style 记录是 `saber_style_manual`；clean 7/12、attacked 8/12 task success，只有 1/12
   attacked unsafe，不能当作官方 SABER attack efficacy；
4. 正式 SABER exact-task R1 在第一条 record 的 chat-model 初始化阶段失败，0 valid record、0 victim
   rollout；
5. SAFE/FIPER 都是 defense baseline 而不是 attack；SAFE partial，FIPER fresh2 于
   2026-07-17 16:14:05 停止，terminal gate 未通过；
6. 当前直接优先新的 VLA-only threat-validation；在其 terminal 结束且用户再次明确授权前，不启动或
   继续任何 CTDA v2、AEGIS、SAFE/FIPER、clean method pilot 或 attacked+defended 工作。

完整叙述见 [`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)，机器记录见
[`attack_reproduction_evidence_audit_20260717.json`](../experiments/attack_reproduction_evidence_audit_20260717.json)。

## 仓库状态规则

- 已终止的 protocol/result 不 resume、不覆盖、不重新分类；
- 所有正式执行必须先在 clean commit 冻结 protocol，再使用 fresh absent output root；
- timing 保留原始记录但不是下一实验 gate；
- raw artifact、ledger、manifest 和 terminal summary 必须一起保存；
- archive 只用于历史追溯，不作为当前方法或 CLI 来源。
- 新工作顺序、里程碑、停止条件和工作机交接以 [`optimization_plan.md`](optimization_plan.md) 与
  [`next_experiment_prompt.md`](next_experiment_prompt.md) 为准。
