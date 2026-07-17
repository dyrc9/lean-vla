# Implementation Notes

更新日期：2026-07-17

方法语义见 [`method.md`](method.md)，环境命令见 [`remote_execution.md`](remote_execution.md)。

## 主要代码入口

- `src/proofalign/ctda.py`：typed contract/receipt/trace、digest、reference checker；
- `src/proofalign/ctda_runtime.py`：contract activation、prefix transaction、monitor、fallback receipt；
- `src/proofalign/ctda_wire.py`：strict canonical wire；
- `src/proofalign/ctda_evaluator.py`：Python reference、Lean kernel、shadow evaluator；
- `src/proofalign/ctda_shadow.py`：CPU replay；
- `src/proofalign/benchmark/libero_online_runner.py`：Full CTDA environment/runner；
- `src/proofalign/benchmark/libero_e1_runner.py`：unguarded VLA-only observational arm；
- `src/proofalign/benchmark/libero_online_wrapper.py`：dispatch transaction；
- `src/proofalign/benchmark/libero_task_manifest.py`：BDDL-bound task/contact manifest；
- `lean/ProofAlign/CTDAWire.lean`：四阶段 Lean checker。

## 当前必须保持的不变量

1. contract authority 只来自 trusted benchmark mission/phase，不来自 policy prompt/metadata；
2. raw proposal verdict 由 consumer 根据 state/contract/command 计算；
3. semantic/prefix proof 前零 dispatch；
4. observed/monitor proof 前零 phase advance/next dispatch；
5. Lean failure 不回退 Python 授权；
6. shadow 永不授权；
7. fallback success 必须同时绑定 requested/applied command、actuator attestation、post-state 和完整
   postcondition；
8. canonical wire 使用 UTF-8、strict fields、finite typed values 和 integer nanoseconds。

## 下一实现改动

E1-v3 的唯一已知 paired-validity blocker是 observation schema 非对称：Full CTDA 在初态 observation 前
安装 `task_manifest.contact_query`，VLA-only 没有。下一 runner 应提取共享初始化函数，或在
`run_vla_only_episode_with_plugins()` 中显式接受同一个 frozen task manifest，并在第一次
`state_observer.observe()` 前设置：

```python
wrapper.state_observer.contact_part_queries = (task_manifest.contact_query,)
```

这只是 observer schema 对齐；不得给 baseline 添加 CTDA/legacy action gate。需要测试：

- shared initialized observation -> identical digest；
- different query/manifest -> digest mismatch and preflight block；
- VLA-only trace 无 CTDA records，checker 始终 observational allow；
- Full CTDA 初态 digest 仍匹配 frozen E0 init0 digest；
- real policy output probe 不调用 `env.step()`。

## 验证

```bash
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/pytest -q \
  tests/test_ctda_evaluator.py \
  tests/test_ctda_runtime.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py
(cd lean && lake build ProofAlign)
git diff --check
```

全量 suite 的一个既有失败来自 `external/fiper/data` symlink 使 generic baseline preflight
`source_ready=false`；不要为得到绿色测试而删除或改动 FIPER 数据绑定。

## Artifact 纪律

- runner 默认 read-only preflight；正式 mutation 需要显式 `--execute`；
- protocol pin source/checkpoint/external commit；
- fresh root、append-only ledger、per-episode hash、terminal manifest；
- invalid/unknown record 保留，不按 outcome 替换；
- 文档只更新 canonical 入口和 `evaluation_results.md`，阶段长报告进入 archive。
