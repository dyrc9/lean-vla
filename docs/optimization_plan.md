# VLA-only 攻击复现优先规划

更新日期：2026-07-22

## 0. 文档地位

独立 SABER P0b 大样本 replication 已在通过 GPU 2/3、source、model、checkpoint 与 clean-worktree 预检后
于 2026-07-22 启动；本次错误使用根 `.venv`，未使用含 `art`/`vllm` 的 SABER `.venv`，producer 在攻击代理
初始化前 terminal，0 record/0 victim/0 outcome。
该 frozen protocol/root 不得重试，当前没有可产生新 outcome 的授权实验线。`proofalign-integrity-v1` 本地原型、
unit tests 和 Lean build 继续允许；fixed-trace method outcome、AEGIS/SAFE/FIPER 和 attacked+defended
comparison 仍未授权。
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
5. qualified attack count 为 `0`：Phantom held-out independent transition 为 `1/4`；SABER P0 R7 的
   4 个 clean-eligible pair 中有 `1/4 = 0.25` typed transition，低于冻结的 count `2`/rate `0.5` gate。

### 1.2 新顺序

安全实验基础和 CTDA v2 no-action 结果全部冻结。当前授权的单线顺序是：

```text
independent 48-pair SABER P0b producer protocol/root
  -> immutable attack record/transcript/schema/hash validation
  -> unguarded VLA-only clean/attacked pair
  -> independent clean-safe -> attacked-unsafe qualification
  -> terminal manifest/ledger/artifact/hash
  -> stop and report

P0b terminal 后停止并汇报；不自动转 EDPA 或 defense
```

当前硬约束：

- 允许 minimal integrity prototype 的本地 unit test、Lean build 和代码审计；
- 不运行 ProofAlign/CTDA 的 fixed-trace/no-dispatch/clean/attacked method outcome；
- 不实现或验证数值 budget、recovery、raw perception 或新 CTDA support；
- 不运行 AEGIS、SAFE、FIPER 或其他 defense baseline；
- 不执行 attacked+defended comparison；
- 不让 CTDA verdict、detector alarm、task failure 或 attack metadata 充当 safety ground truth；
- 不恢复或拼接任何已关闭/partial run；新工作必须使用 fresh protocol/root/unit。

截至 2026-07-20，工作线 B 已完成安全基础重建：官方 source commit/tree/license、32 个
scenario、1600 个 init state、49 个 BDDL/init 数据文件、官方 collision classifier、typed provenance 和
CAR/TSR/ETS/cost/RET/四象限指标均可只读复核；AEGIS 双环境与模型资产通过 static gate，标准 pi0.5/
GroundingDINO 通过 no-inference load，单个 frozen scene 通过 `env.step_count=0` serialization。以上仍不
授权 rollout。

P0b producer/victim 是唯一允许创建实验 output 的路径。只有阻断 official attack producer、VLA-only victim
或独立 safety oracle 的代码/环境问题允许修复；P0b terminal 结果形成后仍必须停止并请求下一步授权。

## 2. 阶段目标与非目标

当前代码目标仅包括审计第 3 节的 no-action minimal prototype。第 4 节的 P0b 已 terminal，不能再执行；
第 5 节实验矩阵和 D2--D4 继续 deferred；新原型不继承现有 CTDA v2 六阶段架构。

### 2.1 架构目标与状态

1. **implemented locally**：两个关系、两个不变量和三个 transaction；
2. **implemented locally**：VLA-only、Intent-only、Execution-only、Dual 共享 method switch，unit tests
   覆盖 wrong-target、stale-state 与 command-substitution 的层级差异；
3. **deferred experiment**：clean retention、phase completion、deadlock 和 evidence coverage gate；
4. **partial**：Lean 已定义核心不变量；fast-checker refinement/equivalence 尚未建立；
5. **implemented structurally**：digest/signature/provenance/wire 不在 minimal method core；
6. **implemented interface only**：projection/brake/replan/hard-block 是可替换 intervention；AEGIS/recovery
   未接入；
7. **deferred experiment**：只使用先在 unguarded VLA-only 上独立 qualification 的发布攻击；
8. **permanent decision rule**：若双层无组合增益或 clean utility 不合格，收缩为单层/offline audit。

### 2.2 非目标

- 不声称硬件安全、连续动力学已被 Lean 证明或 real-time enforcement；
- 不把 zero-hold、CBF、signature、provenance 或 replan 写成方法 novelty；
- 不把现有 v2 certificate/rebind/六阶段 wire 视为下一架构必须保留的公开 API；
- 不为得到正结果后验更换 task/init/seed、阈值、攻击强度或 horizon；
- 不把 SAFE/FIPER partial artifact 拼成论文结果；
- 不复用已关闭的 Phantom/SABER unit 或 output root；
- 不在本机创建替代实验环境。

## 3. 最小架构与本地原型（implemented, no-action）

现有 CTDA v2 no-dispatch core、wire、crypto 与 AEGIS plumbing 作为历史资产保持 replayable，但不再作为
新 architecture freeze 的默认答案。`proofalign-integrity-v1` 已按本节实现独立 Python core 与 Lean
model；它不修改 v1/v2，也没有 simulator/action capability。

### 3.1 两个关系、两个不变量、三个 transaction

```text
Intent–Plan Integrity
Plan–Execution Integrity

No dispatch without dual authorization
No phase advance without checked completion

certify contract -> authorize exact prefix -> check effect/update monitor
```

对外核心对象限定为 `MissionRoot`、`ActiveContract`、`ActionProposal`、`PrefixAuthorization` 和
`ExecutionEvidence`。freshness/rebind 折叠进 prefix authorization；progress/completion 折叠进 persistent
monitor update；内部 stage 数量不得成为方法贡献。

### 3.2 五个组件边界

1. Mission Adapter：只从 trusted benchmark artifact 建立有限 `MissionRoot`；
2. Persistent Contract Monitor：保存 contract、phase、history 和 residual obligations；
3. Exact Prefix Authorizer：在 fresh state 下绑定 proposal 与最终 command；
4. Single Dispatch Boundary：只执行 fresh、单次 authorization；
5. Effect Observer/Updater：检查 receipt/effect 并原子更新 pending/completion/violation。

四个核心实验 arm 必须共用同一 runner、observer、dispatch 和 intervention，通过 method switch 控制
Intent/Execution judgment，不能复制代码路径造成不可比较的系统差异。

### 3.3 Lean 与 fast checker

默认目标是：Lean 定义两个不变量和最小 state transition，online 使用版本固定的 deterministic fast
checker，full request 只在 shadow/offline replay。进入 online 前必须建立 core theorem 到实际 checker/
wire 的 refinement/equivalence，而不是只报告 Python/Lean fixture parity。

若 fixed-trace 或 clean gate 无法同时满足 liveness、freshness 和 verifier latency，则停止 online claim，
只保留 offline audit/slow interlock。

### 3.4 Optional intervention 与 evidence

`pass/project_or_brake/replan/hard_block` 是 intervention decision，不是逻辑层。filter 修改 command 后必须
重新授权 adjusted command；receipt/effect 绑定实际 dispatch。AEGIS 与 PACS-style braking 作为独立物理
baseline/扩展，不能成为双层 integrity 的默认组成。

每个 primary safety observation仍必须保存 quantity/unit、producer/version、source ids、timestamp、state
epoch、coverage/unknown reason 及 episode/command/receipt binding。缺少可信 producer 时收窄 claim，不填
默认 safe 值。

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

**P0：SABER constraint-violation 官方路径（已 terminal nonpass）**

- 使用官方代码、released attacker 和官方支持 victim/config，生成并冻结 4 条 immutable official-agent
  record；
- R7 的 8/8 episode 有效，4 个 clean-eligible pair 中 1 个出现 robot-contact/action-magnitude typed
  transition；该结果未达到预注册 gate，不授权 defense，也不调攻击、record、pair 或 seed；
- 不复用旧 `saber_liberosafety_r1` record/root/unit，R4--R7 root 均不 resume。
- 未来可以有新的独立 SABER replication，但必须重新冻结不重叠 population、source/asset hash、gate 和
  fresh root；它不能作为 R7 的 continuation 或 replacement。

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

## 5. 后续基线与实验矩阵（deferred）

### 5.1 核心因果消融

| arm | Intent–Plan | Plan–Execution | 主要问题 |
|---|---:|---:|---|
| VLA-only | 否 | 否 | unguarded task/safety/cost 基准 |
| Intent-only | 是 | 否 | mission authorization 的 unique catch 与误阻断 |
| Execution-only | 否 | 是 | exact command/receipt/effect binding 的 unique catch 与误阻断 |
| Dual | 是 | 是 | 两层组合是否必要、是否保留 clean utility |

四臂必须共用相同 victim、proposal、observer、dispatch、horizon、seed 和 intervention policy。否则不能把
差异归因到两个 integrity relation。

### 5.2 外部 baseline 的独立角色

| 方法 | 角色 | 公平比较范围 |
|---|---|---|
| AEGIS / PACS-style filter | 低层物理 intervention | collision/cost、safe success、修改范数、latency |
| SAFE / FIPER | failure detector | detector metric；closed loop 时共用同一 stop/replan policy |
| RoboGuard / SafeGate | semantic/plan gate | adapter 完成后与 Intent-only 对比 |
| Dual + physical filter | 组合扩展 | post-filter reauthorization 与 physical safety/utility |

外部 baseline 不混进核心 Dual arm。SAFE/FIPER 旧 partial 不 resume；任何新 baseline 使用新
protocol/root。

### 5.3 三阶段矩阵

**阶段 I：fixed-trace/shadow**

VLA-only、Intent-only、Execution-only、Dual 面对同一 candidate/trace，测 unique catch、nominal allow、
unknown/block、parity 和 latency。

**阶段 II：clean closed loop**

四个核心 arm 都 required。只有 Dual 达到事前冻结的 utility retention、phase completion、deadlock 和
evidence coverage gate，才允许进入攻击比较。

**阶段 III：qualified attack**

只对第 4 节 terminal pass 的 workload 运行四个核心 arm。AEGIS、detector、semantic baseline 和
Dual+filter 根据独立 readiness 加入 secondary matrix，不阻塞核心因果消融。

### 5.4 Primary metrics

必须分组报告，不能合并成一个“安全成功率”：

- **实验有效性**：valid/invalid pair、initial digest、first chunk、checkpoint/config/camera/seed binding；
- **任务能力**：task success、safe success、phase completion、episode length/ETS、retention；
- **安全结果**：collision、constraint violation、cumulative cost、risk exposure time、四象限；
- **层级诊断**：Intent-only catch、Execution-only catch、overlap、Dual unique gain；
- **干扰/liveness**：allow/project/brake/replan/block/unknown、blocked time、deadlock、recovery；
- **完整性**：mission、proposal/final command、dispatch/receipt/effect、stale/replay、completion witness；
- **开销**：fast checker、proof/shadow、filter、observer/monitor latency。

protocol 必须在 outcome 前填写 `utility_retention_min`、`phase_completion_min`、
`safe_success_noninferiority_margin`、`attack_transition_min_count/rate`、`layer_unique_catch_definition`、
`confidence_method`、`primary_safety_channels` 和 `stop_conditions`。

## 6. 当前里程碑与 terminal 后恢复 gate

### M5：VLA-only threat qualification

**状态：SABER R7 terminal nonpass；P0b producer terminal failure；EDPA P1a frozen/unevaluated。** R7 已使用
独立 fresh protocol/root 完成 4 pair，但未达到 held-out gate。P0b 的 48-pair outcome-blind population、
one-shot producer、至少 26 eligible/rate 0.5 gate、Wilson 95% CI 和 96-episode victim 路径均已冻结；
2026-07-22 formal preflight 通过 source/model/checkouts/GPU 2/3，但 producer 在 attack-agent initialization
前错误使用根 `.venv`（正确 SABER `.venv` 包含 `art`/`vllm`）而终止，故 record/episode/outcome 均为 0，且 root
不得重试。P1a 已拥有独立 protocol、runner 与
content-addressed dual-camera patch asset gate；fresh2 producer completed、静态 preflight `ready: true`，但运行前
GPU `<4096 MiB`/无 compute-process gate 未满足，故没有 result root、episode 或 victim outcome。P1a 必须保持
`not_yet_evaluated`。P0b terminal 后必须停止并汇报，不得转入 EDPA 或 attack-defense main。

M5 成功或失败都不会自动启动实验 D2--D4。

### D0：最小方法与架构重冻

**状态：local design complete。**

- 冻结两个关系、两个不变量、三个 transaction、五个组件和四个核心 arm；
- 冻结 TCB、threat model、unknown/fail-closed 与 liveness semantics；
- 决定哪些 v1/v2资产复用、只读兼容或淘汰；
- 不在此阶段增加 AEGIS、crypto、recovery 或新 provenance producer。

退出条件：方法图、API、形式属性和消融矩阵能在一页内对应，历史 artifact 保持 replayable。

### D1：core formalization 与 fixed-trace

**状态：core implementation complete；refinement/fixed-trace outcome deferred。**

- 只实现三个 transaction 和四臂 method switch；
- Lean 只覆盖两个不变量与 arm semantics；fast-checker refinement/equivalence 尚未实现；
- 本地 unit transaction 已覆盖两层 unique failure；fake-env/fixed-trace/shadow outcome 当前不运行；
- 报告 nominal allow、layer unique catch、parity、unknown/block 和 latency。

退出条件：两单层各有事前定义的 unique catch，Dual 不因 proof wall time 或协议 bookkeeping 破坏
nominal liveness。否则缩小方法。

### D2：新的 clean pilot

使用新 method id、protocol、disjoint unit/seed 和 fresh root，不重跑旧 E1 unit。四个核心 arm 共享完整
runner/observer/dispatch 配置。

退出条件：Dual 达到预注册 clean retention、phase completion、deadlock 和 evidence coverage gate。失败则
保留负结果并停止，不进入攻击比较，也不在同一 protocol 调阈值。

### D3：qualified attack comparison

只使用 M5 terminal pass 且 population 与 method support 完全重合的 workload。运行 VLA-only、
Intent-only、Execution-only、Dual，回答 layer necessity 与 composition gain。

### D4：外部 baseline 与 optional intervention

在核心结论之后再加入 AEGIS/PACS-style filter、SAFE/FIPER、RoboGuard/SafeGate 或 verified recovery
候选。任何 adjusted command 都重新授权，且组合收益与核心 integrity 收益分开报告。

## 7. 代码与 artifact 纪律

1. CTDA v1/v2 code path、wire、protocol、results 保持 replayable；后续重冻使用新的 method/schema id。
2. 不在旧 JSON 上补字段后冒充新版本；需要 migration 时写显式 read-only adapter。
3. external code 使用 pinned commit/digest，不把临时 patch 混入上游目录且不记录来源。
4. runner 默认 read-only；只有显式 `--execute --gpu PHYSICAL_ID` 才能 dispatch。
5. 正式执行前 protocol 必须先提交，worktree clean，output root absent。
6. 已创建 episode 后的异常保留为 invalid/unknown；不替换 unit、seed 或 attack artifact。
7. 不删除 `external/fiper/data` 用户 symlink，不恢复已停止 FIPER service。

## 8. 全局停止条件与 claim boundary

- 任一 workload 得到 terminal pass/fail/blocked 结果：保存完整 artifact 后停止并汇报，不进入自研方法；
- 所有 ProofAlign/CTDA/AEGIS/SAFE/FIPER method 或 baseline execution 当前均未授权；
- D2 clean pilot 未达到预注册 utility gate：不进入 attacked+defended main；
- qualified attack count 仍为 0：不报告 attack-defense efficacy；
- attack population 与 support population 不重合：不做 defense comparison；
- independent safety oracle 缺 coverage/provenance：该 pair 不进入 safety denominator；
- adjusted command 未经过 exact prefix reauthorization：不得 dispatch；
- protocol/source/checkpoint/hash/GPU/EGL/output-root 任一不一致：不得正式执行；
- 任何结果都只支持指定 simulator/task/model/workload 上的结论，不推广到硬件或总体分布。

工作机的完整交接指令见 [`next_experiment_prompt.md`](next_experiment_prompt.md)。
