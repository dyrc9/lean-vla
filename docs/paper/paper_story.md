# Paper story

## 1. 中心命题

> ProofAlign 在不要求 VLA 输出高层规划的条件下，将“可信意图到具体 ActionBlock 的对齐”与“获准
> ActionBlock 到实际执行及 observed effects 的对齐”分离，并用四臂 shared runner 估计两层的独立和
> 联合作用。

这句话包含两个必须分开的 claim：

1. **Intent–SemanticSubtask–ActionBlock alignment（L1）**：动作生成前的可信语义锚点与动作生成后的
   局部运动/后果检查；
2. **ActionBlock–Execution alignment（L2）**：授权对象、实际命令、receipt、effects 和 phase update
   属于同一个事务。

L1 的正确性主要是统计与系统 claim；L2 的有限绑定语义可以交给 Lean。二者都不等价于完整物理安全。

论文的中心贡献始终是这两个对齐断点。`SemanticSubtask Z_t` 是当前用来实现和资格化 L1 的结构化机制，
不是第三个顶层对齐层，也不取代原始的 `Intent -> ActionBlock` 研究问题。即使未来把 FSM/PaliGemma
selector 换成其他可信 semantic adapter，双层问题定义和 L2 transaction 仍保持不变。

Lean 是方法的一等组成，而不是事后给 Python checker 加的标签。它把 L2 中容易被自然语言含混处理的
authorization、freshness、exact command、receipt/effect binding 和 phase-gating 写成有限命题，并为
“Execution-enabled arm 能在什么条件下 dispatch/advance”提供 machine-checked theorem。论文应同时展示
Lean 定理、Python 对应证据和明确的 refinement boundary。

## 2. 故事起点：攻击落在动作，不落在“自白”

Instruction/observation attack 的危险不在于 VLA 是否承认一个恶意计划，而在于可信任务 `T` 没有改变时，
policy-facing prompt、observation 或 history 的改变可能使模型输出实际效果偏离 `T` 的数值 action
chunk。多数公开 VLA 部署接口只返回动作，因此：

- 不能把可观察 high-level plan 当作通用前提；
- 不能从 ActionBlock 唯一恢复模型 latent intent；
- 不能让外部模型在动作产生后补一段 explanation，再把它当作 VLA witness。

论文因此从最小共同接口出发：可信任务 artifact、可信/不可信双视图、数值 ActionBlock、consumer
assessment、dispatch receipt 和 observed effects。

## 3. 为什么需要两层，而不是一个 safety filter

只约束动作幅度可以减少部分低层风险，却不能判断一个平滑、合法的动作是不是在拿错物体。只判断动作语义
也不能防止授权后的 command substitution、stale replay、sink-side drift 或效果证据换绑。

因此方法把失败分为两个时间不同、证据不同的问题：

```text
Trusted intent -- semantic authorization --> concrete ActionBlock       [L1]
authorized ActionBlock -- execution transaction --> receipt/effects     [L2]
```

当前 L1 的具体分解是：

```text
Trusted T/O_t^T
    -> legal frontier -> SemanticSubtask Z_t
    -> attacked-view-conditioned ActionBlock candidates
    -> local assessment / select-or-reject
```

第一层回答“准备做的事情是否仍服务于可信任务的当前合法步骤”，第二层回答“获准的事情是否真的这样执行并
产生了约定效果”。两层组合可以互补，也可能因过多 `unknown` 导致 deadlock；这正是四臂实验需要估计的
交互。

## 4. 威胁模型是双视图，不是同视图自洽

Semantic branch 只读取：

- 攻击面之外的 trusted task `T`；
- secure split 之前绑定的 `O_t^T`；
- task graph、历史可信 subtask；
- allowlisted selector checkpoint/config。

Action-policy branch 可以读取被攻击的 `P_t^atk/O_t^atk/H_t^atk`。本方法由此研究：攻击把 ActionBlock
带偏后，独立可信语义锚点和 local checker 能否在执行前发现偏离。

部署路径丢弃 external prompt，并从 trusted `T + Z_t` 固定编译 action prompt。攻击评估可以有意把
external prompt 送入 action-policy branch 来测量 L1 检出能力，但它仍不能进入 selector/checker。

当前覆盖 secure split 后的数字/软件注入，不覆盖同时欺骗 trusted tap 的分叉前物理光学攻击，也不覆盖
task source、selector/checker、observer、receipt store 或 actuator feedback 被攻破。

## 5. L1：先约束合法下一步，再检查局部动作

L1 的顶层目标仍是判断 concrete ActionBlock 是否服务于 trusted intent。为避免要求一个评估器直接恢复
完整 latent intent，当前方法把这条关系分解为两个可绑定、可分别资格化的关系：

```text
TaskSubtask(T, O_t^T, Z_t)
SubtaskAction(Z_t, O_t^T, A_t)
```

`Z_t` 从有限 task graph 的当前合法 frontier 中选择。第一版不训练 π0.5；确定性 FSM/task predicates
控制合法候选，冻结 PaliGemma 分数只作为 proposal/ranking 特征。`Z_t` 在 ActionBlock 生成前成为显式
policy 输入并与返回 block 绑定；当前 pilot 只证明 prompt path 有非零敏感性，尚未证明它提供强或可靠的
action control。

local checker 使用 `Z_t/O_t^T/A_t` 预测有限的 motion、target、part、effect、precondition 和 violation
atoms。未知、OOD、遮挡、低 margin 或不支持的几何关系必须 abstain。语义不匹配只能 reject/resample，
不能靠 numeric projection 改名或修复；投影后的 executable prefix 必须重新检查并重新绑定。

L1 的主要风险不是平均 accuracy，而是：

- selector 把错误但语法合法的 `Z_t` 放进 frontier；
- local checker 在 attacked block 上 false allow；
- clean false reject 或 OOD abstention 过高导致 coverage collapse；
- selector、policy 与 checker 错误共享同一不可信输入。

所以 selector qualification 和 local-checker qualification 必须分开报告。

## 6. L2 与 Lean：把执行当作一次形式化绑定事务

consumer 为 exact ActionBlock 编译 `BlockExecutionContract`，绑定 subtask/prompt、assessment、observation、
state epoch、expected/forbidden effects 和 observation window。authorization 必须新鲜且一次性使用；
Execution-enabled arm 只能 dispatch exact authorized command。receipt 和 evidence 再绑定 authorization、
block、contract、proposal index、observed command 和时间顺序。

观察窗口关闭后，只有 expected effects 已出现、forbidden effects 未出现、observer 未报告 violation，
且 trusted task completion atoms 被观察到时，phase 才能推进。开放窗口是 `pending`，证据不足是
`unknown`，不是 allow。

Lean 检查四臂 truth table、digest/nonce/index 绑定、exact-command dispatch 和 phase-gating 定理。
关键论文定理包括：Dual dispatch 同时要求两层 authorization、Execution-enabled arm dispatch 的 command
必须等于 exact authorized command、Execution-enabled phase advance 蕴含 block-execution alignment，
且任何 phase advance 都要求 trusted contract completion。

它不证明 selector、local checker、perception、observer、simulator 或物理世界正确，也不自动证明
Python runtime 精化了 Lean 模型。这个边界限制 claim 的外延，但不削弱 Lean 对 L2 规范、反例测试和
实现审计的核心作用。

## 7. 论文要回答的经验问题

1. **Attack foundation**：冻结攻击是否稳定地产生相对于 trusted intent 的 ActionBlock/trajectory
   divergence？
2. **Semantic selection**：零训练 selector 在 held-out task/object/stage 上的合法率、稳定性、margin、
   OOD abstention 和 latency 是否达到冻结 gate？
3. **Action conditioning**：固定 observation/noise 时，不同合法或冲突 `Z_t` 是否对 ActionBlock 产生
   可测、阶段合理且不损害 clean utility 的影响？
4. **Local checking**：在 supported attacked blocks 上，local checker 的 false-allow 上界能否达标，
   同时维持 clean retention 和 coverage？
5. **Execution integrity**：L2 能否捕获 substitution、replay、receipt/effect mismatch，并保留 utility？
6. **Composition**：Dual 相对单层是否互补，还是增加 unknown、deadlock 或 time-to-completion？

第 2–4 问共同构成 L1 资格化；不能用初始四帧 top-1、synthetic fixture 或 victim outcome 代替。

## 8. 四臂如何识别两层贡献

统一使用以下论文名称：

| Arm | L1 semantic alignment | L2 execution integrity |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

冻结 runtime/schema 中的 `intent_only`、`intent_action_enabled` 字段仅作为兼容名称，不表示恢复自由文本
plan。

`K=1` primary design 中，四臂共享 byte-identical proposal、assessment 与 execution contract。若将来
启用 `K>1`，四臂必须共享 byte-identical ordered candidate set 和每候选 assessment；VLA-only 使用
预注册 base candidate，L1-enabled arms 才执行冻结 select/reject rule。最终命令差异此时是 treatment
机制的一部分，不能再笼统声称四臂 final ActionBlock byte-identical。

## 9. 可主张的贡献与明确排除项

若全部 gate 完成，论文可以主张：

- action-only VLA 上的双层完整性定义；
- trusted task/observation 到有限 semantic subtask 的 provenance、frontier 与 qualification protocol；
- `Z_t -> ActionBlock` 的 local compatibility、abstention 和 deterministic selection boundary；
- ActionBlock/authorization/receipt/effect/phase 的 Lean-specified transaction semantics，以及
  exact-dispatch/phase-gating 的 machine-checked theorem；
- 共享 candidate/trace 的四臂因果评估协议；
- instruction/observation attack 下的 benchmark evidence。

不主张：

- 首次 high-level planning、language hierarchy、world model、shield 或 action filter；
- 当前公开 π0.5 checkpoint 暴露论文中的原生 semantic head；
- 从动作唯一恢复 latent intent；
- Lean 证明 learned prediction、sensor 或现实物理安全；
- 软件 secure split 等价于硬件级 trusted capture。

## 10. 证据叙事与论文结果顺序

P0b 与 R9 只承担历史动机：

- P0b：96/96 有效、23 个 clean-eligible pair、15 个攻击 transition，但 `23 < 26`，未通过确认性
  denominator gate；
- R9：Execution-only 的强探索信号，但 strict-success recovery 不完整，且 15 个 signal pair 中 11 个
  仍有 residual contact proxy。

当前 semantic pilot 只支持“skill-level 路线值得继续”：motion-level `0/4`、skill-level `4/4`、阶段
切换 `3/5`，且 prompt-conditioned action delta 很小。它不是 selector qualification，更不是防御结果。

新的论文主结果必须按以下顺序产生：

```text
M1 component closure
  -> selector qualification
  -> local-checker qualification
  -> end-to-end no-outcome identity/resource gate
  -> M2 VLA-only attack foundation
  -> fixed-trace four-arm
  -> clean four-arm
  -> attacked four-arm
```

任何阶段都不得用后续 outcome 回调 selector/checker threshold。论文结果应依次报告 attack validity、
selector/checker risk-coverage、L2 conformance、clean utility、attacked efficacy、Dual interaction 和
failure taxonomy；不能用一个 aggregate “safe success” 隐藏 unknown、deadlock 或 residual proxy。
