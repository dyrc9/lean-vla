# ProofAlign 执行环境

更新日期：2026-07-24

当前没有新 GPU rollout 授权。R9 已 terminal complete，现有 root 只读保存。确认性或四臂实验必须使用
新 protocol、clean commit、fresh root 和单独授权。

## 1. 固定路径

```text
workspace        /home/ldx/lean-vla
repo Python      /home/ldx/lean-vla/.venv/bin/python
OpenPI Python    /home/ldx/lean-vla/external/openpi/.venv/bin/python
Lean toolchain   /home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin
LIBERO-Safety    /home/ldx/lean-vla/external/LIBERO-Safety
OpenPI source    /home/ldx/lean-vla/external/openpi
pi0.5 checkpoint /data0/ldx/libero_safety_models/pi05_libero_safety
```

外部 checkout、模型和 raw results 都是本机资产，不上传远端。不要重新下载模型或混用 repo `.venv`
与 OpenPI `.venv`。

## 2. CPU/Lean 验证

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/python -m pytest -q
(cd lean && lake build ProofAlign)
make paper-artifacts-check
git diff --check
```

`make paper-artifacts-check` 在本地 R9 raw bundle 或 LIBERO-Safety checkout 缺失时明确 skip 对应的
source-derived 检查。skip 只表示环境缺少本地资产，不代表结果已独立复现。

## 3. OpenPI/LIBERO 环境

```bash
cd /home/ldx/lean-vla
source scripts/env_vla.sh
unset VIRTUAL_ENV
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH="$PWD/src:$PWD:$PWD/external/LIBERO-Safety:$PWD/external/openpi/src:$PWD/external/openpi/packages/openpi-client/src"

external/openpi/.venv/bin/python --version
test -d external/LIBERO-Safety
test -d external/openpi
test -d /data0/ldx/libero_safety_models/pi05_libero_safety
```

保留 runner：

- `run_liberosafety_pi05_openpi_eval.py`：VLA-only clean/attacked victim；
- `run_saber_threat_validation_r5.py`：P0b threat validation；
- `run_saber_integrity_action_envelope_r0.py`–`r3.py`：冻结的 action-envelope 审计链；
- `generate_saber_threat_records_r2.py`：outcome-blind attack records；
- `saber_io.py`：SABER 主线共用的 artifact、Git 与 GPU gate 工具。

R0–R3 launcher 和 R0–R9 protocol/status 是 terminal R9 的历史审计链，不得把默认 output path 当成可
继续使用的 root。新实验必须复制语义到新版本并重新冻结所有 hash。

## 4. GPU 规则

每次正式启动前重新检查：

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader
nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_memory --format=csv,noheader
```

永久约束：

- 不沿用历史 GPU 编号或空闲判断；
- 在 protocol 中事前冻结 policy GPU、EGL GPU、稳定窗口和最大显存；
- launch 后核验实际 JAX compute 与 EGL graphics context；
- binding probe 和 episode 期间监控外部 compute process，资源 gate 被破坏时 fail closed；
- 不停止、迁移或修改无关用户进程；
- 不 resume/覆盖任何已有 root；
- 未经授权不运行 `--execute`。

## 5. R9 artifact 复核

完整本地 bundle：

```bash
cd /home/ldx/lean-vla/results/saber_integrity_action_envelope_r9_20260723_fresh1
sha256sum -c SHA256SUMS
```

不得修改 raw root、ledger、manifest、episode JSON 或 checksums。可复算论文表：

```bash
cd /home/ldx/lean-vla
uv run python scripts/generate_action_envelope_paper_artifacts.py --check
uv run python scripts/freeze_confirmatory_preregistration.py --check
```

远端仓库只保留 compact terminal summary、derived tables、taxonomy、protocol 和代码。

## 6. 新实验执行顺序

1. 完成 no-outcome producer/victim/shared-runner/fixed-trace readiness；
2. 冻结 population、endpoint、统计、停止条件、资源预算和所有 digest；
3. clean commit，验证 fresh output root 不存在；
4. 运行 unit、Lean、dry-run、artifact validator；
5. 提交 readiness packet 并获得单独授权；
6. 当次重新选择 GPU、运行 binding probe；
7. 正式运行后写 append-only ledger、terminal summary 和 checksums；
8. 独立重算结果并更新 canonical 文档。

详细 gate 见 [实验规则](experiments.md)。
