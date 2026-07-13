# 论文故事：双层 VLA 执行完整性

更新日期：2026-07-10

## 一句话定位

> ProofAlign preserves a trusted frozen mission across untrusted VLA prompts and
> carries its obligations across raw action prefixes: no command is dispatched
> without mission refinement and fresh prefix conformance, and no task phase
> advances without checked cumulative completion.

中文：ProofAlign 把安全关键 VLA 执行定义为两个同时必要的完整性问题——合同必须忠实于
trusted, locally frozen mission；实际 raw prefix 和累计 trace 必须持续实现该合同。

## 1. 问题

高 task success 不等于按原始授权安全执行。VLA 可能：

- 因 attacked/replanned prompt 执行未授权对象、部件或子目标；
- 局部动作看似安全，却在多个 action chunks 中累积成超时、错误顺序或 constraint violation；
- proposal 合法，但实际 dispatch、receipt 或 observed effect 已偏离；
- 把 `safe_pending`、旧 trace 或 policy 自报 completion 当成任务完成。

现有单一 collision checker 无法识别任务授权漂移；单一 semantic gate 又无法保证合同被实际
实现。因此需要两个不可互相推出的关系。

## 2. 两层方法

### Layer 1: Mission refinement

合同只能来自 frozen benchmark mission、active phase 和 residual obligations。policy-facing
prompt 与 policy symbolic metadata 都是不可信输入，不能改写任务根。

### Layer 2: Proposal/effect trace conformance

raw proposal 通过独立 binder 绑定 active contract；每次只授权 fresh bounded prefix；dispatch
之后的 receipt 和 observed trace 继续绑定同一 transaction；persistent monitor 跨 policy calls
累积时序义务。

两个核心不变量：

- no dispatch without dual authorization；
- no phase advance without checked completion。

## 3. 论文只保留三个贡献

1. **问题与安全属性**：把 VLA 安全执行拆成 mission authorization integrity 和 execution
   realization integrity，并说明两者的 failure surface 互补。
2. **方法与形式化协议**：提出 mission-rooted persistent dual monitor，给出 typed staged
   judgments、fresh transaction 和 cumulative completion semantics；Lean 只证明离散协议中
   真正接通的部分。
3. **攻击无关的配对评测**：在不针对攻击调参的条件下，比较 VLA、collision checker、单层和
   dual monitor，在 clean、published instruction attack 和 published camera attack 上报告安全
   收益、false block 和 verifier tax。

攻击复现不是方法贡献。攻击只负责产生独立、版本化、可配对的 workload。

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

主表只有五个方法与三个 workload。详细协议见 [`experiments.md`](experiments.md)。

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
  -> trusted frozen mission
  -> persistent mission-rooted contract
  -> independent raw-prefix binding
  -> cumulative completion monitor
  -> two protocol invariants and TCB
  -> published attack workloads
  -> paired utility/safety/overhead evaluation
```
