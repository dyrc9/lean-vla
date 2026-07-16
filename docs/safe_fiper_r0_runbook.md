# SAFE / FIPER R0 运行手册

本页是 SAFE/FIPER 官方 R0 的唯一运行入口。项目总进度与 claim boundary 以
[`project_status.md`](project_status.md) 为准，冻结实验定义分别在
`experiments/safe_r0_protocol.json` 和 `experiments/fiper_r0_protocol.json`。

## 当前结论（2026-07-16 13:30 Asia/Shanghai）

SAFE 仍保持停止。FIPER 的第一条 2026-07-16 fresh run 在 seed 0 的 `pretzel/rnd_a` 训练结束后
无 traceback、无 terminal manifest 退出；该目录保持 partial/audit-only。用户要求 baseline 后台继续，
因此第二条独立 fresh run 由 `experiments/fiper_r0_restart2_20260716.json` 授权，并使用 user systemd
transient service 与 SSH 会话解耦。任何 run 在 terminal gate 前都不能写成“复现成功”，也不能进入
ProofAlign 比较表。

| Baseline | 中断位置 | 审计产物 | 当前判定 |
|---|---|---|---|
| SAFE | 500 个 episode 中写出 335 个 env pickle | `/data0/ldx/safe-fiper-r0/safe/runs/safe-pi0-libero10-r0-20260715` | partial corpus；无 completed manifest，不得训练 detector |
| FIPER 原始入口 | seed 0 / `sorting` 时触发上游 `np.bool` 兼容性错误 | `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-20260715`，manifest 状态为 `failed` | 保留为首次失败证据 |
| FIPER compatibility run | seed 0；完成 `sorting`、`stacking`，在 `push_t / rnd_oe` 训练中中断 | `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-compat1-20260715` | partial outputs；无 completed manifest |
| FIPER first fresh run | seed 0；前三个 task 已评测，`pretzel/rnd_a` 训练结束后进程消失 | `/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-fresh-20260716-104000` | manifest 仍为 `started`；partial outputs，不得拼接 |

上述位置只是中断快照，不是最终指标。禁止把 partial outputs 与未来运行拼接，禁止复用这些
result directory，也禁止从日志推断缺失结果。SAFE 如需继续，必须先冻结 fresh 或 resume
协议；FIPER 只能在全新的 result directory 重跑完整官方矩阵。

2026-07-16 的 fresh restart 分别由
`experiments/fiper_r0_restart_20260716.json` 和 `experiments/fiper_r0_restart2_20260716.json`
事前授权。它们固定复用现有
`/data0/ldx/uv-envs/fiper-r0`，禁止创建环境或安装依赖，并把 GPU、唯一 fresh result directory、
parent protocol digest 与“不续接/不拼接”规则绑定到 launcher。正式 `--execute` 缺少该授权文件或
任一绑定字段不一致时必须 fail closed。

原专用 worktree `external/worktrees/safe-fiper-r0` 已在收尾文档和代码合入主仓库后删除。
以后从主仓库 `/home/ldx/lean-vla` 运行，不需要重新创建 ProofAlign worktree。

## 本机资源位置：全部复用，不要下载

### 固定源码

三个仓库已经在主目录的 ignored `external/` 下独立保存，不依赖已删除的 worktree：

| 源码 | 本地路径 | 固定 commit |
|---|---|---|
| SAFE | `/home/ldx/lean-vla/external/SAFE` | `b6036abe07b2b2bb9996afb2c07f13d6a9f507c0` |
| SAFE OpenPI | `/home/ldx/lean-vla/external/SAFE-openpi` | `9c99ed53f6a0c9be93a1c63cee5792620777d96b` |
| FIPER | `/home/ldx/lean-vla/external/fiper` | `13d79c5c3069def843e454787ff128defc249838` |

SAFE OpenPI 的 `third_party/libero` 子模块必须为
`f78abd68ee283de9f9be3c8f7e2a9ad60246e95c`。运行前只校验 commit 和 clean status，
不要 `pull`、不要切分支、不要修改上游源码。

### 模型、数据与历史输出

| 资源 | 本地路径 |
|---|---|
| SAFE π0 checkpoint | `/data0/ldx/safe-fiper-r0/openpi/openpi-assets/checkpoints/pi0_libero` |
| PaliGemma tokenizer | `/data0/ldx/safe-fiper-r0/openpi/big_vision/paligemma_tokenizer.model` |
| FIPER 官方 zip | `/data0/ldx/safe-fiper-r0/fiper/fiper_data.zip` |
| FIPER 解压后的只读 rollouts | `/data0/ldx/safe-fiper-r0/fiper/extracted/data_all` |
| SAFE/FIPER 历史运行 | `/data0/ldx/safe-fiper-r0/{safe,fiper}/runs` |

SAFE checkpoint 为 19 个文件、12,014,131,888 bytes；FIPER zip 为
5,676,727,608 bytes，解压树为 3,030 个文件、21,153,402,168 bytes。SHA-256 和 tree digest
已经冻结在两个 protocol JSON 及 `/data0/ldx/safe-fiper-r0` 下的 manifest 中。路径缺失时先查
挂载和 digest，不要直接运行 downloader。

## uv 与 Python 环境

唯一允许使用的 uv 是：

```bash
UV=/home/ldx/.conda/envs/proofalign-libero/bin/uv
"$UV" --version
```

当前记录版本为 uv `0.11.25`。已有环境不要重建：

| 用途 | 环境 | Python |
|---|---|---|
| SAFE detector | `/data0/ldx/uv-envs/safe-r0` | 3.10.20 |
| SAFE OpenPI server | `/data0/ldx/uv-envs/safe-r0-openpi` | 3.11.15 |
| SAFE LIBERO client | `/data0/ldx/uv-envs/safe-r0-libero-client` | 3.8.20 |
| FIPER | `/data0/ldx/uv-envs/fiper-r0` | 3.11.15 |

uv cache 为 `/data0/ldx/uv-cache`，uv-managed Python 为 `/data0/ldx/uv-python`。
精确包版本见 `experiments/safe_fiper_r0_env/resolved_environments.json`；同目录 requirements
只用于灾难恢复，不代表每次运行都要重新安装。

## 每次执行前的只读检查

从主仓库执行：

```bash
cd /home/ldx/lean-vla

git -C external/SAFE rev-parse HEAD
git -C external/SAFE status --short
git -C external/SAFE-openpi rev-parse HEAD
git -C external/SAFE-openpi status --short
git -C external/SAFE-openpi submodule status
git -C external/fiper rev-parse HEAD
git -C external/fiper status --short

/home/ldx/lean-vla/.venv/bin/python \
  scripts/baseline_reproduction_preflight.py \
  --workspace . \
  --source-root /home/ldx/lean-vla/external
```

在当前中断状态下，全局 `ready` 必然为 false，`gpu_execution_authorized` 也固定为 false；这是
fail-closed 设计，不是环境安装失败。判断某条线的输入是否齐全时读取
`input_readiness.safe_rollout`、`input_readiness.safe_detector` 或 `input_readiness.fiper`，并单独完成
新的 GPU inventory 和事前执行授权。

主仓库预检会按 launcher 的真实 import 上下文检查现有环境：SAFE detector 使用 `external/SAFE`
作为工作目录，OpenPI server 使用 `external/SAFE-openpi/src`，LIBERO client 同时使用 frozen LIBERO
submodule 与 `packages/openpi-client/src`。在源码、环境、checkpoint 和 FIPER 数据均保持当前冻结状态
时，预期为 `safe_rollout=true`、`safe_detector=false`、`fiper=true`；其中 detector 只因缺少一套新的
500-episode terminal rollout 而保持 false。预检不得为修复 import 检查而新建或重建环境。

每次 GPU run 都重新记录：

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.used,memory.total,utilization.gpu \
  --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory \
  --format=csv,noheader
```

launcher 的 dry-run 与正式 `run_manifest.json` 同时保存上述两项 inventory、ProofAlign 根仓库
HEAD/dirty status、三个 frozen upstream HEAD 和 uv 版本。正式运行必须从 clean ProofAlign checkout
启动；dry-run 如显示根仓库仍有未提交修改，先完成验证与提交，不得直接启动长任务。

先用 `--dry-run` 检查生成的 manifest 和绝对路径。dry-run 不创建 result directory：

```bash
PY=/home/ldx/lean-vla/.venv/bin/python

"$PY" scripts/run_safe_fiper_r0.py \
  --target safe-rollout --dry-run \
  --run-dir /data0/ldx/safe-fiper-r0/safe/runs/DRY_RUN_NAME \
  --safe-root /home/ldx/lean-vla/external/SAFE \
  --safe-openpi-root /home/ldx/lean-vla/external/SAFE-openpi \
  --policy-gpu POLICY_GPU --egl-gpu EGL_GPU

"$PY" scripts/run_safe_fiper_r0.py \
  --target fiper --dry-run \
  --run-dir /data0/ldx/safe-fiper-r0/fiper/runs/DRY_RUN_NAME \
  --fiper-root /home/ldx/lean-vla/external/fiper \
  --policy-gpu GPU_ID
```

`POLICY_GPU` 与 `EGL_GPU` 必须是 fresh inventory 中两个不同的物理 GPU id。不要照抄旧运行用过的
GPU 4 等编号。

## SAFE：fresh rollout 与 detector

只有新协议明确选择 fresh run 后才执行；不能从 335/500 目录续写：

```bash
cd /home/ldx/lean-vla
PY=/home/ldx/lean-vla/.venv/bin/python
RUN=/data0/ldx/safe-fiper-r0/safe/runs/safe-pi0-libero10-r0-fresh-YYYYMMDD-HHMMSS

test ! -e "$RUN"
"$PY" scripts/run_safe_fiper_r0.py \
  --target safe-rollout --execute --run-dir "$RUN" \
  --safe-root /home/ldx/lean-vla/external/SAFE \
  --safe-openpi-root /home/ldx/lean-vla/external/SAFE-openpi \
  --policy-gpu POLICY_GPU --egl-gpu EGL_GPU
```

launcher 会启动 π0 policy server，等待端口 ready，再运行 10 tasks × 50 trials 的 LIBERO client；
输出位于 `$RUN/rollouts/pi0-libero_10`，server/client 日志和 `run_manifest.json` 位于 `$RUN`。
只有 manifest 为 `completed` 才进入 validator：

```bash
ROLLOUT="$RUN/rollouts/pi0-libero_10"

"$PY" scripts/baseline_reproduction_assets.py inspect-safe "$ROLLOUT" \
  --trust-pickle --output "$RUN/safe_rollout_inspection.json"
"$PY" scripts/baseline_reproduction_assets.py manifest "$ROLLOUT" \
  --output "$RUN/safe_rollout_tree_manifest.json"
```

validator 必须确认 500 个 env records、policy-call count 相等、schema/shape 合法且同时存在 success
和 failure。然后才允许启动官方完整 detector matrix：

```bash
DETECTOR_RUN=/data0/ldx/safe-fiper-r0/safe/runs/safe-detector-r0-YYYYMMDD-HHMMSS
test ! -e "$DETECTOR_RUN"

"$PY" scripts/run_safe_fiper_r0.py \
  --target safe-detector --execute --run-dir "$DETECTOR_RUN" \
  --safe-root /home/ldx/lean-vla/external/SAFE \
  --safe-rollout-root "$ROLLOUT"
```

reduced smoke 不能替代官方 seeds/learning-rate/regularization 完整矩阵。

## FIPER：fresh 官方完整 pipeline

FIPER commit `13d79c5` 使用了 NumPy 已删除的 `np.bool`。项目入口
`scripts/run_fiper_compat.py` 只恢复 `np.bool = np.bool_`，不修改上游文件或数值算法。

```bash
cd /home/ldx/lean-vla
PY=/home/ldx/lean-vla/.venv/bin/python
AUTH=/home/ldx/lean-vla/experiments/fiper_r0_restart2_20260716.json
RUN=/data0/ldx/safe-fiper-r0/fiper/runs/fiper-r0-fresh2-20260716-133000

test ! -e "$RUN"
"$PY" scripts/run_safe_fiper_r0.py \
  --target fiper --execute --run-dir "$RUN" \
  --restart-authorization "$AUTH" \
  --fiper-root /home/ldx/lean-vla/external/fiper \
  --policy-gpu 1
```

launcher 会自动创建 `$RUN/runtime_data/{task}`，每个 task 只用 `rollouts` symlink 引用冻结的官方
数据；processed tensors、RND checkpoints 和 results 均写入本次 `$RUN/runtime_data`。运行期间
`external/fiper/data` 是临时 symlink，正常完成、失败或 Ctrl-C 后都会移除。Hydra 输出固定到
`$RUN/hydra`，主日志为 `$RUN/00_fiper-official-full-pipeline.log`。

R0 pass 必须完成 5 tasks × seeds `[0,1,2,42,43]` × 全部官方方法、window、quantile 和 threshold
style；只完成 seed 0 或只跑 `rnd_oe/entropy` 都不能算复现。

## 监控、停止与 terminal gate

实验以前台 launcher 为进程根运行，日志可在另一终端查看：

```bash
tail -F "$RUN"/*.log
```

需要人工停止时，对 launcher 使用一次 `Ctrl-C`/`SIGINT`，等待它清理 SAFE server process group 或
FIPER 临时 data link；不要只杀某个 Python child，也不要用已有 partial directory重新启动。新的
launcher 会把 Ctrl-C 记录为 manifest `status: interrupted`。

每条线退出后必须依次满足：

1. `run_manifest.json` 存在且状态为 `completed`；
2. source commit、submodule、GPU、uv 和 protocol digest 均写入 manifest；
3. target-specific schema/count/result validator 通过；
4. 输出 tree digest 冻结，日志和所有失败 attempt 保留；
5. 项目状态明确更新为 `reproduced_upstream` 或 `blocked_upstream`；
6. 只有 `reproduced_upstream` 才能另开事前协议开发 π0.5 adapter 或 baseline comparison。

任一项未满足都必须停止，不能用日志片段、smoke test 或主观判断补齐结果。
