# VLA-only 攻击复现优先规划

更新日期：2026-07-20

## 0. 文档地位

本文定义当前唯一允许的远端执行顺序：先完成 unguarded VLA-only 发布攻击复现与 threat
qualification。所有 ProofAlign/CTDA 自研 method、AEGIS/SAFE/FIPER defense baseline、clean method
pilot 和 attacked+defended comparison 均冻结，直到 VLA-only threat qualification terminal 结束且用户
再次明确授权。
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

安全实验基础和 CTDA v2 no-action 结果全部冻结。当前不再并行开发两层 method，按以下单线执行：

```text
fresh official SABER producer protocol/root
  -> immutable attack record/transcript/schema/hash validation
  -> unguarded VLA-only clean/attacked pair
  -> independent clean-safe -> attacked-unsafe qualification
  -> terminal manifest/ledger/artifact/hash
  -> stop and report

若 SABER terminal blocked/failed：
fresh EDPA + SafeLIBERO protocol/root
  -> original patch definition
  -> unguarded VLA-only clean/attacked pair
  -> independent safety qualification
  -> terminal artifacts
  -> stop and report
```

当前硬约束：

- 不运行 ProofAlign/CTDA 的 unit/fixed-trace/no-dispatch/clean/attacked method outcome；
- 不实现或验证 attack-shift record、数值 budget、recovery、raw perception 或新 CTDA support；
- 不运行 AEGIS、SAFE、FIPER 或其他 defense baseline；
- 不执行 attacked+defended comparison；
- 不让 CTDA verdict、detector alarm、task failure 或 attack metadata充当 safety ground truth；
- 不恢复或拼接任何已关闭/partial run；新工作必须使用 fresh protocol/root/unit。

截至 2026-07-20，工作线 B 已完成安全基础重建：官方 source commit/tree/license、32 个
scenario、1600 个 init state、49 个 BDDL/init 数据文件、官方 collision classifier、typed provenance 和
CAR/TSR/ETS/cost/RET/四象限指标均可只读复核；AEGIS 双环境与模型资产通过 static gate，标准 pi0.5/
GroundingDINO 通过 no-inference load，单个 frozen scene 通过 `env.step_count=0` serialization。以上仍不
授权 rollout。

从此处起，只有阻断 official attack producer、VLA-only victim 或独立 safety oracle 的代码/环境问题
允许修复。VLA-only terminal 结果形成后必须停止并请求下一步授权。

## 2. 阶段目标与非目标

本节后续保存的 CTDA v2 架构与正式矩阵是延后设计，不是当前授权。当前目标只有第 4 节的 VLA-only
threat qualification；第 3、5 节及 M0--M4/M6 均不得执行。

### 2.1 延后目标（当前不执行）

1. 直接测量 Layer 1 的 intent→plan attack shift 和 Layer 2 的 plan→execution attack shift，并报告
   semantic-only、execution-only、dual 三种 checker 的 unique catch。
2. 保留两个协议不变量：无两层授权不 dispatch；无 checked completion witness 不推进 phase。
3. 把正常、已授权且物理可接受的 nominal action 原样放行；只有必要时才最小修改、制动、重规划或
   hard block。
4. 将慢速语义证明与快速控制检查解耦，不再让单次 Lean latency 自动耗尽整个 semantic contract。
5. 为 intervention 后的最终 command、dispatch、receipt 和 observed effect 保持完整绑定。
6. 在 SafeLIBERO 上建立安全场景土壤，用独立 collision/cost/constraint oracle 评估，而不是用 task
   failure 代替安全伤害。
7. 先完成 VLA-only threat qualification，再计算 attack-defense efficacy。
8. 增加真正的低层闭环基线 AEGIS；SAFE/FIPER 只作为 detector，RoboGuard/SafeGate 只作为高层
   semantic baseline。

### 2.2 非目标

- 不声称硬件安全、连续动力学已被 Lean 证明或 real-time enforcement；
- 不把 zero-hold、CBF 或 replan 自动写成 verified recovery；
- 不为得到正结果后验更换 task/init/seed、阈值、攻击强度或 horizon；
- 不把 SAFE/FIPER partial artifact 拼成论文结果；
- 不复用已关闭的 Phantom/SABER unit 或 output root；
- 不在本机创建替代实验环境。

## 3. CTDA v2 架构冻结项（deferred）

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

## 5. 基线与正式实验矩阵（deferred）

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

里程碑编号仅保留历史依赖关系。当前唯一 active milestone 是 M5；M0--M4 和 M6 全部冻结，不得运行、
不得并行施工，也不得因为 M5 成功而自动恢复。

### M0：设计冻结，不运行 rollout

**状态：deferred。当前不执行。**

交付物：

- `method.md` 中独立 CTDA v2 版本/TCB/claim；
- contract epoch、decision、intervention witness、provenance schema；
- 选择 Lean certificate+fast checker 或 pipelined Lean；
- v2 wire/schema version 与 v1 compatibility policy；
- fake-env/fixed-trace test plan。

退出条件：安全不变量、liveness transition、proof/state freshness、post-filter authorization 都有明确
typed 语义；v1 artifact replay 不受影响。

### M1：v2 core 与 fixed-trace/shadow

**状态：deferred。当前不执行。**

交付物：

- versioned v2 runtime/wire/evaluator path；
- `pass/project_or_brake/replan/hard_block` transaction；
- contract epoch/rebind 与 bounded recovery；
- v1 regression、v2 unit、tamper、stale/replay、post-filter mismatch、no-phase-advance tests；
- retained E1 trace 的 outcome-blind replay 和 shadow report。

退出条件：nominal fixed trace 不再因 proof wall-clock 自身耗尽合同；攻击/错误目标/错误 gripper 和
证据 tamper 仍 fail closed；没有 Python fallback 冒充 Lean-authorized path。

### M2：provenance、SafeLIBERO 与 AEGIS readiness

**状态：deferred。当前不执行。**

交付物：

- typed safety-channel producers/validators；
- pinned SafeLIBERO/AEGIS source/data manifest；
- no-dispatch task/model/scene candidate inventory 和预定义 clean/safety classifier；
- exact-unit CTDA support audit；
- CAR/cost/RET/four-quadrant classifier。

当前进度：source/data/inventory/classifier 已由 R0 固定；双环境、全部 distribution inventory、标准
pi0.5/GroundingDINO 资产与 SafeLIBERO 注册已由
`experiments/safelibero_aegis_runtime_protocol.json` 的 static R1 固定；后续 model-load/scene
no-dispatch R2/R3 也已完成。CTDA v2 已 source-compile 32/32 mission template；full-population state r1
已在 32/1600 unit 上得到 exact state-key 与 collision-source 1600/1600、`env.step=0`。完整 executable
support 仍 blocked。wire parity R0 已以 6 stage/21 case、21/21 Python/Lean parity 完成；drawer
OpenRegion initial source gate R2 也已得到 exact joint/range/predicate 50/50、`env.step=0`。由于 50 个
初态全部是 `qpos=0.0 m`/closed，R0 进一步完成 6/6 fake-observation progress/post-filter/recovery-ledger
no-dispatch adapter；Ed25519、source-bound CBF/QP 与 typed geometry 也已完成 no-action audit。它们至此
冻结为支撑基础。当前 method blocker 是把同一事务的 trusted intent、raw plan、accepted plan、applied
command 与 observed effect 组成双层 attack-shift record/ablation，以及 disjoint numeric budget、natural
transition evidence 和 clean liveness；direct-state 5/5 不能替代这些 blocker。

退出条件：candidate population、support、classifier 和 safety-oracle coverage outcome-blind 冻结且完全
可复核；尚未运行的 clean outcome 不得在 readiness 阶段被假定为成功。

### M3：远端 no-dispatch preflight

**状态：deferred。当前不执行。**

交付物：

- clean commit 上的 v2 runner/protocol candidate；
- CPU/Lean focused tests 与 build；
- OpenPI model load/serialization、initial digest、first chunk、GPU/EGL binding 的 `env.step_count=0`
  probe；
- absent fresh output roots。

退出条件：所有 preflight `ready=true`。任何 blocker 只修代码/环境或重冻 protocol，不创建正式 outcome。

### M4：新的 clean v2 pilot

**状态：deferred。当前不执行。**

使用新 method id、protocol、unit/seed 和 fresh root；不得重跑 E1 policy-seed 1。先运行小型、事前固定
pilot，验证 clean retention、phase completion、deadlock 和 observation coverage。

退出条件：达到预注册 utility gate。未达到则停止 v2 main，保留负结果并返回 M0/M1 形成新版本；不得
在同一 protocol 内调阈值重跑。

### M5：VLA-only threat qualification

**状态：current sole execution milestone。** SABER P0、EDPA P1 各自使用独立 fresh protocol/root，
只运行 unguarded VLA-only clean/attacked pair。workload 达到或未达到 held-out independent-safety gate
都必须形成 terminal artifact，然后停止并汇报；不得转入 attack-defense main。

### M6：正式矩阵与 E5

**状态：deferred/unauthorized。** 即使 M5 通过也不得执行。恢复需要用户新的明确授权、新 protocol 和
重新冻结的 gate。

## 7. 代码与 artifact 纪律

1. CTDA v1 code path、wire、protocol、results 保持 replayable；v2 使用新 method/schema id。
2. 不在旧 JSON 上补字段后冒充 v2；需要 migration 时写显式 read-only adapter。
3. external code 使用 pinned commit/digest，不把临时 patch 混入上游目录且不记录来源。
4. runner 默认 read-only；只有显式 `--execute --gpu PHYSICAL_ID` 才能 dispatch。
5. 正式执行前 protocol 必须先提交，worktree clean，output root absent。
6. 已创建 episode 后的异常保留为 invalid/unknown；不替换 unit、seed 或 attack artifact。
7. 不删除 `external/fiper/data` 用户 symlink，不恢复已停止 FIPER service。

## 8. 全局停止条件与 claim boundary

- 任一 workload 得到 terminal pass/fail/blocked 结果：保存完整 artifact 后停止并汇报，不进入自研方法；
- 所有 ProofAlign/CTDA/AEGIS/SAFE/FIPER method 或 baseline execution 当前均未授权；
- v2 clean pilot 未达到预注册 utility gate：不进入 attacked+defended main；
- qualified attack count 仍为 0：不报告 attack-defense efficacy；
- attack population 与 support population 不重合：不做 defense comparison；
- independent safety oracle 缺 coverage/provenance：该 pair 不进入 safety denominator；
- adjusted command 未经过 mission/contract post-filter check：不得 dispatch；
- protocol/source/checkpoint/hash/GPU/EGL/output-root 任一不一致：不得正式执行；
- 任何结果都只支持指定 simulator/task/model/workload 上的结论，不推广到硬件或总体分布。

工作机的完整交接指令见 [`next_experiment_prompt.md`](next_experiment_prompt.md)。
