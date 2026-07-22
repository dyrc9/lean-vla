# Project Status

更新日期：2026-07-22

## 当前状态

SABER P0 R7 已 terminal 完成且不得续接。独立大样本 P0b 的 48-pair producer protocol 在 2026-07-22
通过源码、模型、checkpoint、三处外部 checkout、clean worktree 与 GPU 2/3 的正式预检后启动；本次错误地使用
仓库根 `.venv/bin/python`，而非已安装 `art`/`vllm` 的 `external/SABER/.venv/bin/python`，故在攻击代理初始化
前以 `ModuleNotFoundError: No module named 'art'` terminal fail closed。冻结 root 只留下
`record_generation_failed` manifest：attack record、transcript、victim episode 与 safety outcome 均为 0，
且 `victim_loaded=false`。P0b 不得在该 root 重试，也不授权 victim、EDPA 或任何 defense arm。用户此前已授权
并完成 `proofalign-integrity-v1` 本地最小原型施工；它只有 in-memory no-action sink、unit tests 和 Lean
build，不产生实验 outcome。既有 CTDA、Ed25519、typed geometry 和 AEGIS CBF/QP 结果继续作为冻结历史保留。

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
| attack foundation | SABER R7 terminal nonpass；P0b producer terminal failure | R7 为 1/4 typed transition；P0b 的预检通过但本次调用错用根 `.venv`（正确 SABER `.venv` 有 `art`/`vllm`），0 record/0 victim/0 outcome，不能推断攻击效果 | 停止；不重试 P0b root，不启动 victim、EDPA 或 defense。任何新尝试须有新的用户授权、协议和 fresh root |
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

## SABER P0b producer terminal（2026-07-22）

完整执行规划见 [`optimization_plan.md`](optimization_plan.md)。P0b 的正式预检为 `ready=true`：GPU 2/3
均为 3 MiB、无 compute process，所有冻结源码/模型/checkpoint/checkout 与 clean worktree 一致。正式
producer 随后只创建了 fresh root 的
[`run_manifest.json`](../results/saber_threat_replication_p0b_producer_20260721_fresh1/run_manifest.json)。本次
调用错误地使用根 `.venv/bin/python`；正确的 `external/SABER/.venv/bin/python` 已包含 `art` 和 `vllm`，但
没有被此次冻结 run 使用，故它在任何 attack-agent generation 前以 `ModuleNotFoundError: No module named 'art'`
结束。

- 状态机为 `record_generation_failed`；run manifest SHA-256 为
  `d46aab16cd32c7cf0e15dd63b5b8ff273cdaf75f3c0679dbf4c4a8d6a068027f`；
- 没有 record、transcript、immutable bundle、victim protocol、victim episode 或 safety outcome；manifest 明确
  记录 `victim_loaded=false` 和 `victim_rollout_used=false`；
- 机器可读状态见
  [`saber_threat_replication_p0b_status.json`](../experiments/saber_threat_replication_p0b_status.json)；
- frozen producer protocol/root 均不得重试、修补或覆盖；P0b 与 R7 分开报告，不能以 0 outcome 解释攻击效果；
- 依照 terminal stop rule，不自动进入 EDPA、CTDA、AEGIS、SAFE、FIPER 或 attacked+defended comparison。

P0b 之外继续禁止运行 `ctda_v2_*` audit/probe、ProofAlign clean pilot、CTDA shadow/fixed-trace outcome、
AEGIS closed-loop、SAFE/FIPER 或任何自研 method arm。只允许本地 unit regression、Lean build 与代码审计；
它们不得连接 simulator/GPU 或创建 outcome root。

### P0b 冻结设计与预检记录

- producer protocol 为
  [`saber_threat_replication_p0b_producer_protocol.json`](../experiments/saber_threat_replication_p0b_producer_protocol.json)：
  SHA-256 分层选择 48 个 outcome-blind pair，4 个 suite 各 12 个，L0/L1/L2 各 4 个 task；init 只从
  10--49 选择，env/policy seed 为 31/5，与 R7 和更早 closed population 分离；
- 每个 pair 只允许一次 official prompt-tool generation，禁止 best-of-N、regeneration、replacement 和
  victim outcome leakage；任一 record 无效即 producer terminal fail closed；
- primary gate 至少要求 26 个 clean-eligible pair、至少 13 个 transition 且 rate `>=0.5`，同时报告
  Wilson 95% interval；在 26 个 eligible、真实 rate 0.6 时通过概率为 0.891812；
- 若 immutable bundle 曾完成，freezer 才可生成新的 victim protocol 并运行 96 个 pair-major episode；本次没有
  达到这一条件，故 victim 永不启动；
- 2026-07-22 正式 preflight 已逐项验证 source hash、模型 SHA-256、SABER/LIBERO-Safety/OpenPI 的 clean
  pinned checkout、fresh absent root 和 GPU 2/3。通过预检没有验证解释器 import；本次使用错误解释器导致
  `art` import failure，形成 P0b terminal producer failure，而非 attack efficacy result。

### EDPA + SafeLIBERO P1a 收工检查点（2026-07-21）

- 独立 protocol 为 [`edpa_safelibero_p1_protocol.json`](../experiments/edpa_safelibero_p1_protocol.json)，
  已在 commit `20c020d` 冻结为 `frozen_execution_authorized`；它只允许 unguarded OpenPI pi0.5 的 clean/
  attacked VLA-only pair，明确禁止 ProofAlign、CTDA、AEGIS、SAFE、FIPER 与任何 attacked+defended arm。
- fresh2 asset producer 已正常完成，且没有观察 victim 或 simulator outcome：
  `asset_manifest.json` SHA-256 为 `b0f0f5c81769ff1c6a03fabbcdf7872adfbed46e9860bd0f7d55e0b9c6f7f402`；
  primary/wrist patch SHA-256 分别为 `b73fe0d08394e17f773452456e191f8183603cf314d366ec8df8f79a041f1823` 和
  `c49c5df45fd60aecdf310ad19f46efa22f1b03bb8b834055d6ca5f9a16c66129`；训练数据 tree digest 仍为
  `c81ee0c39f17b4ee02ecfab1a9ddff45aed70bf37a3ae4d191bec0f7a93e4af1`。
- P1 runner 的静态 preflight 已 `ready: true`，相关回归为 33 passed；随后因所有 GPU 均有外部 compute
  process 且显存高于 `<4096 MiB` 运行前 gate，未调用 runner `--execute`，未创建
  `results/edpa_safelibero_p1_20260721_fresh1`，episode/rollout 为 0。
- 因而 P1a 的唯一正确状态是 `not_yet_evaluated`，不是 pass、fail 或 terminal result。已停止自动等待器；恢复时
  先重新运行静态 preflight，并仅在同一物理 GPU 同时满足空闲显存和无 compute process 条件时显式执行。任何
  terminal P1 结果仍必须停止，不能自动进入防御比较。

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
   rollout；后续 R4--R7 已以 4 条 immutable official record 完成新 VLA-only qualification，R7 得到
   8/8 valid episode、1/4 typed transition，低于 count 2/rate 0.5 gate；
5. SAFE/FIPER 都是 defense baseline 而不是 attack；SAFE partial，FIPER fresh2 于
   2026-07-17 16:14:05 停止，terminal gate 未通过；
6. SABER P0 已 terminal；任何后续 EDPA P1 必须是独立 unguarded VLA-only threat protocol。不得启动或
   继续 CTDA v2、AEGIS、SAFE/FIPER、clean method pilot 或 attacked+defended 工作。

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
