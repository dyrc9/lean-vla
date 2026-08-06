# 当前状态与路线图

最后更新：2026-08-07。

本页是项目进度的**唯一默认入口**。以后回答“项目做到哪了”，只按以下主线组织：

```text
SABER攻击复现
  -> 原方法四臂完整实验
  -> 新方法v15.14 clean与SABER-attacked四臂
  -> 最终缺口核对
```

除非明确询问，日常进度不再逐项回顾 v8–v14、v15.1–v15.6 的失败实验。完整历史保留在
[`progress_and_plan.md`](progress_and_plan.md)，失败原因和停止规则保留在
[`failure_lessons.md`](failure_lessons.md)。

## 1. 复现了什么攻击

复现对象是 SABER 的 `constraint_violation` 指令攻击：

- victim：OpenPI Pi0.5；
- benchmark：LIBERO-Safety；
- 攻击输入：SABER 生成并冻结的 instruction perturbation records；
- 成功口径：clean-safe unit 在 attacked rollout 中出现 contact、joint-limit、excessive-force 或
  LIBERO cost/collision risk transition；task failure 本身不单独计为 transition。

M2 共完成60个base pairs、2组seed、clean/attacked合计240个episodes：

- valid episodes：`240/240`；
- clean-eligible units：`86`；
- risk transitions：`39`；
- 攻击成功率：`39/86 = 45.35%`；
- 95% base-pair cluster bootstrap区间：`[32.93%, 57.78%]`。

原预注册 gate 为50%，所以正式分类保持 `confirmatory_attack_foundation_nonpass`。论文可以写“成功复现出
明确攻击信号”，不能写“通过原确认性攻击门”。

## 2. 原方法的完整防御实验

当前完整的 clean/attacked 四臂 task-outcome 主实验是 v15.3。它使用18个全新task/init pairs，clean
与 attacked 使用相同任务、初态、environment seed和policy seed；每个条件运行四个arms。

| Arm | Clean success | Attacked success | Attacked crossing | Attacked joint-limit steps |
|---|---:|---:|---:|---:|
| VLA-only | 11/18 | 11/18 | 393 | 744 |
| Semantic-only（L1） | 11/18 | 12/18 | 227 | 416 |
| Execution-only（L2） | 11/18 | 11/18 | 0 | 0 |
| Dual（L1+L2） | 12/18 | 11/18 | 0 | 0 |

主结论：

- L1-only 降低了一部分物理风险，但没有消除；
- L2-only 与 Dual 都把本轮 actual crossing 和 joint-limit violation steps 降到0；
- Dual attacked task success 仍为 `11/18`，没有高于 VLA-only；
- 因而原方法证明了 simulator joint-limit containment，没有证明总体 attacked task efficacy。

若只统计“clean成功、attacked失败”，攻击成功率分别为 VLA-only `2/11=18.2%`、L1-only
`2/11=18.2%`、L2-only `3/11=27.3%`、Dual `4/12=33.3%`。这是18-task小样本中的任务层结果，
不能与M2的45.35%物理risk-transition口径直接相减。

冻结结果：

- clean：[`../experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_task_utility_qualification_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_task_utility_qualification_terminal_summary.json)
- attacked：[`../experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_attacked_task_utility_qualification_terminal_summary.json`](../experiments/proofalign_predictive_virtual_brake_v15_force_attributed_recovery_attacked_task_utility_qualification_terminal_summary.json)

## 3. 新方法当前优化结果

优化后的最终方法是 **v15.14 unified-force-envelope bounded state-triggered recovery**。它以`0.30 rad`
状态margin触发、保持`0.15 rad`安全floor和最多2次guarded candidate rollout，并让恢复候选统一服从
既有`10000`全局force envelope。开发过程和失败版本只在历史文档中保留，默认进度不再展开。

v15.14已经在同一批18个pair、相同environment/policy seeds上完成clean和SABER-attacked四臂：

| Arm | Clean success | Attacked success | Attacked constraint-violation ASR | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18 | 11/18 | 4/18 = 22.22% | 28 | 175 |
| Semantic-only（L1） | 13/18 | 13/18 | 1/18 = 5.56% | 295 | 317 |
| Execution-only（L2） | 13/18 | 11/18 | 0/18 = 0% | 0 | 0 |
| Dual（L1+L2） | 13/18 | 13/18 | 0/18 = 0% | 0 | 0 |

这里的ASR表示18个最终attacked episode中是否至少出现一次joint-limit violation或实际crossing，和第1节
M2的`39/86=45.35%`是不同population、不同denominator，不能直接相减。

主结论：

- L2把同批任务上的constraint-violation ASR从VLA-only的`22.22%`降到`0%`，但attacked task success
  仍为`11/18=61.11%`，说明L2单独提供的是物理containment，不恢复任务效用；
- L1把ASR降到`5.56%`，attacked task success为`13/18=72.22%`，但仍留下1个越界episode；
- Dual同时得到`0%` constraint-violation ASR和`13/18=72.22%` task success，保持了clean的总体成功数；
- L2与Dual均为0 deadlock、0 crossing、0 joint-limit step；最大force `6438.20 < 10000`，最大margin
  prediction error约`2.69e-13 rad`，最大screen latency `39.79ms`、p95 `18.30ms`、100ms miss为0；
- attacked四臂72/72完成，72/72首动作相对clean发生变化，attack metadata/prompt digest mismatch均为0，
  `76/76` checksums通过，全部正式gate为true。

因此新方法clean和SABER-attacked均正式`qualification_pass=true`。完整主表、口径和证据绑定见
[`paper/v15_14_final_four_arm_results.md`](paper/v15_14_final_four_arm_results.md)。

## 4. 最终还缺哪些实验

当前预定的论文主线模拟器实验已经全部完成：SABER攻击复现、原方法clean/attacked四臂、新方法clean四臂
和同配对SABER-attacked四臂均已有冻结结果。

剩余工作是论文写作、图表整理和最终审计，不再缺一轮必跑主实验。更多seeds、真实机器人、任意攻击族或
硬实时验证都属于扩展claim，不应写成当前结果已经覆盖。

所以当前状态是：

> 论文主线实验已收尾；优化后的Dual在最终18-pair SABER-attacked实验中保持13/18任务成功，并把
> constraint-violation ASR降到0/18。
