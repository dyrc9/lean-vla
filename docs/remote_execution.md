# 远程执行与授权边界

## 1. 默认状态

仓库中的 M1/M2 protocol 默认不授权 GPU rollout、simulator step 或真实 dispatch。`--dry-run`、
validator、fixed-trace shadow 和 Lean build 是 no-outcome 操作。

不再需要运行 high-level plan text probe。真实 victim 导出原生 ActionBlock；进入 L1/四臂前还必须导出
trusted semantic context、`Z_t`、exact prompt、trusted/policy observation 和 executable-prefix binding。

## 2. 本机环境选择

本仓库有两个用途不同的 Python 环境，不应混用：

- `.venv/bin/python`（Python 3.10）用于 ProofAlign 单测、validator、artifact 生成和 no-outcome
  检查；它不安装 JAX；
- `external/openpi/.venv/bin/python`（Python 3.11）是按 OpenPI `uv sync` 建立的模型环境，包含
  JAX、Orbax 和 `openpi`，只在需要加载 π0.5 checkpoint 时使用。

先加载仓库统一的本机缓存配置：

```bash
source scripts/env_vla.sh
```

普通检查继续使用项目环境：

```bash
.venv/bin/python -m pytest -q
```

E6 这类离线 π0.5 测量必须使用 OpenPI 环境：

```bash
external/openpi/.venv/bin/python \
  scripts/run_semantic_resource_smoke_e6.py --check-state
```

当前 E6 v2 runner 按冻结协议把物理 GPU 0 映射为进程内 `cuda:0`，并关闭 JAX 显存预分配。E6 不创建
simulator，因此不需要 `MUJOCO_GL` 或 `MUJOCO_EGL_DEVICE_ID`。任何含 simulator/dispatch/outcome 的
后续命令仍需单独授权。

E7 数据到位后，先检查 contract，再对 manifest 和真实资产运行资格化：

```bash
.venv/bin/python \
  scripts/run_deployment_perception_dataset_qualification_e7.py \
  --check-contract
.venv/bin/python \
  scripts/run_deployment_perception_dataset_qualification_e7.py \
  --audit --manifest /path/to/manifest.json \
  --asset-root /path/to/assets
```

当前 source/evidence 绑定状态使用只读 E8 audit 检查：

```bash
.venv/bin/python scripts/generate_semantic_source_binding_e8.py --check
```

## 3. 本地 no-outcome 检查

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" \
  lake --dir lean build ProofAlign
.venv/bin/python scripts/generate_checker_equivalence_evidence.py --check
.venv/bin/python scripts/run_action_block_fixed_trace_gate.py --check
.venv/bin/python scripts/validate_m1_readiness.py --check
```

M1 runner dry-runs：

```bash
.venv/bin/python scripts/generate_saber_confirmatory_records.py --dry-run
.venv/bin/python scripts/run_saber_confirmatory_victim.py --dry-run
.venv/bin/python scripts/export_proofalign_fixed_trace.py --dry-run
```

## 4. 远程环境必须冻结

- repository commit/tree digest；
- OpenPI/LIBERO-Safety checkout；
- policy checkpoint/config；
- trusted task source、observation tap、secure split allowlist；
- task graph、`Z_t` vocabulary、selector/config、prompt template；
- CUDA/device/dtype；
- 60 base pairs 和两个 seed blocks；
- attack record bundle；
- ActionBlock adapter；
- local-checker implementation/config/threshold；
- Lean source/theorem/equivalence evidence digest；
- observer schema；
- resource budget；
- fresh output directory。

执行 successor 的 repository binding 允许当前 HEAD 位于冻结 source commit 之后，但要求冻结 commit/tree
真实存在且为当前 HEAD 的祖先、所有 protocol source SHA-256 仍完全一致、tracked worktree 干净。这样
可以把协议和审计包提交到 Git，同时任何受控源码变化仍会 fail closed。

## 5. M2 执行顺序

1. 先通过 selector、local-checker、semantic identity、Lean evidence 和资源 no-outcome gate；
2. 运行 producer：每个 base pair 一条 attack record，不看 victim outcome；
3. 校验 record bundle 数量、顺序、source/digest；
4. 运行 240 个 VLA-only clean/attacked episode；
5. 关闭输出并运行 denominator/signal gate；
6. gate 未通过则停止，不运行四臂；
7. gate 通过后才生成 fixed ActionBlock traces 并运行四臂。

2026-07-27 状态：60-record producer successor 已授权并通过 population、source、model、checkout 和
fresh-root 预检；冻结资源门要求两张预启动显存占用 `<1 GiB` 的 GPU，当前只有 GPU 0 满足，因此未
启动生成，也未创建 partial output root。不得通过放宽门槛或占用他人进程绕过。

## 6. 四臂运行顺序

```text
fixed-trace shadow (zero dispatch)
  -> 480 clean closed-loop
  -> 480 attacked closed-loop
```

每个 unit 的四臂顺序按冻结 Latin-square/hash rule；同一 unit/condition 必须共享 VLA seed、candidate
generation rule、assessor、observer 和初始状态。`K=1` fixed-trace 必须共享 exact proposal bytes；
`K>1` 必须共享 ordered candidate set。closed-loop 在 treatment 首次介入后允许轨迹自然分叉，但不能在
不同 arm 中重新定义 selector、阈值、candidate seed 或 observer。

## 7. 故障处理

- 不替换失败 unit/seed；
- 不覆盖 fresh output；
- 不从 partial root 静默恢复，除非 protocol 明确允许并绑定 resume manifest；
- GPU OOM、driver、timeout、invalid observation 都记录为预定义 invalid/infra outcome；
- 不因初步效果修改 threshold、population 或 attack family。

## 8. 历史 artifacts

冻结 v1 preregistration 和 P0b/R9 结果保持 audit-only。其字段可能仍使用旧层名；validator 可以读取，但
新 runner/result schema 必须使用 `intent_action_enabled` 与 `action_execution_enabled`。
