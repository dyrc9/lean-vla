# ProofAlign 当前与目标架构

更新日期：2026-07-14

本文描述代码中已经存在的路径，以及 first sprint 需要闭合的目标路径。方法语义以
[`method.md`](method.md) 为准。

## 1. 目标数据流

```text
trusted benchmark task / BDDL / registry
  -> locally frozen MissionSpec
  -> mission-rooted active contract

policy-facing prompt + RGB
  -> untrusted VLA
  -> raw action proposal

MissionSpec + active contract + trusted state + raw proposal
  -> independent proposal binder
  -> ctda-wire-v1 semantic/prefix request
  -> Lean CTDA evaluator
  -> exact dispatch or fail-closed

dispatch + simulator receipt + trusted observed state
  -> plant/event prefix
  -> ctda-wire-v1 observed/monitor request
  -> persistent monitor
  -> safe_pending / complete / fail-closed
```

只有两层 alignment：

- **Intent–Plan Alignment**：trusted mission intent/phase/residual 与 VLA planned raw action；
- **Plan–Execution Alignment**：第一层接受的 exact plan 与 dispatch/applied/receipt/observed effect。

serialization、digest、provenance、uncertainty 和 fallback 是共享机制，不是额外的 alignment
layer。

## 2. 当前代码模块

| 模块 | 当前职责 | 当前边界 |
|---|---|---|
| `src/proofalign/ctda.py` | typed mission/contract/evidence、digest 与 Python reference checks | 不是 online Lean evaluator |
| `src/proofalign/ctda_runtime.py` | mission-rooted contract、raw binder、四阶段 evaluator transaction、persistent monitor | 当前只支持有限 Pick/Place slice |
| `src/proofalign/ctda_wire.py` | strict `ctda-wire-v1`、canonical digest 与 Python reference semantics | 不替换 episode/attack schema |
| `src/proofalign/ctda_evaluator.py` | Python/Lean/shadow evaluator、cache 与 replay artifact | 当前逐 request 编译，非 real-time |
| `src/proofalign/ctda_shadow.py` | JSON/JSONL/episode/fixture CPU replay、parity、latency、provenance | synthetic corpus 不提供 ground truth |
| `src/proofalign/benchmark/libero_online_wrapper.py` | LIBERO reset、policy call、raw-step dispatch、trace 和 fallback | simulator adapter 属于声明 TCB |
| `src/proofalign/benchmark/libero_task_manifest.py` | source-bound LIBERO task manifest 校验与 exact contact-part mission 编译 | E0 v2 已冻结 12-task non-real-time supported slice |
| `src/proofalign/benchmark/libero_online_runner.py` | task root、SafetySpec、fallback manifest、evaluator mode 和 CLI | simulator adapter 属于 TCB |
| `experiments/libero_openpi_plugin.py` | pi0.5/OpenPI inference、完整归一化 action chunk 与 policy-call audit id | `proofalign_action` 来自 instruction heuristic，只能作兼容 metadata |
| `experiments/libero_vla_plugin.py` | legacy action abstraction 与 OpenVLA diagnostic | 不是 paper CTDA contract authority |
| `src/proofalign/lean_bridge.py` | legacy Lean claim bridge | 不用于 paper CTDA wire path |
| `lean/ProofAlign/CTDA.lean` | CTDA datatypes、staged checks、monitor、theorem | 核心 typed specification |
| `lean/ProofAlign/CTDAWire.lean` | 共同支持的四阶段 wire checker | 有限离散 semantics，不证明 adapter 真值 |
| `scripts/run_liberosafety_pi05_openpi_eval.py` | 纯 pi0.5 clean/attack rollout | 不导入 defense checker |
| `scripts/run_libero_online_batch.py` | defense/ablation online batch | evaluator mode 必须进入每个 artifact |

## 3. 当前运行模式

### `legacy-lean-boolean`

Python 构造 concrete Boolean claim，Lean 以 `by decide` 检查。该路径证明 Lean 能进入真实
rollout，但其结果不能当作 CTDA theorem/evaluator 的在线证据。

### `ctda-python-reference`

当前完整 CTDA simulator loop。它实现 typed bindings、persistent state 和 fail-closed behavior，
但 authoritative judgment 仍来自 Python reference code。

### `ctda-lean-kernel`

每个共同支持的 `semantic`、`prefix_pre`、`observed_prefix` 和 `monitor_step` request 经
`ctda-wire-v1` 送入 Lean；只有 kernel 检查通过才允许 dispatch/phase advance。

### `ctda-shadow`

Python 与 Lean 同时评估但不改变 action，用于 parity、latency 和 clean false-block calibration。
shadow 结果不能授权实际执行。

当前本地 golden corpus 为零 mismatch，但逐 request Lean replay p99 约 0.65--1.95 秒，因此该
mode 目前是 slow interlock/offline audit，不是 20 Hz real-time evaluator。

## 4. First sprint 已闭合的四个 P0 接口

### 4.1 Trusted task adapter

输入 benchmark-owned task artifact，输出有限域 `MissionSpec`。必须明确 supported task slice；
unsupported task fail closed。当前不是通用 verified BDDL compiler。

E0 v2 candidate registry 逐 task 固定 BDDL SHA-256、single `CheckGripperContactPart` target/geom set。
runner 还要求显式 registry trust-anchor；observer 直接读取 MuJoCo contacts，分别记录左右 fingerpad
命中的 object geoms。exact goal atom 只有在两侧均命中时成立；该路径不调用 benchmark success oracle。

### 4.2 Mission-rooted contract provider

从 `MissionSpec + active phase + residual obligation` 提供 active contract。policy prompt 和
policy `proofalign_action` 只能记录在 untrusted metadata 中，不能改变 active contract。

### 4.3 Independent raw proposal binder

从 trusted state 和 raw commands 判断 prefix 是否与 active contract 一致。binder verdict 必须由
consumer 计算，不能接受 policy 自报 Boolean。最小支持 `Pick`/`Place` slice。

Pick/approach 的 bounded-stutter 分支使用合同级累计预测平移、累计六维 command-path、持久
no-progress 与原 deadline 四重上限。预算在 authorization commit 时消耗，reset/replan 不退款；其
连续动作解释仍属于 Python binder/adapter TCB，而不是 Lean raw-action theorem。

### 4.4 CTDA evaluator transaction

统一 evaluator interface：

```text
evaluate(canonical wire request) -> verdict + proof/audit artifact
```

状态提交顺序：

```text
construct request
  -> evaluate
  -> if proven: atomically commit authorization/monitor state
  -> else: no dispatch and no partial state mutation
```

## 5. `ctda-wire-v1` 最小 envelope

```json
{
  "schema_version": "ctda-wire-v1",
  "request_id": "content-addressed id",
  "stage": "semantic | prefix_pre | observed_prefix | monitor_step",
  "time_unit": "ns",
  "checker_version_digest": "...",
  "payload": {}
}
```

要求：

- canonical UTF-8 JSON、稳定 key 顺序、拒绝 NaN/Infinity；
- 时间只用非负 integer nanoseconds；
- temporal formula 使用 tagged union，不执行任意字符串；
- critical digest 由 consumer 重算；
- 未知字段/enum、缺字段和类型错误默认拒绝；
- 保存 request、generated Lean artifact、checker digest、stdout/stderr 和 verdict，支持 kernel
  replay。

该 wire schema 是内部协议，不替换 episode JSON 或 attack-record schema。

## 6. 信任边界

当前方法允许 simulator state adapter 属于 TCB。因此 camera attack 可以攻击 policy RGB，但
不能同时被描述为攻陷 CTDA observer。若未来让 policy 与 monitor 共用同一被攻击 camera，必须
重新定义保证或加入独立 sensing。

以下不是当前 TCB 能力：

- 密码学 task authentication；
- authenticated IPC/process isolation；
- hardware actuator receipt；
- sensor attestation；
- verified dynamics/fallback。

## 7. Fail-closed 规则

以下任一条件发生时不得 dispatch 或 phase advance：

- unsupported/ambiguous mission or contract；
- missing/stale/replayed/cross-episode binding；
- raw proposal binder `refuted/unknown`；
- serialization/Lean build/evaluator/cache/parity error；
- receipt/command/trace mismatch；
- timestamp rollback 或 monitor history mismatch；
- missing completion/post evidence；
- evaluator timeout。

Fail-closed 本身不是安全收益。实验必须单独报告 false block、deadlock 和 availability cost。

## 8. 当前环境分工

- 本地无 GPU：contract source、binder、wire、Lean evaluator、golden corpus 和 shadow harness
  已完成；下一本地工作只允许 latency 优化与 fixture calibration。
- 远程 GPU：在本地 readiness gate 通过后运行 pi0.5/OpenPI、LIBERO-Safety 和发布攻击
  workload。详见 [`remote_execution.md`](remote_execution.md)。
