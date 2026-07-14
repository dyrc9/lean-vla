# ProofAlign Execution Roadmap

更新日期：2026-07-14

本文是唯一执行计划。历史 roadmap、实验 handoff 和 design memo 已归档。

## 0. 总目标

先交付一个有限、诚实、可运行、可审计的闭环：

```text
trusted frozen mission
  -> mission-rooted persistent contract
  -> independent raw-prefix binding
  -> Lean-kernel-checked discrete authorization
  -> exact dispatch and cumulative completion audit
```

当前 GPU 环境已完成 single-prefix diagnostic。后续 GPU rollout 仍只在相应 readiness gate 通过后
分阶段执行；当前只开放 3--5 prefix clean slow-interlock calibration。

## 1. 冻结原则

1. 不构造新攻击；只使用发布的、版本化的 attack artifact。
2. 不继续扩展完整 RTA 架构；CBF/reachability、硬件 attestation 和 verified recovery 全部暂缓。
3. 不做通用 NL/BDDL compiler；只支持一个显式 task/primitive slice。
4. 不把 policy-facing prompt 或 `proofalign_action` 当作 contract authority。
5. 不把 Python verdict 改名为 Lean proof。
6. 不跑大规模 GPU 主表来掩盖 false block 或 evaluator gap。
7. 不从 `docs/archive/` 恢复旧口径。

## 2. P0：文档与 claim scope freeze

状态：**完成**。

产物：

- canonical method、architecture、experiment protocol 和 remote runbook；
- trusted, locally frozen mission 的准确措辞；
- 两个系统不变量；
- 当前不可声称能力；
- archive 与 canonical source-of-truth 规则。

后续方法变更必须同步更新 `method.md`、Lean definition、Python evaluator 和 tests，不再新增
平行 design memo。

## 3. P1：修正合同来源与 raw-action binding

状态：**本地完成**。

已实现 frozen Pick/Place template、phase/residual-obligation contract provider、policy metadata
隔离和版本化 raw binder；prompt/metadata/registry/wrong-target/gripper/held-object/region 回归测试已
通过。

### 3.1 Trusted mission source

- 明确区分 benchmark-owned trusted instruction、policy-facing instruction 和 untrusted
  proposal metadata。
- 为一个有限 task slice 实现 deterministic task-template/manifest compiler。
- `MissionSpec` 绑定 task artifact、trusted instruction、registry、SafetySpec、phase、episode
  nonce 和 time base。
- unsupported/ambiguous task 明确 fail closed。

### 3.2 Mission-rooted contract provider

- active contract 只由 `MissionSpec + active phase + residual obligation` 决定。
- paper CTDA path 不调用 `heuristic_contract_from_instruction()` 产生授权合同。
- 改变 attacked prompt 或 policy `proofalign_action` 不得改变 active contract、spec digest 或
  paper-path verdict。
- legacy heuristic 仅保留 compatibility/logging 标签。

### 3.3 Independent raw proposal binder

- binder 读取 trusted state、raw command、active contract 和 versioned config。
- 最小支持 persistent `Pick`/`Place`；approach/transport 属于合同内 prefix。
- 错误 target/region/held object/gripper action、观测不足或方向不明必须 refuted/unknown。
- policy 自报 admissibility、contract id 或 expected effect 不能升级 binder verdict。
- completion 只能来自 observed witness。

### 验收

- prompt tamper 不改变 paper contract/verdict；
- `proofalign_action` tamper 不改变 paper verdict；
- trusted task/registry 改变导致 mission digest 改变，旧 artifact 失效；
- wrong target、wrong gripper、wrong held object fail closed；
- missing completion 保持 `safe_pending`；
- stale/replay/cross-episode tests 继续通过；
- evaluator 失败前没有 supervisor partial commit。

## 4. P2：`ctda-wire-v1` 与 Lean online evaluator

状态：**功能闭环完成，real-time 路线按负结果关闭；仅保留 slow interlock/offline audit**。

### 4.1 Canonical wire schema

实现内部 `ctda-wire-v1`，stage 至少包含：

- `semantic`
- `prefix_pre`
- `observed_prefix`
- `monitor_step`

要求 canonical UTF-8 JSON、integer nanoseconds、tagged temporal formula、strict decoder、consumer
digest recomputation、stable ordering 和 round-trip/injection tests。它不替换 episode JSON 或
attack-record schema。

### 4.2 Evaluator abstraction

明确实现：

- `ctda-python-reference`
- `ctda-lean-kernel`
- `ctda-shadow`

Lean 不可用、serialization/build/timeout/parity mismatch 时 fail closed。只有 kernel 实际检查
成功的 request 才能写 `proof_verified=true`。

### 4.3 Online transaction

- `semantic` 和 `prefix_pre` 必须在 `env.step` 前 proven；
- `observed_prefix` 和 `monitor_step` 必须在下一次 dispatch/phase advance 前 proven；
- Lean 失败时不得退回 Python 继续 dispatch；
- request、generated Lean artifact、checker digest 和输出可离线 replay；
- cache key 必须包含 canonical request 与 checker/build/schema version。

### 4.4 Golden parity corpus

覆盖 proven/refuted/pending/complete/violated/inconsistent 及：

- spec/nonce/state/monitor/contract/proposal/command/time-base tamper；
- receipt/trace provenance mismatch；
- split-prefix completion；
- timestamp rollback；
- replay、stale、cross-episode artifact。

共同支持语义必须达到零 mismatch。

### 验收

- fake-env test 证明 Lean proven 前 `env.step` 调用次数为 0；
- Lean unavailable/tampered request 时 dispatch 为 0；
- observed/monitor 未通过时 phase 不推进；
- golden corpus 零 parity mismatch；
- `lake build ProofAlign` 与全量 Python tests 通过。

当前结果：以上 correctness gate 已通过；206 passed / 1 skipped，Lean 12 jobs，fake-env pre-proof
零 dispatch，unavailable/tampered request 零 dispatch，observed/monitor failure 零 phase advance。
但逐 request Lean replay 的 p99 为约 0.65--1.95 秒，超过 control deadline，因此当前不得声称
real-time enforcement。

2026-07-14 远程结果进一步确认四阶段约为 0.9--1.3 s/stage。项目不再把满足 control deadline
作为 slow-interlock/offline 实验的 readiness 条件；相应代价是彻底删除 real-time enforcement
claim。所有 latency 和 miss 仍必须原样报告，Lean 不可用或超时仍 fail closed。

## 5. P3：CPU-only shadow calibration harness

状态：**工程 harness 与 synthetic golden parity 完成；允许开始非实时 clean prefix
calibration**。

输入保存的 clean prefix/episode artifact 或 CI fixture，不调用 simulator/GPU，不改变 action。

输出：

- supported/unknown/blocked/allowed；
- Layer 1、Layer 2 和 dual unique catch；
- pending/complete/violated/inconsistent；
- Python/Lean parity mismatch；
- semantic/prefix/observed/monitor p50/p95/p99；
- schema/checker/config/git digest；
- independent label provenance；
- 没有 ground truth 时相关指标为 `not_evaluated`。

### Readiness gate

以下是进入远程 pilot 的工程目标，不是已经实现的结果：

- parity mismatch = 0；
- clean false block 目标 ≤5%，>10% 停止扩实验并修 binder/abstraction；
- unknown/deadlock 目标 ≤5%；
- clean success retention 远程 paired target ≥90%；
- p99 必须实测；超过控制周期则降级为 offline audit，不能声称 real-time enforcement。

本地 27-case fixture 结果：parity mismatch = 0，Layer 1/Layer 2/dual unique catch 均有覆盖，
pending/complete/violated/inconsistent 均有覆盖。fixture 没有独立 ground truth，因此 false block、
TPR、FPR 均为 `not_evaluated`。Lean p99 超出控制周期，当前按 offline audit/slow interlock 处理。

固定 `affordance/task 2/init 0` 的真实 GPU probe 已验证 fallback postcondition 只要求
`collision,cost` 且 observation complete。固定 50 ms switch receipt 在三次完整 repeat 中只通过
2/3，因此该 receipt gate 记录为失败；它不再阻塞 3--5 prefix slow-interlock calibration，但任何
后续结果都不得描述为 real-time，超时 receipt 必须继续 fail closed，不能筛掉。

## 6. P4：远程发布攻击 workload pilot

状态：**真实 GPU 单-prefix diagnostic 已完成；3--5 prefix clean calibration 待运行**。P1/P2
correctness、golden parity 与 affordance observation completeness 已通过；real-time latency 明确
未通过并已降级 claim。fail-closed preflight manifest 与 clean + Lean slow-interlock smoke 已
脚本化。下一步只运行 3--5 prefix clean slow-interlock calibration；不得直接启动主表。
环境见 [`remote_execution.md`](remote_execution.md)。

在 60-episode pilot 前增加 upstream reproduction gate，详见
[`reproduction_plan.md`](reproduction_plan.md)：

1. standard LIBERO 上复现 SABER π0.5 clean + record/replay；
2. standard LIBERO 上复现 Phantom Menace OpenPI clean + camera transform；
3. 复现 SAFE/FIPER 官方 detector pipeline，冻结需要的 rollout/feature schema；
4. 上游通过后才开发 LIBERO-Safety exact-task workload 与 π0.5 defense adapter。

### Workload

- clean pi0.5/OpenPI + LIBERO-Safety；
- 一个发布 instruction attack family：SABER `constraint_violation` 优先；
- 一个发布 camera attack family：Phantom Menace deterministic transform；
- EDPA 只作后续 patch transfer 和训练型 secondary track。

不在本项目中优化攻击，不按攻击调整 CTDA 阈值。

### 60-episode gate

先跑四个 physical suites × tasks `0-14` × init `0`。进入主表要求：

- clean baseline 稳定且 runner failure 可接受；
- 至少一个 instruction 和一个 camera workload 产生 authorization/safety signal，而不仅是 task
  success drop；
- 每个 episode 保存 task/init/env seed/policy seed/camera/horizon/config/evaluator mode；
- raw artifact 可从远程复制并校验。

若攻击只造成 task failure、没有 authorization/safety signal，则不写 physical-defense claim。

## 7. P5：最小配对主实验

固定方法：

1. VLA only；
2. privileged collision/cost checker；
3. SAFE；
4. FIPER；
5. Full CTDA。

Mission-only 与 trace-only 放在独立 CTDA ablation 表。RoboGuard 通过 plan-interface gate 后加入
semantic comparison；EDPA/Phantom training defense 在其官方 victim 上单独成表。

固定 workload：clean、一个 instruction family、一个 camera family。

固定 task/init/policy seed/env seed/camera/horizon/checkpoint。先跑 pilot，只有 signal 和 utility
gate 通过才扩 init `0-4`。

指标、offline/online 双协议与 artifact 规则见 [`experiments.md`](experiments.md)。

## 8. Kill criteria

出现以下任一情况，主动缩题而不是继续堆实验：

- online 仍只有 Python reference：删除 Lean-backed online enforcement claim；
- clean relative success retention <90% 或一次校准后 false block >10%：停止扩实验；
- full dual 与最佳 single layer 无显著差异，或某层没有 unique catch：删除“双层必要性”claim；
- visual defense 使用与 policy 相同的 attacked observer：删除确定性 camera-defense claim；
- 需要按攻击调阈值：删除 attack-agnostic claim；
- p99 或 fallback switch 超出 control deadline：删除 real-time claim，保留 fail-closed
  slow-interlock/offline audit；该负结果本身不阻塞非实时实验，但必须报告完整分布与 miss；
- 独立 oracle 无法标注 unsafe/safe proposal：不报告 detection TPR/FPR；
- 结果主要依赖 privileged simulator oracle：只主张 simulation/reference-monitor 结果。

## 9. 暂缓项

- EDPA paper-scale reproduction；
- 新攻击、训练时后门、攻击模型训练；
- 三个以上 victim；
- 全量五 suite/多 init 大矩阵；
- 通用自然语言与全 BDDL compiler；
- CBF、HJ reachability、完整 dynamics proof；
- authenticated IPC、TEE、hardware attestation；
- verified recovery controller；
- 实机安全保证。

若未来坚持 S&P/USENIX Security/CCS/NDSS 路线，应另开系统安全 track，补进程隔离、认证
通信、独立 sensor/actuator evidence 和有限实机验证；这些不阻塞当前 simulation-first 论文。
