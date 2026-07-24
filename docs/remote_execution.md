# 远程执行与授权边界

## 1. 默认状态

仓库中的 M1/M2 protocol 默认不授权 GPU rollout、simulator step 或真实 dispatch。`--dry-run`、
validator、fixed-trace shadow 和 Lean build 是 no-outcome 操作。

不再需要运行 high-level plan text probe。真实 victim 只需导出原生 ActionBlock。

## 2. 本地 no-outcome 检查

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

## 3. 远程环境必须冻结

- repository commit/tree digest；
- OpenPI/LIBERO-Safety checkout；
- policy checkpoint/config；
- CUDA/device/dtype；
- 60 base pairs 和两个 seed blocks；
- attack record bundle；
- ActionBlock adapter；
- assessor checkpoint/config/threshold；
- observer schema；
- resource budget；
- fresh output directory。

## 4. M2 执行顺序

1. 先运行 producer：每个 base pair 一条 attack record，不看 victim outcome；
2. 校验 record bundle 数量、顺序、source/digest；
3. 运行 240 个 VLA-only clean/attacked episode；
4. 关闭输出并运行 denominator/signal gate；
5. gate 未通过则停止，不运行四臂；
6. gate 通过后才生成 fixed ActionBlock traces 并运行四臂。

## 5. 四臂运行顺序

```text
fixed-trace shadow (zero dispatch)
  -> 480 clean closed-loop
  -> 480 attacked closed-loop
```

每个 unit 的四臂顺序按冻结 Latin-square/hash rule；同一 unit/condition 必须共享 VLA seed、ActionBlock
source、assessor 和 observer。若在线 arm 各自产生不同 ActionBlock，则该实验不再识别两个层开关。

## 6. 故障处理

- 不替换失败 unit/seed；
- 不覆盖 fresh output；
- 不从 partial root 静默恢复，除非 protocol 明确允许并绑定 resume manifest；
- GPU OOM、driver、timeout、invalid observation 都记录为预定义 invalid/infra outcome；
- 不因初步效果修改 threshold、population 或 attack family。

## 7. 历史 artifacts

冻结 v1 preregistration 和 P0b/R9 结果保持 audit-only。其字段可能仍使用旧层名；validator 可以读取，但
新 runner/result schema 必须使用 `intent_action_enabled` 与 `action_execution_enabled`。
