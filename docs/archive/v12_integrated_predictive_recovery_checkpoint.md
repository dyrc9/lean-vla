# v12.5 integrated predictive-recovery checkpoint

> 状态：2026-07-30 terminal pass。该 checkpoint 只覆盖 source-digest-bound、no-outcome、
> in-memory fixed-trace composition；不覆盖 simulator-integrated recovery、policy action dispatch、
> clean utility、attacked efficacy 或物理安全。

## 1. 组合目标

v12.4c 已证明 fresh π0.5 prefix 可以进入 controller-aware predictive screen；v12.2 已独立证明
typed recovery authorization、逐步 receipt、replay protection 和 fresh-state binding。v12.5
增加二者之间缺失的唯一入口：

```text
PolicyPrefixShadowDecision
  ├─ allow_exact       -> exact policy authorization
  ├─ block_replan      -> no authorization
  └─ recovery_required -> revoke policy authorization
                         -> one-use recovery session
                         -> ordered receipts
                         -> fresh-state reauthorization
```

组合层不加载 policy、不创建 simulator，也不检查任务 outcome。

## 2. population 与冻结边界

工程 pilot 使用 fresh-policy pilot 的3个 pair；formal 使用与之不重叠的 fresh formal 15个 pair。
每个 formal pair 从冻结 ledger 绑定 nominal/synthetic 两个实际 source-prefix digest，并运行四条路径：

1. nominal exact allow；
2. nominal prefix-digest substitution；
3. synthetic recovery happy path；
4. synthetic recovery-selection state substitution。

因此 formal 有15 pairs、30个 fresh source cases、60个 integrated cases。recovery sink 是内存 sink，
只用于验证 command/receipt identity；30次 sink apply 来自15条 happy path × 2 actions，不是
simulator recovery。

## 3. 正式结果

| 指标 | 结果 |
|---|---:|
| Valid / expected route | 60/60 |
| Source verdict match | 60/60 |
| Nominal exact authorization | 15/15 |
| Prefix substitution reject | 15/15 |
| Recovery open | 15/15 |
| Selection-state substitution reject | 15/15 |
| Recovery completion / receipt identity | 15/15 / 15/15 |
| Fresh-state policy authorization | 15/15 |
| Old policy authorization accepted | 0 |
| Recovery authorization replay accepted | 0 |
| Substituted fresh state accepted | 0 |
| Negative-path sink side effect | 0 |
| Policy load / inference / action dispatch | 0 / 0 / 0 |
| Simulator create / outcome read | 0 / 0 |

分类为 `integrated_predictive_recovery_v12_fixed_trace_pass`，全部冻结 gate 通过。

## 4. 当前结论与下一步

fresh screen 与 typed recovery 的 transaction composition 已在固定证据上关闭：exact allow 不改
prefix，两个 substitution path 在任何 sink side effect 前拒绝，trigger 后旧 authorization 和
recovery replay 都不可用，只有绑定 fresh recovered state 的新 policy authorization 可继续。

这仍不是 simulator-integrated recovery。下一步只授权 no-outcome simulator pilot：在少量独立
reset states 上进行 fresh inference、read-only predictive screen、typed recovery env steps、
receipt 验证和恢复后 fresh-state replan；继续丢弃 transition outcome。该 pilot 通过前不生成
clean/attacked 协议。
