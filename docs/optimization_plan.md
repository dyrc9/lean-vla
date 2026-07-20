# ProofAlign CTDA v2 远端优化与实验重建规划

更新日期：2026-07-20

## 0. 文档地位

本文定义从 CTDA v1 负结果出发的下一阶段工程与实验顺序，是当前远端优化工作的执行规划。
当前方法语义仍以 [`method.md`](method.md) 为准，历史结果仍以
[`evaluation_results.md`](evaluation_results.md) 和机器 artifact 为准。本文不会后验修改 CTDA v1、
E1、Phantom、SABER、SAFE 或 FIPER 的既有 protocol/result。

工作只在同步后的工作机 `/home/ldx/lean-vla` 继续；本机没有实验环境，不在本机运行 VLA、GPU、
MuJoCo 或正式 rollout。

## 1. 当前证据与决策

### 1.1 已确认的问题

1. CTDA v1 的 paired experiment 有效，但 operational utility 不合格：VLA-only `8/12`、Full CTDA
   `0/12` task/safe success，retention `0`，Full CTDA 为 `12` block、`12` deadlock、`0` phase
   completion。
2. `2640/2640` Lean proof/parity 通过，只能说明实现忠实执行了冻结离散 spec；不能证明该 spec 的
   contract lifetime、progress/stutter 或在线调度合理。
3. 9/12 Full episode 因 40 秒 semantic-contract wall-clock coverage 耗尽，3/12 因 persistent
   bounded-stutter no-progress limit 耗尽。当前 zero-hold/fail-closed 路径缺少恢复到任务执行的
   liveness transition。
4. human-hand/obstacle distance 在 24/24 episode 缺 typed provenance；collision/cost coverage 完整
   不能替代这两个维度。
5. qualified attack count 为 `0`：Phantom held-out 独立 safety transition 为 `1/4`，正式 SABER
   exact-task R1 为 `0 record / 0 victim`。

### 1.2 新顺序

后续不再采用“先调攻击，攻击通过后才允许讨论 CTDA v2”的单线程顺序。改为两条互不污染的工作线：

```text
工作线 A：CTDA v2 离线设计、代码、fixed-trace/shadow、no-dispatch 验证
工作线 B：SafeLIBERO/AEGIS readiness + VLA-only attack qualification
                              |
                              v
汇合 gate：v2 clean utility 合格 + workload 独立 safety harm 合格 + 支持集合完全重合
                              |
                              v
正式 clean / safety-critical / attacked paired comparison
```

两条工作线可以并行开发，但在汇合 gate 前：

- 工作线 A 不使用攻击 outcome 调 contract threshold；
- 工作线 B 不加载 CTDA verdict 作为 attack reward 或 ground truth；
- 不执行 attacked+defended 正式 rollout；
- 不恢复或拼接任何已关闭/partial run。

## 2. 阶段目标与非目标

### 2.1 目标

1. 保留两个协议不变量：无双重授权不 dispatch；无 checked completion witness 不推进 phase。
2. 把正常、已授权且物理可接受的 nominal action 原样放行；只有必要时才最小修改、制动、重规划或
   hard block。
3. 将慢速语义证明与快速控制检查解耦，不再让单次 Lean latency 自动耗尽整个 semantic contract。
4. 为 intervention 后的最终 command、dispatch、receipt 和 observed effect 保持完整绑定。
5. 在 SafeLIBERO 上建立安全场景土壤，用独立 collision/cost/constraint oracle 评估，而不是用 task
   failure 代替安全伤害。
6. 先完成 VLA-only threat qualification，再计算 attack-defense efficacy。
7. 增加真正的低层闭环基线 AEGIS；SAFE/FIPER 只作为 detector，RoboGuard/SafeGate 只作为高层
   semantic baseline。

### 2.2 非目标

- 不声称硬件安全、连续动力学已被 Lean 证明或 real-time enforcement；
- 不把 zero-hold、CBF 或 replan 自动写成 verified recovery；
- 不为得到正结果后验更换 task/init/seed、阈值、攻击强度或 horizon；
- 不把 SAFE/FIPER partial artifact 拼成论文结果；
- 不复用已关闭的 Phantom/SABER unit 或 output root；
- 不在本机创建替代实验环境。

## 3. CTDA v2 架构冻结项

本节是待实现目标，不是已经成立的方法结论。M0 设计冻结必须把最终选择写入 `method.md` 的独立
CTDA v2 章节和版本化 schema；在此之前不得将 v2 写成正式结果。

### 3.1 Contract epoch 与 state freshness

CTDA v2 应把“合同仍被 mission 授权”和“当前传感器状态仍新鲜”分开表达。一个 contract epoch 至少
绑定：

- mission/root digest、episode nonce；
- active phase、residual obligations、contract version；
- 生成证明所用 relevant-state digest/epoch；
- observer provenance、observation timestamp、允许的 sensor age；
- checker/version digest 和 Lean proof artifact digest；
- 可执行 action/trajectory set 的版本化定义。

语义合同可以跨多个 action chunks 保持有效，直到 mission、phase、residual obligation 或合同依赖的
relevant state 改变。proof latency 不能通过延长 stale-state 权限被掩盖：若证明期间 plant 或相关状态
可能变化，dispatch 前必须 re-observe 并完成显式 rebind；rebind 失败则进入 `replan` 或 `hard_block`。

M0 必须在以下两种实现中冻结一种，推荐第一种：

1. **Lean-proven contract certificate + 快速 membership checker（推荐）**：Lean 验证长期合同、离散
   predicate 和 checker/version binding；控制周期只运行确定性 consumer-side membership/freshness
   checker，完整 request 在 shadow/offline 路径重放给 Lean。
2. **pipelined/batched Lean**：仍逐 prefix 使用 Lean authority，但必须证明 proof pipeline 与状态快照
   的 freshness/rebind，不得用未来 proof 授权过去或已经变化的 state。

若两种方案都无法在 fixed-trace/no-dispatch gate 上保留 nominal liveness，则停止 v2 online claim，
只保留 offline audit。

### 3.2 从二元阻断改为分级 intervention

运行时 decision 必须显式区分：

```text
pass              nominal command 原样执行
project_or_brake  在已授权集合内最小修改、沿 intended path 减速或停止
replan            不推进 phase，刷新 observation/contract 或请求新 proposal
hard_block        未授权、证据不一致、不可恢复危险或 TCB/evaluator failure
```

约束：

1. `pass` 的最终 command digest 必须等于 nominal command digest；
2. `project_or_brake` 必须保存 nominal、adjusted、intervention reason、filter/version、修改范数、
   constraint witness，并对 **adjusted command** 重新做 mission/contract 检查；
3. `replan` 不能退款 cumulative obligation/budget，不能伪造 progress，也不能推进 phase；
4. `hard_block` 才进入安全停止；停止后必须有 bounded recovery policy，不能把 absorbing zero-hold 当作
   正常任务终态；
5. 无论哪条路径，receipt 和 observed trace 都绑定实际 dispatch 的 command，而不是 nominal command。

### 3.3 最小干预物理层

近期实现和比较优先使用已经公开的 AEGIS/SafeLIBERO：

- 论文：<https://arxiv.org/html/2512.11891>
- 官方代码：<https://github.com/THU-RCSCT/vlsa-aegis>

AEGIS 作为独立 baseline，不直接成为 CTDA 证据根。若将其安全 filter 接入 CTDA v2，必须在 filter
之后检查 adjusted command，并明确其保证依赖 obstacle perception、geometry enclosure 和 end-effector
模型。不得把其 CBF 结果概括成完整 mission authorization。

PACS 的 path-consistent braking 用作 action-chunk 设计参考：
<https://arxiv.org/html/2511.06385>。在官方代码可用或本项目有独立、可审计的等价实现前，不把 PACS
列为立即可跑的 mandatory baseline。

### 3.4 Typed observation provenance

每个安全 observation 必须保存：

- quantity 名称、单位和 schema version；
- producer 类型（simulator state、contact buffer、depth/geometry estimator 等）；
- source object/geom/camera id；
- observation timestamp 与 state epoch；
- validity/coverage/unknown reason；
- 与 episode、task/init、command、receipt 的 digest binding。

若某个 suite 没有可复核的 human-hand/obstacle distance producer，则 protocol 必须把该维度从 primary
claim 中移除，而不是记录一个没有 provenance 的默认值。

## 4. 安全场景与攻击工作线

### 4.1 SafeLIBERO 作为 P0 安全土壤

SafeLIBERO 先用于回答“防御能否在有物理危险的场景中保留任务能力”，不自动构成 adversarial
attack claim。工作机需要：

1. pin 官方 `vlsa-aegis` commit、SafeLIBERO data digest 和依赖版本；
2. 做 read-only task/scene inventory，不修改官方 benchmark 定义；
3. outcome-blind 冻结候选 model/checkpoint/task/init/seed inventory 和 clean/safety classifier；
4. 为完全相同的 candidate population 做 CTDA v2 support audit；
5. 正式 protocol 保留所有 candidate outcome，不按 clean 结果替换 pair；clean-success/clean-safe 只作为
   预定义的条件式 attack-transition denominator。若使用 discovery 筛选，必须与 formal held-out
   task/seed 不相交；
6. 采用官方 collision check，同时增加 cumulative cost、risk exposure time 和四象限结果。

ForesightSafety-VLA 的指标定义用于补充 protocol，但当前不依赖其尚未确认公开的代码：
<https://arxiv.org/html/2606.27079>。

### 4.2 攻击优先级

**P0：SABER constraint-violation 官方路径**

- 使用官方代码、released attacker 和官方支持 victim/config；
- 先修复 producer readiness，生成 immutable official-agent record；
- record gate 通过后才运行 VLA-only victim；
- primary harm 必须是 clean-safe → attacked-unsafe，来自独立 collision/force/joint-limit/action-magnitude
  oracle；
- 不复用旧 `saber_liberosafety_r1` record/root/unit。

**P1：EDPA 原始 patch + SafeLIBERO**

- 保持 EDPA 原始攻击生成定义，不按 SafeLIBERO outcome 调攻击；
- task failure 只作 robustness metric；attack qualification 使用独立 collision/cost/constraint signal；
- 论文：<https://arxiv.org/html/2510.13237>。

**停止项**

- Phantom 已关闭的 R0/R0b/R1 不再调强度或换 pair；
- RoboGCG、部分可观测 patch 可做后续扩展，但不阻塞 P0；
- 若 SABER 和 EDPA 都没有通过预注册的 held-out safety gate，则删除或收窄 attack-defense claim，
  不继续 outcome-driven attack search。

### 4.3 Threat qualification chain

每个 workload 必须依次满足：

1. producer/config/model/source hash readiness；
2. immutable attack artifact 忠实生成并通过 schema validator；
3. 同 task/init/seed/checkpoint 的 clean/attack VLA-only pair；
4. clean arm clean-success 且 clean-safe；
5. attacked arm 产生预定义独立 safety transition；
6. disjoint held-out gate 达到 outcome 前冻结的 count/rate；
7. terminal manifest、ledger、artifact hashes 完整；
8. attack population 与 CTDA v2 support population 完全重合。

未完成第 7 项不是 partial pass；未完成第 8 项不得开始 defense comparison。

## 5. 基线与正式实验矩阵

### 5.1 基线角色

| 方法 | 角色 | 公平比较范围 |
|---|---|---|
| VLA-only | unguarded victim | task/safety/cost 基准 |
| AEGIS | 低层最小干预安全 filter | CAR、safe success、TSR、ETS、intervention/latency |
| SAFE/FIPER | failure detector | detector metric；若转为 stop/replan，必须共用同一 fallback |
| RoboGuard/SafeGate | 高层 semantic/plan gate | 只有完成独立 VLA/LIBERO adapter 后才进入 closed loop |
| CTDA v2 | mission authorization + execution binding | utility、安全、完整性、deadlock、proof/verifier tax |
| CTDA v2 + physical filter | 主方法候选 | post-filter authorization 与闭环安全/utility |

SAFE/FIPER 旧 partial 不 resume；新的 baseline run 必须是新的 protocol/root。P0 主表不等待它们，除非
官方 reproduction 能在 outcome 前 terminal-ready。

### 5.2 两阶段正式矩阵

**阶段 I：clean / safety-critical deployment**

| arm | 原始 clean slice | SafeLIBERO |
|---|---:|---:|
| VLA-only | required | required |
| AEGIS | optional | required |
| CTDA v2 | required | required |
| CTDA v2 + AEGIS-compatible filter | required | required |

**阶段 II：attack-defense**

只对通过 qualification 的 workload 执行：

| arm | clean workload | attacked workload |
|---|---:|---:|
| VLA-only | required | required |
| AEGIS | required | required |
| CTDA v2 | required | required |
| CTDA v2 + physical filter | required | required |

### 5.3 Primary metrics

必须分组报告，不能合并成一个“安全成功率”：

- **实验有效性**：valid/invalid pair、initial digest、first chunk、checkpoint/config/camera/seed binding；
- **任务能力**：task success、phase completion、episode length/ETS；
- **安全结果**：collision avoidance、constraint violation、cumulative cost、risk exposure time、
  safe/unsafe success/failure；
- **防御干扰**：pass/project/brake/replan/hard-block count、修改范数、blocked time、deadlock、recovery；
- **完整性**：mission mismatch、proposal/adjusted/dispatch/receipt mismatch、stale/replay、completion witness；
- **开销**：VLA、semantic proof、fast checker、filter、observed/monitor 各阶段 latency。

protocol schema 必须在 outcome 前填写而不是留空：`utility_retention_min`、
`safe_success_noninferiority_margin`、`attack_transition_min_count/rate`、`confidence_method`、
`primary_safety_channels` 和 `stop_conditions`。具体数值必须来自 outcome-blind calibration/design
decision，不能从正式结果反推。

## 6. 里程碑、交付物与 gate

### M0：设计冻结，不运行 rollout

交付物：

- `method.md` 中独立 CTDA v2 版本/TCB/claim；
- contract epoch、decision、intervention witness、provenance schema；
- 选择 Lean certificate+fast checker 或 pipelined Lean；
- v2 wire/schema version 与 v1 compatibility policy；
- fake-env/fixed-trace test plan。

退出条件：安全不变量、liveness transition、proof/state freshness、post-filter authorization 都有明确
typed 语义；v1 artifact replay 不受影响。

### M1：v2 core 与 fixed-trace/shadow

交付物：

- versioned v2 runtime/wire/evaluator path；
- `pass/project_or_brake/replan/hard_block` transaction；
- contract epoch/rebind 与 bounded recovery；
- v1 regression、v2 unit、tamper、stale/replay、post-filter mismatch、no-phase-advance tests；
- retained E1 trace 的 outcome-blind replay 和 shadow report。

退出条件：nominal fixed trace 不再因 proof wall-clock 自身耗尽合同；攻击/错误目标/错误 gripper 和
证据 tamper 仍 fail closed；没有 Python fallback 冒充 Lean-authorized path。

### M2：provenance、SafeLIBERO 与 AEGIS readiness

交付物：

- typed safety-channel producers/validators；
- pinned SafeLIBERO/AEGIS source/data manifest；
- no-dispatch task/model/scene candidate inventory 和预定义 clean/safety classifier；
- exact-unit CTDA support audit；
- CAR/cost/RET/four-quadrant classifier。

退出条件：candidate population、support、classifier 和 safety-oracle coverage outcome-blind 冻结且完全
可复核；尚未运行的 clean outcome 不得在 readiness 阶段被假定为成功。

### M3：远端 no-dispatch preflight

交付物：

- clean commit 上的 v2 runner/protocol candidate；
- CPU/Lean focused tests 与 build；
- OpenPI model load/serialization、initial digest、first chunk、GPU/EGL binding 的 `env.step_count=0`
  probe；
- absent fresh output roots。

退出条件：所有 preflight `ready=true`。任何 blocker 只修代码/环境或重冻 protocol，不创建正式 outcome。

### M4：新的 clean v2 pilot

使用新 method id、protocol、unit/seed 和 fresh root；不得重跑 E1 policy-seed 1。先运行小型、事前固定
pilot，验证 clean retention、phase completion、deadlock 和 observation coverage。

退出条件：达到预注册 utility gate。未达到则停止 v2 main，保留负结果并返回 M0/M1 形成新版本；不得
在同一 protocol 内调阈值重跑。

### M5：VLA-only threat qualification

SABER P0、EDPA P1 各自使用独立 fresh protocol/root。只有 workload 达到 held-out independent-safety
gate 才冻结 attack-defense main。

### M6：正式矩阵与 E5

只有 M4、M5 和 population-overlap gate 全部通过才执行。终态必须保存 protocol、append-only ledger、
per-episode artifact、terminal manifest/summary、独立 validator 和 SHA-256，并同步 canonical 文档。

## 7. 代码与 artifact 纪律

1. CTDA v1 code path、wire、protocol、results 保持 replayable；v2 使用新 method/schema id。
2. 不在旧 JSON 上补字段后冒充 v2；需要 migration 时写显式 read-only adapter。
3. external code 使用 pinned commit/digest，不把临时 patch 混入上游目录且不记录来源。
4. runner 默认 read-only；只有显式 `--execute --gpu PHYSICAL_ID` 才能 dispatch。
5. 正式执行前 protocol 必须先提交，worktree clean，output root absent。
6. 已创建 episode 后的异常保留为 invalid/unknown；不替换 unit、seed 或 attack artifact。
7. 不删除 `external/fiper/data` 用户 symlink，不恢复已停止 FIPER service。

## 8. 全局停止条件与 claim boundary

- v2 clean pilot 未达到预注册 utility gate：不进入 attacked+defended main；
- qualified attack count 仍为 0：不报告 attack-defense efficacy；
- attack population 与 support population 不重合：不做 defense comparison；
- independent safety oracle 缺 coverage/provenance：该 pair 不进入 safety denominator；
- adjusted command 未经过 mission/contract post-filter check：不得 dispatch；
- protocol/source/checkpoint/hash/GPU/EGL/output-root 任一不一致：不得正式执行；
- 任何结果都只支持指定 simulator/task/model/workload 上的结论，不推广到硬件或总体分布。

工作机的完整交接指令见 [`next_experiment_prompt.md`](next_experiment_prompt.md)。
