# Related Work：VLA 任务授权与执行完整性

更新日期：2026-07-23

> 本文用于研究定位、baseline 选择和 novelty 审计，不是运行状态或执行授权来源。方法定义以
> [`method.md`](../method.md) 为准；当前执行优先级是 resource-isolated Execution-only
> action-envelope successor，其余实验暂停。

## 0. 定位结论

ProofAlign 不以以下任何单点为新意：

- 首次给机器人任务建立 formal contract；
- 首次在执行前设置 semantic/safety gate；
- 首次使用 temporal/runtime monitor；
- 首次验证 planner 或让 plan 携带 proof；
- 首次使用 runtime assurance、CBF、brake 或 fallback；
- 首次检查 mission、data、command 或 trajectory integrity；
- 首次用 Lean 检查机器人控制协议。

这些方向都有直接先例。ProofAlign 只保留一个更窄、需要实验证明的候选空隙：

```text
trusted mission authority
  -> persistent task contract
  -> dynamically generated VLA proposal
  -> exact final-command authorization
  -> applied command / receipt / observed effect
  -> checked completion
```

也就是把两个已有但通常分开的完整性关系连接起来：

1. **Intent–Plan Integrity**：accepted plan 必须继续由独立 trusted mission 授权；
2. **Plan–Execution Integrity**：executed/observed prefix 必须继续绑定 accepted exact plan。

这是组合型候选贡献，不是“组件更多”的贡献。若单层方法已经覆盖相同 failure surface，或 Dual 没有
unique catch / clean utility，novelty 就不成立。

## 1. VLA 安全、benchmark 与攻击

VLA safety benchmark 和攻击工作已经表明，task success 不能代替安全或授权正确性：模型可以完成任务
却发生碰撞、危险 affordance、约束违反、action inflation，或在 attacked instruction/observation 下执行
错误目标。

本项目当前使用的发布 workload 入口是：

- [SABER](https://github.com/wuxiyang1996/SABER)：instruction-channel attack，提供 π0.5/OpenPI、
  LIBERO、released attacker 和 record/replay 路径；
- [Phantom Menace](https://github.com/ZJUshine/Phantom-Menace)：camera/microphone sensor transforms；
- [EDPA](https://github.com/trustmlyoungscientist/EDPA_attack_defense)：adversarial patch 与 VLA attack/
  defense 路径；
- [VLSA/AEGIS 与 SafeLIBERO](https://arxiv.org/abs/2512.11891)：提供物理 safety benchmark 和
  plug-and-play constraint layer。

这些工作提供 threat workload 或 safety scenario，不自动证明 ProofAlign 有效。攻击必须先在 unguarded
VLA-only 上形成独立、held-out、clean-safe→attacked-unsafe 的 terminal evidence；attack metadata、task
failure 或 defense checker verdict 不能代替 harm oracle。

## 2. 直接 VLA failure detection 与 defense

[SAFE](https://github.com/vla-safe/SAFE)从 VLA 内部 feature 学习 failure score，并使用 calibrated/
conformal threshold；[FIPER](https://github.com/learnsyslab/fiper)使用 observation representation 与
action-chunk uncertainty/entropy 进行 generative-policy failure prediction。它们是重要的 direct VLA
baseline，但其典型输出是 alarm 或 risk score：

- alarm 不等于任务授权；
- OOD/uncertainty 不一定识别“高置信但做错对象”的动作；
- detector 若触发 stop/replan，其闭环效果依赖独立 intervention policy。

因此 SAFE/FIPER 与 ProofAlign 公平比较时应先报告 detector metrics；若转成 closed-loop arm，必须共享
同一 stop/replan/recovery policy，避免把 fallback 差异误算成 detector 或 integrity 方法收益。

[RoboGuard](https://arxiv.org/abs/2503.07885)使用 trusted rule grounding、semantic graph、temporal
specification 与 control synthesis 来修正不安全计划，是 Intent–Plan 层最强的近邻之一。它已经否定了
“trusted semantic rules + temporal plan guard”本身是 ProofAlign novelty。ProofAlign 只能进一步检验：
在连续 VLA raw chunks 下，独立 mission authority 是否能持续绑定 exact command、receipt 和 effect。

## 3. Semantic gate、task safety contract 与 temporal monitor

[SafeGate / Task Safety Contracts](https://arxiv.org/abs/2604.05427)把 pre-execution safety gate、
invariants、guards、abort conditions、solver checks 和 continuous monitoring组合到 LLM-controlled robot
systems 中。它与 ProofAlign 的 mission contract、pre-dispatch gate 和 runtime monitoring 高度重叠。

[Code-as-Monitor](https://arxiv.org/abs/2412.04455)把视觉语言模型生成的程序作为时空约束 monitor，进行
reactive/proactive failure detection；[SafeManip](https://arxiv.org/abs/2605.12386)用 LTLf finite-trace
properties 和 symbolic traces 评估 robotic manipulation/VLA 的 temporal safety。这些工作说明：

- execution/completion temporal monitoring 不是新意；
- 把自然语言约束编译成 monitor 不是新意；
- finite-trace、LTL/LTLf、abort condition 或 completion check 不能单独列贡献。

ProofAlign 相对这一组只能保留更窄的区别：

1. policy-facing prompt 与 mission authority 显式分离；
2. contract 跨多个 policy calls/action chunks 持续存在；
3. monitor 不能自己成为任务信任根；
4. `pending`、局部安全和 policy 自报 success 不能推进 phase；
5. observed effect 必须绑定此前获授权的 exact final command。

SafeGate/RoboGuard 应视为 Intent–Plan 与 shared monitor substrate 的强 baseline，而不是 strawman。

## 4. Proof-carrying planning 与形式化 plan verification

[Proof-Carrying Plans](https://arxiv.org/abs/2008.04165)使用 resource logic、pre/post conditions 和 Agda
formalization，使 AI planner 产生的计划可以被独立检查。这说明“plan 携带 machine-checkable proof”已有
明确先例。

ProofAlign 的候选差异不是换用 Lean，而是验证对象不同：

| Proof-carrying planning | ProofAlign 候选对象 |
|---|---|
| 离散、相对完整的 plan | 闭环、动态产生的短 action prefix |
| planner state/pre/post proof | mission authorization + fresh state + monitor history |
| 计划正确性 | proposal、final command、receipt、effect 的持续绑定 |
| plan completion | partial/pending 与 checked completion 的区分 |

即便如此，只有 core theorem 真正连接实际 runtime checker/wire 时，才能写 proof-backed runtime。把 Python
计算出的 verdict 放进 `by decide`、或只证明 normalized payload parity，不能扩大成 raw continuous
execution 已被证明。

## 5. Runtime assurance、continuous safety filter 与 recovery

[SOTER](https://arxiv.org/abs/1808.07921)把 uncertified advanced controller、certified safe controller 和
safety specification 组合成 runtime-assurance modules，并处理监督切换。Simplex/RTA、ModelPlex、
VeriPhy、CBF、predictive safety filtering 和 reachability 进一步覆盖 safe set、dynamics、switching、
fallback 与 recoverability。

[VLSA/AEGIS](https://arxiv.org/abs/2512.11891)为 VLA 增加 plug-and-play CBF constraint layer；
[PACS](https://arxiv.org/abs/2511.06385)利用 action chunk/path 的一致性进行 braking 和 safety filtering，
直接触及 chunk-level physical safety 与 utility preservation。

这些工作对 ProofAlign 有三个约束：

1. Boolean tube、zero-hold 或简单 hard block 不能声称优于成熟 RTA/filter；
2. CBF、projection、brake、replan 和 recovery 应是可替换 intervention，不是第三个 integrity layer；
3. filter 后的 adjusted command 必须重新接受任务授权与 execution binding，但 filter witness 本身不能证明
   mission authorization。

局部物理安全和任务授权是正交关系：一个 command 可以满足 barrier condition，却移动错误对象；也可以
语义正确，却因 dynamics/obstacle constraint 不可执行。因此物理 filter 是强 baseline/consumer，而不是
ProofAlign 核心的替代或天然组成部分。

## 6. Mission、data 与 trajectory execution integrity

安全领域已有与 ProofAlign 第二层非常接近的工作：

- [ARI, USENIX Security 2023](https://www.usenix.org/conference/usenixsecurity23/presentation/wang-jinwen)
  定义 Real-time Mission Execution Integrity，关注自主 CPS mission 是否被正确、及时执行及其
  attestation；
- [DIAT, NDSS 2019](https://www.ndss-symposium.org/ndss-paper/diat-data-integrity-attestation-for-resilient-collaboration-of-autonomous-systems/)
  关注自主系统协作中的数据生成、处理和传输完整性；
- [TAT, USENIX Security 2026](https://www.usenix.org/conference/usenixsecurity26/presentation/yao-chengtao)
  定义 robotic-arm trajectory integrity，并用 motion events 与 joint measurements检查真实运动是否符合
  intended path。

因此 proposal→authorization→execution→observation binding 也不能笼统声称为首次。更窄的候选差异是：
VLA 的 plan 不是事先固定程序或轨迹，而是受不可信语言/视觉驱动、在闭环中不断产生；ProofAlign 试图让
独立任务语义持续约束这些动态 prefixes。

如果 threat model 包含恶意 host、IPC、observer 或 actuator，仅有普通 hash、`authenticated=true` 或
软件内 receipt 不足以建立 security claim；需要签名/密钥、隔离 reference monitor、可信 counter、
sensor/actuator attestation 和清晰的 remote verifier。当前 prototype 明确信任 host-side monitor 与
simulator adapter，所以不能借用 ARI/TAT 的安全结论。

## 7. Evidence 类型不能混用

相关工作比较要求区分：

| Evidence | 能证明什么 | 不能证明什么 |
|---|---|---|
| binding metadata | id/version/digest/timestamp 对象一致性 | producer 诚实、物理量真实 |
| trusted attestation | 在声明密钥/隔离假设下的 producer 身份与软件状态 | 感知模型正确、世界状态真实 |
| consumer-checkable witness | 独立复核 proof/barrier/tube/trace proposition | 超出模型/abstraction 的物理结论 |
| observed outcome | 指定 episode 的 task/safety 结果 | protocol theorem、总体分布保证 |

当前更准确的名称是 mission-rooted evidence-carrying runtime，而不是无条件 proof-carrying physical
execution。

## 8. 最接近工作的差异矩阵

| 方向 | 已有能力 | ProofAlign 不能声称 | 仍需证明的可能增量 |
|---|---|---|---|
| SafeGate | pre-execution gate、task contract、runtime monitor | formal contract/gate 是首次 | attacked prompt 与独立 mission authority 分离后的持续 prefix binding |
| RoboGuard | trusted semantic rules、temporal plan synthesis | trusted plan guard 是首次 | 连续 raw chunk、exact final command、receipt/effect 接口 |
| Code-as-Monitor / SafeManip | spatio-temporal/LTLf monitoring、completion/failure properties | temporal monitor 是首次 | monitor state 与 prior authorization 的 transaction binding |
| SAFE / FIPER | VLA failure/OOD/uncertainty detection | detector 等于任务授权 | 高置信未授权动作与执行替换的结构化区分 |
| Proof-Carrying Plans | machine-checkable plan pre/post proof | proof-carrying plan 是首次 | 动态 prefix、partial completion 与 physical receipt/effect |
| SOTER / Simplex | controller supervision、switching、safe fallback | runtime assurance/fallback 是首次 | RTA decision 始终受 mission contract 约束 |
| AEGIS / PACS | CBF、path-consistent filtering/braking | chunk filter/physical safety 是首次 | adjusted command 的 post-filter mission reauthorization |
| ARI / DIAT / TAT | mission/data/trajectory integrity attestation | execution/trajectory binding 是首次 | trusted task semantics 到动态 VLA prefix/effect 的连接 |

## 9. Baseline 与消融含义

核心方法必须先做四臂因果消融：

| arm | 回答的问题 |
|---|---|
| VLA-only | 无监控时的 task/safety/cost 基准 |
| Intent-only | semantic authorization 单独抓到什么、误阻断多少 |
| Execution-only | exact binding/receipt/effect monitoring 单独抓到什么、误阻断多少 |
| Dual | 两个关系组合是否产生不可由单层解释的增量 |

外部工作按角色加入，而不是混成一个 Full CTDA：

- SafeGate/RoboGuard：semantic/plan baseline；
- SAFE/FIPER：failure detector baseline；
- AEGIS/PACS-style filter：physical intervention baseline；
- ARI/TAT：security property 与 attestation 设计参照，除非有公平可运行 adapter，否则不做数字对比。

## 10. Novelty falsification tests

候选 novelty 只有在以下测试同时通过时才成立：

1. **Layer necessity**：Intent-only 与 Execution-only 各有预先定义的 unique catch；
2. **Composition gain**：Dual 的覆盖不是任一单层或普通 filter 已经达到；
3. **Clean viability**：Dual 达到预注册 clean retention、phase completion、deadlock 和 availability gate；
4. **End-to-end binding**：proposal、final authorization、dispatch/receipt 和 observed effect 来自同一事务；
5. **Assumption honesty**：形式 theorem、TCB attestation 与 simulator outcome 分开报告；
6. **Attack independence**：defense 不参与 attack tuning，且 workload 先在 VLA-only 上独立 qualification。

任一关键条件失败，都应缩小贡献：

- 无 Layer 1 unique catch：收缩为 execution-integrity monitor；
- 无 Layer 2 unique catch：收缩为 mission/semantic guard；
- clean utility 不合格：收缩为 offline audit/slow interlock；
- attack qualification 为 0：不报告 attack-defense efficacy；
- 依赖 CBF 才有效：把结果写成 integrity + physical filter composition，而不是纯 CTDA 收益。

## 11. 最终 claim 边界

最稳健的候选表述是：

> ProofAlign formulates VLA control as two coupled integrity relations: accepted
> prefixes must remain authorized by a trusted mission, and applied/observed
> prefixes must remain bound to the accepted exact action until checked
> completion.

论文不能把双 checker、Lean、pre-gate、post-monitor、temporal logic、certificate、signature、provenance、
CBF 或 fallback 单独列为 novelty。最终保证必须分开报告：

1. **协议保证**：两个不变量；
2. **离散形式保证**：实际 checker 对 typed proposition 的 soundness/refinement；
3. **条件物理保证**：只在 observer、dynamics、timing、actuation、abstraction 和 fallback assumptions
   成立时讨论安全结果。

三者不能合并成无条件的“robot safety proof”。
