# 相关工作与定位

## 1. Action-only / Action-chunk VLA 是默认对象，不是 blocker

[OpenVLA](https://arxiv.org/abs/2406.09246) 用语言模型预测 tokenized actions，并解码为可直接执行的连续
动作；[Diffusion Policy](https://arxiv.org/abs/2303.04137) 直接生成动作序列并以 receding-horizon
方式执行。这类接口并不承诺可观察的离散高层计划，因此安全层若依赖模型自报 plan，会排除大量实际 VLA。

[π0.5](https://arxiv.org/abs/2504.16054) 的论文系统支持 high-level semantic prediction 和 action
chunks，但某个部署 checkpoint 是否公开该语义输出是接口事实，不能从论文能力推断。本项目因此把数值
ActionBlock 作为最小共同接口，不要求 high-level plan。

与 [RT-H](https://arxiv.org/abs/2403.01823) 的关系也需要说清：RT-H 显式预测 language motion，再
条件化生成动作。这说明显式中间语义可以带来结构和干预接口，但它是 policy architecture 的选择，不是
验证 ActionBlock 的必要条件。未来可以把原生 language motion 作为额外 cross-check；当前主 claim
不依赖它。

## 2. 从 ActionBlock 预测后果

L1 最接近 action-conditioned prediction / model-based control，而不是 chain-of-thought faithfulness。

- [Unsupervised Learning for Physical Interaction through Video Prediction](https://arxiv.org/abs/1605.07157)
  学习 action-conditioned video prediction，明确把不同未来动作对应的视觉后果作为学习对象；
- [Deep Visual Foresight for Planning Robot Motion](https://research.google/pubs/deep-visual-foresight-for-planning-robot-motion/)
  将 action-conditioned prediction 与 MPC 结合，在真实机器人上选择动作；
- [VLMPC](https://www.roboticsproceedings.org/rss20/p106.pdf) 对候选动作序列预测未来帧，再以视觉/
  语义成本评估；
- [How safe am I given what I see?](https://proceedings.mlr.press/v242/mao24c.html) 研究图像控制系统的
  calibrated safety-chance prediction。

这些工作支持 `Assess(O, A) -> predicted outcome/risk` 的技术可行性，但并不会自动给出本项目所需的
trusted-intent binding、attack-specific false-allow gate 或 execution receipt chain。ProofAlign 的
L1 贡献点应表述为：把冻结 outcome predictor 的有限语义输出绑定到可信任务 artifact 和具体
ActionBlock，并把 uncertainty/coverage 作为 confirmatory gate。

## 3. Shielding、safety filters 与 runtime assurance

已有工作常在状态-动作层判断或修正不安全动作：

- [A Learnable Safety Measure](https://proceedings.mlr.press/v100/heim20a.html) 学习 state-action
  safety measure；
- [Realizable Continuous-Space Shields](https://proceedings.mlr.press/v283/kim25c.html) 在连续状态/
  动作空间验证并最小修改 agent action；
- [Adaptive Shielding with HJ Reachability](https://proceedings.mlr.press/v283/lu25a.html) 将模型
  mismatch 纳入保守 shielding；
- [Measurement-Robust Control Barrier Functions](https://proceedings.mlr.press/v155/dean21a.html)
  显式处理 learned perception 的测量不确定性。

ProofAlign 不声称发明 action filter。区别是研究目标和证据链：

1. 原始 instruction/observation attack 使 VLA 输出可能偏离**可信任务意图**，不仅是违反几何安全集；
2. L1 评估 concrete block 的 task semantics 与 violation risk；
3. L2 将 intervention 后的 exact command、receipt、effects 和 phase transition 绑定；
4. 四臂实验分离 L1、L2 及组合贡献。

若 shield 修改了 ActionBlock，修改后的 block 必须重新 assessment 并生成新 execution contract；旧
digest/witness 不可沿用。

## 4. 运行时失败预测与校准

runtime failure prediction、OOD detection 和 conformal risk control 与 L1 assessor qualification
高度相关。它们提供 risk-coverage、abstention 和 calibrated threshold 的工具，但通常预测的是通用
failure 或 distribution shift。本文需额外验证：

- assessor 不读取攻击后的 authoritative field；
- trusted target/part/region 与 predicted effects 的兼容性；
- attacked blocks 上的 false-allow，而不只 clean accuracy；
- unknown/deadlock 与 utility 的代价。

因此“加一个 classifier”不足以构成方法；其冻结数据边界、阈值和 false-allow confidence bound 是
主要实验对象。

## 5. 形式化方法、proof-carrying control 与 Lean

形式化规划、runtime verification、temporal logic shields 和 proof-carrying plans 证明的是给定模型/
规范中的离散或连续性质。ProofAlign 吸收它们的 transaction discipline，但缩小 claim：

- Lean 不解析自然语言 intent；
- Lean 不验证 learned world model 的真实性；
- Lean 验证 ActionBlock、authorization、final command、receipt、effect evidence 与 phase update 的
  有限绑定语义；
- 物理安全仍受 observer completeness、model mismatch 和 sensor trust 限制。

这避免把“proof checker 接受一个结构”误写为“机器人在现实中安全”。

## 6. 最窄新颖性声明

当前可辩护的新颖性不是“VLA 首次有计划”或“首次 action shielding”，而是：

> 在不要求 VLA 暴露高层规划的条件下，针对 instruction/observation attack，将可信任务意图到具体
> ActionBlock 的 calibrated consequence alignment，与 ActionBlock 到 observed execution/effects 的
> Lean-specified transaction integrity 组合，并在 byte-identical shared runner 上用四臂设计识别两层
> 的独立和联合贡献。

只有当 assessor qualification、fixed-trace identity、M2 denominator gate 和 closed-loop 四臂结果都
完成后，才能把这句话提升为经验性有效性 claim。
