# ProofAlign Roadmap

更新日期：2026-07-23

## 目标

完成一个诚实、有限、可复核的 VLA runtime safety evaluation：同时报告安全收益和正常任务完成度
trade-off，不追求绝对安全或通用证明。

## 已完成

1. **方法闭环**：trusted mission、persistent contract、consumer-side raw binder、canonical wire、
   Lean kernel evaluator、observed trace monitor。
2. **E0 support**：固定 12 个 affordance/init0 supported unit。
3. **E3 safety**：clean 12/12 safety preserved；独立 post-dispatch challenge 原始行为和 primary unknown
   均已封存。
4. **E4 robustness**：35/35 frozen fault case fail closed；timing 负结果保留。
5. **外部 workload gates**：Phantom held-out 与 SABER P0 R7 均按冻结停止条件关闭；R7 的 1/4 typed
   transition 低于 2/4、0.5 gate。
6. **E1 clean utility**：新 policy-seed 1 pilot 12/12 valid pair；VLA-only 8/12、Full CTDA 0/12
   task/safe success，retention 0，completion loss 原样封存。
7. **v1 validity decision**：实验/internal parity 有效，但 clean operational utility 不合格；当前 v1
   判定为 revision required，不再扩大 rollout 或 runtime claim。
8. **attack evidence audit**：Phantom held-out 为 1/4（gate 2/4）；旧 SABER exact-task R1 为 0
   record/0 victim，新的 SABER P0 R7 为 8/8 valid episode、1/4 typed transition；SAFE/FIPER 均未
   terminal reproduced。qualified attack count 仍为 0，所有 root 已 terminal 或暂停。
9. **EDPA R0 历史草案**：保留 official-source-pinned 双相机 patch adapter、protocol、预检和
   validator 作参考；它已被当前 v2 规划取代，不是 EDPA + SafeLIBERO P1 protocol，不生成
   patch，不运行 victim。
10. **SafeLIBERO foundation R0**：固定官方 AEGIS commit/tree/MIT license、32 scenario/1600 init/49
    个数据文件 digest、官方 obstacle-displacement collision label、typed provenance 与
    CAR/TSR/ETS/cost/RET/四象限 classifier；只读 gate 为 ready，AEGIS runtime 仍 blocked，零 rollout。
11. **SafeLIBERO R1--R3 + v2 state coverage**：双环境/资产、no-inference model load、单场景 serialization
    和全 1600 init exact goal-reference key/collision-source coverage 已通过；r0 的 1250/1600 adapter
    负结果保留，r1 为 1600/1600，所有路径 `env.step=0`。
12. **CTDA v2 M0/M1 no-dispatch core**：独立 method/core/wire schema、certificate/rebind lease、四级
    intervention、post-filter binding、progress ledger、13 个 v2 core test 与初始 Lean theorem 已实现；
    retained E1 117 prefix/9+3 block 归因保持原标签。
13. **CTDA v2 wire/Lean parity R0**：六阶段 strict canonical wire、独立 Lean replay evaluator 与 21-case
    golden corpus 已完成；21/21 Python/Lean verdict parity，0 dispatch、0 `env.step`。
14. **OpenRegion initial source gate R2**：CPU OSMesa 对冻结 drawer 的 50/50 init 完成 exact official joint
    source、asset range 与 strict predicate agreement；0 `env.step`/policy/model/socket/dispatch。所有 qpos
    都是 `0.0 m`/closed，故尚无 positive-state 或 transition claim。
15. **Online-evidence/filter adapter R0**：6/6 unit/fake-observation adversarial case 通过；exact-source
    progress attestation、fresh post-filter witness、adjusted-command membership/authorization、replan
    non-refund 和 untrusted hard-block 已接线，AST 与运行 counter 均为零。issuer 仍是 simulator-test TCB，
    没有 recovery controller 或 rollout authority。
16. **OpenRegion strict-threshold R0**：五个事前固定 qpos 直接注入并精确读回，official/reference 5/5；
    两个 open、三个 closed，`qpos == -0.14 m` 明确 closed。全程 `env.step=0`，但不是自然 drawer
    transition 或 production sensor evidence。
17. **Ed25519 evidence R0**：11/11 exact producer/version authentication、tamper/wrong-key/revocation 与
    signed progress integration 通过；ephemeral test key、0 persistent private key、0 dispatch。
18. **AEGIS CBF/QP filter R0**：9/9 fail-closed/signature/CTDA binding unit 与 5/5 CVXPY/OSQP parity 通过；
    最大误差 `4.44e-16`，完整 result tamper 在 authorization 前 hard-block，0 dispatch。
19. **AEGIS typed geometry R0**：8/8 authenticated provenance unit 与 4/4 pinned
    `compute_h_coeffs_3d` parity 通过；最大误差 `1.53e-16`，raw perception trust 仍 blocked。
20. **Minimal integrity prototype**：独立 `proofalign-integrity-v1` 已实现五组件、三 transaction、四臂
    method switch、one-use exact authorization 与 checked completion；28 个 focused unit 和
    `ProofAlign.IntegrityCore` build 通过。当前只有 in-memory no-action sink，无实验 outcome。

## 已完成阶段：clean utility trade-off

在相同 clean task、init、实际 policy seed 下，Full CTDA 相比 VLA-only 的任务完成度和 safe
success 损失已经得到有效 pilot 答案：12/12 valid pair，VLA-only 8/12、Full CTDA 0/12，两种
retention 都为 0；两臂 collision/cost coverage 100%、observed unsafe 0，Full CTDA 为 12 block/
deadlock、0 phase completion、0 Lean parity mismatch。

执行顺序：

```text
shared-observer fix + tests
  -> outcome-blind no-dispatch init/policy probe
  -> freeze new protocol on policy_seed=1
  -> clean commit
  -> GPU/EGL/model/Lean preflight
  -> fresh paired execution
  -> retained artifact validation
  -> scoped utility/safety report
```

本轮停止条件全部按冻结执行：

- 两臂 initial-state digest 或 first policy chunk digest 不同：不 dispatch 正式 pair；
- protocol/source/checkpoint/hash/preflight 任一不一致：不创建正式 output root；
- 已进入 episode 后发生异常：保留为 invalid/unknown，不替换该 unit；
- 0 valid pair：终态为 not evaluated，不计算 retention；
- 不因结果调整支持 task、policy seed、horizon 或 classifier。

所有 12 pair 均 valid，未触发 0-pair `not_evaluated`；大 completion loss 没有触发重跑或 gate 放宽。

## 已完成阶段：retained-trace utility failure analysis

离线归因没有产生新 rollout，也没有改写旧结果：

1. 12/12 Full episode 最终都是 approach-phase pre-dispatch `refuted`，0 phase completion；
2. 9/12 在 12 个 dispatch 后耗尽 40 秒 semantic contract wall-clock coverage；
3. 3/12 pour task 在 3 个 dispatch 后耗尽 persistent bounded-stutter no-progress limit；
4. 24/24 episode 缺 human/obstacle distance provenance；collision/cost coverage 完整但不能替代这些
   safety dimensions；
5. closed-loop block 继续只标 intervention；没有独立 action counterfactual 时不计算 false positive。

## 当前阶段：resource-isolated action-envelope successor

详细架构、里程碑、实验矩阵和停止条件以 [`optimization_plan.md`](optimization_plan.md) 为准。
P0b fresh2 已完成 48 record 和 96/96 valid clean/attacked episode，但只有 23 个 clean-eligible pair，
低于冻结的 26-pair gate。当前用户明确指定的唯一实验优先级是 exploratory Execution-only action-envelope
attacked+defended successor。clean R1 retention 为 `22/23 = 0.9565`；R2 在新 `env.step` 前因 non-finite
command terminal；R3 zero-brake attempt 因 runtime GPU contention/device mapping mismatch 在 binding probe
完成前停止，0 episode/outcome。当前等待修复隔离、冻结 successor protocol 和 fresh root，并等待稳定双 GPU。
完整 checkpoint 见 [`current_experiment.md`](current_experiment.md)。

### P0b 与 R1--R3 checkpoint

1. SafeLIBERO/AEGIS source/data foundation 已完成：官方 commit `57b1aef...`、32 scenario、1600 init、
   official collision label 和 typed metrics 已固定；
2. AEGIS static runtime R1 已完成：隔离 Python 3.11/3.8 环境、242/152 distribution inventory、
   标准 `pi05_libero` 与 GroundingDINO digest、4/32/1600 注册均通过，禁止操作计数为 0；
3. no-dispatch R2/R3 已完成：GroundingDINO 与标准 pi0.5 分别加载成功，单个冻结 scene 的 init/完整
   observation 已序列化；0 inference、0 socket、0 `env.step`，formal rollout 仍 blocked；
4. SABER R7 已 terminal；R4--R7 artifact 不续接、不补样；
5. R7 的 immutable record/transcript/schema/hash 和 VLA-only clean/attacked pair 均通过有效性校验，但
   primary safety gate 未通过；
6. primary threat signal 必须是独立 oracle 给出的 clean-safe→attacked-unsafe，不用 task failure、attack
   metadata 或 detector verdict 代替；
7. P0b fresh2 保留 48 record、96/96 valid episode、23 clean-eligible、15 transition；denominator gate
   不通过，正式分类为 `p0b_blocked_insufficient_clean_baseline`；
8. action-envelope clean R1 完成 48/48 valid episode，baseline-eligible strict success `22/23`；attacked
   R2/R3 都没有产生可解释的 attacked+defended outcome；
9. EDPA P1a 在 OpenPI CLI parsing、policy/simulator/episode 前 terminal，保持次要冻结线。

### 冻结线：ProofAlign/CTDA 与 defense baseline

1. 既有 v1/v2 code、protocol、artifact 原样保留，不覆盖、不续跑；
2. 不运行 CTDA v2 audit/probe、fixed-trace/shadow outcome或新的 clean pilot；仅当前 action-envelope
   successor attacked+defended arm例外；
3. minimal integrity prototype 可以做本地 unit/Lean build，但不接 simulator、GPU、online wire outcome；
4. 不继续数值预算、raw perception、recovery 或 CTDA support 施工；
5. 不运行 AEGIS、SAFE、FIPER 或其他 defense baseline。

### 汇合 gate

当前不开放 Full CTDA/四臂汇合 gate。action-envelope successor 是已明确授权的探索性 Execution-only
measurement，不能把 P0b 改写为 qualified attack，也不自动开放其他 ProofAlign/CTDA 或 baseline。

v1 冻结判定见
[`proofalign_method_validity_decision_20260717.json`](../experiments/proofalign_method_validity_decision_20260717.json)。

## 后续阶段

### 独立 containment challenge

clean utility 结果已经形成；若考虑新的 post-dispatch challenge，仍必须使用新的实验单位或新 fault，
事前冻结与当前 typed receipt schema 一致的 validator；旧 12 条不得重跑或升级。

### E5 external comparison

当前暂停。VLA-only 攻击复现终态不会自动打开 E5；后续是否运行 AEGIS、CTDA、SAFE/FIPER 或正式
comparison，等待用户重新授权。旧 partial 不 resume。

## 永久 claim boundary

即使后续全部通过，也只声称指定 simulator/task/workload 上的 safety/utility trade-off；不声称绝对
安全、硬件安全、verified recovery、通用攻击防御或实时控制。
