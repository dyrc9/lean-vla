# 论文故事：VLA 的任务授权与执行完整性

更新日期：2026-07-20

> 本文描述候选论文叙事，不代表当前已获得 defense efficacy。当前唯一执行线仍是 VLA-only 发布攻击
> 复现；方法实验保持冻结。

## 一句话定位

> ProofAlign treats VLA control as two coupled integrity problems: whether a
> proposed action remains authorized by a trusted task, and whether the accepted
> action is the one actually applied and observed until checked completion.

中文：ProofAlign 只检查两件事——VLA 计划的动作是否仍获可信任务授权，以及被接受的动作是否被真实
执行并产生了经过检查的效果。

## 1. 问题

高 task success 不等于按原始授权完成任务。VLA 可能：

- 因 attacked prompt、视觉或历史执行错误对象、部件、顺序或 gripper 操作；
- 输出局部看似合理的 chunks，却跨 calls 累积成未授权效果；
- proposal 合法，但 filter、dispatch、applied command 或 observed effect 已被替换；
- 把 `pending`、旧 trace 或 policy 自报 completion 当成任务完成。

这些失败属于两个不可互相推出的关系：

```text
trusted intent -- Intent–Plan Integrity --> accepted planned action
accepted planned action -- Plan–Execution Integrity --> applied/observed action
```

semantic-only 方法看不到执行替换；physical/filter-only 方法又可能放行物理上安全但任务上未授权的动作。

## 2. 最小方法

论文只展示三个转换：

```text
1. certify contract
   trusted mission + phase + residual obligations -> persistent contract

2. authorize exact prefix
   contract + fresh state + raw proposal -> one exact final command authorization

3. check execution/effect
   authorization + receipt + observed effect -> pending / complete / violation
```

两个不变量：

- **No dispatch without dual authorization**：没有 mission-rooted contract 和 fresh exact-prefix
  authorization，不得 dispatch。
- **No phase advance without checked completion**：没有覆盖合同 postcondition 的 completion witness，
  不得推进任务阶段。

persistent monitor 只是保存跨 chunks 的合同、history、deadline 和 residual obligation，不是第三层方法。

## 3. 论文只保留三个贡献

1. **安全属性**：把攻击下 VLA 执行拆成 Intent–Plan 和 Plan–Execution 两个互补完整性关系，并给出
   两个协议不变量。
2. **最小协议**：提出 mission-rooted persistent monitor，通过合同建立、exact-prefix authorization 和
   execution/effect update 三个事务实现 complete mediation；只形式化真正进入运行路径的离散性质。
3. **因果评估**：在相同 proposal/trace 与配对 closed loop 下比较 VLA-only、Intent-only、
   Execution-only 和 Dual，先检验 clean utility，再检验两层 unique catch 和组合收益。

攻击生成、签名、source hash、provenance、wire schema、Lean、AEGIS/CBF 和 recovery 都不是独立方法贡献。
它们分别属于 workload、assurance plumbing 或 optional intervention。

## 4. 候选新意及其举证责任

最稳健的候选增量是：

> A trusted mission remains the authorization root while dynamically generated
> VLA prefixes are bound across proposed, authorized, executed, and observed
> forms until a checked completion witness advances the task.

它依赖四个同时成立的事实：

1. policy-facing prompt 与 trusted mission authority 分离；
2. contract 跨多个 VLA chunks 持续存在；
3. proposal、final authorized command、dispatch/receipt 和 effect 使用同一 transaction binding；
4. `pending` 不得升级为 completion。

这是组合型 novelty，不能只靠架构图成立。论文必须证明：

- Intent-only 和 Execution-only 各自抓到对方抓不到的失败；
- Dual 的收益不是单层或普通 filter 已经覆盖；
- Dual 保留预注册的 clean retention、phase completion 和 availability；
- 更复杂的 plumbing 不是结果的真正来源。

若这些条件不成立，应收缩 claim，而不是增加 stage。

## 5. 方法图中不出现什么

主图不展示：

- 六阶段 wire replay；
- certificate/rebind/lease class hierarchy；
- digest、signature、cache、provenance 字段；
- AEGIS QP、geometry producer 或 recovery controller；
- Python/Lean artifact plumbing。

这些内容只在实现或 TCB 图中出现。方法图最多包含 mission root、contract monitor、prefix authorization、
dispatch boundary 和 effect update。

## 6. Lean 的论文角色

Lean 用于：

- 定义两个核心不变量和最小 state transition；
- 验证 contract/checker 的离散 obligation；
- 建立实际 fast checker 与形式 spec 的 refinement/equivalence；
- 在 shadow/offline 路径 replay artifacts。

Lean 不用于声称 raw vision、continuous dynamics、sensor/actuator truth 或 complete robot safety 已被证明。
若 runtime authority 是 Python，必须写成 Lean specification + Python runtime；只有实际接通并有
equivalence evidence 的路径才写 Lean-backed checker。

## 7. 实验叙事

### 阶段 A：fixed-trace/shadow

四个 arm 面对完全相同的 proposal、state 和 trace，报告：

- Intent-only / Execution-only unique catch；
- Dual 是否严格增加覆盖；
- nominal allow、unknown、block 和 parity；
- checker 与 proof/replay latency。

### 阶段 B：clean closed loop

先冻结并检查：safe-success retention、phase completion、deadlock、blocked time、evidence coverage 和
verifier tax。clean gate 不通过，不进入 attack-defense main。

### 阶段 C：qualified attack

只使用已经在 unguarded VLA-only 上通过独立 clean-safe→attacked-unsafe gate 的发布 workload。比较
VLA-only、两个单层和 Dual，不用 task failure 或 defense 自报 verdict 代替物理/约束 harm。

### 阶段 D：optional intervention

最后单独加入 AEGIS/CBF、brake、replan 或 recovery，回答 physical safety/utility 问题。它们不与核心
integrity contribution 混成一个不可消融的 Full CTDA arm。

## 8. Claim boundary

当前不声称：

- 首次使用 formal contract、pre-execution gate、temporal monitor、Lean 或 runtime fallback；
- 已证明双层方法优于单层或外部 baseline；
- 已建立发布攻击下的 defense efficacy；
- cryptographic authentication、malicious-host resistance 或 verified recovery；
- pixel grounding、continuous dynamics、hardware actuation 或 real-time control 被 Lean 证明。

当前 v1 负结果必须进入正文：在 evaluated slice/seed 上 VLA-only 8/12，而 Full CTDA 0/12。它是促使
方法收缩和 clean-first gate 的主要证据，不能只放 appendix。

## 9. 推荐叙事顺序

```text
two integrity failures
  -> why semantic-only and execution-only are insufficient
  -> two invariants
  -> three protocol transitions
  -> TCB and assumption boundary
  -> four-arm causal ablation
  -> clean utility gate
  -> independently qualified attacks
  -> optional physical intervention
```
