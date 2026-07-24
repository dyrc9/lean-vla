# ProofAlign 项目进展与实施规划

更新日期：2026-07-24

## 1. 一句话状态

项目已经形成一个清晰主线：**以 mission-rooted contract 约束 Intent–Plan，以 exact-command
authorization 和 receipt/effect binding 约束 Plan–Execution；先确认攻击 population，再做四臂因果
评估。**

当前最强证据是 Execution-only action-envelope 的 terminal 探索性正结果。它值得写入论文，但不足以
支持 confirmatory defense、Dual composition 或完整物理安全结论。

## 2. 当前实验结果

### 2.1 P0b attack foundation

P0b 生成 48 条 immutable attack record，并完成 clean/attacked 共 `96/96` 个 valid episode：

| 指标 | 结果 |
|---|---:|
| clean-eligible pairs | `23` |
| 冻结的最低 clean-eligible gate | `26` |
| clean-safe→attacked-unsafe transitions | `15/23` |
| 正式分类 | `p0b_blocked_insufficient_clean_baseline` |

问题不是 transition 太少，而是 clean baseline denominator 没达到事前门槛。因此这 15 个 pair 可以做
固定的探索性 signal subset，不能被后验称为确认性 attack population。

### 2.2 Execution-only action envelope

| 指标 | 结果 | 含义 |
|---|---:|---|
| clean strict-success retention | `22/23 = 95.7%` | 通过冻结的 `0.80` gate |
| attacked+defended valid episodes | `48/48` | 无 missing/invalid |
| final commands inside L2 envelope | `17,828/17,828` | 该切片 complete mediation 成立 |
| projected actions | `13,108/17,828 = 73.5%` | intervention 使用频繁 |
| projection L2 | median `0.002853`, P95 `0.008507`, max `0.039266` | 修改幅度整体较小 |
| full-population strict success without cost | `26/48 = 54.2%` | task utility 仍有明显损失 |
| full-population cost/collision unsafe | `1/48 = 2.1%` | 仍有一个 coarse unsafe |
| signal subset defended cost/collision | `0/15` | 未防御的 `15/15` 降为 `0/15` |
| signal subset recovered strict success | `8/15 = 53.3%` | 只恢复一部分任务 |
| signal subset residual contact proxy | `11/15` 高于 clean | 不能声称完整物理安全 |

正式分类：

```text
exploratory_attacked_defended_complete_not_confirmatory
```

允许的论文表述：在固定 simulator workload 上，exact execution-time projection 提供强探索性低层风险
缓解证据，并基本保留 clean utility。

不允许的表述：

- 已确认一般攻击防御有效；
- Intent-only、Full ProofAlign 或 Dual 已得到验证；
- contact、joint、force 或连续动力学意义上的完整物理安全；
- 跨 task、seed、hardware 或实时部署可推广。

机器来源：

- [`terminal summary`](../experiments/saber_integrity_action_envelope_terminal_summary.json)
- [`paper tables`](../experiments/action_envelope_paper_tables.json)
- [`failure taxonomy`](../experiments/action_envelope_failure_taxonomy.json)
- [`generated result report`](paper/action_envelope_results.md)

## 3. 工程状态

当前工作树只保留：

- Python minimal integrity core、action-envelope/SABER 主线 adapter 和精简 LIBERO runtime；
- Lean `IntegrityCore`；
- 当前 runners、artifact/preregistration generator 与 resource-isolated launch 检查；
- R0–R9 compact protocol/status audit chain；
- terminal summary、paper tables、taxonomy 和 preregistration；
- 主线测试、方法/实验/环境/论文文档。

CTDA v1/v2、AEGIS、EDPA、Phantom、SAFE/FIPER、旧 LIBERO runner、toy example、旧 handoff、重复状态文档
和不参与当前结论的结果已从工作树删除，可从 Git 历史恢复。

完整 R9 raw episode bundle 约 71 MiB，只在实验机本地保留。远端只保存代码和 compact result；缺少
raw bundle 的远端 clone 会明确 skip raw-derived consistency check。

当前实现缺口：

1. Python fast checker 与 Lean `IntegrityCore` 尚无 machine-checked refinement/equivalence；
2. confirmatory producer/victim 和四臂 shared runner 尚未冻结；
3. fixed-trace exporter 尚未冻结；
4. trusted observer、continuous dynamics、hardware sensing/actuation 仍在范围外或 TCB 内；
5. 新实验的 GPU、wall-clock、存储和 fresh-root readiness packet 尚未完成。

本轮主线清理后的验证结果：

- Python：`76 passed`；
- Lean：`lake build ProofAlign` 成功；
- R9 action-envelope paper artifact `--check` 成功；
- confirmatory preregistration `--check` 成功；
- 27 份保留的 experiment JSON 均可解析；
- retained module import、Python compile、Markdown 本地链接和 `git diff --check` 均通过。

## 4. 下一步跑什么

下一项正式 rollout 是 **独立确认性 attack foundation**，不是继续 R9，也不是直接跑四臂 defense。

### 规模

- 60 个与 P0b 不重叠的 base pair；
- 两个 seed block：`(env=43, policy=11)` 和 `(env=59, policy=17)`；
- 120 个 unit；
- 每个 unit 跑 clean/attacked VLA-only，共 `240` episode。

### Gate

必须同时满足：

- `240/240` terminal valid；
- clean-eligible unit `>=52`，覆盖 base pair `>=26`；
- transition unit `>=26`，覆盖 base pair `>=18`；
- transition rate `>=0.50`；
- 100,000 次 base-pair cluster bootstrap 95% lower bound `>=0.30`。

任一 gate 失败即写 terminal nonpass，不补样、不换 pair、不进入 defense。

## 5. 分阶段规划

### M0：终态收口

状态：**本轮完成**

- 清理废弃方案，只保留主线；
- 保存本地 R9 raw evidence；
- 保留远端所需 compact protocol/result；
- 自动生成论文表和 failure taxonomy；
- 把当前结果、claim boundary 和规划集中到 canonical 文档。

### M1：no-outcome execution readiness

状态：**当前下一工作**

1. 实现并冻结 60-record producer、validator 和禁止 replacement 规则；
2. 实现 confirmatory VLA-only victim runner；
3. 实现四臂 shared runner 和 fixed-trace exporter；
4. 绑定 checkpoint/source/config/camera/runner/population/validator digest；
5. 补 fast checker/Lean core equivalence evidence；
6. 冻结 GPU、CPU/RAM、wall-clock、episode、磁盘和 abort 预算；
7. 定义 fresh roots，完成 unit、Lean、dry-run 和 artifact validator；
8. 形成只读 readiness packet，再单独请求 GPU 执行授权。

M1 不产生新 outcome，也不自动启动 GPU。

### M2：确认性 attack foundation

状态：**等待 M1 与授权**

按第 4 节运行 `240` 个 VLA-only episode。只有所有 gate 通过才继续。

### M3：四臂 fixed-trace/shadow

状态：**等待 M2 pass**

四臂读取 byte-identical proposal trace，`dispatch=false`，检查 unique catch、overlap、Dual additional
catch、unknown/block、latency 和 checker equivalence。失败则 terminal stop。

### M4：四臂 clean closed loop

状态：**等待 M3 pass**

120 unit × 4 arm，共 `480` clean episode。主要 gate：

- `480/480` valid；
- Dual strict-success retention `>=0.80`；
- Dual−VLA paired bootstrap 95% lower bound `>=-0.10`；
- Dual phase completion `>=0.80`；
- Dual deadlock `<=0.05`；
- unknown/unbound primary evidence `=0`。

失败则不执行 attacked stage。

### M5：四臂 attacked closed loop

状态：**同时等待 M2 与 M4 pass**

120 unit × 4 arm，共 `480` attacked episode。报告 full population 和预定义 signal subset，并分别分析
task success、cost/collision、contact、joint-limit、force、risk exposure 和 intervention magnitude。

Dual composition 必须同时优于 Intent-only 和 Execution-only；两项比较使用 Holm
family-wise `alpha=0.05` 与 100,000 次 paired base-pair cluster bootstrap。

### M6：外部 baseline 与论文冻结

状态：**M5 后决定**

- 用同一 proposal、population、oracle、fallback、资源和 endpoint 接入至少一个 terminal baseline；
- 从机器 artifact 生成最终表、区间、消融和 failure cases；
- 保留探索性结果和限制，不隐藏 negative/nonpass；
- 根据四臂结果收缩或保留论文主张。

## 6. 总资源上限

所有 gate 都通过时，主线最多包含：

- confirmatory VLA-only：`240` closed-loop episode；
- four-arm clean：`480`；
- four-arm attacked：`480`；
- 合计 `1,200` closed-loop episode，另加无 dispatch 的 Stage A。

正式运行前必须用 smoke 实测吞吐并冻结 GPU-hours、wall-clock、磁盘和 raw retention，不能直接按历史
运行时间外推。

## 7. 当前立即行动

1. 完成本轮清理后的 Python、Lean、artifact、link 和 import 验证；
2. 将清理后的代码与 compact results 同步远端，R9 raw 继续留本地；
3. 开始 M1：先做 producer/victim/shared-runner/fixed-trace 的 no-outcome 实现；
4. 形成 readiness packet；
5. 获得授权后再运行 M2。

项目接下来要回答的三个核心问题是：

1. 攻击信号能否在独立 population 上确认？
2. Intent–Plan 与 Plan–Execution 是否各有独立因果贡献？
3. Dual 能否在保留 clean utility 的同时产生统计上可信的组合增益？
