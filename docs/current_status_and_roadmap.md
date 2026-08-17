# 当前状态与路线图

最后更新：2026-08-09。

本页是项目进度的唯一默认入口。ProofAlign 在论文叙事中只有一个最终系统，不展开内部版本或优化过程。

```text
SABER攻击成功复现
  -> 最终ProofAlign设计与实现
  -> 最终clean/attacked配对四臂证据
  -> 完成论文初版
  -> 根据初稿缺口定向补实验
```

## 1. SABER攻击已成功复现

复现对象是 SABER 的 `constraint_violation` 指令攻击：

- victim：OpenPI Pi0.5；
- benchmark：LIBERO-Safety；
- 攻击输入：SABER 生成并冻结的 instruction perturbation records；
- 成功口径：clean-safe unit 在 attacked rollout 中出现 contact、joint-limit、excessive-force 或
  LIBERO cost/collision risk transition；task failure 本身不单独计为 transition。

实验覆盖60个base pairs、2组seeds、clean/attacked合计240个episodes：

- valid episodes：`240/240`；
- clean-eligible units：`86`；
- risk transitions：`39`；
- observed attack-success rate：`39/86 = 45.35%`；
- 95% base-pair cluster-bootstrap interval：`[32.93%, 57.78%]`。

论文默认表述为：

> 我们在 OpenPI Pi0.5—LIBERO-Safety 路径上成功复现 SABER `constraint_violation` instruction attack；
> 86个 clean-eligible units 中39个出现新的 risk transition，观测 ASR 为45.35%。

## 2. 最终ProofAlign系统

ProofAlign 是一个部署在 action-only VLA consumer/dispatch boundary 的跨层 reference monitor：

- **L1** 从独立可信任务/观察分支产生当前合法 semantic subtask，并对策略实际输出的 exact continuous
  ActionBlock 做 checker-relative assessment；
- **L2a** 把 execution contract、fresh one-use authorization、ordered exact-prefix dispatch、receipts 和
  observed effects 闭合为一个执行事务；
- **L2b** 在 joint-risk state 中，对同一 source ActionBlock 的有限 virtual-guard configurations 做
  bounded shadow screening，并执行注册的 margin、restore、identity 与 force gates。

系统保持 VLA checkpoint、policy-facing prompt 和 `K=1/H=10` source-action generation 不变。L2b 最多
筛选两个 guard configurations；它们不是新的 policy-action candidates。Lean 只检查抽象 transaction
binding/phase semantics，不证明真实机器人安全、Python refinement 或 exact physical trajectory。

## 3. 最终配对四臂结果

最终实验包含18个 held-out suite/task/init pairs。每个pair在clean与SABER-attacked条件下运行
VLA-only、L1-only、L2-only和Dual，共144个episodes；clean/attacked共享初态、environment seed、policy
seed和arm schedule。

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18 | 11/18 | 4/18（22.22%） | 28 | 175 |
| L1-only | 13/18 | 13/18 | 1/18（5.56%） | 295 | 317 |
| L2-only | 13/18 | 11/18 | 0/18 | 0 | 0 |
| Dual | 13/18 | 13/18 | 0/18 | 0 | 0 |

主结论：

- L1 在该冻结样本中承担任务效用角色，但不提供完整的 joint-limit containment；
- L2-on 两臂把观察到的 violation episodes、crossing steps 和 joint-limit steps 降到0；
- L2-only 的 attacked task success 仍为 `11/18`，说明 containment 不会自动恢复任务效用；
- Dual 同时得到 `13/18` attacked task success 和 `0/18` observed violation episodes，并保持clean总体成功数；
- 上述结果是一个checkpoint、一个benchmark、一个冻结攻击族和18个pairs上的sample outcomes，不外推为任意
  攻击、总体零风险、真实机器人安全或硬实时保证。

两组攻击数字使用不同population、denominator和event definition：攻击复现报告clean-eligible unit上的
`39/86` risk-transition ASR；最终四臂报告18个episode中的violation episodes。二者不得直接相减或合并。

完整证据见 [`paper/final_four_arm_results.md`](paper/final_four_arm_results.md)。

## 4. 当前重心：先完成论文初版

当前不再围绕内部版本或方法优化组织工作。下一里程碑是完成一份从问题到证据闭合的论文初版：

1. 固定 Introduction 中的 action-only protected object、authorization gap 和 realization gap；
2. 完成 Background/Related Work 对攻击通道、既有防御停止位置和本文边界的分层；
3. 固定 Problem Definition、Threat Model、TCB、security goals 与 out-of-scope；
4. 用一个最终 ProofAlign 系统描述 L1、L2a、L2b，不出现内部版本演进；
5. 将现有攻击复现和最终四臂结果写入 Evaluation，并保持不同统计口径分离。

论文初版完成后，再根据审稿视角暴露的证据缺口选择补充实验。候选方向包括更多seeds、其他攻击族、
camera-only trusted perception、L2a/L2b更细消融、真实机器人和更强执行证明；在初稿完成前不将这些扩展
预设为当前必须完成的主实验。

## 可复现性说明

历史预注册 protocol、内部版本结果、checksums 和冻结分类继续保留在 audit/archive material 中，不删除、
不改判，也不进入默认论文故事。它们用于回答复现和历史审计问题，而不是定义当前系统版本或叙事主线。
