# ProofAlign: VLA ActionBlock 双层完整性

本仓库研究一个不要求 VLA 输出高层规划的问题：

> 在可信任务意图保持不变、policy-facing instruction/observation/history 可能被攻击时，如何判断 VLA
> 输出的 ActionBlock 是否仍服务于可信意图，并确认获准的 ActionBlock 在执行后没有发生命令或效果偏移？

核心链路是：

```text
TrustedIntent T ─────────────────────────────┐
                                             v
attacked policy view -> VLA -> ActionBlock A -> consumer assessor S -> L1
                               |
                               +-> BlockExecutionContract C
                                      |
                                      v
                               dispatch -> receipt R -> effects E -> L2/Lean
```

两层的含义：

1. **Intent–ActionBlock alignment（L1）**：冻结的 consumer-side assessor 根据当前观测和具体
   ActionBlock 预测 skill/effects/violations，再与可信 intent 比较。它不声称恢复 VLA 的“内在意图”；
   不确定时必须 abstain/fail closed。
2. **ActionBlock–Execution alignment（L2）**：检查获准 block、最终命令、dispatch receipt、观测效果
   和任务 phase transition 是否属于同一个绑定事务。Lean 只用于这层的有限、离散命题；不证明 learned
   assessor、传感器或物理世界正确。

四臂实验是同一 runner 上的两个开关：

| Arm | L1 Intent–Action | L2 Action–Execution |
|---|---:|---:|
| VLA-only | off | off |
| Intent–Action-only | on | off |
| Execution-only | off | on |
| Dual | on | on |

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

1. M1 no-outcome readiness：冻结 confirmatory producer/victim、四臂 shared runner、
   ActionBlock trace exporter、digest、资源预算、validator；
2. 资格化 L1 assessor：独立于被攻击 policy view，报告 coverage、false-allow、校准、OOD abstention
   和 latency；
3. 运行 M2：60 base pair × 2 seeds，共 240 个 clean/attacked VLA-only episode；
4. M2 gate 通过后，依次运行 fixed-trace 四臂、480 clean 四臂、480 attacked 四臂。

入口文档：

- [方法定义](docs/method.md)
- [ActionBlock assessor 设计与资格化](docs/action_block_assessment.md)
- [实验协议](docs/experiments.md)
- [旧实验复用与迁移](docs/experiment_reuse.md)
- [相关工作](docs/paper/related_work.md)
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
与 outcome-blind ActionBlock prefix adapter 完成；剩余 blocker 是 assessor qualification、授权后的资源/
延迟 smoke measurement，以及 clean-commit binding。
