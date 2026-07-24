# ProofAlign: VLA ActionBlock 双层完整性

本仓库研究一个不要求 VLA 输出高层规划的问题：

> 在可信任务意图保持不变、policy-facing instruction/observation/history 可能被攻击时，如何判断 VLA
> 输出的 ActionBlock 是否仍服务于可信意图，并确认获准的 ActionBlock 在执行后没有发生命令或效果偏移？

核心链路是：

```text
Trusted T + pre-attack O_t^T -> frozen selector -> SemanticSubtask Z_t ─┐
                                                                       v
external prompt / injected O_t^atk -> π0.5 -> ActionBlock candidates -> L1
                                                                       |
                                                  BlockExecutionContract
                                                                       |
                                           dispatch -> receipt/effects -> L2/Lean
```

两层的含义：

1. **Intent–SemanticSubtask–ActionBlock alignment（L1）**：只用可信任务和安全分叉前 observation
   产生并绑定 `Z_t`，再检查 π0.5 ActionBlock 的局部运动/后果是否与 `Z_t` 兼容。不确定时必须
   abstain/fail closed。
2. **ActionBlock–Execution alignment（L2）**：检查获准 block、最终命令、dispatch receipt、观测效果
   和任务 phase transition 是否属于同一个绑定事务。Lean 只用于这层的有限、离散命题；不证明 learned
   assessor、传感器或物理世界正确。

顶层 motivation 始终是 `Intent -> ActionBlock` 与 `ActionBlock -> Execution` 两层对齐；`Z_t` 是 L1
的结构化机制。Lean 是 L2 的核心方法组件，用于固定 transaction semantics 并检查 exact-dispatch 与
phase-gating theorem，而不是事后附加的形式化说明。

四臂实验是同一 runner 上的两个开关：

| Arm | L1 Intent–Action | L2 Action–Execution |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

冻结 runtime 中的 `intent_only` / `intent_action_enabled` 只是 Semantic-only 的兼容 schema 名称。

## 当前证据边界

- P0b：96/96 episode 有效，得到 23 个 clean-eligible pair 和 15 个攻击 transition；因
  `23 < 26` 未通过确认性 denominator gate。
- R9 Execution-only：clean retention `22/23 = 95.7%`；attacked+defended `48/48`
  有效；cost/collision unsafe `1/48`；signal subset `15/15 -> 0/15` cost/collision；
  strict-success recovery `8/15`；`11/15` 仍有 residual contact proxy。

因此现有结果仍是**强探索性正结果**，不能声称一般防御有效、完整物理安全或 Dual 已验证。旧结果可复用为：

- P0b：原始 instruction/observation attack、clean pairing 和攻击 transition 基础；
- R9：ActionBlock dispatch、intervention、receipt/effect logging 和 Execution-only 基线。

它们不能替代新的 L1 assessor qualification，也不能改名为 Dual 结果。

## 当前主线

1. M1A component closure：冻结 producer/victim、四臂 runner、trace exporter、Lean evidence 与 validator；
2. M1B selector qualification：冻结 task graph、`Z_t` 词表、margin/unknown、OOD 和 latency gate；
3. M1C local-checker qualification：报告 attacked false allow、clean retention、coverage 和 worst group；
4. 贯通 `Z_t`/prompt/ActionBlock/contract identity，并更新 fixed-trace 与资源 gate；
5. 运行 M2：60 base pair × 2 seeds，共 240 个 clean/attacked VLA-only episode；
6. M2 gate 通过后，依次运行 fixed-trace 四臂、480 clean 四臂、480 attacked 四臂。

入口文档：

- [方法定义](docs/method.md)
- [`Z_t` 可信输入与注入边界](docs/trusted_semantic_boundary.md)
- [零训练 semantic hierarchy](docs/semantic_subtask_hierarchy.md)
- [ActionBlock assessor 设计与资格化](docs/action_block_assessment.md)
- [实验协议](docs/experiments.md)
- [旧实验复用与迁移](docs/experiment_reuse.md)
- [相关工作](docs/paper/related_work.md)
- [论文故事](docs/paper/paper_story.md)
- [代码与实验准备清单](docs/implementation_and_experiment_readiness.md)
- [进展与下一步](docs/progress_and_plan.md)

常用检查：

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" \
  lake --dir lean build ProofAlign
.venv/bin/python scripts/run_action_block_fixed_trace_gate.py --check
bash scripts/check_all.sh
```

冻结的旧协议、旧结果和废弃路线只用于审计，不授权新 rollout。

当前 M1 packet 已确认 producer/victim、shared runner、Lean evidence、fresh roots、fixed-trace exporter
与 outcome-blind ActionBlock prefix adapter 完成；剩余 blocker 是 semantic runtime integration、
selector/local-checker qualification、授权后的资源/延迟 smoke measurement，以及 clean-commit binding。
