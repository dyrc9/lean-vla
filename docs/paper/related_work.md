# 相关工作与定位

## 1. 组织原则：两层对齐对应两组不同文献

ProofAlign 的顶层问题不是“如何让 VLA 产生一个 semantic plan”，而是两个连续但不可互相替代的断点：

```text
trusted intent -> concrete ActionBlock                    [L1]
authorized ActionBlock -> dispatch / observed effects    [L2]
```

`SemanticSubtask Z_t` 是当前实现 L1 的结构化中间层。相关工作因此应按以下逻辑比较：

1. VLA 攻击与安全 benchmark 说明为什么需要研究可信 intent 和实际轨迹之间的偏离；
2. action-only VLA 与 language/action hierarchy 说明 L1 可以如何获得结构，但不自动提供可信性；
3. action-conditioned prediction、failure monitoring 和 shielding 说明如何评估或修改动作，但不自动提供
   trusted-intent binding；
4. runtime verification 和 formal methods 说明如何约束执行事务，但不自动证明 learned semantics 或
   物理世界。

论文的新颖性只能来自这些边界的组合和证据设计，不能来自把其中任一已有组件改名。

## 2. VLA 攻击与安全 benchmark：给出问题，不给出完整防御链

[SABER](https://arxiv.org/abs/2603.24935) 研究黑盒 instruction perturbation，并以 task failure、动作长度
和 constraint violation 等行为后果评估攻击；它直接支持本项目“攻击是否改变实际执行，而不是模型是否
承认恶意计划”的问题设定。[FreezeVLA](https://arxiv.org/abs/2509.19870) 则说明视觉输入可以诱发
action-freezing，进一步表明攻击面不只在文本通道。

[LIBERO-Safety](https://arxiv.org/abs/2606.23686) 同时研究物理与语义安全，并报告语义错位和轨迹合成之间
的 tension；[SafeVLA-Bench](https://arxiv.org/abs/2606.00773) 用 task-aware temporal specifications
区分成功与 unsafe success；[ForesightSafety-VLA](https://arxiv.org/abs/2606.27079) 将 instruction、
perception 和 physical-interaction 风险拆开诊断。这些 benchmark 共同说明：

- task success 不能替代过程安全；
- cost/collision 不能吞掉 contact、错误目标或 deadlock；
- language、vision 和 scene variation 应分别报告。

它们主要提供 attack/evaluation surface。ProofAlign 的不同目标是在线或 no-dispatch runtime integrity：
在 trusted intent 保持不变时，对一个 exact ActionBlock 做预执行语义授权，并把授权对象继续绑定到
dispatch receipt 和 effects。已有 benchmark outcome 可以作为 endpoint，但不能自动充当 L1 assessment
或 L2 transaction witness。

## 3. Action-only VLA 与显式层级：结构来源不等于可信来源

[OpenVLA](https://arxiv.org/abs/2406.09246) 预测 tokenized actions 并解码为可执行连续动作；
[Diffusion Policy](https://arxiv.org/abs/2303.04137) 直接生成动作序列并以 receding-horizon 方式执行。
这类接口不承诺暴露离散高层计划，所以依赖模型自报 plan 的 verifier 不是通用方案。ProofAlign 把数值
ActionBlock 作为最低共同接口，保留对 action-only checkpoint 的适用性。

[π0.5](https://arxiv.org/abs/2504.16054) 的论文系统使用 high-level semantic prediction、object
detection 和 low-level action 等混合训练信号；[RT-H](https://arxiv.org/abs/2403.01823) 显式预测
language motion，再条件化动作。这两项工作说明 semantic/action hierarchy 可以改善策略结构和干预
接口。

ProofAlign 与它们的关系需要严格区分：

- π0.5/RT-H 的 semantic output 属于 policy architecture；ProofAlign 的 `Z_t` 属于攻击面之外的
  consumer-side trusted boundary；
- 原生 semantic head 若可用，可以成为额外 proposal/cross-check，但不能仅因来自 policy 就自动可信；
- 当前公开 `pi05_libero` 路径只返回数值动作，不能从论文能力推断本地 checkpoint 暴露 semantic API；
- 当前 `Z_t` 在动作生成前作为显式输入并绑定 ActionBlock，但 action-conditioning 强度仍是经验问题，
  不能由“prompt 被传入”推出“动作被可靠控制”。

因此本文不主张首次提出 language hierarchy。它使用有限 task graph 和 zero-training selector，把层级
转换成一个可审计的 L1 分解：

```text
TaskSubtask(T, O_t^T, Z_t)
SubtaskAction(Z_t, O_t^T, A_t)
```

## 4. Action-conditioned prediction：支持 local checker，但不完成 L1

L1 的 `SubtaskAction` 部分与 action-conditioned prediction、model-based control 和 calibrated risk
prediction 相邻：

- [Unsupervised Learning for Physical Interaction through Video Prediction](https://arxiv.org/abs/1605.07157)
  学习不同动作条件下的视觉未来；
- [Deep Visual Foresight for Planning Robot Motion](https://research.google/pubs/deep-visual-foresight-for-planning-robot-motion/)
  将 action-conditioned prediction 与 MPC 结合；
- [VLMPC](https://www.roboticsproceedings.org/rss20/p106.pdf) 为候选动作预测未来帧并按视觉/语义成本选择；
- [How safe am I given what I see?](https://proceedings.mlr.press/v242/mao24c.html) 研究图像控制系统的
  calibrated safety-chance prediction；
- [Model-Based Runtime Monitoring with Interactive Imitation Learning](https://arxiv.org/abs/2310.17552)
  结合未来预测、OOD 与 failure detection 做运行时监测。

这些工作支持 `Assess(O, A) -> predicted outcome/risk` 的技术可行性，但没有自动解决四个 ProofAlign
特有条件：

1. authoritative task/target 来自 trusted `T/O_t^T`，而非 attacked policy view；
2. `Z_t` 必须属于当前合法 frontier，且在动作生成前冻结；
3. attacked blocks 上报告 false-allow confidence bound，而不只 clean accuracy；
4. assessment 必须绑定 exact executable prefix，并在任何 projection 后重新生成。

因此 learned outcome predictor 是可选增强，不是第一版方法的必要前提。首版优先使用 task predicates、
解析运动学/几何 checker 和保守 abstention；无论采用哪种 assessor，都必须单独资格化。

## 5. Shielding、safety filters 与 runtime assurance：解决约束，不自动解决意图

已有工作常在状态–动作层判断或修正不安全动作：

- [A Learnable Safety Measure](https://proceedings.mlr.press/v100/heim20a.html) 学习 state-action safety
  measure；
- [Realizable Continuous-Space Shields](https://proceedings.mlr.press/v283/kim25c.html) 在连续状态/动作
  空间验证并最小修改 agent action；
- [Adaptive Shielding with HJ Reachability](https://proceedings.mlr.press/v283/lu25a.html) 将模型
  mismatch 纳入保守 shielding；
- [Measurement-Robust Control Barrier Functions](https://proceedings.mlr.press/v155/dean21a.html)
  显式处理 learned perception 的测量不确定性。

ProofAlign 不声称发明 action filter。传统 shield 主要问动作是否留在安全集合内，而 L1 还要问一个
几何上安全的动作是否仍在推进可信任务的正确 object/part/region。L2 则继续检查 shield 或其他
intervention 之后的 exact command 是否真的被 dispatch，并产生了约定效果。

只要 intervention 改变 ActionBlock，原 assessment、contract 和 authorization 就失效；修改后的 block
必须重新检查和授权。这条 transaction discipline 是 ProofAlign 对现有 filter 的组合要求，而不是新的
连续控制理论。

## 6. 运行时失败预测、校准与 abstention：qualification 是方法的一部分

OOD detection、selective prediction、conformal risk control 和 failure forecasting 可为 selector/local
checker 提供 risk-coverage 与 abstention 工具。但一个高拒绝率分类器可能看起来 false-allow 很低，同时
让机器人长期 deadlock。

本文因此必须同时报告：

- selector legal-frontier accuracy、stage stability、margin 和 OOD abstention；
- local-checker attacked false allow、clean false reject 和 coverage；
- suite/task/object/attack-family worst group；
- p50/p95/p99 latency 和资源；
- unknown、replan、deadlock、time-to-completion 与 task utility。

所以“加一个 classifier”不是完整贡献。可信输入边界、冻结阈值、support definition、false-allow
confidence bound 和 abstention 代价共同构成 L1 evidence。

## 7. Formal methods 与 proof-carrying control：L2 证明的是事务，不是世界

形式化规划、runtime verification、temporal-logic shields 和 proof-carrying control 在给定模型与规范中
证明离散或连续性质。ProofAlign 借用其 fail-closed 和 binding discipline，但刻意缩小 Lean claim：

- Lean 不解析自然语言 intent，也不选择 `Z_t`；
- Lean 不验证 selector、assessor、perception 或 observer 的现实正确性；
- Lean 检查 ActionBlock、assessment、execution contract、authorization、exact command、receipt、
  effect evidence 和 phase update 的有限关系；
- Python serializer/runtime 到 Lean model 的对应仍需要独立 equivalence/refinement evidence；
- 物理安全仍受 sensor trust、observer completeness、model mismatch 和 TCB 假设限制。

因此正确表述是 “Lean-specified/Lean-checked execution transaction semantics”，不是 “formally proven
robot safety”。

## 8. 横向比较

| Work family | Intent→Action semantics | Trusted dual view | Action modification | Receipt/effect binding | Formal transaction |
|---|---:|---:|---:|---:|---:|
| VLA hierarchy / RT-H / π0.5 | policy-internal | no | policy-dependent | no | no |
| Action-conditioned predictor | predicted consequence | not inherent | candidate selection | no | no |
| Shield / CBF / runtime assurance | safety-set compatibility | not inherent | yes | usually no | sometimes model-level |
| VLA safety benchmark | post-hoc endpoint | evaluation-dependent | no | post-hoc trace | sometimes temporal specs |
| ProofAlign L1 | trusted task/subtask/action relation | required | select/reject/project+recheck | feeds L2 | statistical/system claim |
| ProofAlign L2 | no new semantic truth | inherits bindings | exact reauthorization | required | finite Lean semantics |

这张表的目的不是声称所有先前工作都缺少某项能力，而是说明本文 estimand：L1 和 L2 必须在同一
ActionBlock identity chain 上组合，并由四臂实验分别估计。

## 9. 最窄新颖性声明

当前可辩护的顶层新颖性仍然是双层对齐：

> 在不要求 VLA 暴露高层规划的条件下，针对 instruction/observation attack，将可信任务意图到具体
> ActionBlock 的可资格化语义对齐，与 ActionBlock 到 observed execution/effects 的 Lean-specified
> transaction integrity 分离并组合；当前 L1 用可信有限 `SemanticSubtask` 将完整意图对齐分解为
> task–subtask 和 subtask–action 两个可审计关系，并在共享 candidate/trace 的四臂设计中识别两层的独立
> 和联合贡献。

只有当 selector/local-checker qualification、runtime identity、M2 denominator gate 和 closed-loop
四臂结果完成后，才能把这句话从方法贡献提升为经验性有效性 claim。若这些 gate 未通过，论文仍只能报告
组件语义、探索性攻击/Execution-only 信号和明确失败边界。
