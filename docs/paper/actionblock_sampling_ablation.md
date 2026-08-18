# ActionBlock长度与候选采样数消融

状态：**frozen auxiliary evidence**。最后整理：2026-08-09。

本页登记已经完成的 ActionBlock interface 消融，避免其在单一最终系统叙事中丢失。这里包含两个不同变量：

- `H`：一个 source ActionBlock 中纳入 checker assessment 的连续动作步数；
- `K`：在相同 `H=10` 接口下累计考虑的独立 source ActionBlock 候选数。

两项消融均为 matched、no-task-outcome、zero-dispatch 的 initial checker-availability 测量。它们不执行动作，
不读取任务结果，也不估计 task success、攻击防御效果或物理安全。其作用是解释 ActionBlock interface 的
availability，而不是构成最终四臂 outcome 实验的一部分。

## A. ActionBlock长度消融：H=2/5/10

实验在45个 `task/init/source-policy-chunk` paired units 上，从同一个原生 `H=10` source chunk 提取
nested prefixes，并在相同 checker 条件下比较 `H=2,5,10`。`H=2/5` 只做 shadow assessment；固定
`min_progress=0.002 m`、`max_projection_l2=0.5`，未因结果调整阈值。

| Assessed block length | Eligible | Eligible rate | 新增eligible（相对前一长度） | Hard-violation candidates |
|---:|---:|---:|---:|---:|
| H=2 | 0/45 | 0% | — | 0 |
| H=5 | 17/45 | 37.78% | +17、0 loss | 0 |
| H=10 | 36/45 | 80.00% | +19、0 loss | 0 |

H=10 的 suite-level availability 为：

- `human_safety`：`12/15 = 80.00%`；
- `obstacle_avoidance`：`13/15 = 86.67%`；
- `obstacle_avoidance_human`：`11/15 = 73.33%`。

eligibility pattern（H2/H5/H10）为 `000:9, 001:19, 011:17`。该结果说明，在固定progress checker下，
较长prefix提供了更多可观测进度，因此 initial checker availability 随 `H` 单调增加；它不证明长block会
提高闭环task success或安全性，也不支持拼接超过policy原生输出上限的stale-observation open-loop动作。

冻结绑定：

- terminal summary：
  [`../../experiments/proofalign_four_arm_v4_l1_block10_terminal_summary.json`](../../experiments/proofalign_four_arm_v4_l1_block10_terminal_summary.json)；
- protocol：
  [`../../experiments/proofalign_four_arm_v4_l1_block10_qualification_protocol.json`](../../experiments/proofalign_four_arm_v4_l1_block10_qualification_protocol.json)，
  SHA-256 `91586bbd2fd59b527a345109e8777fdbb432bd046dd4f75c13d1db372dc45509`；
- terminal summary绑定的frozen result root为
  `results/proofalign_four_arm_v4_l1_block10_qualification_20260728_fresh1`；该raw root当前不在checkout中，
  如需逐行复现必须恢复原始不可变目录并重新校验checksums，不能由summary补造；
- frozen `summary.json` SHA-256：
  `5c36801a9bba4154a6329f5c37d94f3e87d90494d9db08befd17ab72cb2dcee6`。

## B. 候选采样数消融：固定H=10，K=1/2/4

实验在另一组冻结的45个 `task/init/ordered-source-candidates` paired units 上，对每行生成4个相互不同的
`H=10` source ActionBlocks。`45/45` 行均有4个不同的 source-chunk digests，然后比较累计考虑前
`K=1,2,4` 个候选时，是否至少存在一个 checker-eligible ActionBlock。

| Candidate count | 至少一个eligible | Coverage | 相对K=1净增 |
|---:|---:|---:|---:|
| K=1 | 35/45 | 77.78% | — |
| K=2 | 35/45 | 77.78% | 0 |
| K=4 | 36/45 | 80.00% | +1/45（2.22 pp） |

K=4 的 suite-level availability 为：

- `human_safety`：`14/15 = 93.33%`；
- `obstacle_avoidance`：`13/15 = 86.67%`；
- `obstacle_avoidance_human`：`9/15 = 60.00%`。

累计 eligibility pattern（K1/K2/K4）为 `111:35, 001:1, 000:9`。尽管每行4个ActionBlocks均不相同，
blind stochastic resampling 从K=1增加到K=4只额外覆盖1个初态。因此这项消融不支持“增加IID候选采样即可
实质解决checker availability”的解释，并为最终系统保持 `K=1,H=10` 的单一source-action接口提供了
范围受限的工程证据。它不证明K>1在其他policy、checker或distribution下永远无效。

冻结绑定：

- terminal summary：
  [`../../experiments/proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json`](../../experiments/proofalign_four_arm_v4_l1_block10_k4_terminal_summary.json)；
- protocol：
  [`../../experiments/proofalign_four_arm_v4_l1_block10_k4_qualification_protocol.json`](../../experiments/proofalign_four_arm_v4_l1_block10_k4_qualification_protocol.json)，
  SHA-256 `e65bd7387209cb7a3ba03e8380d9bca5f52e31d7f6be027149bfad1d7fdbcfc0`；
- terminal summary绑定的frozen result root为
  `results/proofalign_four_arm_v4_l1_block10_k4_qualification_20260728_fresh1`；该raw root当前不在checkout中，
  如需逐行复现必须恢复原始不可变目录并重新校验checksums，不能由summary补造；
- frozen `summary.json` SHA-256：
  `c68b28a04ec20847ac5835e4dd86560f510abfc1c4ac2bde3a59c4098ac98b89`。

## 论文可用表述

> 在独立的45-unit、zero-dispatch/no-outcome interface ablations 中，固定checker下的initial availability
> 随ActionBlock长度从H=2的0/45、H=5的17/45增加到H=10的36/45；而固定H=10后，将独立source-block
> 采样数从K=1增加到K=4只将coverage从35/45提高到36/45。前者表明checker需要足够长的prefix观察局部
> 进度，后者表明blind IID resampling在该冻结配置上的边际收益很小。这些结果只度量checker availability，
> 不代表闭环任务成功、安全性或攻击防御效果。
