# 论文故事：双层 VLA 执行完整性

更新日期：2026-07-20

## 一句话定位

> ProofAlign defends VLA execution against two attack-induced shifts: an
> intent-to-plan shift, where the model plans an action inconsistent with the
> trusted task intent, and a plan-to-execution shift, where the applied or
> observed action diverges from the accepted plan.

中文：ProofAlign 只解决两层对齐——可信任务意图与 VLA 规划动作的对齐，以及已接受规划动作与实际
执行/观测动作的对齐。

## 1. 问题

高 task success 不等于按原始授权安全执行。VLA 可能：

- 因 attacked/replanned prompt 执行未授权对象、部件或子目标；
- 局部动作看似安全，却在多个 action chunks 中累积成超时、错误顺序或 constraint violation；
- proposal 合法，但实际 dispatch、receipt 或 observed effect 已偏离；
- 把 `safe_pending`、旧 trace 或 policy 自报 completion 当成任务完成。

现有单一 collision checker 无法识别任务授权漂移；单一 semantic gate 又无法保证合同被实际
实现。因此需要两个不可互相推出的关系。

## 2. 两层方法

### Layer 1: Intent–Plan Alignment

从 frozen benchmark task 得到 trusted intent/phase/residual obligations；把 VLA raw action proposal 视为
planned action，通过 mission-rooted contract 与 independent proposal binder 判断它是否仍实现该意图。
policy-facing prompt、RGB 和 symbolic metadata 都是不可信输入，攻击后的自洽计划不能改写任务根。

### Layer 2: Plan–Execution Alignment

第一层接受的 exact planned prefix 被短时、单次授权；dispatch、actuator-applied command、receipt 与
observed effect 必须继续绑定该 exact plan。任何 substitution、stale/replay、未授权 filter rewrite、执行
偏差或伪 completion 都由这一层拒绝；persistent monitor 跨 policy calls 累积未完成义务。

两个核心不变量：

- no dispatch without dual authorization；
- no phase advance without checked completion。

## 3. 论文只保留三个贡献

1. **问题与安全属性**：把攻击下 VLA 安全执行拆成 intent–plan alignment 和 plan–execution
   alignment，并说明两种 shift 的 failure surface 互补。
2. **方法与形式化协议**：提出 mission-rooted persistent dual monitor，给出 typed staged
   judgments、fresh transaction 和 cumulative completion semantics；Lean 只证明离散协议中
   真正接通的部分。
3. **攻击无关的配对评测**：在不针对攻击调参的条件下，比较 VLA、collision checker、单层和
   dual monitor，在 clean、published instruction attack 和 published camera attack 上报告安全
   收益、false block 和 verifier tax。

攻击复现不是方法贡献。攻击只负责产生独立、版本化、可配对的 workload。

signature、source hash、provenance audit 和 AEGIS CBF 也不是方法贡献。它们只保证实验中参与比较的
intent/plan/execution 对象没有被测试脚手架混淆，或提供一个可选低层 intervention baseline。

## 4. 关键差异

不能把“用了 Lean”“执行前 gate”“执行后 monitor”“formal contract”单独写成 novelty。候选
增量是：

- trusted mission 与 policy-facing prompt 分离；
- contract 跨 action chunks 持久存在；
- raw proposal、dispatch、receipt 和 cumulative trace 的完整绑定；
- pending 不能升级成 completion；
- 两层分别捕获独有失败，同时 dual 保留可接受 clean utility。

## 5. 实验叙事

实验按两阶段展开：

1. **fixed-trace shadow protocol**：所有方法面对同一 proposal/trace artifact，测 unique catch、
   false block、Python/Lean parity 和 latency。
2. **paired closed-loop protocol**：相同 task/init/policy seed/horizon 下运行 clean、attacked 和
   attacked+defended，测 safe success、success-but-unsafe、intervention lead time 和 deadlock。

主表只有五个方法与三个 workload。详细协议见 [`experiments.md`](../experiments.md)。

## 6. Claim boundary

当前论文不声称：

- cryptographic authentication 或 malicious-host resistance；
- general verified BDDL/NL compilation；
- pixel grounding、continuous dynamics 或 hardware actuation 被 Lean 证明；
- zero-hold 是 verified recovery；
- camera attack 下使用同一被攻击 observer 仍有确定性保证；
- 现有结果已经证明 CTDA 优于 baseline。

若 online 路径仍是 `ctda-python-reference`，论文必须写成 Lean specification + Python reference
runtime；只有真实接通的 stage 才能写 Lean-kernel-checked online judgment。

## 7. 推荐叙事顺序

```text
two integrity failures
  -> why semantic-only and physical-only are insufficient
  -> Layer 1: trusted intent vs planned action
  -> Layer 2: accepted plan vs applied/observed action
  -> contracts/binders/receipts as implementation machinery
  -> two protocol invariants and TCB
  -> published attack workloads
  -> paired utility/safety/overhead evaluation
```
