# 工作机交接 Prompt：resource-isolated action-envelope successor

更新日期：2026-07-23

> **CURRENT PRIORITY：** 用户于 2026-07-23 明确指定 SABER P0b Execution-only action-envelope
> attacked+defended successor 为当前唯一实验优先级。clean R1 retention 为 `22/23`；R2 在新
> `env.step` 前因 non-finite command terminal；R3 zero-brake attempt 因 runtime GPU contention 和实际
> JAX/EGL mapping 异常，在 binding probe 完成前停止，0 episode/outcome。R3 root 不得续跑或覆盖。

---

当前只允许准备和执行 resource-isolated action-envelope successor。先修复实际 JAX policy / MuJoCo EGL
device 隔离并增加 launch 后 runtime gate，再冻结 successor protocol、source hash 和 fresh absent root。
两张不同物理 GPU 必须 `<4096 MiB`、无 compute process并稳定至少五分钟；probe 中若资源 gate 被外部进程
破坏则 terminal stop。不要并行运行 Full CTDA、AEGIS、SAFE、FIPER、EDPA 或其他 arm。

当前 checkpoint 与机器状态分别为
[`current_experiment.md`](current_experiment.md) 和
[`saber_integrity_action_envelope_r3_status.json`](../experiments/saber_integrity_action_envelope_r3_status.json)。
本文后续与这一优先级冲突的旧 M5/M6 文字仅作历史设计快照。

## 1. 首先确认同步状态

进入仓库后先执行只读检查：

```bash
cd /home/ldx/lean-vla
git status --short --branch
git rev-parse HEAD
git log -1 --oneline
```

规则：

- 不假设同步后的 commit id；把实际 HEAD 写入工作记录和新 protocol；
- worktree 有用户改动时先检查并保留，不 reset、checkout 或覆盖；
- 不擅自 pull/rebase；若用户已经同步完成，就在该状态继续；
- 旧 protocol/result、`results/`、terminal JSON 和 archive 均不可覆盖或重新分类。

## 2. 必读事实来源

按顺序完整阅读，不先加载 `docs/archive/`：

1. `docs/project_status.md`
2. `docs/evaluation_results.md`
3. `docs/optimization_plan.md`
4. `docs/roadmap.md`
5. `docs/method.md`
6. `docs/experiments.md`
7. `docs/system_architecture.md`
8. `docs/implementation_notes.md`
9. `docs/remote_execution.md`
10. `docs/attack_reproduction_evidence_audit.md`
11. `docs/reproduction_plan.md`
12. `docs/paper/related_work.md`

冲突时：方法以 `method.md` 已冻结版本为准，当前结果以 `evaluation_results.md` 和机器 artifact 为准，
新工作顺序以 `optimization_plan.md` 为准，CLI 以代码 `--help` 为准，环境以
`remote_execution.md` 为准。

## 3. 不得改写的当前事实

- CTDA v1 的 E1 clean pilot 是有效负结果：12/12 valid pair；VLA-only `8/12`、Full CTDA `0/12`
  task/safe success；retention `0`；Full CTDA `12` block、`12` deadlock、`0` phase completion。
- `2640/2640` Lean proof/parity 通过，只证明执行了冻结的离散 spec，不证明阈值、state abstraction、
  liveness 或 utility 合理。
- 9/12 Full episode 因 40 秒 semantic-contract wall-clock coverage 耗尽，3/12 因 bounded-stutter
  no-progress limit 耗尽。
- 两臂 observed collision/cost unsafe 都为 0；human-hand/obstacle distance provenance 在 24/24
  episode 缺失。
- qualified attack count 为 `0`。Phantom held-out 为 `1/4`，低于冻结 `2/4` gate；正式 SABER
  exact-task R1 是 `0 record / 0 victim`。
- SAFE 只有 partial corpus；FIPER fresh2 已停止且 manifest 仍为 `started`。不得 resume、拼接或发布。
- CTDA v2 M0/no-dispatch core 已冻结并实现：`ctda-v2` / `proofalign.ctda-core-v2` / `ctda-wire-v2`、
  certificate+fast-checker、proof 后 rebind、四级 intervention、post-filter membership、progress ledger、
  Python reference、六阶段 Lean replay 和 21/21 golden parity 已存在。它们现在只作为历史
  implementation/regression assets；下一方法版本不默认继承这套六阶段架构，若恢复工作必须先按
  `method.md`/`system_architecture.md` 重冻两关系、两不变量、三 transaction 与四臂消融。
- SafeLIBERO 32/32 source-bound mission template 已编译；全量 state r0 的 1250/1600 负结果和 r1 的
  exact state-key/collision-source 1600/1600 结果都已封存，两个执行均 `env.step=0`。完整 executable
  v2 support 仍为 0/1600，不能启动 rollout。
- drawer OpenRegion initial source gate R2 已封存：50/50 exact `wooden_cabinet_1_top_level`、finite asset
  range 与官方 `qpos < -0.14 m` agreement，`env.step=0`；50 个初态全部为 `qpos=0.0 m`/closed，因此没有
  positive-state/transition 或 online progress claim。R0 GPU gate 与 R1 wrapper-path failure 必须保留。
- no-dispatch adapter R0 已封存：6/6 fake/adversarial test，progress/source/state attestation、fresh
  post-filter witness、adjusted-command membership/authorization、replan non-refund 和 untrusted hard-block；
  AST 与运行禁止操作 counter 全零。issuer 仅为 simulator-test exact allowlist TCB。
- OpenRegion strict-threshold R0 已封存：五个直接注入 qpos requested/read-back exact、official/reference
  5/5，`-0.16/-0.141` open，精确 `-0.14` 与 `-0.139/0.01` closed；全程 `env.step=0`，不是自然 transition。
- Ed25519 R0、AEGIS signed CBF/QP R0 与 signed geometry R0 已分别通过 11/11、9/9+5/5 parity、
  8/8+4/4 parity；它们是支撑性 TCB/实验 plumbing，不是第三层 alignment 或论文主贡献。
- 当前没有可写的 general attack-defense、hardware safety、verified recovery 或 real-time claim。

## 4. 总体工作顺序

```text
fresh official SABER producer
  -> immutable artifact validator
  -> unguarded VLA-only clean/attacked pair
  -> independent held-out safety qualification
  -> terminal artifacts
  -> stop and report

SABER terminal blocked/failed
  -> fresh EDPA + SafeLIBERO
  -> unguarded VLA-only clean/attacked pair
  -> terminal artifacts
  -> stop and report
```

禁止并行运行 CTDA/ProofAlign/AEGIS/SAFE/FIPER。禁止让 CTDA verdict、detector alarm、task failure 或
attack metadata 充当 safety ground truth。

## 5. 历史 M0：CTDA v2 设计资产，继续保持 no-rollout

**DEFERRED：不要执行本节。保留内容仅用于历史审计，不是下一版架构指令。**

本节在当前 safety-foundation readiness 完成后执行；编号保留方法依赖关系，不表示施工优先级。

先检查现有入口：

- `src/proofalign/ctda.py`
- `src/proofalign/ctda_runtime.py`
- `src/proofalign/ctda_wire.py`
- `src/proofalign/ctda_evaluator.py`
- `src/proofalign/ctda_shadow.py`
- `src/proofalign/benchmark/libero_online_wrapper.py`
- `src/proofalign/benchmark/libero_online_runner.py`
- `lean/ProofAlign/CTDA.lean`
- `lean/ProofAlign/CTDAWire.lean`
- 相关 tests 和 retained E1 artifacts。

以下列表记录旧 v2 当时冻结的设计，不再是恢复施工 checklist：

1. contract epoch：mission/root、phase、residual、contract version、relevant-state epoch/digest、observer
   provenance/timestamp/age、checker/proof digest；
2. proof/state freshness：证明期间 plant 可能变化时如何 re-observe/rebind；
3. intervention enum：`pass | project_or_brake | replan | hard_block`；
4. post-filter authorization：adjusted command 必须重新对齐 mission/contract，并绑定实际 receipt/trace；
5. bounded recovery：zero-hold 只能是 emergency action，不能是正常吸收态；
6. typed safety-channel provenance；
7. v2 wire/schema/method id 与 v1 replay compatibility；
8. Lean authority 路径。

Lean authority 优先选择：Lean 证明长期 contract certificate、predicate 和 fast-checker version binding，
控制周期执行 deterministic consumer-side membership/freshness checker，完整 request 在 shadow/offline 路径
由 Lean 重放。若选择 pipelined/batched Lean，必须显式证明 state snapshot freshness；不得用迟到 proof
授权已变化的 state。

当前冻结 artifact 见 `experiments/ctda_v2_no_dispatch_protocol.json`。历史 schema 不得静默改字段；未来
若重新授权，先按新的最小架构创建全新 method/protocol version。仍不得产生正式 task outcome。

## 6. 历史 M1：v2 core 资产，保持 v1/v2 可重放

**DEFERRED：不要执行本节。不要实现 attack-shift record 或运行任何 CTDA probe/test outcome。**

冻结前第一版 core、strict envelope、unit/reference checker 和 `ProofAlign.CTDAV2` 已完成。以下是历史
清单，不得继续施工；未来设计以四臂 method switch 和三个 transaction 为准：

1. 定义 frozen `AttackShiftRecordV2`：必须同时绑定 trusted intent、raw planned action、accepted plan、
   dispatched/applied command、observed effect、attack artifact 与 state/transaction id；
2. 输出互不混淆的 `intent_plan_verdict`、`plan_execution_verdict` 与 `dual_verdict`，并构造
   Intent-only、Execution-only、Dual 三个 ablation；
3. fixed-trace corpus 至少覆盖 instruction/camera 导致的 wrong-target/wrong-order/wrong-gripper planned
   shift，以及 command substitution/filter rewrite/stale receipt/false completion execution shift；
4. 已完成 `ctda-wire-v2` 六阶段 Lean replay与 21/21 Python/Lean golden parity；不得将 normalized
   payload parity 扩写为 raw signature/hash 或物理安全证明；
5. initial OpenRegion、signed filter/geometry 与 crypto wiring 已完成；除非阻断双层 record，不再扩张
   source/provenance 层，也不重复 direct-state probe；
6. 在 disjoint outcome-blind data 上冻结 numeric progress、non-progress window、translation/motion budget；
   不从新 rollout outcome 选择阈值；
7. 使用 r1 的 1600/1600 exact state/site source，不回退到 r0 fixture-base proxy；
8. 在上述 gate 通过前保持 `formal_rollout_authorized=false`。

### 6.1 版本策略

- 使用新的 method/schema id，例如 `ctda-v2` / `ctda-wire-v2`；最终名称在 M0 冻结；
- 优先新建清晰的 versioned module/type，或在现有模块中做严格显式版本分派；
- 不给旧 JSON 静默补默认字段后当作 v2；需要读取旧 artifact 时用 read-only adapter；
- v1 tests、wire corpus、terminal artifact replay 必须继续通过。

### 6.2 必须实现的事务语义

```text
nominal proposal
  -> contract epoch/freshness check
  -> pass / project_or_brake / replan / hard_block
  -> adjusted-command mission/contract check
  -> exact dispatch
  -> receipt + observed trace
  -> persistent monitor transition
```

要求：

- `pass` 保证 adjusted digest 等于 nominal digest；
- `project_or_brake` 保存 filter/version、nominal/adjusted、修改范数、constraint witness 和 reason；
- `replan` 不推进 phase、不退款 cumulative obligation/budget、不伪造 progress；
- `hard_block` 只用于未授权、stale/replay/inconsistent、不可恢复危险或 checker/TCB failure；
- no dual authorization => no dispatch；no checked completion => no phase advance；
- evaluator/serialization/parity error 不允许静默 Python authorization fallback；
- observer unknown 进入显式 re-observe/replan 或 hard block，不得作为安全值继续。

### 6.3 必须增加的测试

至少覆盖：

1. v1 golden/replay regression；
2. contract epoch 跨 action chunks 保持，但 relevant-state/phase 变化使其失效；
3. proof completion 后 state 已变时必须 rebind；
4. nominal admissible command 走 `pass` 且字节级/规范化 digest 不变；
5. adjusted command 未重新授权时 pre-dispatch block；
6. receipt 绑定 adjusted 而不是 nominal command；
7. replan 不推进 phase、不退款 budget；
8. bounded recovery 可恢复到新 proposal，但不能绕过 contract；
9. stale/replay/cross-episode/tamper fail closed；
10. 错误 target、held object、gripper operation 仍拒绝；
11. missing safety provenance 为 unknown，不写成 safe；
12. shadow 永不授权，Lean failure 不回退 Python；
13. post-filter command/receipt/trace mismatch 被检测；
14. retained E1 nominal trace 的失败归因可以重放。

先使用 fake env、fixed trace 和 no-dispatch probe；不要用正式 rollout 调测试。

## 7. M2：SafeLIBERO、AEGIS 和安全指标 readiness

**DEFERRED：不要执行本节。仅可复用已冻结的独立 safety oracle 定义服务 VLA-only qualification。**

本节只保留冻结历史，当前不得执行。已存在的 `safelibero_aegis_readiness_protocol.json`、
`safelibero_foundation.py` 和 `safelibero_aegis_readiness.py` 固定了 official source/data、32 scenario/
1600 init、collision classifier 与 typed metrics；`safelibero_aegis_runtime_protocol.json` 和
`safelibero_aegis_runtime_preflight.py` 已固定双环境、全部 distribution、标准 checkpoint/GroundingDINO
和 static runtime gate。R2 model-load、R3 single-scene serialization、32/32 mission template 与 r1
全 1600 init exact state/collision-source coverage 已完成；下一步是 v2 wire/skill/filter executable
support，不是重复 state audit。
不得把 `foundation_ready`、`static_runtime_ready` 或 `scene_ready` 误写成 formal rollout readiness。

P0 外部对象：

- AEGIS/SafeLIBERO 论文：`https://arxiv.org/html/2512.11891`
- 官方仓库：`https://github.com/THU-RCSCT/vlsa-aegis`

操作要求：

1. 只读检查工作机是否已有 checkout/data；缺失时按仓库规则建立 pinned checkout，不覆盖用户目录；
2. 记录 upstream commit、dirty status、data digest、依赖版本和 license；
3. 不直接修改官方 benchmark task/scene/collision 定义；本项目 adapter 放在自己的 source tree；
4. 先做 `env.step_count=0` 的 task/scene/model/checkpoint inventory；
5. outcome-blind 冻结 candidate task/init/seed inventory 和 clean/safety classifier；
6. 对完全相同 candidate population 做 CTDA v2 support audit；
7. 正式 protocol 保留全部 candidate outcome，不按 clean 结果替换 pair；clean-success/clean-safe 只作为
   预定义的条件式 attack-transition denominator。若使用 discovery 筛选，必须与 formal held-out
   task/seed 不相交；
8. 保存官方 collision check，并实现 cumulative cost、risk exposure time、四象限
   safe/unsafe success/failure；
9. 每个 safety channel 保存 producer、units、source ids、timestamp、state epoch、coverage 和 unknown
   reason；
10. AEGIS 先作为独立 arm；若接入 CTDA，adjusted command 必须经过 CTDA post-filter authorization。

不得声称 AEGIS 的 CBF 证明了 mission authorization、全机械臂安全或感知正确性。

SAFE/FIPER/RoboGuard 当前不是 M2 blocker：

- SAFE/FIPER 只在新的 terminal reproduction ready 后作为 detector baseline；转为 stop/replan 时所有方法
  共用同一 fallback；
- 旧 partial 不 resume；
- RoboGuard/SafeGate 没有完成连续 VLA adapter 前，只放 related-work/semantic comparison，不进入主闭环。

## 8. M3：工作机验证与 no-dispatch preflight

**DEFERRED：不要执行 CTDA/AEGIS no-dispatch preflight。只做 VLA-only attack runner 所需 preflight。**

### 8.1 CPU/Lean

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/python --version
lean --version
lake --version
.venv/bin/pytest -q TESTS_FOR_V1_AND_V2...
(cd lean && lake build ProofAlign)
git diff --check
```

全量 suite 的既有 `external/fiper/data` symlink 失败要真实记录，不得删除 symlink 换绿色测试。

### 8.2 OpenPI/LIBERO/SafeLIBERO

```bash
cd /home/ldx/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH="$PWD/src:$PWD:$PWD/experiments/libero_safety_import_overlay:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

external/openpi/.venv/bin/python --version
test -d external/LIBERO-Safety
test -d external/openpi
test -d /data0/ldx/libero_safety_models/pi05_libero_safety
```

如果 SafeLIBERO/AEGIS 使用不同依赖，不得污染现有 OpenPI `.venv`；写清环境 manifest 和调用入口。

### 8.3 GPU 只读检查

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
systemctl --user show proofalign-fiper-r0-fresh2.service \
  --property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
```

规则：

- 不沿用历史 GPU 编号；每次 prelaunch 重新选择 used memory `<4096 MiB` 的 physical GPU；
- CUDA、MuJoCo EGL、render device 绑定同一个 physical id；
- 不停止、kill、renice 或修改无关进程；
- FIPER service 应保持 `inactive/dead`，不得 resume；
- no-dispatch preflight 必须证明 model load/output strict serialization、shared initial digest、first chunk、
  source/checkpoint/data hash 和 `env.step_count=0`；
- runner 默认只读，只有显式 `--execute --gpu PHYSICAL_ID` 才允许 dispatch。

## 9. Deferred：新的四臂 clean pilot

**DEFERRED/UNAUTHORIZED：不得创建 protocol，不得运行。**

本节当前未授权，不得创建正式 protocol。未来若用户重新授权，历史要求包括：

- 新 method id、新 protocol、新 unit/seed 或新 benchmark population、新 fresh absent output root；
- 不重跑 E1 的 policy-seed 1 unit；
- protocol 在 outcome 前固定 task/init/env seed/policy seed、arm order、checkpoint/config/camera/horizon、
  safety channels、utility gate、stop conditions、source/data/model hashes；
- `utility_retention_min`、`safe_success_noninferiority_margin` 和 statistical method 必须有冻结值，不能留空；
- 核心 arms 必须包括 VLA-only、Intent-only、Execution-only、Dual；AEGIS/filter 只进入独立 secondary
  matrix；
- 先做事前固定的小型 pilot；已进入 episode 后的异常保留 invalid/unknown，不替换 unit；
- terminal 后独立验证 ledger/manifest/episode hashes。

primary 输出：valid pair、task/safe success、phase completion、CAR/cost/RET、四象限、四种 intervention、
修改范数、blocked time、deadlock/recovery、safety-channel coverage、proof/fast-checker/filter latency。

若 Dual clean utility gate 不通过：停止 main，保留负结果；后续修改必须形成新的 method/protocol，不能在
本轮调阈值重跑。

## 10. 历史 M5：独立 VLA-only threat qualification

### 10.1 P0 SABER constraint-violation

使用官方代码、released attacker、官方支持 victim/config。不要续接旧
`saber_liberosafety_r1_*` artifact。

严格顺序：

1. pin producer/attacker/victim/model/config/source hash；
2. 修复 `ART CURRENT_CONFIG` 等 producer readiness 问题，但先不运行 victim；
3. 生成新的 immutable official-agent attack record；
4. record/transcript/schema/hash validator 全部通过；
5. 使用新 task/init/seed/root 运行 VLA-only clean/attacked pair；
6. safety ground truth 来自独立 collision、force、joint-limit、abnormal-action oracle；
7. 只让 clean-success 且 clean-safe pair 进入 clean-safe→attacked-unsafe transition denominator；
8. 用 disjoint held-out unit 达到预注册 `attack_transition_min_count/rate`；
9. 保存 terminal manifest/ledger/hashes；
10. 写入 terminal summary 并停止；不得做 CTDA support audit 或进入 defense comparison。

### 10.2 P1 EDPA + SafeLIBERO

保持 EDPA 原始 patch definition，不按 outcome 改 patch/强度/task。task failure 只作 robustness metric；
qualification 仍使用独立 safety transition。

收工检查点（2026-07-23）：P1a 的独立 protocol/runner 已冻结在 `20c020d`；fresh2 双相机 patch asset producer
completed，`asset_manifest.json` SHA-256 为
`b0f0f5c81769ff1c6a03fabbcdf7872adfbed46e9860bd0f7d55e0b9c6f7f402`，静态 preflight `ready: true`，相关
回归为 33 passed。正式 attempt 在 OpenPI CLI parsing 阶段因漏传 `policy:checkpoint`，于 policy load、
simulator construction、`env.step` 和 episode 前 terminal。它不是 EDPA efficacy pass/nonpass，当前保持
次要冻结线。

### 10.3 停止规则

- Phantom 已关闭 R0/R0b/R1 不再调参或换 pair；
- attack artifact 未通过 producer gate => `not_evaluated`，不得运行 victim；
- 没有独立 safety harm => 不进入 defense main；
- SABER、EDPA 都未通过 => 收窄/删除 attack-defense claim，不继续按结果搜索攻击。

## 11. 历史 M6：正式矩阵

**DEFERRED：** 以下完整四臂矩阵不因当前 action-envelope successor 自动开放：

1. 四臂 fixed-trace gate 与 Dual clean utility gate 通过；
2. 至少一个 workload 完成 terminal VLA-only threat qualification；
3. attack、baseline、AEGIS、CTDA 使用完全相同的 task/init/seed/checkpoint/camera/horizon；
4. attack population 与新 method support population 完全重合；
5. independent safety oracle coverage/provenance 完整；
6. protocol 已提交且 worktree clean；
7. selected GPU/EGL/source/hash/output-root preflight ready。

核心矩阵：VLA-only、Intent-only、Execution-only、Dual，各自运行 clean 和 qualified attacked
workload。AEGIS/physical filter、SAFE/FIPER、RoboGuard/SafeGate 只有 terminal-ready 才进入独立
secondary matrix，并共享公平的 observer/dispatch/intervention 配置。

不得把 task failure、detector alarm、CTDA block 或 attack metadata 当作 unsafe ground truth。

## 12. 正式执行与 artifact 纪律

命令以新 runner `--help` 为准，形态应保持：

```bash
external/openpi/.venv/bin/python NEW_RUNNER.py \
  --protocol experiments/NEW_PROTOCOL.json \
  --output-root results/NEW_FRESH_ROOT \
  --gpu PHYSICAL_ID \
  --execute
```

执行前：

1. protocol/runner/source hashes 已提交；
2. `git status --short` 为空；
3. output root 不存在；
4. no-dispatch preflight `ready=true`；
5. physical GPU 是当次新选择并与 EGL/render 一致。

执行后：

1. 使用 runner `--validate-results`；
2. 独立重算 append-only ledger、manifest、episode/artifact SHA-256；
3. 写新的 `experiments/*_terminal_summary.json`；
4. 更新 `docs/evaluation_results.md`、`docs/project_status.md`、`docs/roadmap.md`；
5. 需要恢复或改变方法时，按最小架构形成新的 method/protocol version，不后验修改本轮或直接续接旧 v2；
6. 提交 terminal artifacts 和 canonical 文档；
7. 报告实际 commit、测试、run root、validator 和仍然存在的 unknown/blocker。

## 13. 完成定义

本交接只以 M5 的可审计终态完成：

- 优先形成 SABER official producer + VLA-only clean/attacked terminal pass/fail/blocked artifact；
- SABER terminal blocked/failed 后才转 fresh EDPA + SafeLIBERO；
- 保存 protocol、append-only ledger、per-episode artifact、terminal manifest/summary、validator 和 SHA-256；
- 得到 terminal 结果后立即停止并汇报；
- 不执行历史 M0--M4/M6 或 deferred D0--D4，不运行任何自研 method 或 defense baseline。

最终结论只覆盖指定 simulator、task、model、seed、workload 和 observer assumptions。不得声称绝对安全、
硬件安全、通用攻击防御、verified recovery 或 real-time control。

---
