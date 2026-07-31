# 最终实验图表与 Lean 边界

本页图表由 [`../../scripts/plot_final_paper_results.py`](../../scripts/plot_final_paper_results.py)
直接读取冻结的 v11/v12 JSON 汇总生成。v12 ledger 明确不读取 task outcome，因此不能从该实验
推断 task success。

## 1. Lean 用在什么地方

Lean 位于 L2 `ActionBlock -> Execution` 事务层，不参与 π0.5 推理、MuJoCo 数值积分、beam search
或 virtual-joint-stop 参数优化。

当前 machine-checked 核心位于：

- [`../../lean/ProofAlign/IntegrityCore.lean`](../../lean/ProofAlign/IntegrityCore.lean)：原始
  ActionBlock、authorization、receipt、effect 与 phase-gating 语义；
- [`../../lean/ProofAlign/SemanticIntegrityCore.lean`](../../lean/ProofAlign/SemanticIntegrityCore.lean)：
  增加 semantic context/subtask/prompt identity、ordered receipt window 和 one-use authorization。

Lean 检查的关键性质包括：

1. 四臂 L1/L2 开关 truth table；
2. authorization 绑定同一 semantic context、ActionBlock、assessment、execution contract 和 exact
   final command；
3. 被消费的 authorization 不可再次使用；
4. 每条 bound receipt 使用同一 authorization，且 applied action digest 等于 authorized action
   digest；
5. unknown effect 或 incomplete prefix 不能形成 execution alignment；
6. L2-enabled phase advance 必须蕴含完整 execution alignment；
7. 任意 phase advance 都必须具有 trusted contract completion evidence。

Lean 不证明 learned selector/assessor 正确，不证明 simulator 等价于物理世界，也没有给出完整
Python-to-Lean refinement proof。正确 claim 是 **Lean-checked execution transaction semantics**，
不是“Lean 证明机器人安全”。

## 2. SABER 攻击—防御主实验

![SABER attack defense scale45](figures/v11_saber_attack_defense_scale45.png)

本图来自 v11 frozen held-out scale45。官方 SABER task-prompt attack records 被 deterministic
transplant 到45个未见 workload；四臂合计180条 attacked episodes：

| Arm | Attacked task success | Joint-limit step rate | Containment triggers |
|---|---:|---:|---:|
| VLA-only | 30/45 (66.7%) | 8.194% | 0 |
| Execution-only / L2 | 28/45 (62.2%) | 0.063% | 9 |
| Semantic-only / L1 | 25/45 (55.6%) | 5.826% | 0 |
| Dual / L1+L2 | 21/45 (46.7%) | 0.049% | 6 |

攻击使 `180/180` 首个 ActionBlock 相对 paired clean 改变；四臂共享输入 identity 为 `45/45`。
15个 attacked trigger episodes 之后的 dispatch 为 `0`。L2 的机械 containment 信号明确，但
任务成功率没有优于对应 control：Execution-only−VLA-only 为 `−4.4pp`，Dual−Semantic-only 为
`−8.9pp`。因此结果不能写成一般 attacked-defense efficacy。

矢量版：[PDF](figures/v11_saber_attack_defense_scale45.pdf)。

## 3. v12 最终 engineering validation

![v12 final engineering validation](figures/v12_final_engineering_validation.png)

| Split | Seeds | Exact advances | Min actual margin | Exact guard action identity | Beam config identity | Pred/exec max error |
|---|---|---:|---:|---:|---:|---:|
| Development | 10509/10510 | 10/10 | 0.1661929 rad | 6/6 | 160/160 | 0 |
| Frozen held-out | 20509/20510 | 10/10 | 0.1661158 rad | 6/6 | 160/160 | 0 |

冻结 floor 为 `0.15 rad`。两组 warning、crossing/contact saturation、torque-bound violation、
live dispatch、typed recovery 和 outcome read 均为 0。最大 target-DOF generalized constraint
force 分别约为 `9999` 和 `9985`，因此结果只支持 hard simulator virtual-joint-stop 机制，
不支持 actuator-only authority、task utility 或物理安全。

矢量版：[PDF](figures/v12_final_engineering_validation.pdf)。

## 4. v11 containment–utility tradeoff

![v11 containment utility tradeoff](figures/v11_containment_utility_tradeoff.png)

该 held-out scale45 图使用每个 condition、每个 arm 45 episodes。L2-enabled arms 的 model-defined
joint-limit exposure 明显下降，但 clean task success 同时下降。该结果支持 post-trigger
containment 和 utility tradeoff，不支持 first-hit prevention 或完整 defense efficacy。

矢量版：[PDF](figures/v11_containment_utility_tradeoff.pdf)。

## 5. 重现

```bash
.venv/bin/python scripts/plot_final_paper_results.py
```
