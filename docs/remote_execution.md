# Remote / GPU Execution Runbook

更新日期：2026-07-10

本文是远程环境、迁移和 GPU 运行的唯一 canonical 说明。旧 benchmark handoff、OpenVLA mock
批次、legacy commands 和 SABER run notes 已归档。

当前本地环境没有 GPU。迁移前必须先完成 [`roadmap.md`](roadmap.md) 的 CPU/Lean readiness
gate。

## 1. 重要边界

- 当前主 victim/backend：`pi05_libero_safety` + OpenPI `pi05_libero`。
- OpenVLA/OFT 仅保留为历史 diagnostic，不进入当前主表。
- 纯攻击 runner 与 defense runner 分开；攻击结果不自动等于防御效果。
- 旧机器路径和 GPU id 是 known-good example，不是新机器硬要求。
- CLI 以当前代码和 `--help` 为准。
- `external/`、`results/` 和 `/data0/ldx` 内容不会随 Git 自动迁移。

## 2. 旧远程机器 known-good layout

```text
/home/ldx/lean-vla                         # source workspace
/home/ldx/lean-vla/external/LIBERO-Safety # benchmark checkout
/home/ldx/lean-vla/external/openpi        # OpenPI checkout
/home/ldx/lean-vla/external/SABER         # attack checkout

/data0/ldx/libero_safety_models/pi05_libero_safety
/data0/ldx/libero_safety_assets/assets
/data0/ldx/huggingface
/data0/ldx/uv-cache
/data0/ldx/pip-cache
```

大模型、数据、weights 和 cache 放 `/data0/ldx`；源码、patch、配置和小型 JSON artifact 留在
workspace。不要在 `/data0/ldx` 新建代码工作区。

LIBERO-Safety upstream assets 仍需让 `libero/libero/assets` 和 `~/.libero/config.yaml` 指向正确
checkout/assets。

## 3. Git 不会带走的内容

迁移代码前单独盘点：

- `external/openpi`
- `external/LIBERO-Safety`
- `external/SABER`
- `results/`
- attack-record JSON/JSONL
- `/data0/ldx/libero_safety_models/pi05_libero_safety`
- LIBERO assets
- Hugging Face/OpenPI/SABER caches（按需迁移，可重新下载时不必复制）

在源机器记录：

```bash
git rev-parse HEAD
git status --short
git -C external/openpi rev-parse HEAD
git -C external/LIBERO-Safety rev-parse HEAD
git -C external/SABER rev-parse HEAD
```

还应记录但目前旧文档没有完整保存：

- OpenPI、SABER、实际运行 LIBERO-Safety exact commit；
- checkpoint 与 asset manifest/checksum；
- GPU 型号/显存、driver、CUDA、JAX、torch、vLLM 版本；
- raw result/attack-record file checksum。

不要在文档中写 SSH 密钥、token、账号密码或私有 host secret。

## 4. 基础环境

旧机器使用：

```bash
cd /home/ldx/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV
```

`scripts/env_vla.sh` 是默认环境值的代码来源：

```text
PROOFALIGN_UV=/home/ldx/.conda/envs/proofalign-libero/bin/uv
HF_HOME=/data0/ldx/huggingface
HUGGINGFACE_HUB_CACHE=/data0/ldx/huggingface/hub
TRANSFORMERS_CACHE=/data0/ldx/huggingface/transformers
HF_ENDPOINT=https://hf-mirror.com
UV_CACHE_DIR=/data0/ldx/uv-cache
PIP_CACHE_DIR=/data0/ldx/pip-cache
```

主 OpenPI 后端必须使用 OpenPI 自己的 uv project：

```bash
export LIBERO_SAFETY_ROOT="$PWD/external/LIBERO-Safety"
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

"$PROOFALIGN_UV" --project external/openpi run python ...
```

不要把旧文档中的裸 `conda run -n proofalign-libero python ...` 当 canonical；已完成的 GPU run
曾因该环境缺 `imageio` 失败，成功入口是上述 OpenPI uv project。

Lean 在旧机器上的 known-good 路径：

```bash
PATH=/home/ldx/.local/lean-4.24.0/bin:$PATH lean --version
(cd lean && PATH=/home/ldx/.local/lean-4.24.0/bin:$PATH lake build ProofAlign)
```

## 5. GPU / EGL 映射

旧机器 known-good：

```text
VLA GPU: physical 4
MuJoCo EGL GPU: physical 5
CUDA_VISIBLE_DEVICES=4,5
MUJOCO_EGL_DEVICE_ID=5
--render-gpu-device-id 5
```

robosuite/MuJoCo EGL 使用 physical GPU id，不是 visible-relative index `1`。新机器先运行
`nvidia-smi`，再设置：

```bash
export VLA_GPU=4
export EGL_GPU=5
```

不要盲抄 4/5。先做单 episode smoke，确认 JAX policy 位于目标 GPU、EGL render 可启动且没有
占用其他用户进程。

## 6. 远程迁移后 preflight

推荐入口是标准库脚本 `scripts/remote_gpu_preflight.py`。它检查并记录：

- ProofAlign、OpenPI 和 LIBERO-Safety checkout 的 commit/dirty state；
- checkpoint、LIBERO config、uv、Lean/Lake 和关键源码是否存在；
- `nvidia-smi` 的 physical GPU inventory，以及 VLA/EGL id 是否确实存在；
- Python/uv/Lake/driver 版本、关键文件 SHA-256；
- 可选的全量 pytest 与 Lean build 结果。

它总会写 JSON manifest；任一硬条件缺失时非零退出。只有 GPU 检查和 CPU/Lean verification
都实际完成时，manifest 的 `ready` 才可能为 `true`。不要用 `--skip-gpu` 生成的本地 dry-run
manifest 启动实验。

```bash
export VLA_GPU=4
export EGL_GPU=5

python3 scripts/remote_gpu_preflight.py \
  --workspace "$PWD" \
  --openpi-root "$PWD/external/openpi" \
  --libero-safety-root "$PWD/external/LIBERO-Safety" \
  --checkpoint-dir /data0/ldx/libero_safety_models/pi05_libero_safety \
  --uv "$PROOFALIGN_UV" \
  --vla-gpu "$VLA_GPU" \
  --egl-gpu "$EGL_GPU" \
  --run-verification \
  --output results/remote_preflight.json
```

不要对正式实验传 `--allow-dirty`。该选项只用于诊断已有机器，不能满足可复现实验 gate。

```bash
cd /path/to/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV

"$PROOFALIGN_UV" run pytest
(cd lean && lake build ProofAlign)
git diff --check
```

然后检查：

```bash
test -d external/openpi
test -d external/LIBERO-Safety
test -d /data0/ldx/libero_safety_models/pi05_libero_safety
"$PROOFALIGN_UV" --project external/openpi run python scripts/run_liberosafety_pi05_openpi_eval.py --help
"$PROOFALIGN_UV" --project external/openpi run python scripts/run_libero_online_batch.py --help
```

任何 full run 之前必须先跑一个 task/init/policy-seed smoke，并检查 output 中的 checkpoint、camera、
seed、evaluator mode 和 environment metadata。

完成外部 checkout、模型和 task-bound fallback witness 准备后，可用统一 smoke 入口：

```bash
export WORKSPACE="$PWD"
export OPENPI_ROOT="$PWD/external/openpi"
export LIBERO_SAFETY_ROOT="$PWD/external/LIBERO-Safety"
export CHECKPOINT_DIR=/data0/ldx/libero_safety_models/pi05_libero_safety
export VLA_GPU=4
export EGL_GPU=5
export CTDA_FALLBACK_WITNESS=/path/to/live-task-bound-fallback-v2.json
export CTDA_FALLBACK_WITNESS_SHA256="$(sha256sum "$CTDA_FALLBACK_WITNESS" | awk '{print $1}')"

scripts/run_remote_gpu_smoke.sh
```

默认只跑 `affordance/task 2/init 0`，先做 30 steps clean 环境/GPU smoke，再做 30 steps
`ctda-lean-kernel` slow-interlock smoke，并在 `results/remote_gpu_smoke/` 保存 preflight、raw output、
Lean replay artifact 和 `SHA256SUMS`。可以显式设置 `SMOKE_MODE=clean` 只检查 victim 环境；正式
CTDA smoke 不接受没有 live BDDL/SafetySpec/action-bound 绑定的旧 fallback witness。

## 7. pi0.5 / LIBERO-Safety clean runner

当前纯 victim runner：`scripts/run_liberosafety_pi05_openpi_eval.py`。

旧 protocol：

- checkpoint：`/data0/ldx/libero_safety_models/pi05_libero_safety`
- OpenPI config：`pi05_libero`
- suites：`affordance,obstacle_avoidance,human_safety,obstacle_avoidance_human`
- tasks：`0-14`
- init pilot：`0`；通过后扩 `0-4`
- max steps：`600`
- environment render：256；OpenPI resize：224
- policy seed 与 env seed 分开；默认 policy seed 0

60-episode clean pilot：

```bash
cd /path/to/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV
export LIBERO_SAFETY_ROOT="$PWD/external/LIBERO-Safety"
export PYTHONPATH="$PWD:$PWD/src:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"
export VLA_GPU=4
export EGL_GPU=5

CUDA_VISIBLE_DEVICES="$VLA_GPU,$EGL_GPU" \
MUJOCO_EGL_DEVICE_ID="$EGL_GPU" \
"$PROOFALIGN_UV" --project external/openpi run python \
  scripts/run_liberosafety_pi05_openpi_eval.py \
  --checkpoint-dir /data0/ldx/libero_safety_models/pi05_libero_safety \
  --openpi-config pi05_libero \
  --suites affordance,obstacle_avoidance,human_safety,obstacle_avoidance_human \
  --task-ids 0-14 \
  --init-state-ids 0 \
  --max-steps 600 \
  --num-steps-wait 10 \
  --env-img-res 256 \
  --resize-size 224 \
  --replan-steps 5 \
  --sample-steps 10 \
  --seed 7 \
  --policy-seed 0 \
  --render-gpu-device-id "$EGL_GPU" \
  --continue-on-error \
  --output-dir results/pi05_clean_physical60_init0
```

旧 notes 记录过 75% success / 0 cost，但 raw artifact 不在当前 checkout。必须重新运行或复制
并校验原始 artifact，不能仅引用旧数字。

## 8. Attack-record replay

同一个 pure runner 支持：

```bash
--attack-record /path/to/records.jsonl
```

record key 是：

```text
(suite, task_id, init_state_id)
```

replay 时必须保持 clean run 的 task/init/env seed/policy seed/camera/horizon/checkpoint 完全一致。
attack record 还应保存 source、objective、original/perturbed instruction 和 digest。

示例是在上一 clean command 末尾增加：

```bash
--attack-record "$ATTACK_RECORD" \
--output-dir results/pi05_attacked_physical60_init0
```

SABER 当前 full records 来自 standard LIBERO，不能直接冒充 LIBERO-Safety same-task workload。
只有显式 task mapping 和 paired replay 成立后才进入 ProofAlign 主表。

## 9. Defense / CTDA runner

入口：`scripts/run_libero_online_batch.py`，OpenPI policy：
`experiments.libero_openpi_plugin:create_policy`。

本地 first sprint correctness 已完成。runner 现在显式支持 `--ctda-evaluator
ctda-python-reference|ctda-lean-kernel|ctda-shadow`，并通过 `--ctda-artifact-dir` 保存 replay。默认仍
是 Python reference；mode 标签不能替代实际 kernel 检查。

当前 CTDA mode 的硬约束：

- `--ctda`
- `--warmup-steps 0`
- `--ctda-fallback-witness <v2-json>`
- `--ctda-fallback-witness-sha256 <digest>`
- `--ctda-evidence-mode local-simulator-exact-allowlist`
- `--ctda-evaluator <mode>`
- `--ctda-artifact-dir <path>`
- 禁止 `--skip-existing`

fallback manifest 必须绑定 live BDDL、SafetySpec、action bounds 和 declared switch latency。不要复制
旧 manifest；按当前 `src/proofalign/benchmark/libero_online_runner.py` 和 `--help` 重新生成并固定
SHA-256。该 manifest 仍是 `operator-pinned-simulator-test-only`，不是 verified recovery proof。

远程 smoke 必须确认：

- artifact mode 是真正的 `ctda-lean-kernel`；
- Lean proven 前没有 `env.step`；
- observed/monitor 未通过时没有下一 dispatch/phase advance；
- prompt/`proofalign_action` tamper 不改变 mission-rooted contract；
- request 与 kernel replay artifact 已落盘。

本地 CPU shadow 的 Lean p99 为 semantic 约 1.95 s，其余 stage 约 0.65--0.67 s，远超 20 Hz
control period。远程第一步只能跑一个 clean episode 的 shadow/slow-interlock smoke，并记录远程
p50/p95/p99。若仍超 deadline，固定为 offline audit；不得通过放宽授权窗口声称 real-time。

具体 command 在迁移时从当前 `--help` 生成，不从 archive 复制。保留以下固定实验参数：

```text
--max-steps 600
--max-chunk-steps 5
--continue-on-replan
--camera-height 256
--camera-width 256
--render-gpu-device-id <physical EGL id>
--policy experiments.libero_openpi_plugin:create_policy
```

## 10. SABER artifact producer

SABER 在独立 GPU checkout 中运行，仅生成版本化 attack records；不与 method 分支共享隐式状态。

旧机器环境：

```bash
cd /home/ldx/lean-vla/external/SABER
export HF_ENDPOINT=https://hf-mirror.com
export HF_HOME=/data0/ldx/saber-cache/huggingface
export HF_HUB_CACHE=/data0/ldx/saber-cache/huggingface/hub
export TRANSFORMERS_CACHE=/data0/ldx/saber-cache/huggingface
export TORCH_HOME=/data0/ldx/saber-cache/torch
export UV_CACHE_DIR=/data0/ldx/uv-cache
export OPENPI_DATA_HOME=/data0/ldx/saber-cache/openpi
export XDG_CACHE_HOME=/data0/ldx/saber-cache/xdg
export ROBOSUITE_LOG_PATH="$PWD/outputs/logs/robosuite.log"
```

SABER 使用 repo 自己的 `.venv/bin/python`。LoRA merge 后模型路径：

```text
/data0/ldx/saber/outputs/hf_merged_attack_agents/task_failure
/data0/ldx/saber/outputs/hf_merged_attack_agents/action_inflation
/data0/ldx/saber/outputs/hf_merged_attack_agents/constraint_violation
```

官方 adapters：

```text
IntelligenceLab/saber-attack-agent-task-failure
IntelligenceLab/saber-attack-agent-action-inflation
IntelligenceLab/saber-attack-agent-constraint-violation
```

历史 merge 入口（要求对应 patch 已正确应用）：

```bash
.venv/bin/python scripts/merge_saber_lora.py \
  --objective task_failure \
  --out-dir /data0/ldx/saber/outputs/hf_merged_attack_agents

.venv/bin/python scripts/merge_saber_lora.py \
  --objective action_inflation \
  --out-dir /data0/ldx/saber/outputs/hf_merged_attack_agents

.venv/bin/python scripts/merge_saber_lora.py \
  --objective constraint_violation \
  --out-dir /data0/ldx/saber/outputs/hf_merged_attack_agents
```

旧 full-eval protocol：

```text
victim=openpi_pi05
suites=libero_spatial,libero_object,libero_goal,libero_10
task_ids=7-9
episodes_per_task=5
seed=42
vla_gpu=4
attack_gpu=2
gpu_memory_utilization=0.45
ports=18000/18001/18002
60 scenarios per objective
```

full run 由 historical smoke command 去掉 `--max_eval_scenarios 10` 得到；旧 full run 将 attack
side 限制为 physical GPU 2，并把 `--gpu_memory_utilization` 调为 `0.45`。`action_inflation`
是否加入 `--select_max_attack_steps` 必须写入 run config：加入后是 best-of-N selection，不保留
普通逐场景语义。

records：

```text
external/SABER/outputs/agent_output_records_task_failure_hf/task_failure_openpi_pi05.json
external/SABER/outputs/agent_output_records_action_inflation_hf/action_inflation_openpi_pi05.json
external/SABER/outputs/agent_output_records_constraint_violation_hf/constraint_violation_openpi_pi05.json
```

完整 LoRA merge、objective flags、vLLM/JAX GPU isolation 和 historical eval patches 保存在：

- [`archive/artifacts/saber_patches/0001-Add-SABER-LoRA-eval-handoff-notes.patch`](archive/artifacts/saber_patches/0001-Add-SABER-LoRA-eval-handoff-notes.patch)
- [`archive/artifacts/saber_patches/0002-Complete-SABER-LoRA-eval-notes.patch`](archive/artifacts/saber_patches/0002-Complete-SABER-LoRA-eval-notes.patch)

这些 patch 只能应用到匹配的 SABER upstream commit。当前文档尚未保存 exact upstream commit，
所以迁移前必须先记录并验证，不能盲目 `git apply`。

中断 SABER 后只清理自己启动的进程，并先检查：

```bash
pgrep -af 'eval_attack_vla.py|VLLM::EngineCore|model-service'
```

不要杀其他用户进程。

## 11. EDPA 状态

当前仓库没有 EDPA checkout、checkpoint、安装命令或可重放 artifact。不要根据旧 related-work
引用臆造远程配置。EDPA 已从当前执行路线暂缓。

## 12. 远程结果回传

每批运行结束后生成并复制：

- raw episode JSON/JSONL；
- attack records；
- run config；
- git/external commit manifest；
- environment/version manifest；
- file SHA-256 manifest；
- machine-rebuildable summary；
- warnings/failures log。

回传后先做 schema/episode count/checksum 验证，再进入 paired analysis。不得只把手写 metrics 或
截图带回本地。
