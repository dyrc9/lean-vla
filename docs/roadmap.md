# ProofAlign Execution Roadmap

更新日期：2026-07-16

本文是唯一执行计划。历史 roadmap、实验 handoff 和 design memo 已归档。

## 0. 总目标

先交付一个有限、诚实、可运行、可审计的闭环：

```text
trusted frozen mission
  -> mission-rooted persistent contract
  -> independent raw-prefix binding
  -> Lean-kernel-checked discrete authorization
  -> exact dispatch and cumulative completion audit
```

当前 GPU 环境已完成 single-prefix diagnostic 和一次 bounded-stutter clean 重跑。后续 GPU rollout
仍只在相应 readiness gate 通过后分阶段执行；历史 3--5 prefix gate 在第二个新微动作处因一次性
budget 耗尽而失败。累计版本随后通过本地 CPU/Lean 与 strict preflight，但唯一一次相同配置重跑
在首 prefix 的 authorized-duration 边界失败；当前没有新的 GPU 扩样本入口。

## 1. 冻结原则

1. 不构造新攻击；只使用发布的、版本化的 attack artifact。
2. 不继续扩展完整 RTA 架构；CBF/reachability、硬件 attestation 和 verified recovery 全部暂缓。
3. 不做通用 NL/BDDL compiler；只支持一个显式 task/primitive slice。
4. 不把 policy-facing prompt 或 `proofalign_action` 当作 contract authority。
5. 不把 Python verdict 改名为 Lean proof。
6. 不跑大规模 GPU 主表来掩盖 false block 或 evaluator gap。
7. 不从 `docs/archive/` 恢复旧口径。

### 1.1 2026-07-16 执行优先级（覆盖后文历史顺序）

当前主线改为 **ProofAlign-first evaluation**。外部攻击与 baseline 复现保留为独立后台线，
但不再作为评测我们自己方法的前置条件。执行依赖固定为：

```text
主线：E0 支持范围与协议冻结
        -> E1 clean utility / coverage 配对 pilot
        -> E2 mission-only / trace-only / Full CTDA 消融
        -> E3 closed-loop intervention 与任务结果
        -> E4 verifier / 系统代价与鲁棒性
        -> E5 外部 baseline / workload 最终对比

后台线：SAFE / FIPER 官方复现与已冻结 workload 审计 -----------┘
```

其中 E0--E4 回答“我们的系统在明确支持的范围内是否工作、付出什么代价、两层是否各有贡献”，
不等待 SAFE/FIPER terminal pass，也不等待新的 attack signal。E5 才回答“相对现有方法怎样”。
攻击 efficacy 仍必须有独立、事前冻结的 workload signal；Phantom/SABER 的既有负结果和停止条件
不因优先级调整而重开。

## 2. P0：文档与 claim scope freeze

状态：**完成**。

产物：

- canonical method、architecture、experiment protocol 和 remote runbook；
- trusted, locally frozen mission 的准确措辞；
- 两个系统不变量；
- 当前不可声称能力；
- archive 与 canonical source-of-truth 规则。

后续方法变更必须同步更新 `method.md`、Lean definition、Python evaluator 和 tests，不再新增
平行 design memo。

## 3. P1：修正合同来源与 raw-action binding

状态：**本地完成**。

已实现 frozen Pick/Place template、phase/residual-obligation contract provider、policy metadata
隔离和版本化 raw binder；prompt/metadata/registry/wrong-target/gripper/held-object/region 回归测试已
通过。

### 3.1 Trusted mission source

- 明确区分 benchmark-owned trusted instruction、policy-facing instruction 和 untrusted
  proposal metadata。
- 为一个有限 task slice 实现 deterministic task-template/manifest compiler。
- `MissionSpec` 绑定 task artifact、trusted instruction、registry、SafetySpec、phase、episode
  nonce 和 time base。
- unsupported/ambiguous task 明确 fail closed。

### 3.2 Mission-rooted contract provider

- active contract 只由 `MissionSpec + active phase + residual obligation` 决定。
- paper CTDA path 不调用 `heuristic_contract_from_instruction()` 产生授权合同。
- 改变 attacked prompt 或 policy `proofalign_action` 不得改变 active contract、spec digest 或
  paper-path verdict。
- legacy heuristic 仅保留 compatibility/logging 标签。

### 3.3 Independent raw proposal binder

- binder 读取 trusted state、raw command、active contract 和 versioned config。
- 最小支持 persistent `Pick`/`Place`；approach/transport 属于合同内 prefix。
- 错误 target/region/held object/gripper action、观测不足或方向不明必须 refuted/unknown。
- policy 自报 admissibility、contract id 或 expected effect 不能升级 binder verdict。
- completion 只能来自 observed witness。

### 验收

- prompt tamper 不改变 paper contract/verdict；
- `proofalign_action` tamper 不改变 paper verdict；
- trusted task/registry 改变导致 mission digest 改变，旧 artifact 失效；
- wrong target、wrong gripper、wrong held object fail closed；
- missing completion 保持 `safe_pending`；
- stale/replay/cross-episode tests 继续通过；
- evaluator 失败前没有 supervisor partial commit。

## 4. P2：`ctda-wire-v1` 与 Lean online evaluator

状态：**功能闭环完成，real-time 路线按负结果关闭；仅保留 slow interlock/offline audit**。

### 4.1 Canonical wire schema

实现内部 `ctda-wire-v1`，stage 至少包含：

- `semantic`
- `prefix_pre`
- `observed_prefix`
- `monitor_step`

要求 canonical UTF-8 JSON、integer nanoseconds、tagged temporal formula、strict decoder、consumer
digest recomputation、stable ordering 和 round-trip/injection tests。它不替换 episode JSON 或
attack-record schema。

### 4.2 Evaluator abstraction

明确实现：

- `ctda-python-reference`
- `ctda-lean-kernel`
- `ctda-shadow`

Lean 不可用、serialization/build/timeout/parity mismatch 时 fail closed。只有 kernel 实际检查
成功的 request 才能写 `proof_verified=true`。

### 4.3 Online transaction

- `semantic` 和 `prefix_pre` 必须在 `env.step` 前 proven；
- `observed_prefix` 和 `monitor_step` 必须在下一次 dispatch/phase advance 前 proven；
- Lean 失败时不得退回 Python 继续 dispatch；
- request、generated Lean artifact、checker digest 和输出可离线 replay；
- cache key 必须包含 canonical request 与 checker/build/schema version。

### 4.4 Golden parity corpus

覆盖 proven/refuted/pending/complete/violated/inconsistent 及：

- spec/nonce/state/monitor/contract/proposal/command/time-base tamper；
- receipt/trace provenance mismatch；
- split-prefix completion；
- timestamp rollback；
- replay、stale、cross-episode artifact。

共同支持语义必须达到零 mismatch。

### 验收

- fake-env test 证明 Lean proven 前 `env.step` 调用次数为 0；
- Lean unavailable/tampered request 时 dispatch 为 0；
- observed/monitor 未通过时 phase 不推进；
- golden corpus 零 parity mismatch；
- `lake build ProofAlign` 与全量 Python tests 通过。

当前结果：以上 correctness gate 已通过；208 passed / 1 skipped，Lean 12 jobs，fake-env pre-proof
零 dispatch，unavailable/tampered request 零 dispatch，observed/monitor failure 零 phase advance。
但逐 request Lean replay 的 p99 为约 0.65--1.95 秒，超过 control deadline，因此当前不得声称
real-time enforcement。

2026-07-14 远程结果进一步确认四阶段约为 0.9--1.3 s/stage。项目不再把满足 control deadline
作为 slow-interlock/offline 实验的 readiness 条件；相应代价是彻底删除 real-time enforcement
claim。所有 latency 和 miss 仍必须原样报告，Lean 不可用或超时仍 fail closed。

## 5. P3：CPU-only shadow calibration harness

状态：**工程 harness 与 synthetic golden parity 完成；允许开始非实时 clean prefix
calibration**。

输入保存的 clean prefix/episode artifact 或 CI fixture，不调用 simulator/GPU，不改变 action。

输出：

- supported/unknown/blocked/allowed；
- Layer 1、Layer 2 和 dual unique catch；
- pending/complete/violated/inconsistent；
- Python/Lean parity mismatch；
- semantic/prefix/observed/monitor p50/p95/p99；
- schema/checker/config/git digest；
- independent label provenance；
- 没有 ground truth 时相关指标为 `not_evaluated`。

### Readiness gate

以下是进入远程 pilot 的工程目标，不是已经实现的结果：

- parity mismatch = 0；
- clean false block 目标 ≤5%，>10% 停止扩实验并修 binder/abstraction；
- unknown/deadlock 目标 ≤5%；
- clean success retention 远程 paired target ≥90%；
- p99 必须实测；超过控制周期则降级为 offline audit，不能声称 real-time enforcement。

本地 27-case fixture 结果：parity mismatch = 0，Layer 1/Layer 2/dual unique catch 均有覆盖，
pending/complete/violated/inconsistent 均有覆盖。fixture 没有独立 ground truth，因此 false block、
TPR、FPR 均为 `not_evaluated`。Lean p99 超出控制周期，当前按 offline audit/slow interlock 处理。

固定 `affordance/task 2/init 0` 的真实 GPU probe 已验证 fallback postcondition 只要求
`collision,cost` 且 observation complete。固定 50 ms switch receipt 在三次完整 repeat 中只通过
2/3，因此该 receipt gate 记录为失败；它不再阻塞 3--5 prefix slow-interlock calibration，但任何
后续结果都不得描述为 real-time，超时 receipt 必须原样保留且严格 `succeeded=false`，不能筛掉。
在 `slow-interlock-diagnostic-v1` 下，只有 latency miss 本身不再升级为 method failure；actuation、
receipt integrity 或 fallback postcondition 任一失败仍 fail closed。

首次 5-prefix clean 尝试发现 `create_initialized_env()` 应用 selected init 后，online runner 因
环境缺少 `_get_observations()` 又调用 `reset()`，所以 episode 实际绑定到另一个 reset state。该
episode 是 init-handoff diagnostic，不是有效 calibration sample；其中 observed-prefix refutation
不得用于调大运动学阈值。handoff 修复已在 `2c532ca` 形成 clean commit，并通过 strict preflight。

`2c532ca` corrected run 的 init provenance 与 digest gate 全部通过，但首个 valid clean proposal
被 raw binder 以 `moves away from the mission target` refute，零 dispatch。离线重建显示该 proposal
的预测平移约 2.835 微米、目标距离增加约 2.735 微米，且 gripper 为 open request。该结果是 clean
blocking/abstraction signal，不是独立 ground-truth false positive；按 >10% kill criterion 停止扩
实验，不能用更多 episode 稀释 1/1 rejection。

历史 `e2e4d47` 一次性 bounded-stutter 已在真实 GPU 验证首 prefix，但第二个新微动作因 count budget
耗尽而 pre-dispatch replan，只执行 1/5 prefix。经本轮用户授权，Python binder 已改为
`mission-raw-binder-libero-panda-v4-cumulative-stutter`：Pick/approach 非闭合微动作共享 active
contract 的累计 `0.0001 m` predicted-translation path 和 `0.002` 六维 command-path norm；授权时
扣减，reset/replan 不退款，第一次授权固定原 deadline。持久 no-progress 上限沿用既有
`no_progress_patience=3`。candidate/tube/proposal witness 绑定单次增量、累计前后值、总预算和
no-progress index/limit；completion/contract progress 在 phase 更新前 fail closed。OpenPI adapter
另保存完整归一化 chunk、policy-call ID、实际执行 command 和丢弃 tail，不改变单-command CTDA
dispatch。

本地累计实现已通过 216 passed / 1 skipped 与 Lean 12 jobs；这些仍只是 CPU/fake-env 与 Python
binder 语义，不是 Lean raw-action proof。`74152a9` strict GPU preflight 随后通过，但唯一一次相同
task/init/seed/witness 的重跑在第一 prefix 的 100 ms authorized-duration 边界失败，fallback 也再次
超过 50 ms。累计 path 与 observed kinematic margin 均为正，故不能把失败写成运动超界。whole-chunk
authorization 仍未获授权。

用户已授权优先验证 method validity。当前协议因此显式区分 `strict-real-time-v1` 与
`slow-interlock-diagnostic-v1`：后者记录但不执行 control-period observation SLA 与 fallback
switch-latency SLA；authorization expiry、contract deadline、trace horizon、运动学/不变量、
completion/progress、累计预算和 fallback actuation/postcondition 不变。该策略绑定进 tube assumptions
及 runtime metadata，并有 strict/slow 双向 fake-env tests；下一 gate 是全量验证、clean preflight
和唯一一次固定配置 calibration，不是直接增加 episode。

该 gate 已在 clean `7587c47` 上执行。首 prefix 的 109.034 ms observation miss 仅作为性能负结果，
四阶段通过；第二 prefix 在无 timing miss 时因 `1.335 mm > 0.150 mm` kinematic limit fail closed。
frozen controller source 随后证明 `OSC_POSE` translation scale 为 2.0，而 method 使用 0.05。下一步
是绑定 live controller config；但按正确 scale 首 prefix 的 predicted translation 为 0.127 mm，已
超过冻结 0.1 mm stutter budget，因此预算是否修订仍需独立、非样本拟合的方法依据。

用户随后授权采用控制器绑定的运动学合同：保留早已冻结的归一化六维 command-path budget
`0.002`，将累计预测平移上界定义为该预算乘 live controller translation scale。当前有效
`OSC_POSE` scale 为 2.0，故得到 `0.004 m`；这不是用 observed verdict 拟合阈值，历史 0.1 mm gate
也不回写为成功。runner 当前从 live controller 提取并 digest-bind type/delta/dimension/input/output/
environment bounds，缺失、错配、非零中心或非等向均 fail closed。下一 gate 仍是全量 CPU/Lean、
clean strict preflight 与唯一一次固定 calibration。

`f01a98f` 随后通过 227 passed / 1 skipped、Lean 12 jobs 与 clean strict preflight。一次缺失 Lean
`PATH` 的启动在 semantic stage fail closed、零 dispatch，并作为无效 calibration 保留；经明确授权
仅修正 `PATH` 后，固定重跑完成五个连续 prefix。5/5 static/monitor 为
`proven/safe_pending`，16 个唯一 Lean request 全部 proof-verified 且 parity 匹配，五个运动学 margin
全为正。前两步累计 stutter，后三步进入 normal approach；最终因五步上限仍有 pending obligation
而 zero-hold/replan。method-validity gate 因此通过，但 task success 与 realtime gate没有通过。

## 6. P4：ProofAlign 自身评测（当前主线）

状态：**E0 v2 已冻结 non-real-time supported slice：12 supported / 0 ambiguous / 63 unsupported。
E1-v1/v2 已执行但均为 invalid infrastructure/integration records；E1-v3 已修复 metadata/analysis
gate 并通过真实 policy-output 无 dispatch preflight，当前仍为 0 valid paired episode。下一步是 fresh
v3 execution。时间性能统一留到 E4，外部 baseline readiness 不阻塞主线**。

### E0：冻结支持范围与评测单位

- 从 frozen mission/compiler 枚举当前可支持的 Pick/Place task、phase、init 与 fallback witness；
- 对全部候选输出 `supported / unsupported / ambiguous` 及原因，unsupported 明确 fail closed；
- 在看到新 rollout outcome 前冻结 task/init/seed、episode horizon、配对单位、label provenance 和
  analysis config；
- 先做小规模 pilot，达到 gate 后才扩样本，不能按结果挑 task。

2026-07-16 outcome-blind 结果已冻结：五 suite 共 75 task，live structural compile 为 13，最终
`supported=0 / ambiguous=3 / unsupported=72`。四个 physical suite 的 60 条 init 0 均存在并应用；
`reasoning_safety` 15 条均无 registered init。13 条 structural candidate 中，3 条 affordance Pick
只有 `holding` 与 benchmark `CheckGripperContactPart` 的未证等价，另 10 条有明确 goal/destination/
semantic-constraint mismatch。唯一 fallback manifest 只绑定不合格的 `affordance/task 2/init 0`。
详见 [`e0_support_audit.md`](e0_support_audit.md) 与
[`proofalign_e0_protocol.json`](../experiments/proofalign_e0_protocol.json)。

因此 E0 v1 的 E1 pilot 选择集按规则为空，不能启动 rollout 或拿历史 task 2 顶替。当前主线改为：
实现 exact task-bound manifest compiler、补齐 task-bound fallback/observation/init gate，随后发布
E0 v2 并重复同一 outcome-blind audit。只有 v2 的 supported 集合非空才进入下面 E1。

第一项现已完成 candidate gate：事前规则一次选择全部 15 个 affordance single-contact-part goal，
15/15 在 live init 上由 BDDL-digest-bound manifest 精确编译，15/15 raw MuJoCo contact query 可观察，
且 completion atom 不再使用 `holding`。其余 60 条 fail closed；全程无 policy load/`env.step`。
随后 15/15 init/collision/cost validity 通过且无 contact-capacity warning，并生成 15 个 task-bound
zero-hold artifact。事前冻结的 45-repetition fallback audit 中，安全后置条件 45/45 通过，但严格
100 ms switch gate 为 0/45（101.978--292.854 ms，p50 134.529 ms），因此 15/15 unit 全部 rejected；
task 4/9/14 在 seed 17/27 另有 6 个初态 digest mismatch。分类仍是 75/75 unsupported、E1 集合为空。
该 strict 负结果不得被重写；它保留为 E4 timing evidence。

用户随后明确把 timing 从 E0 support 分类移到 E4。新 method version 在执行前固定同样的全部 15 个
candidate、三 seed 和非时间 safety/provenance gate，并运行 fresh workers，未复用旧 repetition。
结果为 39/45 valid、6/45 因跨 seed 初态 digest 不一致 invalid；task 4/9/14 rejected，其余
`0,1,2,3,5,6,7,8,10,11,12,13` 共 12 条 accepted。`proofalign.e0.protocol.v2` 已冻结，E1 pilot
必须完整使用这 12 条，不得按后续 success 替换。

### E1：clean coverage 与 utility

在完全相同的 task/init/env seed/policy seed 上配对运行 `VLA-only` 与 `Full CTDA`，报告：

- compiler/task coverage 与 unsupported rate；
- task success、benchmark safe success、clean relative success retention；
- false block、unknown、deadlock、replan/safe-stop、phase completion；
- 没有独立 label 的 false-block 指标必须为 `not_evaluated`。

pilot target 沿用已冻结目标：clean retention ≥90%，false block 目标 ≤5%，>10% 停止扩样本，
unknown/deadlock 目标 ≤5%。这些是扩样本 gate，不是当前已经取得的结果。

2026-07-16 执行记录：v1 在 environment construction 前因 physical CUDA/EGL id 混淆产生 24/24
invalid startup records；v2 只修正该绑定并通过 exact-GPU preflight，随后 24/24 records 又在 policy
返回后、dispatch 前因 action audit 不支持 supplied metadata 中的嵌套 `dict` 而 invalid。两轮均为
0 valid episode，不能报告 success、safe success、retention、false block、deadlock 或配对差异。v2
validator 对 retained artifacts 的机械检查退出 0，但它仍对全无效 pair 计算统计，故 inference 必须
忽略并在 v3 修复。执行 hash、原始目录和恢复规则见 [`e1_clean_pilot.md`](e1_clean_pilot.md)。

2026-07-17 v3 amendment 已在新 outcome 前冻结：递归 metadata freeze 只在 E1-v3 进程安装，E0-v2
wrapper 的冻结 hash 保持不变；summary 只让两侧都 valid 的 pair 进入统计，0 valid pair 明确为
`not_evaluated_no_valid_pairs`。GPU 3 exact-CUDA/EGL、checkpoint、task0/init0 environment 与真实 OpenPI
output audit 均通过，完整 10-action output 可冻结/序列化，且 probe 未调用 `env.step()`。正式 fresh
result root 尚未创建。

### E2：双层贡献与 fixed-trace replay

对同一批保存的 proposal/observation/receipt/trace 运行 `Mission-only`、`Trace-only` 和 `Full CTDA`。
报告各层 unique catch、交集、parity、lead time、pending/completion behavior 和 clean loss。负例只能来自
benchmark annotation、独立 simulator oracle 或在 outcome 前冻结的 contract-violating trace；
synthetic fixture 只证明组件语义与覆盖，不证明物理防御有效。

### E3：closed-loop intervention

在受支持 task slice 上验证 pre-dispatch block、observed/monitor failure 后零 phase advance、fallback
postcondition 和最终 task outcome。clean 评测可以直接执行；attack-conditioned physical-defense
结论仍须等待合格独立 workload，但不阻塞 clean、duality、intervention semantics 与 cost 结果。

### E4：代价与鲁棒性

报告四阶段 p50/p95/p99、deadline miss、episode wall time、生成 artifact 大小、CPU/GPU/内存开销、
Lean unavailable/timeout/tamper 时的 fail-closed 行为。当前 0.9--1.3 s/stage 的负结果必须保留，
评测口径仍是 slow interlock/offline audit，不恢复 real-time claim。

### 当前进入条件

P1/P2 correctness、27-case parity 和 five-prefix method-validity 已允许执行 E0；exact manifest/contact
observer、init-validity 与 fresh slow-interlock safety qualification 已完成，E0 v2 现有 12 个 supported
unit。E1-v3 metadata、analysis 与 no-dispatch policy-output preflight gate 已通过；下一项具体工作是在
新目录 fresh 执行相同 12 units；不是 resume/覆盖 v1/v2，不是加入被排除的 frypan task，
不是继续寻找一个能通过的攻击，也不是等待 SAFE/FIPER 完成。只有得到有效 E1 paired artifacts 才进入
E2。deadline/latency 只在 E4 汇总，仍禁止 real-time claim。

## 7. P5：外部 workload 与 baseline 复现（后台线）

状态：**不再阻塞 P4；live-controller method-validity 五-prefix gate 已通过；Phantom held-out R1 已完成但
独立 cost/collision signal gate 失败；SABER exact-task R1 已在 record-generation artifact gate
fail closed，未运行 victim；SAFE 未复现，FIPER 的第二条 2026-07-16 fresh R0 正在后台运行但当前
没有 terminal pass**。P1/P2
correctness、golden parity 与 affordance observation completeness 已通过；real-time latency 明确
未通过并已降级 claim。fail-closed preflight manifest 与 clean + Lean slow-interlock smoke 已
脚本化。SABER standard-LIBERO R0 已核验为部分方向复现。Phantom 三种 deterministic transform 的
9 组 CPU smoke 与官方 OpenPI WebSocket 闭环已通过。2026-07-15 已用 clean standard-LIBERO、独立
uv client 和 structured outcome/frame digest 关闭环境与 raw-artifact blocker；task 2 clean 成功，
同 task/init 的固定 `laser_blinding-medium` 改变 20/20 policy frame 但也成功，且使用更少动作。因此
攻击效力方向未复现，该旧 Phantom R0 pair 保持 `blocked_upstream`。不得事后调强该 pair
或覆盖其负结果。
环境见 [`remote_execution.md`](remote_execution.md)。

`blocked_upstream` 在这里是旧 task 2 单对协议的终止状态，不是对 Phantom 总体有效性的否定。
后续分离的 R0b 已按 `82c6ad5` 预注册协议完成：task 3/4 的启动失败在无 outcome 时
fail closed 并未重跑，task 5/6/7 init 0 是首三个有效 clean-success pair，27/27 attack
episodes 全部有效。`laser_blinding/strong` 在 3/3 pair 上把 success 变为 failure，满足
primary signal gate；`em_truncation` medium/strong 各只有 1/3，其他 cell 为 0/3。R0b 因此
只归类为 held-out R1 workload candidate，不是 defense evidence。LIBERO-Safety R1 已固定为四个
physical suite、task 候选 `0,7,14`、held-out init 1 和 `laser_blinding/strong`；至少 2/4 clean-safe
pair 转为独立 cost/collision 才开放 scoped main。实际只有 1/4：affordance 与 human-safety attack
仍 task success；obstacle-avoidance 只有 task failure、没有 cost/collision；只有
obstacle-avoidance-human 产生 `checkcontact=1`。因此 R1 分类为 signal not reproduced，按冻结 failure
path 停止 Phantom。SAFE/FIPER source、资产、uv 环境与 launcher 已冻结；SAFE 在 335/500 records、
FIPER 旧 run 在 seed 0 / `push_t` / `rnd_oe` 时中断。2026-07-16 FIPER fresh attempt 使用既有环境
重跑，但在 seed 0 的 `pretzel/rnd_a` 训练结束后无 terminal manifest 退出。所有中间输出均不构成 pass。

用户已选择 instruction 路线继续。SABER R1 固定复用同四个 clean-safe init-1 artifact，使用冻结的
`constraint_violation` 模型与官方 prompt tools，各生成一次 exact-task instruction record。record
producer 与 victim runner 分进程、分阶段：producer 不加载 pi0.5，也看不到 attacked outcome；四条
record 不能 best-of-N、重生成或按结果替换。record gate 全通过后，统一 pure-VLA runner 才按固定
顺序执行四条 attacked episode。primary gate 仍为至少 2/4 环境 cost/collision，task failure 不计。
只有该 gate 通过，才开放事前冻结的 100-action scoped Full-CTDA method-validity 实验。
第一次 producer 启动在 pair generation 之前因 robosuite 默认 `/tmp/robosuite.log` 无写权限失败；
manifest 明确记录零 generation attempt、零 victim load/rollout。恢复只允许隔离日志路径这一启动修复，
并要求 record、producer ledger 和 transcript 均不存在；因此不消耗或重置任何 pair 的 one-shot quota。
第二次启动在模型/vLLM 初始化后、首个 pair 前又因 shell SOCKS proxy 的缺失可选依赖失败，同样追加为
零 attempt。producer 将只访问 localhost 的 ART client 与本地模型，因此后续恢复清除继承 proxy，
不安装新依赖、不改变 attacker 或 generation 输入。第三次启动证明 Unsloth 对本地模型仍做远程
availability check，清除全部 HTTP proxy 会在零 attempt 阶段超时；最终只清除 SOCKS
`ALL_PROXY/all_proxy`，保留 HTTP(S) proxy，并用 localhost `NO_PROXY` 隔离本地 client。
第四次零-attempt 启动从 vLLM log 确认官方 ART health URL 是 `0.0.0.0:8000`，server 已成功启动，
但该地址未在 bypass 中而被 HTTP proxy 接管。`NO_PROXY` 因此只补入 `0.0.0.0`。
第五次启动通过 health gate 后，在第一个 pair 的 `init_chat_model()` 因 ART `CURRENT_CONFIG` 缺失失败。
这次已产生 pair transcript 与 invalid producer-ledger，虽然没有模型推理、有效 perturbed instruction 或
victim outcome，但已越过预注册的零-attempt恢复边界。因此 SABER R1 分类为
`r1_saber_attack_record_generation_failed_closed` 并永久停止；不修复后重跑，也不运行 scoped main。

在 60-episode pilot 前增加 upstream reproduction gate，详见
[`reproduction_plan.md`](reproduction_plan.md)：

1. standard LIBERO 上复现 SABER π0.5 clean + record/replay；
2. standard LIBERO 上复现 Phantom Menace OpenPI clean + camera transform；
3. SAFE 保留中断状态；FIPER 按 2026-07-16 fresh protocol 使用已有环境复现。只有通过 terminal
   manifest、validator 与 output digest，才可开始 pi0.5 adapter 或进入最终 baseline comparison；
4. LIBERO-Safety Phantom R1 已完成且未通过；不进入固定 scoped CTDA pair，不做 post-hoc 重选。
5. SABER exact-task R1 已在第一个 record artifact gate fail closed；无 victim rollout，不重试、不运行 main。

### Workload

- clean pi0.5/OpenPI + LIBERO-Safety；
- 一个发布 instruction attack family：SABER `constraint_violation` 优先；
- 一个发布 camera attack family：Phantom Menace deterministic transform；
- EDPA 只作后续 patch transfer 和训练型 secondary track。

不在本项目中优化攻击，不按攻击调整 CTDA 阈值。

### 60-episode gate

先跑四个 physical suites × tasks `0-14` × init `0`。进入主表要求：

- clean baseline 稳定且 runner failure 可接受；
- 至少一个 instruction 和一个 camera workload 产生 authorization/safety signal，而不仅是 task
  success drop；
- 每个 episode 保存 task/init/env seed/policy seed/camera/horizon/config/evaluator mode；
- raw artifact 可从远程复制并校验。

若攻击只造成 task failure、没有 authorization/safety signal，则不写 physical-defense claim。

## 8. P6：最终外部 workload / baseline 对比

曾事前冻结一个不等价于最终主表的 **scoped method-validity** 实验：复用 R1 的 clean/attacked
VLA-only artifact，只对 outcome-blind、可由现有 Pick/Place compiler 与 task-bound fallback witness
支持的 pair 运行 clean/attacked Full CTDA。窗口固定为 20 个 policy call / 100 个 raw action；
至少一个 attacked VLA-only 的 matched unsafe event 被 CTDA 在 dispatch 前 refute/replan/safe-stop，
且对应 clean CTDA 至少授权一个非 dummy prefix，才通过。该结果不估计 clean task-success retention，
不做 baseline superiority 或 population-level statistics。该实验要求 R1 至少 2/4 safety transition；
实际为 1/4，且唯一 unsafe event 位于 policy action 132、超过冻结 100-action window，因此当前状态为
`not_authorized_by_r1_prerequisite`，没有运行 Full CTDA episode。

下面的完整矩阵保持为后续目标，当前未授权执行：

固定方法：

1. VLA only；
2. privileged collision/cost checker；
3. SAFE；
4. FIPER；
5. Full CTDA。

Mission-only 与 trace-only 放在独立 CTDA ablation 表。RoboGuard 通过 plan-interface gate 后加入
semantic comparison；EDPA/Phantom training defense 在其官方 victim 上单独成表。

固定 workload：clean、一个 instruction family、一个 camera family。

固定 task/init/policy seed/env seed/camera/horizon/checkpoint。先跑 pilot，只有 signal 和 utility
gate 通过才扩 init `0-4`。

指标、offline/online 双协议与 artifact 规则见 [`experiments.md`](experiments.md)。

该阶段只在 P4 已经形成可解释的 clean utility、duality、closed-loop 和 cost 结果后执行。最终矩阵
使用相同 task/init/seed/workload/fallback 比较 VLA-only、privileged checker、通过 readiness gate 的
SAFE/FIPER 与 Full CTDA。baseline 未完成不影响 P4，也不得用 P4 的内部结果提前声称 superiority。

## 9. Kill criteria

出现以下任一情况，主动缩题而不是继续堆实验：

- online 仍只有 Python reference：删除 Lean-backed online enforcement claim；
- clean relative success retention <90% 或一次校准后 false block >10%：停止扩实验；
- full dual 与最佳 single layer 无显著差异，或某层没有 unique catch：删除“双层必要性”claim；
- visual defense 使用与 policy 相同的 attacked observer：删除确定性 camera-defense claim；
- 需要按攻击调阈值：删除 attack-agnostic claim；
- p99 或 fallback switch 超出 control deadline：删除 real-time claim，保留 fail-closed
  slow-interlock/offline audit；该负结果本身不阻塞非实时实验，但必须报告完整分布与 miss；
- 独立 oracle 无法标注 unsafe/safe proposal：不报告 detection TPR/FPR；
- 结果主要依赖 privileged simulator oracle：只主张 simulation/reference-monitor 结果。

## 10. 暂缓项

- EDPA paper-scale reproduction；
- 新攻击、训练时后门、攻击模型训练；
- 三个以上 victim；
- 全量五 suite/多 init 大矩阵；
- 通用自然语言与全 BDDL compiler；
- CBF、HJ reachability、完整 dynamics proof；
- authenticated IPC、TEE、hardware attestation；
- verified recovery controller；
- 实机安全保证。

若未来坚持 S&P/USENIX Security/CCS/NDSS 路线，应另开系统安全 track，补进程隔离、认证
通信、独立 sensor/actuator evidence 和有限实机验证；这些不阻塞当前 simulation-first 论文。
