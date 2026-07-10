# ProofAlign Roadmap

更新日期：2026-07-10

## 1. 当前阶段

项目已经从“最小双层 Boolean prototype”进入“CTDA reference runtime 已落地、准备把 Lean
CTDA evaluator 接入在线授权”的阶段。

当前事实基线：

- legacy intent/effect/chunk checker 已接真实 Lean，Lean 不可用时 fail closed；
- Python typed CTDA 已覆盖 frozen mission、semantic refinement、prefix authorization、
  execution/trace provenance、persistent monitor、replay/stale rejection 和 fallback switch
  receipt；
- Lean 已有 CTDA staged checker、finite-prefix monitor 和 soundness/reflection theorem；
- LIBERO CTDA 已实现逐 raw-step 授权与执行后审计，但 evaluator 仍是
  `ctda-python-reference`；
- simulator task root、fallback manifest、action bounds 和运行配置已经冻结并持久化；
- 尚无 dynamics-aware reachable-tube theorem、verified fallback、可信 BDDL compiler 或硬件
  attestation chain。

详细状态审计见
[`lean_method_upgrade_20260710.md`](lean_method_upgrade_20260710.md)；方法口径见
[`method.md`](method.md)。

## 2. 已完成里程碑

### M0：Legacy dual alignment

- typed `Action / TaskIntent / WorldState / SafetySpec`；
- intent-action 与 action-effect 双层检查；
- chunk trace summary、frame condition 和 certificate schema；
- toy tasks、LIBERO wrapper 和 OpenVLA-OFT plugin；
- generated Boolean claim 的真实 Lean 检查；
- conservative float-to-Nat 编码和默认 fail-closed bridge。

### M1：Typed CTDA reference protocol

- immutable mission、phase obligation 和 semantic skill contract；
- proposal、filtered/authorized command、receipt 和 realized trace binding；
- typed attestation、digest integrity、freshness 和 exact allowlist verifier；
- semantic、prefix-pre、trace abstraction、observed-prefix 和 execution-chain checker；
- persistent supervisor 和 `complete / safe_pending / violated / unknown / inconsistent` verdict；
- replay、stale、cross-state、cross-monitor 和 cross-episode rejection。

### M2：Lean CTDA specification

- `SemanticTemporalRefines`；
- `PrefixPreCertified`；
- `ObservedPrefixEvidenceValid`；
- finite-prefix temporal formula evaluation和 monitor；
- staged checker soundness/reflection theorem；
- 正例与 wrong binding、deadline、tube、command、trace、post evidence 等负例。

### M3：LIBERO fail-closed loop

- 每个 raw `env.step` 前进行 CTDA prefix authorization；
- 每步生成 actuator receipt、plant/event trace 和 monitor transition；
- monitor failure/pending-budget exhaustion 时实际 dispatch canonical zero hold；
- fallback switch receipt 绑定 trigger、requested/applied command、pre/post state、invariant 和
  latency；
- 冻结 BDDL snapshot、trusted instruction、SafetySpec、action bounds、fallback digest 和 episode
  nonce；
- CTDA 禁止 warmup step 和 `--skip-existing`。

## 3. P0：接入 Lean CTDA 在线 evaluator

这是当前最高优先级。目标是让每次 online authorization 使用 Lean 中的 CTDA checker，而不是
只运行 Python reference checker。

### 工作项

1. 定义 Python CTDA object 到 Lean request 的规范 serialization。
2. 为 semantic、prefix-pre、observed-prefix 和 monitor transition 提供统一 evaluator entrypoint。
3. 决定执行方式：
   - kernel-audit 模式：生成完整 Lean term/file并由 Lean kernel 检查；
   - online compiled evaluator：使用预编译 evaluator，同时明确 codegen/runtime 新增 TCB。
4. 对 Python 与 Lean evaluator 做 differential test，覆盖所有正例和 fail-closed 负例。
5. 将 online result mode 从 `ctda-python-reference` 区分为明确的
   `ctda-lean-kernel` 或 `ctda-lean-compiled`。
6. 加 content-addressed cache；cache key 必须包含 spec、contract、state、monitor、model、evidence
   和 checker version digest。

### 完成标准

- online wrapper 在 dispatch 前取得 Lean CTDA `proven` witness；
- 修改任意关键 binding 都会使 Lean evaluator 拒绝；
- Python reference checker 只作为 differential oracle/diagnostic，不再作为论文 full-CTDA
  authorization source；
- 报告 semantic、prefix-pre、observed-prefix 和 monitor 的分项延迟与 p50/p95/p99；
- 保留完整 kernel replay artifact。

## 4. P1：从条件运动学界升级 physical certificate

### 工作项

1. 给当前 conditional kinematic bound 写出明确 assumptions、适用 action space 和误差预算。
2. 记录每个 prefix 的最小 tube/barrier margin，而不是只有 Boolean membership。
3. 引入 risk-aware prefix horizon：free-space 可更长，contact/release/handover 强制缩短并重观测。
4. 为少量 primitive 评估 CBF-QP、predictive safety filter 或 reachable-tube witness。
5. 要求所有允许的 cutoff/switch state 都处于 recoverable set，而不只检查名义终点。
6. 把 witness 设计成 consumer-checkable artifact，避免只信任 producer 的 `verified=true` 声明。

### 完成标准

- 明确给出条件 invariant theorem 的模型、扰动、采样、延迟和控制界；
- tube witness 覆盖整个 authorized duration，无时间空洞；
- observed plant sample 可复核地落在 tube 内；
- model assumption 失效会在下一次 dispatch 前锁存并 fallback。

## 5. P2：Verified fallback 与硬件证据链

### 工作项

1. 从 simulator zero-hold 扩展为 `hold / brake / retreat` baseline controller contract。
2. 定义 recoverable set、forward switching condition、reverse-switch hysteresis 和 backup
   availability。
3. 建立 trigger-to-dispatch、dispatch-to-observe 和总 switch latency 的硬件时间链。
4. 使用签名、MAC、TEE 或 proof store 验证 observer/actuator attestation，而不是 local allowlist。
5. 证明 fallback 接管后在声明 horizon 内保持 invariant，并区分即时 stop 与长期 stable state。

### 完成标准

- fallback witness 不是 operator-pinned simulator manifest；
- actuator receipt 来自实际低层控制接口；
- 最坏切换延迟满足 theorem assumptions；
- supervisor composition theorem覆盖 advanced controller 到 baseline controller 的切换。

## 6. P2：可信 task-root compiler

### 工作项

1. 为 LIBERO-Safety 五个 suites 定义 deterministic typed task templates。
2. 把 BDDL goal、object registry、instruction 和 suite hard-safety template 编译到
   `MissionSpec`。
3. 验证 compiler preserves goal/constraint semantics，或产生可由 Lean 检查的 compilation
   certificate。
4. 保持 suite hard safety 对 task prompt 的优先级，攻击 prompt 不得重写 task root。
5. 对 referent ambiguity、unknown object/region 和 contradictory source 产生显式 fail-closed
   verdict。

### 完成标准

- 同一 task artifact 确定性生成同一 mission claim digest；
- BDDL/registry 任意变化都会使冻结任务根失效；
- benchmark attack 只能改变 policy-facing prompt，不能改变 authenticated mission；
- goal-completing obligation 可追溯到原始 BDDL goal。

## 7. P3：实验与 ablation

所有方法必须使用相同 policy checkpoint、task、init state、policy seed、camera、horizon 和原始
proposal source。

### 主要对照

1. VLA only；
2. collision/safety filter only；
3. legacy Boolean Intent only；
4. legacy Boolean Effect only；
5. legacy Dual Lean；
6. temporal semantic layer only；
7. predictive physical-effect layer only；
8. CTDA without command binding；
9. CTDA without uncertainty handling；
10. CTDA with simulator fallback；
11. full available CTDA。

### 指标

- task success、safe success、success-but-unsafe；
- collision/cost、spec violation、violation severity；
- unsafe action rejection、false rejection、unknown rate；
- intervention lead time、risk exposure time、fallback success/latency；
- semantic/prefix/monitor checker latency和总 verifier tax；
- contract completion、pending timeout、replan 和 deadlock rate。

### 攻击与场景

- LIBERO-Safety 五 suites；
- SABER instruction perturbation/action inflation；
- dynamic obstacle、human intrusion 和 object binding swap；
- stale/replay/cross-episode evidence injection；
- actuator mismatch、observation loss、model-assumption failure；
- temporal ordering、deadline 和 cumulative-effect failure。

### 完成标准

- 每个主结果都区分 evaluator mode、evidence source 和 guarantee class；
- simulator oracle、noisy observer 和硬件 evidence 不混表；
- task success 与 safety decision 分开报告；
- 所有 paper table 可以由保存的 episode artifact 和版本化 summary script 重建。

## 8. P4：形式化组合定理

在前三阶段证据接口稳定后，建立：

```text
authenticated mission
∧ semantic refinement witness
∧ each prefix-pre certificate
∧ each observed-prefix certificate
∧ monitor-chain continuity
∧ plant/observer/timing/fallback assumptions
  => every checked prefix preserves the declared invariant
     ∧ complete implies the contract trace guarantee
     ∧ task phase advances only after a completion witness
```

定理必须明确区分：

- 对离散 artifact 的无条件 Lean 结论；
- 对 perception/dynamics/actuation assumptions 的条件保证；
- statistical uncertainty coverage；
- simulator-only 与 hardware-backed evidence。

## 9. 工程纪律

- 修改方法语义时同步更新 `docs/method.md`、Lean definition、Python reference checker 和
  differential tests；
- 新增 allow path 必须有对应 fail-closed negative tests；
- mock、empty evidence 或未验证 learned score 不得进入 authorization path；
- 不从缓存 episode 元数据替代 live task root/state/action-bound validation；
- 大模型和数据放 `/data0/ldx`，代码保留在仓库；
- 推送前至少运行 `uv run pytest` 和 `cd lean && lake build ProofAlign`。
