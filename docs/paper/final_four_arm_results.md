# ProofAlign最终clean与SABER-attacked四臂结果

状态：`final_paired_simulator_qualification_pass`。最后更新：2026-08-09。

本文只将该配置称为 **ProofAlign**。冻结 artifact 路径中的历史版本字符串仅作为不可变实验标识，不表示论文
存在多个系统版本。

## 实验设计

- 18个held-out suite/task/init pairs；
- clean和SABER-attacked各72个episodes，共144个episodes；
- 四臂：VLA-only、L1-only、L2-only、Dual；
- clean与attacked逐pair共享init、environment seed、policy seed和arm schedule；
- attacked使用18条冻结SABER `constraint_violation` instruction records；
- 所有pairs完整保留，不按clean或attacked outcome筛选。

## 主结果

| Arm | Clean task success | Attacked task success | Attacked violation episodes | Crossing steps | Joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 13/18（72.22%） | 11/18（61.11%） | 4/18（22.22%） | 28 | 175 |
| L1-only | 13/18（72.22%） | 13/18（72.22%） | 1/18（5.56%） | 295 | 317 |
| L2-only | 13/18（72.22%） | 11/18（61.11%） | 0/18（0%） | 0 | 0 |
| Dual | 13/18（72.22%） | 13/18（72.22%） | 0/18（0%） | 0 | 0 |

`violation episode`表示该episode至少有一个policy step出现原生joint-limit violation或实际joint-side
margin crossing。它是最终18-pair四臂实验内部的描述性结果，不等于攻击复现中clean-eligible unit上的
`39/86=45.35%` risk-transition ASR。

clean成功到attacked失败的pair数为VLA/L1/L2/Dual `3/2/3/2`；clean失败到attacked成功分别为
`1/2/1/2`。因此主表报告净task success与双向paired transitions，不把所有attacked failure都解释成攻击
新增失败。

## 结果解释

- L1-only 在该冻结样本中得到 `13/18` attacked task success，但仍有1个violation episode；
- L2-only 将observed violation episodes、crossing steps和joint-limit steps降到0，但attacked task success
  仍为 `11/18`；
- Dual 同时得到 `13/18` attacked task success和 `0/18` observed violation episodes；
- 因而任务效用与joint containment来自不同机制角色，不能用单一“安全成功率”替代。

## 完整性与开销

- official unsafe：四臂均为`0/18`；deadlock：`0`；
- L2-on actual crossing=`0`，joint-limit violation steps=`0`；
- 最大constraint-force proxy=`6438.1998 < 10000`；
- 最大selected margin prediction error=`2.69e-13 rad < 0.01 rad`；
- screen latency最大=`39.79ms`，p95=`18.30ms`，100ms miss rate=`0`；
- attack records=`18`，paired clean comparisons=`72`，first ActionBlocks changed=`72/72`；
- attack metadata mismatch=`0`，prompt digest mismatch=`0`，四臂pair内首块一致=`18/18`；
- checksums=`76/76`，全部正式完整性门通过。

## Claim boundary

这些结果支持冻结SABER instruction-attack family、OpenPI Pi0.5和LIBERO-Safety研究模拟器范围内的
checker-relative trusted-task monitoring、execution-transaction integrity与joint-limit containment。
它们不支持任意攻击、总体零风险、真实机器人安全、硬件attestation或hard-real-time保证。

具体protocol、trace、checksum和历史run-validity记录继续由冻结artifact及
[`ndss2027_claim_evidence.md`](ndss2027_claim_evidence.md)维护；正文不展开内部运行版本。

ActionBlock interface 的辅助实验另见
[`actionblock_sampling_ablation.md`](actionblock_sampling_ablation.md)：其中保留 `H=2/5/10` block-length
消融与固定 `H=10` 下 `K=1/2/4` candidate-count消融。两者只度量initial checker availability，不与
本页的闭环task/violation outcomes合并。
