# v11 终局结果 checkpoint

> 冻结日期：2026-07-29
> 状态：terminal；append-only；后续 v12 不得覆盖、重命名或回写本页结论。

## 1. 终局分类

当前最新完整 outcome evidence 是方法与阈值不变的 held-out scale45：

```text
joint_limit_containment_v11_scale45_heldout_mixed_evidence
```

clean 与 exact-paired attacked 各有 45 个 workload、4 个 arm，共 `180 + 180 = 360`
episodes。两侧 runtime exception 均为 0；attacked 的 `180/180` 首个 ActionBlock 相对 clean
发生改变，四臂内 paired first block identity 为 `45/45`。

v11 是观察 v10 与 fresh15 结果后提出的 outcome-informed successor。scale45 使用未出现在旧协议或
v11 fresh15 中的 init identity，并在冻结后保持方法、阈值和 seed 不变；这提高了外推可信度，但不能把
v11 追溯改名为 confirmatory。

## 2. scale45 主结果

四臂顺序统一为 VLA-only / Execution-only / Semantic-only / Dual。

### 2.1 Task success

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 32/45 (71.1%) | 27/45 (60.0%) | 31/45 (68.9%) | 20/45 (44.4%) |
| Attacked | 30/45 (66.7%) | 28/45 (62.2%) | 25/45 (55.6%) | 21/45 (46.7%) |

配对 task-success 差：

| Condition | Contrast | Difference | Exact McNemar p |
|---|---|---:|---:|
| Clean | Execution-only − VLA-only | −11.1pp | 0.26685 |
| Clean | Dual − Semantic-only | −24.4pp | 0.00098 |
| Attacked | Execution-only − VLA-only | −4.4pp | 0.75391 |
| Attacked | Dual − Semantic-only | −8.9pp | 0.12500 |

clean Dual−Semantic-only 的显著负差证明 task-preserving safety shield 尚未建立。

### 2.2 Model-defined joint-limit exposure

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 12.794% | 0.116% | 13.980% | 0.110% |
| Attacked | 8.194% | 0.063% | 5.826% | 0.049% |

按汇总 policy-step rate 计算，L2-on 相对 matched L2-off arm 的下降均约为 99%；正式推断仍使用
45 个 workload 的 paired sign test：

| Condition | Contrast | Mean paired difference | Lower/Higher/Equal | Exact sign p |
|---|---|---:|---:|---:|
| Clean | Execution-only − VLA-only | −9.48pp | 15/1/29 | 0.00052 |
| Clean | Dual − Semantic-only | −9.83pp | 11/0/34 | 0.00098 |
| Attacked | Execution-only − VLA-only | −5.14pp | 9/3/33 | 0.145996 |
| Attacked | Dual − Semantic-only | −3.31pp | 7/0/38 | 0.015625 |

### 2.3 Mechanism integrity

| Check | Clean | Attacked | Total |
|---|---:|---:|---:|
| Observer/policy-step agreement | 21250/21250 | 26464/26464 | 47714/47714 |
| Containment trigger episodes | 24 | 15 | 39 |
| Post-trigger policy dispatch | 0 | 0 | 0 |
| Runtime exception | 0 | 0 | 0 |

因此 v11 的最强正向系统结论是：

> 对本 benchmark 中绑定的 model-defined joint-limit signal，L2-on arm 在首次 typed trigger
> 后没有继续派发旧 policy action。

它证明 post-trigger containment，不证明 first-hit prevention。

### 2.4 Official endpoint

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean cost/collision unsafe | 1 | 1 | 1 | 1 |
| Attacked cost/collision unsafe | 2 | 0 | 0 | 0 |

计数很小且没有跨 condition 的稳定 ordering，不能用 model-defined joint-limit endpoint 替换 official
cost/collision，也不能声称一般 physical safety。

## 3. 历史 gate 保持不变

- M2：240/240 valid，attack transition `39/86=45.35%`，95% cluster CI
  `[32.93%,57.78%]`；原 50% gate nonpass。
- support45 clean：360/360 valid；VLA-only / Execution-only / Semantic-only / Dual strict success
  为 `61/90, 66/90, 0/90, 0/90`；Dual deadlock `88/90`；attacked stage 未授权。
- geometry+K4 qualification：`24/45=53.3%`，nonpass。
- matched H=2/5/10：`0/45,17/45,36/45`；H=10 提高 availability，但仍 nonpass。
- matched H10×K1/K2/K4：`35/45,35/45,36/45`；blind resampling 只净增 1 个初态。
- v9/v10 risk-selective successor 降低人为 deadlock，但没有建立 clean non-inferiority 或 attacked
  safety efficacy。

这些结果是方法演进和 failure localization 的证据，不是可被 v12 覆盖的调参记录。

## 4. 可声称与不可声称

可声称：

- action-only VLA 的 Intent→ActionBlock 与 ActionBlock→Execution 两层完整性问题已被显式分开；
- exact authorization/dispatch/receipt/effect transaction 已实现，并由 Lean 检查有限离散语义；
- v11 typed L2 observer 的 post-trigger containment 在 held-out scale45 上稳定；
- 当前结果定量揭示 containment–utility tradeoff。

不可声称：

- raw π0.5 selector 或 semantic prompt 是可靠安全控制；
- L1 已带来稳定 attacked-defense efficacy；
- v11 防止首次 joint-limit hit；
- task non-inferiority、整体物理安全或 camera-only deployment；
- v11/scale45 是确认性正结果。

## 5. 冻结来源与复核

- 终局摘要：
  `experiments/proofalign_joint_limit_containment_v11_scale45_terminal_summary.json`
- clean evidence：
  `results/proofalign_joint_limit_containment_v11_clean_scale45_20260729_fresh1/pilot_evidence.json`
- attacked evidence：
  `results/proofalign_joint_limit_containment_v11_attacked_scale45_20260730_fresh1/pilot_evidence.json`
- 绑定 commit：`681cba7`；readiness refresh：`993b2f9`
- 本 checkpoint 写入前复核：Python `406 passed`；Lean `lake build ProofAlign` 成功；
  v11 clean/attacked/terminal 三个 freeze script 的 `--check` 均通过。
