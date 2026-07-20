# 工作机交接 Prompt：CTDA v2 与安全实验重建

更新日期：2026-07-20

> 把下面分隔线之间的整段交给工作机上的下一位 agent。该 prompt 授权其在仓库范围内持续完成设计、
> 实现、验证和满足 gate 后的远端实验；它不授权覆盖旧结果、跳过冻结/preflight、干扰无关 GPU 进程或
> 把 partial artifact 当作结论。

---

你正在工作机 `/home/ldx/lean-vla` 接手 ProofAlign。目标是把 CTDA v1 的有效负结果推进成一个具有
clean liveness、最小干预和独立安全评估的 CTDA v2，并重建可用于防御评估的安全场景/攻击基础。

不要只写计划。先完成设计冻结和 no-rollout 实现；如果工作机环境、协议和全部 gate 允许，继续推进
到新的 clean v2 pilot、VLA-only threat qualification、正式矩阵、artifact validation、canonical
文档和提交。任何负结果都原样保留。

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
- 当前没有可写的 general attack-defense、hardware safety、verified recovery 或 real-time claim。

## 4. 总体工作顺序

两条线可以并行开发，但必须隔离 outcome：

```text
A. CTDA v2 离线设计 -> v2 core -> fixed-trace/shadow -> no-dispatch preflight -> clean v2 pilot
B. SafeLIBERO/AEGIS readiness -> official attack producer -> VLA-only held-out safety qualification

A clean utility gate + B threat gate + exact population overlap
    -> attacked+defended 正式比较
```

在汇合前，禁止让攻击 outcome 参与 CTDA threshold/binder 调整，也禁止让 CTDA verdict 参与攻击 reward
或 safety ground truth。

## 5. M0：先冻结 CTDA v2 设计，不运行 rollout

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

然后在 `docs/method.md` 增加明确标识的 CTDA v2 设计章节，保留 v1 原文和 validity 判定。必须冻结：

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

M0 只允许文档、schema、unit/fake-env design；不得产生正式 task outcome。

## 6. M1：实现 v2 core，保持 v1 可重放

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

## 9. M4：新的 clean CTDA v2 pilot

只有 M0--M3 通过后才创建正式 protocol。要求：

- 新 method id、新 protocol、新 unit/seed 或新 benchmark population、新 fresh absent output root；
- 不重跑 E1 的 policy-seed 1 unit；
- protocol 在 outcome 前固定 task/init/env seed/policy seed、arm order、checkpoint/config/camera/horizon、
  safety channels、utility gate、stop conditions、source/data/model hashes；
- `utility_retention_min`、`safe_success_noninferiority_margin` 和 statistical method 必须有冻结值，不能留空；
- arms 至少包括 VLA-only、CTDA v2；SafeLIBERO 上还包括 AEGIS 和 CTDA v2+filter；
- 先做事前固定的小型 pilot；已进入 episode 后的异常保留 invalid/unknown，不替换 unit；
- terminal 后独立验证 ledger/manifest/episode hashes。

primary 输出：valid pair、task/safe success、phase completion、CAR/cost/RET、四象限、四种 intervention、
修改范数、blocked time、deadlock/recovery、safety-channel coverage、proof/fast-checker/filter latency。

若 clean utility gate 不通过：停止 main，保留负结果；后续修改必须形成新的 CTDA method/protocol，不能在
本轮调阈值重跑。

## 10. M5：独立 VLA-only threat qualification

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
10. 再做 exact population CTDA support audit。

### 10.2 P1 EDPA + SafeLIBERO

保持 EDPA 原始 patch definition，不按 outcome 改 patch/强度/task。task failure 只作 robustness metric；
qualification 仍使用独立 safety transition。

### 10.3 停止规则

- Phantom 已关闭 R0/R0b/R1 不再调参或换 pair；
- attack artifact 未通过 producer gate => `not_evaluated`，不得运行 victim；
- 没有独立 safety harm => 不进入 defense main；
- SABER、EDPA 都未通过 => 收窄/删除 attack-defense claim，不继续按结果搜索攻击。

## 11. M6：正式矩阵

只有以下条件同时成立才执行 attacked+defended：

1. CTDA v2 clean utility gate 通过；
2. 至少一个 workload 完成 terminal VLA-only threat qualification；
3. attack、baseline、AEGIS、CTDA 使用完全相同的 task/init/seed/checkpoint/camera/horizon；
4. attack population 与 CTDA support population 完全重合；
5. independent safety oracle coverage/provenance 完整；
6. protocol 已提交且 worktree clean；
7. selected GPU/EGL/source/hash/output-root preflight ready。

矩阵：VLA-only、AEGIS、CTDA v2、CTDA v2+physical filter，各自运行 clean 和 qualified attacked
workload。SAFE/FIPER 只有 terminal-ready 才追加，且使用相同 fallback。

不得把 task failure、detector alarm、CTDA block 或 attack metadata当作 unsafe ground truth。

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
5. 需要改变 normative v2 方法时先形成新 method version，不后验修改本轮；
6. 提交 terminal artifacts 和 canonical 文档；
7. 报告实际 commit、测试、run root、validator 和仍然存在的 unknown/blocker。

## 13. 完成定义

本交接不是以“代码能 import”或“GPU 进程启动”完成。优先完成到以下可审计状态：

- M0--M3：v2 设计冻结、实现、focused tests/Lean build、fixed-trace/shadow、SafeLIBERO/AEGIS readiness、
  no-dispatch preflight；
- 若 gate 允许，M4：新的 clean v2 terminal pilot 和 method decision；
- 若 producer/环境允许，M5：至少一个 terminal VLA-only threat qualification；
- 只有 M4/M5/overlap 全部通过，才执行 M6；
- 任何停止都必须留下机器可读 terminal/blocker artifact，而不是只在聊天中说明。

最终结论只覆盖指定 simulator、task、model、seed、workload 和 observer assumptions。不得声称绝对安全、
硬件安全、通用攻击防御、verified recovery 或 real-time control。

---
