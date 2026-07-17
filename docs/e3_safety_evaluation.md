# E3 safety-only evaluation

更新日期：2026-07-17 12:08 CST

## 结论

E3 已在提交 `a06eddd` 上完成。冻结的 12 个 E0-v2 affordance unit 均形成有效 Full CTDA record，
安全分类为 `12 preserved / 0 violated / 0 unknown`。117 次 policy dispatch 均有完整且为负的
collision/cost observation，并各自有 `hard_invariants_hold=true` 的 plant sample；没有未验证 Lean
artifact 或 Python/Lean parity failure。

这证明的是冻结 clean simulator trajectory 上的观察性安全保持和 fail-closed intervention semantics，
不是 task utility、attack-defense effectiveness、verified recovery、硬件安全或 real-time enforcement。
正式机器摘要为
[`proofalign_e3_safety_terminal_summary.json`](../experiments/proofalign_e3_safety_terminal_summary.json)。

## 与 E1 的边界

E3 是事前冻结的 Full-CTDA-only 独立实验，不是 E1-v3 的 replacement：

- E1-v3 的 12 个已 dispatch pair 继续保持 `terminal_invalid / 0 valid pair`；
- E3 不使用 VLA-only arm，不计算 retention、paired difference、false-block rate 或 utility；
- E3 初态直接逐 task 对照 E0 validity digest，避免跨 observer schema 配对；
- task success 与 timing 仅随 artifact 保留，不进入安全分类。

协议为 [`proofalign_e3_safety_protocol.json`](../experiments/proofalign_e3_safety_protocol.json)，runner 为
[`run_proofalign_e3_safety.py`](../scripts/run_proofalign_e3_safety.py)。正式 fresh root 是
`results/proofalign_e3_safety_20260717`，service invocation 为
`ed1e143c2d03447d95d4e73e48eec7d5`，GPU 3；GPU 1 的 FIPER 未被占用。

## 安全 gate 与结果

| gate | 结果 |
|---|---:|
| expected / recorded / valid | 12 / 12 / 12 |
| safety preserved / violated / unknown | 12 / 0 / 0 |
| policy dispatch | 117 |
| required / observed collision-cost observations | 117 / 117 |
| hard-invariant samples / failures | 117 / 0 |
| unverified Lean artifact / parity failure | 0 / 0 |
| block episode / block count | 12 / 12 |
| pre-dispatch / post-dispatch block | 12 / 0 |
| phase advance on block | 0 |
| fresh online fallback attempt | 0 |

12 条最终 decision 均为 `replan`，且都在新的 policy action dispatch 前发生；因此这些 block 没有产生
额外 raw action，也没有推进 mission phase。所有 episode 的 task success 均为 false，但这是明确分离的
utility 负诊断，不影响 collision/cost/hard-invariant 的安全分类，也不能反过来声称 false-block rate。

## Fallback stratum

fresh clean trajectory 没有出现 post-dispatch monitor failure，因此没有触发在线 fallback。E3 只能绑定
此前 outcome-blind、独立冻结的 E0 slow-interlock fallback evidence：当前 12 个 supported unit ×
seed 7/17/27 共 36/36 repetition 均通过 zero-hold actuation、receipt integrity、collision/cost、
hard invariant、contact observation 与 immediate postcondition gate。

所以当前可以写“这 12 个 unit 的独立 zero-hold fallback safety stratum 为 36/36 valid”，不能写
“E3 已验证 live violation 后 recovery”。后者需要另一个事前冻结、带独立 simulator oracle 的
post-dispatch intervention protocol；synthetic/fake-env fixture 只能证明实现语义。

## Artifact 与复核

| artifact | SHA-256 |
|---|---|
| `run_manifest.json` | `e26807ab088588177b61745ba3b38dc9fa1833d453dda5a58c76f276d00458e8` |
| `episodes_ledger.jsonl` | `8accb842dee489e0caefa502839af0ddc8093b6bfd1bc0c76109ec3c98f5281f` |
| `summary.json` | `f9038ea76ea638f2279e0d62196593f83464f644a6df6bfdc4e485f8fb7b8cd0` |

只读重算命令：

```bash
external/openpi/.venv/bin/python scripts/run_proofalign_e3_safety.py \
  --validate-results \
  --output-root results/proofalign_e3_safety_20260717
```

validator 已退出 0。结果目录约 25 MiB，包含 12 个 episode JSON 与 Lean request/result artifacts；不得
resume、覆盖或替换已 dispatch episode。
