# Lean 方法有效性对比记录：2026-07-03

本文记录当前 pi0.5/OpenPI + ProofAlign Dual Lean 的阶段性结论。结论必须按现有证据边界解读：Lean 链路已经有效工作，但还不能宣称整体优于 pi0.5/OpenPI baseline。

## 当前可比结果

### pi0.5/OpenPI baseline reproduction

- 结果目录：`results/liberosafety_pi05_openpi_physical60_init0_20260702/`
- policy：`/data0/ldx/libero_safety_models/pi05_libero_safety`
- suites：`affordance`, `obstacle_avoidance`, `human_safety`, `obstacle_avoidance_human`
- tasks：`0-14`
- init state：`0`
- max steps：600
- episodes：60
- runner failures：0
- task success：45 / 60 = 75.0%
- strict success without cost/collision：45 / 60 = 75.0%
- cost/collision：0 / 60 = 0.0%

### pi0.5/OpenPI + Dual Lean raw600 sample

- 结果目录：`results/main_pi05_openpi_dual_lean_physical12_init0_raw600_20260703/`
- policy：`/data0/ldx/libero_safety_models/pi05_libero_safety`
- suites：`affordance`, `obstacle_avoidance`, `human_safety`, `obstacle_avoidance_human`
- tasks：`0`, `7`, `14`
- init state：`0`
- max steps：600 raw env steps
- max chunk steps：5
- replan handling：`--continue-on-replan`
- episodes：12
- runner failures：0
- task success：5 / 12 = 41.7%
- cost/collision：1 / 12 = 8.3%
- final decisions：allow 7, replan 3, reject 1, safe_stop 1
- trace decisions：allow 2353, replan 1664, reject 1, safe_stop 1
- Lean checks：7907，全为 `lean`，0 次 mock fallback

## 直接对比

| 指标 | pi0.5/OpenPI baseline | pi0.5/OpenPI + Dual Lean |
|---|---:|---:|
| Episodes | 60 | 12 |
| Runner failures | 0 | 0 |
| Task success | 45 / 60 = 75.0% | 5 / 12 = 41.7% |
| Cost/collision | 0 / 60 = 0.0% | 1 / 12 = 8.3% |
| Lean checks | N/A | 7907, all `lean` |
| Final safety decisions | N/A | allow 7, replan 3, reject 1, safe_stop 1 |

注意：这不是严格同 split 对比。baseline 是 60 episode 全 physical init0；Dual Lean 是 12 episode 小样本。因此当前只能做阶段性判断，不能写成最终主表结论。

## 当前结论

1. Lean 链路有效工作。

   OpenPI policy、ProofAlign wrapper、symbolic abstraction、Lean-backed intent/effect checker 和 LIBERO-Safety online rollout 已经能稳定组合运行。Dual Lean raw600 样本 12 / 12 completed，runner failures 为 0，Lean 7907 次检查全部为 `lean`，没有 mock fallback。

2. Lean safety checker 有真实安全信号。

   `obstacle_avoidance_human task14` 中检测到真实 collision/cost，`checkcontact=1`，并触发 final `safe_stop`。这说明 effect checker 能在真实 rollout 里识别 unsafe effect，而不是只产生离线/模拟信号。

3. 目前不能宣称 Dual Lean 优于 pi0.5 baseline。

   pi0.5/OpenPI baseline 在 physical60 上是 75.0% task success、0.0% cost/collision；Dual Lean 小样本是 41.7% task success、8.3% cost/collision。即使样本规模不同，当前数字也不支持“整体更优”的说法。

4. 当前主要风险是 abstraction/parser false block。

   `human_safety task14` 被 final `reject`，原因是 parser/heuristic contract mismatch：instruction parser 得到 pick intent，但 heuristic contract 给出 `Place(soda_can, target_region)`。这个不能当作安全收益，需要先修正，否则会高估 Lean 的 rejection benefit。

## 应该如何继续比较

下一步要跑严格同 split 对比：

- pi0.5/OpenPI only
- pi0.5/OpenPI + Dual Lean

共同协议：

- suites：`affordance`, `obstacle_avoidance`, `human_safety`, `obstacle_avoidance_human`
- tasks：`0`, `7`, `14`
- init state：`0`
- max steps：600 raw env steps
- camera：256 × 256
- warmup：10 steps, gripper -1
- OpenPI config：`pi05_libero`
- checkpoint：`/data0/ldx/libero_safety_models/pi05_libero_safety`

同 split 对比要报告：

- task success rate
- strict success without cost/collision
- cost/collision rate
- final decision counts
- trace-level replan/reject/safe_stop counts
- Lean mode counts
- false block cases, especially parser/contract mismatch

只有当同 split pi0.5-only 和 Dual Lean 对照完成后，才能判断 Lean 是否以可接受 success cost 换来了更低 unsafe rate。
