# 当前状态与路线图

最后更新：2026-07-31。

本页是项目状态、可主张结论和下一里程碑的唯一简明入口。详细实验时间线保留在
[`progress_and_plan.md`](progress_and_plan.md)，论文结果图和 Lean 边界见
[`paper/final_results_figures.md`](paper/final_results_figures.md)。

## 1. 当前结论

ProofAlign 已形成可复现的研究原型，核心贡献是：

1. 把 action-only VLA 的完整性分成 `Intent -> ActionBlock`（L1）与
   `ActionBlock -> Execution`（L2）两个可独立审计的断点；
2. 用 Lean 固定 authorization、freshness、exact dispatch、receipt/effect binding 和
   phase-gating 的有限事务语义；
3. 在共享四臂 runner 中报告机制收益、coverage/deadlock 与任务效用，而不把 unknown 或停止
   隐藏进单一“安全成功率”；
4. 保留所有冻结 gate 的 non-pass 和结果后 successor，使失败机制可以复算。

当前证据足以支持“形式化执行事务 + 可审计失败定位 + containment–utility tradeoff +
simulator virtual-brake engineering validation”的系统论文。它不支持一般 defense efficacy、
clean non-inferiority、actuator-only recovery、真实部署或物理安全证明。

## 2. 证据状态

| 证据线 | 终局 | 允许的结论 |
|---|---|---|
| L1 component qualification | mixed | deterministic privileged-geometry selector、analytic checker 与 observer 在冻结 benchmark corpus 上通过；raw π0.5 selector 和 semantic prompt behavioral control 未通过 |
| M2 confirmatory attack foundation | non-pass | 240/240 valid，transition `39/86=45.35%`，低于预注册 `50%` gate |
| support45 四臂 clean | non-pass | 360/360 valid；旧 Semantic-only/Dual 各 `0/90`，Dual deadlock `88/90`；attacked stage 未授权 |
| risk-selective L1 v10 | mixed/negative | nominal-safe block exact passthrough，deadlock 明显下降；未建立 non-inferiority 或 safety efficacy |
| typed L2 containment v11 | mechanism pass / efficacy mixed | held-out scale45 中 trigger 后 dispatch 为0，joint-limit burden 明显下降，同时存在显著 clean utility 代价 |
| recoverable/predictive L2 v12.1–v12.6 | mechanism strengthened / liveness non-pass | contract、snapshot、fresh prefix、typed recovery 和 integrated route 已关闭；首次 simulator-integrated formal 的 fresh authorization 为 `6/9` |
| hard virtual joint stop v12.37 | development pass | seeds `10509/10510`：`10/10` exact advances，最低 actual margin `0.1661929 rad` |
| frozen held-out v12.38 | held-out pass | seeds `20509/20510`：`10/10` exact advances，最低 actual margin `0.1661158 rad` |
| deployment perception E7 | blocked | 当前数据缺7类 supervision，不能资格化 camera-only deployment |

v12.37/v12.38 两个 split 的 guard action identity、beam configuration identity 和
prediction/execution equality 均通过，warning、crossing/contact saturation、live dispatch、
typed recovery 和 outcome read 均为0。最大 target-DOF generalized constraint force 分别约
`9999` 和 `9985`，所以该正结果只能称为 hard simulator virtual-joint-stop 机制证据。

## 3. 论文主线

正文应按以下顺序报告，不能用后继结果覆盖早期冻结结论：

1. 双层问题定义、可信/不可信双视图与 Lean transaction semantics；
2. L1 selector、action-conditioning、checker、observer 和资源资格结果；
3. M2 原 `50%` confirmatory non-pass；
4. full-population geometry support failure 与 support45 clean deadlock；
5. risk-selective L1 与 v11 containment–utility tradeoff；
6. v12 从 state-safe recovery 到 next-policy-safe recovery 的失败定位；
7. v12.37 development 与 v12.38 frozen held-out virtual-brake 正机制结果；
8. deployment perception、约 `10k` constraint force、无 task outcome 和无硬件证据等限制。

论文不得将 v11/v12 写成 first-hit prevention、一般 attacked-defense efficacy、task-preserving
recovery 或完整物理安全。

## 4. 下一里程碑

### G0：仓库与证据收口

- 保持 README、本页、论文就绪度表和最终图表的 v12.38 状态一致；
- 将 v12.37/v12.38 checksum 与 summary 重算接入 `make check` / `scripts/check_all.sh`；
- 任何新实验都使用新 output root 和新冻结 protocol，不覆盖历史 artifact。

### G1：独立 task-outcome protocol

这是唯一合理的近期科学 successor。必须在运行前冻结：

- 与 v12.37/v12.38 不重叠的 development/qualification workload 与 seed；
- virtual-brake arm、无 virtual-brake control 和必要的 L1/L2 开关；
- task success、time-to-completion、joint-limit exposure、trigger/intervention、constraint force、
  latency、unknown/deadlock 和 official cost/collision；
- clean utility gate、配对估计量、停止规则和多重比较；
- 禁止读取当前 no-outcome ledger 的 reward/success 来选任务、阈值或 guard。

先完成 clean utility gate。未通过时停止，不启动 attacked stage；通过后才可冻结独立 attacked
protocol。

### G2：论文与复现包

- 以系统论文而非“全面防御成功”组织正文；
- 固化图表生成、artifact inventory、环境版本和一键检查输出；
- 主文同时报告正结果、non-pass、效用代价和 claim boundary。

### G3：部署与硬件后继

E7 需要新的 outcome-blind perception supervision 数据，至少补齐 camera intrinsics/extrinsics、
target localization、destination geometry、visibility/occlusion、held/contact state 和独立
qualification split。actuator-only 或真实硬件 recovery 必须另立实验路线，不能从 simulator
virtual stop 外推。

## 5. 当前验证入口

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" \
  lake --dir lean build ProofAlign
.venv/bin/python scripts/run_h3_hard_virtual_joint_guard_beam_pilot_v12.py \
  --validate-results
.venv/bin/python scripts/run_h3_hard_virtual_joint_guard_beam_heldout_v12.py \
  --validate-results
bash scripts/check_all.sh
```

所有 validation 命令只读已有冻结结果，不授权新的 policy dispatch、simulator outcome rollout 或
结果后参数修改。
