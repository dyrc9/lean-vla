# Implementation Notes

更新日期：2026-07-10

本文只记录当前本地开发约定。方法语义见 [`method.md`](method.md)，远程 GPU 配置见
[`remote_execution.md`](remote_execution.md)。

## 1. 当前环境

当前 workspace 没有 GPU。允许：

- Python/Lean 代码修改；
- unit/integration/fake-env tests；
- Lean build 和 kernel evaluator development；
- JSON/JSONL fixture replay；
- CPU-only shadow calibration。

禁止在本地阶段下载模型/数据、运行 CUDA/MuJoCo 大实验或声称 GPU 指标。

## 2. Python 与 Lean

本地使用 repository 的 `uv` project：

```bash
uv sync --dev
uv run pytest
```

Lean toolchain 由 `lean/lean-toolchain` 固定。验证：

```bash
(cd lean && lake build ProofAlign)
```

提交方法改动前运行：

```bash
uv run pytest
(cd lean && lake build ProofAlign)
git diff --check
```

Focused suite：

```bash
uv run pytest \
  tests/test_ctda.py \
  tests/test_ctda_runtime.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py \
  tests/test_lean_bridge.py
```

## 3. 当前 mode 语义

- `legacy-lean-boolean`：legacy concrete Boolean claim 由 Lean 检查。
- `ctda-python-reference`：canonical wire 的 Python reference path；`proof_verified=false`。
- `ctda-lean-kernel`：四个 wire stage 确实由 Lean `by decide` 检查；只有成功 kernel request 可写
  `proof_verified=true`。
- `ctda-shadow`：Python/Lean 双评估或 replay；不能授权实际执行。
- mock/unavailable：diagnostic only，不能 dispatch。

任何 artifact 都必须记录真实 evaluator mode。禁止仅修改标签而不改变判定路径。

## 4. First sprint 代码入口

- `experiments/libero_openpi_plugin.py`：policy metadata compatibility/logging；不是 paper authority。
- `experiments/libero_vla_plugin.py`：legacy heuristic abstraction；paper CTDA 不应以它为 authority。
- `src/proofalign/ctda.py`：typed objects、digest、reference checker。
- `src/proofalign/ctda_runtime.py`：contract activation、proposal preparation、transaction state。
- `src/proofalign/ctda_wire.py`：strict canonical wire 与 reference semantics。
- `src/proofalign/ctda_evaluator.py`：三种 evaluator、kernel replay artifact 与 cache。
- `src/proofalign/ctda_shadow.py`：CPU JSON/JSONL/episode/fixture replay 与统计。
- `src/proofalign/benchmark/libero_online_wrapper.py`：pre-dispatch/observe ordering。
- `src/proofalign/lean_bridge.py`：需要扩展 canonical CTDA evaluator，而不是复用 label。
- `lean/ProofAlign/CTDA.lean`：Lean semantics。
- `lean/ProofAlign/CTDAWire.lean`：共同支持的四阶段 wire checker。
- `lean/ProofAlign/CTDAExamples.lean`：positive/negative kernel fixtures。

## 5. 实现纪律

### Contract authority

- benchmark trusted task 与 policy-facing instruction 使用不同字段和类型；
- paper contract 只来自 frozen mission/phase；
- policy `proofalign_action` 只作 untrusted metadata/compatibility logging；
- unsupported/ambiguous task fail closed。

### Raw proposal binding

- binder verdict 由 consumer 计算；
- raw action、state、contract 和 config 全部绑定；
- 不接受 producer 自报 `verified/admissible/preserves_contract` 升级授权；
- 缺 observation 或目标歧义返回 unknown/refuted。

### Evaluator transaction

- evaluator 成功前不能提交 active contract、proposal index、monitor history 或 phase；
- Lean failure 不得回退 Python 继续 dispatch；
- observed/monitor check 必须在下一 dispatch/phase advance 前完成；
- cache 只能缓存真正的 Lean request/result，并绑定 checker/build/schema digest。

### Schema

- `ctda-wire-v1` 是内部 schema，不替换 episode/attack record；
- integer nanoseconds；
- canonical UTF-8 JSON；
- strict enum/type/field checking；
- tagged temporal formula；
- reject NaN/Infinity；
- consumer 重算 critical digest；
- 覆盖 Unicode/escape/source-injection tests。

## 6. Test requirements

至少覆盖：

- attacked prompt 和 `proofalign_action` tamper 不改变 paper contract/verdict；
- trusted task/registry 改变使旧 artifact 失效；
- wrong target/region/gripper/held object fail closed；
- missing completion 保持 pending；
- stale/replay/cross-episode/timestamp rollback；
- Lean unavailable、serialization error、timeout、parity mismatch 零 dispatch；
- observed/monitor 未通过时零 phase advance；
- wire round trip、canonical bytes 和 digest stability；
- shadow 无 ground truth 时输出 `not_evaluated`。

## 7. 文档与 artifact

Golden/shadow CPU replay：

```bash
uv run python -m proofalign.ctda_shadow \
  tests/fixtures/ctda_golden.json \
  --artifact-dir /tmp/proofalign-ctda-shadow-artifacts \
  --output /tmp/proofalign-ctda-shadow-report.json
```

当前 fixture 为 synthetic protocol parity corpus，不是 independent ground truth；false block、TPR、
FPR 必须保持 `not_evaluated`。本地 Lean p99 超出 control period，未经优化只能作为 slow
interlock/offline audit。

- 只更新 [`docs/README.md`](README.md) 列出的 canonical 文档。
- 不新增日期型 status、handoff 或 parallel roadmap。
- 历史材料只在明确追溯时读取 `docs/archive/`。
- 大型/ignored artifact 不进 Git；远程复制与 checksum 规则见
  [`remote_execution.md`](remote_execution.md)。
- CLI 默认值以代码和 `--help` 为准。

## 8. 当前非任务

First sprint 不实现：新攻击、GPU runner 扩展、CBF/reachability、hardware attestation、TEE、
verified fallback、通用 NL/BDDL compiler、第三个 alignment layer 或新 victim。
