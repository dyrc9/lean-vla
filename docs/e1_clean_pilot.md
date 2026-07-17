# E1 clean paired pilot 交接记录

更新日期：2026-07-16 18:25 CST

本文是 E1 当前唯一执行交接页。E0 支持范围仍以
[`proofalign_e0_protocol_v2.json`](../experiments/proofalign_e0_protocol_v2.json) 为准；E1 指标与
claim boundary 仍以 [`experiments.md`](experiments.md) 为准。本页只记录已经发生的执行、不可覆盖的
artifact、失败边界和下一次接手顺序。

## 1. 收尾状态

- E0 v2 已冻结 `12 supported / 0 ambiguous / 63 unsupported`。E1 只能使用 affordance task
  `0,1,2,3,5,6,7,8,10,11,12,13`，统一 init 0、env seed 7、policy seed 0。
- E1-v1 已终止，24/24 ledger entry 都是环境创建前的共同启动失败，0 policy call、0 `env.step()`、
  0 task outcome；它不是 E1 utility/effectiveness 结果。
- E1-v2 已于 2026-07-16 18:25 CST 形成 terminal artifact set，24/24 预注册 episode 均有 ledger
  entry，但 0/24 valid。全部在 policy 返回后、dispatch 前的 action/metadata audit 处以
  `LiberoOnlineIntegrationError: authorized action contains unsupported value: dict` 失败；没有 episode
  JSON 或可用 task/safe-success outcome。
- 因此 **E1 仍未取得一个有效 paired result，E2 不得开始**。v1/v2 目录都不得 resume、覆盖、删行或
  作为零成功率结果使用。
- E1 不纳入 latency、deadline 或资源分类；这些仍留到 E4。GPU 1 的 FIPER 后台线未被 E1 使用。

## 2. 冻结实现与协议

| 对象 | SHA-256 | 作用 |
|---|---|---|
| `experiments/proofalign_e0_protocol_v2.json` | `952996e5edae8482153a59f5388943ff0051f87572295dd735c0decf1f909b67` | E0 12-unit selection freeze |
| `experiments/proofalign_e1_clean_pilot_protocol.json` | `17a9580897bb9a6aa26f4c497e4ac8b9990ab14cdcbf5cbf0bdd3dbd8e12fd38` | E1-v1 base protocol |
| `scripts/run_proofalign_e1_paired.py` | `547dbfa099a939e3eb0f6f19eb477b67b8498b6e66e8f6269c89e11874b1c2e9` | v1 orchestrator and shared execution logic |
| `experiments/proofalign_e1_v1_startup_failure_summary.json` | `32b663298ff44a3016479a8931fd21169df7d1bc927f6feeeed54f0456c15807` | immutable v1 failure summary |
| `experiments/proofalign_e1_clean_pilot_protocol_v2.json` | `7158f18f8d73824c9d0c0adc135de9d48ddc2204f577a2079b4a9f1c3e4e4a2c` | physical EGL-only v2 amendment |
| `scripts/run_proofalign_e1_paired_v2.py` | `69ff7162206f09f527ff14161fe3d1d5a67f844338e2e4882f124abbc758aab6` | v2 launcher |

`src/proofalign/benchmark/libero_e1_runner.py` 提供真正 unguarded、observational 的 VLA-only 路径；
legacy checker 被关闭。Full CTDA 复用 frozen task manifest、Lean slow-interlock evaluator 和逐 task
fallback。每个 pair 固定先 VLA-only、后 Full CTDA，共 12 pair/24 episode；ledger 为 append-only，
entry 后的异常保守标为 invalid/unknown。直接 simulator collision/cost coverage、task success、safe
success、phase completion、unknown/deadlock 和 intervention 均须来自有效 episode；closed-loop
false block 没有独立 counterfactual label 时固定为 `not_evaluated`。

## 3. E1-v1：环境创建前失败

运行根目录为 `results/proofalign_e1_clean_pilot_20260716`，systemd unit 为
`proofalign-e1-clean-pilot.service`，invocation ID 为
`301c0f25978f4f53b0585aa0622fbc4b`。launcher 设置了物理 `CUDA_VISIBLE_DEVICES=3`，却把
`MUJOCO_EGL_DEVICE_ID` 设置为 JAX 进程内逻辑 id `0`；vendored robosuite 在 import 阶段要求 EGL id
属于 CUDA 的物理 id 列表，因而在 environment、policy 和 rollout 之前失败。

原始 artifact SHA-256：

| 文件 | SHA-256 |
|---|---|
| `run_manifest.json` | `f01a1b23edfb2589005c5279bb25381ade7265ab9b03b77b4c14b00c61d3bd3f` |
| `episodes_ledger.jsonl` | `24a491a718cdd83b1ebedbf1ebc613f96d8e656f1764bb6481d0023555e40fac` |
| `summary.json` | `e589ddb3a74a04674f1386c2de1b07c50e273c11bc44cf1f4d9a2f3a0e300de4` |

生成的全零 summary 只是 24 个 invalid startup records 的机械汇总，不得解释为 VLA-only 或 CTDA 的
成功率、安全性、deadlock 或配对差异。

## 4. E1-v2：GPU 启动修复后仍在 episode audit 失败

v2 保持 task、seed、pair order、policy、600-step horizon、CTDA、fallback、label 和 analysis 不变，
只把物理 GPU 3 同时绑定到 `CUDA_VISIBLE_DEVICES`、MuJoCo EGL 和 render device；JAX 在进程内仍看到
逻辑 GPU 0。exact selected-GPU robosuite import、15-task registry、checkpoint/model load 和一次不调用
policy/`env.step()` 的 task0/init0 environment-construction probe 均通过。

执行使用 unit `proofalign-e1-clean-pilot-v2.service`、invocation
`82ef857fef4c46fe9608c35592510a8d`、GPU 3 和独立根目录
`results/proofalign_e1_clean_pilot_v2_20260716`。manifest 记录 18:23:13--18:25:24 CST 完成。最终
artifact SHA-256：

| 文件 | SHA-256 |
|---|---|
| `run_manifest.json` | `13ba8f0b727c24e79364384640f693c593e4d1a99e97592a85e523e595aed116` |
| `episodes_ledger.jsonl` | `09faa470a3e72b1ed25bf5f8aded53d3b8747bf3219525683a30a6c39a0056f5` |
| `summary.json` | `e589ddb3a74a04674f1386c2de1b07c50e273c11bc44cf1f4d9a2f3a0e300de4` |

24/24 records 都在 `_policy_action_audit -> _frozen_action_copy` 遇到 OpenPI supplied metadata 中的嵌套
`dict` 后失败；traceback 位于 dispatch 前，episode JSON 未生成。VLA-only 和 Full CTDA 各 12 条均为
invalid/unknown，不能比较 task success、safe success、retention、false block 或 deadlock。

read-only validator 返回 0，说明 manifest/ledger 的结构、数量和 hash 可复核；但当前 summary/validator
仍把 12 个全无效 pair 当作 complete pair 并计算 `[0,0]` bootstrap interval、McNemar `p=1.0`。这些
统计在 `valid_episodes=0` 时没有估计意义，**必须忽略**。下一版本还必须修正这一 analysis gate，不能
只修 metadata 后直接沿用当前推断逻辑。

## 5. 本轮验证

- E1 focused tests：`8 passed`。
- 全量 Python：`320 passed, 1 skipped, 1 failed`；唯一失败是已知且与 E1 无关的 baseline reproduction
  preflight，因为后台 FIPER checkout 中用户创建的 `external/fiper/data` symlink 使
  `source_ready=false`。不要为通过测试而修改或删除该后台资产。
- Lean：`lake build ProofAlign` 12 jobs 通过。
- `git diff --check` 通过。
- v2 terminal artifacts 的 read-only `--validate-results` 命令退出 0，但只证明 retained artifact
  可解析；不证明 episode 有效，亦不认可它生成的全无效统计。

当前代码、协议和文档均未提交。工作树中还有本轮 E0/E1 的修改与新文件；它们都应保留，下一次先
审计 diff，再决定提交边界。

## 6. 下一次接手顺序

1. 不重启 v1/v2，不覆盖两个结果目录；先校验上面的 SHA 和 24 行 ledger。
2. 为 OpenPI 实际 supplied metadata 的嵌套 JSON tree 增加精确 fixture，修复
   `_frozen_action_copy` 的深层复制/冻结与序列化，同时保持拒绝不支持对象和非有限数值。
3. 修复 summary/validator：只有 pair 两侧均有 valid episode 才能进入 paired rows 和统计；存在 0 个
   valid pair 时 inference 必须明确为 `not_evaluated`，artifact-set terminal 不能冒充实验有效。
4. 增加 policy-output-to-audit 的无 `env.step()` preflight/test，覆盖本轮真实 metadata shape；运行
   focused tests、全量 Python、Lean 和 `git diff --check`。
5. 若修复通过，发布新的 E1-v3 amendment 和 fresh result root；继承相同 12 units/seed/order/labels，
   明确绑定 v1/v2 失败 artifact，不 resume、拼接或替换旧记录。
6. 只有 E1-v3 获得有效配对 episode 并完成 retained-result validation 后，才汇总 E1 并进入 E2。

只读复核命令：

```bash
sha256sum \
  results/proofalign_e1_clean_pilot_v2_20260716/{run_manifest.json,episodes_ledger.jsonl,summary.json}
wc -l results/proofalign_e1_clean_pilot_v2_20260716/episodes_ledger.jsonl
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/proofalign-e1-v2-mpl \
  PYTHONPATH=src:. external/openpi/.venv/bin/python \
  scripts/run_proofalign_e1_paired_v2.py --validate-results
```

最后一条命令当前预期显示 24 recorded、0 valid、24 invalid；其中 inference 字段按本节说明忽略。

## 7. E1-v3：修复与 fresh preflight

v3 在 2026-07-17、任何新 episode outcome 可见前冻结。它保持同一 12 units、init/env/policy seed、
VLA-only/Full CTDA order、victim、600-step horizon、fallback 和 CTDA semantics，只做三项修复：

1. 新增 E1-only `libero_e1_policy_audit`，递归冻结 JSON-like metadata，并在 dispatch 前拒绝 cycle、
   非字符串 key、过深结构、不支持对象和非有限数；通用 online wrapper 恢复 E0-v2 的原始冻结 hash。
2. summary 只让两侧均 `valid=true` 的 pair 进入 paired rows 与 inference；0 valid pair 明确输出
   `terminal_invalid` / `not_evaluated_no_valid_pairs`。
3. fresh root 创建前增加真实 OpenPI output audit probe：构造 task0/init0、调用一次 policy、审计完整
   action chunk 与 metadata，但不调用 `env.step()`。

CPU gate 为 E1 focused `14 passed`、online wrapper `31 passed`；Lean 12 jobs 和 `git diff --check` 通过。
GPU 3 fresh preflight 为 `ready=true`：physical CUDA/EGL 均为 3，15-task registry 与 checkpoint 通过，
policy call `openpi:000000` 返回并审计 10 actions，metadata SHA-256 为
`f339032e9190e40443a8273ecdcfc8c029c46954f5365bf1bef5d334108bd0bb`，`env_step_called=false`。
协议为 `experiments/proofalign_e1_clean_pilot_protocol_v3.json`，计划 fresh root 为
`results/proofalign_e1_clean_pilot_v3_20260717`。本节记录时该 root 尚未创建、仍无有效 E1 outcome。

## 8. 后台运行与会话边界

E1-v2 的 artifact manifest 已 terminal，不需要继续占用 GPU 3。FIPER fresh2 仍属于独立后台线：
`proofalign-fiper-r0-fresh2.service`、GPU 1、目录
`/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-fresh2-20260716-133000`。其 terminal gate 未通过前仍是
`not_reproduced`，不得与旧 partial run 拼接，也不阻塞 E1 修复。user systemd 可跨单个 SSH 断开，
但机器此前为 `Linger=no`；若该用户的全部登录会话都退出，只有管理员开启 linger 才能绝对保证服务
继续存活。
