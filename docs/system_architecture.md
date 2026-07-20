# ProofAlign 当前实现与后续目标架构

更新日期：2026-07-20

本文区分三件事：当前可审计实现、后续最小目标架构、以及不属于方法核心的支撑组件。方法语义以
[`method.md`](method.md) 为准，当前执行授权以 [`optimization_plan.md`](optimization_plan.md) 为准。

> 当前唯一执行线仍是 VLA-only 发布攻击复现。本文的目标架构不授权 CTDA、AEGIS、baseline、clean
> pilot 或 attacked+defended rollout。

## 1. 架构原则

后续架构只服务：

- 两个关系：Intent–Plan Integrity、Plan–Execution Integrity；
- 两个不变量：无双重授权不 dispatch、无 checked completion 不推进 phase；
- 三个转换：建立合同、授权 exact prefix、检查效果并更新 monitor。

任何模块、stage 或 schema 如果不能直接支持上述内容、必要 TCB 或独立消融，就不进入主控制路径。

## 2. 最小目标数据流

```text
trusted task artifact
  -> [Mission Adapter]
  -> MissionRoot

MissionRoot + phase + residual obligations
  -> [Persistent Contract Monitor]
  -> ActiveContract

policy prompt/RGB -> untrusted VLA -> ActionProposal

MissionRoot + ActiveContract + fresh state + monitor + ActionProposal
  -> [Exact Prefix Authorizer]
  -> PrefixAuthorization(final command) | reject | unknown

PrefixAuthorization
  -> [Single Dispatch Boundary]
  -> applied command + receipt + observed effect

receipt + observed effect
  -> [Persistent Contract Monitor]
  -> pending | complete | violated | unknown
```

外部方法图只暴露三个 transaction：

```text
certify contract -> authorize exact prefix -> check effect/update monitor
```

freshness/rebind 是 prefix authorization 的内部前置条件；progress/completion 是 monitor update 的内部状态；
signature、digest、wire 和 Lean artifact 不出现在主方法图中。

## 3. 五个核心组件

| 组件 | 唯一职责 | 明确不负责 |
|---|---|---|
| Mission Adapter | 从 trusted benchmark artifact 生成有限、版本化 `MissionRoot` | 通用自然语言理解、policy prompt trust |
| Persistent Contract Monitor | 保存 active contract、phase、history、residual obligation 和 completion | 独立物理 filter、任务重新规划 |
| Exact Prefix Authorizer | 在 fresh state 下决定 raw proposal/final command 是否同时满足任务授权和执行前约束 | 信任 policy 自报 admissibility |
| Single Dispatch Boundary | 只接受 fresh、单次 exact authorization，记录真正 applied command/receipt | 替 authorization 修改 command |
| Effect Observer/Updater | 检查 receipt/effect binding，原子更新 pending/completion/violation | 用 task success 或 policy metadata 伪造 completion |

Intent-only、Execution-only 和 Dual 共用同一组件边界，通过 method switch 禁用相应 judgment，不能复制
三套 runner。这样四臂消融面对相同 proposal、dispatch adapter、observer 和 intervention policy。

## 4. 三类架构层必须分开

### 4.1 Method core

- mission root；
- persistent contract/monitor；
- exact prefix authorization；
- dispatch/receipt/effect binding；
- checked completion。

它们定义论文方法和两个不变量。

### 4.2 Assurance plumbing

- canonical schema/wire；
- digest、nonce、version、timestamp；
- signature、producer identity、attestation；
- provenance、artifact ledger、cache；
- Lean spec、proof/replay、Python/Lean differential tests。

plumbing 只提高可审计性或支撑声明 TCB，不新增 alignment layer。普通 hash 不提供认证；签名不证明
payload 或物理世界为真；Lean replay 不证明 adapter 输入真实。

### 4.3 Optional intervention

- pass；
- project/brake；
- replan；
- hard block；
- AEGIS/CBF、predictive filter、recovery controller。

intervention 是 authorizer 后、dispatch 前的可替换策略。若它修改 nominal command，adjusted command 必须
重新经过 exact prefix authorization。Dual 的核心收益必须先在不绑定某个专用 filter 的条件下消融。

## 5. 目标 transaction 与状态提交

### 5.1 Contract transaction

```text
construct MissionRoot/ActiveContract
  -> validate trusted source and supported semantics
  -> atomically activate contract
```

### 5.2 Prefix transaction

```text
capture fresh state + monitor snapshot
  -> evaluate proposal/final command
  -> optional intervention
  -> reauthorize adjusted command if changed
  -> atomically commit one-use authorization
  -> dispatch
```

### 5.3 Effect transaction

```text
capture applied command + receipt + observed effect
  -> verify authorization binding
  -> evaluate pending/completion/violation
  -> atomically commit monitor/phase update
```

失败不能留下 proposal index、budget、deadline、history 或 phase 的部分更新。replan/reset 不得退款累计义务
或制造 progress。

## 6. Lean 与 fast checker 架构

目标不是逐 action 编译完整 Lean request，而是：

```text
Lean core specification
  -> proofs of two invariants and checker obligations
  -> versioned deterministic fast checker
  -> online decisions
  -> shadow/offline Lean replay and differential audit
```

进入 online 前至少需要：

1. Lean core theorem 明确对应两个不变量和三个 state transition；
2. fast checker 的输入 schema、版本、整数/浮点语义和 failure behavior 固定；
3. 建立 checker implementation 对形式 spec 的 refinement/equivalence evidence；
4. adapter-derived continuous quantities仍明确留在 TCB，不能写成 Lean 已独立证明；
5. latency、freshness 和 state snapshot/rebind 在真实控制条件下通过 gate。

现有 v1 四阶段和 v2 六阶段 Lean replay 保留作 regression/历史 artifact decoder。目标 API 不继承其公开
stage 数量；内部可以复用实现，但外部只暴露三个 transaction。

## 7. 当前代码映射

| 当前代码 | 当前事实 | 后续定位 |
|---|---|---|
| `src/proofalign/ctda.py` | v1 typed contract/evidence 与 Python checks | 提取可复用 domain types，不直接等于新 core |
| `src/proofalign/ctda_runtime.py` | v1 contract/binder/monitor orchestration | 历史 runtime；用于归因和接口审计 |
| `src/proofalign/ctda_wire.py` | v1 四阶段 canonical wire | 只读 replay compatibility |
| `src/proofalign/ctda_evaluator.py` | Python/Lean/shadow evaluator | 保留 differential/replay 能力 |
| `src/proofalign/ctda_v2.py` | certificate/rebind/intervention/progress prototype | 可复用语义库，不再是预设总架构 |
| `src/proofalign/ctda_v2_wire.py` / evaluator | 六阶段 wire 与 21-case parity | regression/历史 artifact，不决定新 API |
| `src/proofalign/benchmark/libero_task_manifest.py` | source-bound mission slice | Mission Adapter 候选实现 |
| `src/proofalign/benchmark/libero_online_wrapper.py` | simulator dispatch/trace/fallback | Single Dispatch Boundary 候选，仍属 TCB |
| `src/proofalign/benchmark/safelibero_*` | state/safety/provenance/no-action foundation | observer/experiment substrate，不自动进入 method core |
| `src/proofalign/benchmark/aegis_*` | no-action geometry/CBF/filter plumbing | optional intervention baseline |
| `src/proofalign/evidence_crypto.py` | Ed25519 producer/version binding | assurance plumbing |
| `lean/ProofAlign/CTDA*.lean` | v1/v2 typed checks、theorem 与 replay | 形式语义资产；需重建 core-to-wire 连接 |

代码模块暂时不因文档重构而修改。后续恢复时先定义最小接口，再决定复用、包装或淘汰哪些 class/file；
不能反过来让现有文件边界定义方法。

## 8. 当前运行模式的诚实解释

- `ctda-python-reference`：Python 是 authoritative runtime judgment；Lean 不是在线 authority。
- `ctda-lean-kernel`：v1 共同支持 request 逐 stage 进入 Lean，但约 0.65--1.95 秒 p99，只能视为
  slow-interlock/diagnostic。
- `ctda-shadow`：不改变 dispatch，用于 parity、latency、false-block/unique-catch calibration。
- v2 six-stage replay：no-dispatch normalized payload parity，不是 online execution architecture。

以后只有实际进入 dispatch decision、且 core-to-checker refinement 已建立的路径才能标记
`proof_verified=true`。shadow 或历史 replay 不授权任何 action。

## 9. Fail-closed 与 liveness

以下条件应拒绝或返回 unknown：

- unsupported/ambiguous mission；
- stale/replayed/cross-episode state 或 authorization；
- proposal 与 contract 不一致；
- adjusted command 未重新授权；
- command/receipt/effect binding 不一致；
- missing completion evidence；
- checker、serialization 或 TCB evidence failure。

但 fail-closed 不等于方法成功。架构必须显式测量：

- nominal allow rate；
- clean task/safe-success retention；
- phase completion；
- unknown/block/deadlock；
- blocked time 与 recovery；
- checker/filter/proof latency。

如果 clean liveness gate 不通过，停止 online method claim；可保留 offline audit 或 narrow execution-integrity
protocol。

## 10. 后续恢复顺序（当前不执行）

VLA-only threat qualification terminal 且用户重新授权后，按以下顺序恢复：

1. **Architecture refreeze**：冻结五组件、三个 transaction、四个 arm 和 TCB；不先加 filter/crypto。
2. **Core formalization**：只证明两个不变量与最小 transition；建立 fast-checker refinement。
3. **Fixed-trace four-arm shadow**：同一 proposal/trace 测 unique catch、nominal allow 和 latency。
4. **Clean closed-loop gate**：达到预注册 retention、completion、deadlock 和 evidence coverage。
5. **Qualified attack comparison**：只用已通过 VLA-only independent-safety gate 的 workload。
6. **Optional intervention**：最后添加 AEGIS/CBF、brake/replan/recovery 和外部 detector/semantic baseline。

任何一步失败都先缩小方法或 claim，不自动增加 stage、evidence type 或 fallback。

## 11. 当前执行边界

- 不修改 [`roadmap.md`](roadmap.md) 中的 VLA-only 攻击复现优先级；
- 不运行或扩展 CTDA v1/v2、AEGIS、SAFE/FIPER 或其他 defense arm；
- 不启动 architecture refreeze、clean pilot 或 attacked+defended matrix；
- 当前只允许解决阻断 official attack producer、unguarded victim 或独立 safety oracle 的问题；
- threat qualification terminal 后停止并请求新的明确授权。
