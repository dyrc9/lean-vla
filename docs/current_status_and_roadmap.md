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
simulator virtual-brake engineering validation”的系统论文。v13 在 outcome-informed 的45-pair
population 上通过了 clean task-success non-inferiority，但 attacked 阶段没有建立总体 safety
efficacy。v14 development 把 monitor 扩展到全7关节双侧并显著增加风险覆盖，但以17次deadlock和
未通过的任务效用非劣门为代价。同 schedule shadow-only 对照进一步确认：首次 Full trigger 前
20,963 个 policy steps、动作摘要、风险侧和14侧余量完全一致；授予 brake authority 后，L2
crossing 从1,442降至0，但增加17个deadlock并少7个任务成功。该对照仍因预注册
`0.002 rad` shadow prediction/execution门被`0.004651 rad`超过而保持 calibration non-pass，
所以它是 outcome-disclosed causal diagnostic，不是确认性一般防御证据。项目仍不支持
actuator-only recovery、真实部署或物理安全证明。随后冻结的trigger-rich四基线实验把机制比较
扩展到12个development环境和18个未见task/init qualification环境。held-out中predictive相对
shadow将crossing从`818`降至`0`、低余量侧值从`1884`降至`0`；reactive虽几乎阻止crossing，仍有
`402`个post-step低余量值。资格实验因252条low-dose lane中2条意外crossing而保持注册non-pass，
不能改写为总体pass；其余完整性、核心机制和时限gate均通过，但48.41% predictive lane deadlock、
2.045%的50ms deadline miss和约`8049`最大constraint force仍是主要系统代价。

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
| v13 clean outcome Fresh3 | engineering utility pass | 180/180 complete；VLA/Execution/Semantic/Dual success `36/36/32/31`，两个冻结 `−0.20` paired non-inferiority gate 通过；仅1次 trigger、0 intervention、1 deadlock |
| v13 clean shadow-only | causal-path ablation complete | 180/180 complete；任务与 official unsafe 和 full brake 相同；唯一 full-brake case 少执行250 steps并避免225个 joint-limit steps，但样本只有1例 |
| v13 attacked scale45 | data complete / efficacy non-pass | 180/180 checksum-bound episodes；攻击改变180/180首块；2次 trigger、1次 active intervention、随后1次 deadlock；Dual unsafe nonincrease 描述性 gate 未过 |
| v13 attacked shadow-only | causal tradeoff complete | 180/180 complete；full/shadow仅1条episode结局不同；full避免7个joint-limit steps和23个低余量steps，但把shadow的成功任务变成deadlock失败 |
| v14 all-joint clean development | data complete / calibration and utility non-pass | 180/180、每步7关节×双侧审计；29 triggers、12 interventions、17 deadlocks；L2实际低余量/crossing均为0，disabled arms为3306/1455；严格`1e-9 rad`全侧校准门和两条描述性效用非劣门未过 |
| v14 same-schedule shadow-only | registered calibration non-pass / causal identity diagnostic complete | 180/180；90个disabled-arm episode逐步完全一致；首次Full trigger前20,963 steps的action/risk/margin完全一致；Full/Shadow L2低余量为`0/2733`、crossing为`0/1442`，task success为`60/67`、deadlock/unknown为`17/0`；注册`0.002 rad`校准门未过，不改写为pass |
| v14 trigger-rich stress development | registered identity non-pass / threshold diagnostic complete | 12环境、504 stress lanes、2016 baseline lanes；Predictive/Shadow crossing为`0/528`、低余量为`0/1236`，Reactive低余量264；all-side max identity error `0.04755 rad`未过`0.001`门，但35,280个侧值在0/0.15/0.16/0.22/0.30阈值分类分歧均为0 |
| v14 held-out stress qualification | registered low-control non-pass / core axes complete | 18个未见task/init、756 stress lanes、3024 baseline lanes；Predictive/Shadow crossing `0/818`、低余量`0/1884`，Reactive crossing/低余量`2/402`；唯一失败gate是2条low negative-control crossing；active contact、identity、containment、availability和timing gate通过，整体仍不改写为pass |
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
8. v13 clean utility、shadow-only causal-path ablation 与 attacked scale45；
9. attacked 中唯一 active guard 的一步 containment、下一步 deadlock，以及2016个全机械臂
   joint-limit exposure steps 对单 joint-1-upper monitor 的 coverage failure；
10. deployment perception、约 `10k` constraint force、无硬件证据等限制。
11. v14 全关节 clean development 的 coverage 增益、零L2低余量/crossing、17次deadlock、
    task-utility non-pass 与全侧 calibration non-pass。
12. v14 同schedule shadow-only 的exact pre-divergence identity、`1442 -> 0` crossing containment、
    `67 -> 60`任务成功与`0 -> 17` deadlock代价，以及注册 calibration non-pass。
13. v14 trigger-rich development四基线比较、注册all-side identity non-pass与零threshold-classification
    disagreement诊断。
14. v14 held-out stress qualification的唯一low-control non-pass、核心机制/时限分轴结果、48.41%
    deadlock、2.045% deadline miss、active contact-capacity零异常和高constraint-force限制。

论文不得将 v11/v12 写成 first-hit prevention、一般 attacked-defense efficacy、task-preserving
recovery 或完整物理安全。

## 4. 下一里程碑

### G0：仓库与证据收口

- 保持 README、本页、论文就绪度表和最终图表的 v12.38 状态一致；
- 将 v12.37/v12.38 checksum 与 summary 重算接入 `make check` / `scripts/check_all.sh`；
- 任何新实验都使用新 output root 和新冻结 protocol，不覆盖历史 artifact。

### G1：独立 task-outcome protocol（已完成）

v13 clean、shadow-only 与 attacked 三阶段均已完成。clean 180条通过冻结 utility gate；attacked
180条在机械分析修正后数据完整。原 `pilot_evidence.json` 因 nested hook 顺序保留
`incomplete`，终态脚本从原 checksum-bound episodes 重建 v13 metrics，不修改 rollout、
episode、manifest 或 checksum。修正后的结果仍是 efficacy non-pass，而不是把分析 bug 当作方法成功。

### G2：多关节风险效应 successor

当前最优先的科学 successor 必须同时关闭 coverage 与因果识别：

- exact attacked shadow-only 已完成：full/shadow前236个policy steps和首次risk action/state/
  unguarded prediction完全一致；只有该episode结局不同；
- 全关节 clean development 已完成：每步14个 joint-side margins 全量记账，29次trigger覆盖
  joint3/5/6 upper；L2实际低余量/crossing为0，但17次deadlock导致utility gate未过；
- 同schedule全关节shadow-only已完成：90个disabled-arm episodes逐步完全一致，73个无trigger
  L2 episodes结局完全一致；17个首trigger episodes在分叉前action/risk/margin零误差。Full相对
  Shadow避免2733个低余量侧值和1442个crossing，但增加17个deadlock并少7个任务成功；
- 注册shadow校准门仍non-pass：最大prediction/execution逐侧误差`0.004651 rad`超过
  `0.002 rad`门。后验诊断只分离“causal identity complete”，不修订注册结论；
- trigger-rich generalized-force / near-limit stress development已完成；注册all-side identity门未过，
  但所有风险阈值分类相同，四基线描述性差异已冻结；
- 新task/init与environment seed的outcome-blind mechanism qualification已完成；唯一失败gate是2条
  low negative-control crossing，整体保持non-pass，核心mechanism/timing轴单独完整；
- 下一步不再重标low dose或追逐同一gate，而是冻结独立task-outcome utility qualification，并将
  deadlock recovery/backup controller作为明确因子；
- 主终点为 crossing、minimum margin、joint-limit exposure、official unsafe、task success、
  deadlock/recovery 和 latency，禁止用 development outcome 选择确认集。

### G3：论文与复现包

- 以系统论文而非“全面防御成功”组织正文；
- 固化图表生成、artifact inventory、环境版本和一键检查输出；
- 主文同时报告正结果、non-pass、效用代价和 claim boundary。

### G4：部署与硬件后继

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
.venv/bin/python scripts/freeze_predictive_virtual_brake_v13_attacked_terminal.py \
  --check
.venv/bin/python scripts/freeze_predictive_virtual_brake_v13_attacked_shadow_terminal.py \
  --check
.venv/bin/python scripts/freeze_predictive_virtual_brake_v14_multijoint_clean_terminal.py \
  --check
.venv/bin/python scripts/freeze_predictive_virtual_brake_v14_multijoint_shadow_only_terminal.py \
  --check
.venv/bin/python scripts/freeze_predictive_virtual_brake_v14_multijoint_shadow_only_diagnostic.py \
  --check
.venv/bin/python scripts/freeze_v14_multijoint_stress_development_terminal.py --check
.venv/bin/python scripts/freeze_v14_multijoint_stress_qualification_terminal.py --check
bash scripts/check_all.sh
```

所有 validation 命令只读已有冻结结果，不授权新的 policy dispatch、simulator outcome rollout 或
结果后参数修改。
