# ProofAlign

ProofAlign 是一个面向 Vision-Language-Action（VLA）系统的执行完整性研究原型。当前主线只保留两层
关系：

1. **Intent–Plan Integrity**：proposal 是否仍实现可信 mission、当前 phase 与剩余 obligation；
2. **Plan–Execution Integrity**：实际 dispatch 的 final command 是否就是被检查和授权的 command。

方法只有两个核心不变量：

```text
No dispatch without dual authorization
No phase advance without checked completion
```

在线协议被收敛为三个 transaction：冻结 contract、授权 exact prefix、检查 effect 并更新 persistent
monitor。当前 Python 原型和 Lean core 都已实现；两者之间尚缺 machine-checked refinement，因此 Lean
只能作为离线形式化模型，不能描述为实时证明控制器。

## 当前实验结论

当前 terminal 结果来自 Execution-only action-envelope 探索实验：

| 指标 | 结果 |
|---|---:|
| P0b immutable attack records | `48` |
| P0b valid clean/attacked episodes | `96/96` |
| P0b clean-eligible pairs | `23`，低于预注册门槛 `26` |
| P0b clean-safe→attacked-unsafe signal pairs | `15` |
| clean strict-success retention | `22/23 = 95.7%` |
| attacked+defended valid episodes | `48/48` |
| envelope 内最终命令 | `17,828/17,828` |
| 被 projection 修改的动作 | `13,108/17,828 = 73.5%` |
| full-population strict success without cost | `26/48 = 54.2%` |
| full-population LIBERO cost/collision unsafe | `1/48 = 2.1%` |
| signal subset defended cost/collision | `0/15` |
| signal subset recovered strict success | `8/15` |
| signal subset residual contact proxy 高于 clean | `11/15` |

结论是：exact execution-time projection 在这个固定 simulator workload 上提供了强探索性缓解证据，
同时基本保留 clean utility；但 P0b 的 clean-eligible denominator 未达到冻结门槛，而且 residual
contact/joint proxy 仍然存在。因此当前分类保持
`exploratory_attacked_defended_complete_not_confirmatory`，不能声称一般攻击防御有效、完整物理安全
或 Dual 方法已经得到验证。

详细解释和后续 gate 见
[项目进展与实施规划](docs/progress_and_plan.md)；机器结果见
[terminal summary](experiments/saber_integrity_action_envelope_terminal_summary.json)。

## 下一实验

下一项正式实验不是继续扩大 R9，而是独立确认性 attack foundation：

- `60` 个与 P0b 不重叠的 base pair；
- `2` 个冻结 seed block，共 `120` 个 unit；
- 每个 unit 跑 clean 与 attacked VLA-only，共 `240` 个 episode；
- clean-eligible 必须 `>=52` unit 且覆盖 `>=26` base pair；
- transition 必须 `>=26` unit 且覆盖 `>=18` base pair；
- transition rate 必须 `>=0.50`，base-pair cluster bootstrap 95% lower bound 必须 `>=0.30`。

在它之前先完成 no-outcome readiness：冻结 producer/victim/shared runner、fixed-trace exporter、digest、
资源预算、fresh output root 和 validator。确认性 gate 未通过时，四臂防御实验不启动；通过后才依次
运行 fixed-trace shadow、`480` 个 clean 四臂 episode、`480` 个 attacked 四臂 episode。

预注册见 [confirmatory/four-arm design](docs/paper/confirmatory_preregistration.md)。

## 当前主线结构

- `src/proofalign/integrity_*.py`：两层完整性、四臂开关、exact-command authorization、dispatch receipt
  与 persistent monitor；
- `src/proofalign/benchmark/`：immutable attack record、action envelope、LIBERO runtime 和 SABER
  replication 主线适配；
- `lean/ProofAlign/IntegrityCore.lean`：两个不变量和四臂语义的最小 Lean 模型；
- `scripts/`：当前 runner、artifact generator、preregistration freezer 与 resource-isolated launch 检查；
- `experiments/`：紧凑 protocol/status/terminal summary；R0–R9 协议链保留用于审计；
- `tests/`：仅覆盖当前主线；
- `docs/`：方法、实验规则、结果报告和论文材料。

废弃的 CTDA v1/v2、AEGIS、EDPA、Phantom、SAFE/FIPER、旧 LIBERO runner、旧 handoff 和重复结果已
从工作树删除；需要时仍可从 Git 历史恢复。

## 验证

```bash
cd /home/ldx/lean-vla
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
.venv/bin/python -m pytest -q
(cd lean && lake build ProofAlign)
make paper-artifacts-check
```

也可以运行 `scripts/check_all.sh`。

完整 R9 raw episode bundle 只保留在实验机本地。远端只保存代码、协议、terminal summary、派生表、
failure taxonomy 和校验绑定；远端缺少本地 raw bundle 时，raw-dependent 检查会明确 skip，不能把
skip 解释为独立复现。confirmatory preregistration 的重新生成同样依赖本地忽略的
`external/LIBERO-Safety` checkout。

GPU/OpenPI 环境和执行边界见 [远程执行说明](docs/remote_execution.md)。R9 root 已冻结，禁止续跑或
覆盖；任何新 rollout 都必须使用新 protocol、clean commit、fresh root 和单独的执行授权。
