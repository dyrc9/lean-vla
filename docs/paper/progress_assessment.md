# 论文就绪度评估

> 2026-07-29 更新：本页原 support45 评估保留为历史诊断；最新 outcome checkpoint 已推进到
> v11 unchanged-method held-out scale45。终局结果和不可覆盖边界见
> [`../v11_terminal_checkpoint.md`](../v11_terminal_checkpoint.md)，后继优化见
> [`../v12_recoverable_alignment_plan.md`](../v12_recoverable_alignment_plan.md)。v12 首轮
> no-outcome 资格结果见
> [`../v12_qualification_checkpoint.md`](../v12_qualification_checkpoint.md)，多关节 typed
> recovery 后继见
> [`../v12_recovery_successor_checkpoint.md`](../v12_recovery_successor_checkpoint.md)，controller
> shadow 后继见
> [`../v12_policy_prefix_shadow_checkpoint.md`](../v12_policy_prefix_shadow_checkpoint.md)，simulator
> integrated non-pass 与结果后优化见
> [`../v12_simulator_integrated_recovery_checkpoint.md`](../v12_simulator_integrated_recovery_checkpoint.md)。

| 模块 | 就绪度 | 证据/缺口 |
|---|---|---|
| Threat model | 高 | 沿用原始可信 intent + attacked policy view |
| 双层问题定义 | 高 | Intent→ActionBlock 与 ActionBlock→Execution 的 estimand 已稳定 |
| Trusted semantic boundary | 中高 | context/allowlist/prompt/double-view binding 已接入 opt-in online path；尚无硬件级 trusted tap |
| Semantic selector | benchmark 中高 / deployment 低 | raw π0.5 未通过；deterministic privileged-geometry FSM 160/160，通过 unknown fail-closed |
| Action conditioning | 低 | E2 未通过，semantic prompt 不作为独立 safety control |
| Local ActionBlock checker | benchmark 中高 / deployment 低 | E3 v2 analytic corpus 通过；approach progress 与 near-target 已分离；camera perception supervision 尚不足 |
| ActionBlock runtime schema | 高 | semantic-bound v4 proposal/assessment/contract/authorization/receipt/evidence 已端到端贯通 |
| Action–Execution checker | 中高 | Python tests + Lean semantic core + scoped equivalence；仍无完整 Python refinement 或现实世界证明 |
| Four-arm fixed trace | 高（no-dispatch） | C5/E4 共覆盖 8 proposals × 4 arms，identity gate 通过且 zero dispatch |
| Observer adequacy | benchmark 中高 / deployment 低 | E5 v2 analytic observer 通过并在线接线；camera/contact attestation 尚未资格化 |
| Resource readiness | 高（冻结本机 workload） | E6 v2 10 项 gate 通过，policy/pipeline p99 约 97 ms |
| Source/evidence binding | 已关闭 | E8 clean commit binding 完整，未绑定 semantic scope path 为 0 |
| Closed-loop no-attack smoke | 工程链路通过、活性风险待量化 | 2 个 effect-allow prefix、10 个 exact receipts；随后 K=1 proposal 被 L1 fail-closed |
| M2 confirmatory foundation | 终局 nonpass | 240/240 valid；39/86 transition=`45.35%`，95% cluster CI `[32.93%,57.78%]`；原 50% gate 未通过 |
| Four-arm v4 full population | 结构性不可执行/不可通过 | fresh1 首单元在 dispatch 前 fail closed；15/60 affordance pairs 缺少可信 part geometry，而 clean gate 要求 0 unknown |
| Support-conditioned successor | clean 终局 nonpass | 360/360 valid；VLA-only 61/90、Execution-only 66/90、Semantic-only/Dual 0/90 strict success；Dual deadlock 88/90，attacked 未授权 |
| Risk-selective L1 v10 | mixed/negative | exact passthrough 消除大部分人为动作改写；clean/attacked fresh15 未建立 non-inferiority 或 safety efficacy |
| Typed L2 containment v11 | mechanism pass / efficacy mixed | fresh15 与 held-out scale45 均为 trigger 后旧 policy dispatch 0；scale45 joint-limit burden 显著下降，但 clean Dual−Semantic-only task success `−24.4pp` |
| Recoverable L2 v12.1 | no-outcome preflight pass / efficacy 未测 | 655-case contract gate 与45-pair simulator-reset recovery gate 通过；只覆盖 joint-5 upper-limit，未加载策略或读取 outcome |
| Recoverable L2 v12.2/v12.3 | mechanism strengthened / efficacy 未测 | typed runtime 10/10；多关节210-case覆盖209，actual recovery 209/209；v12.2因full-state identity 201/210保持non-pass，v12.3 trusted-arm identity 210/210通过 |
| Policy-prefix shadow v12.4 | fresh no-outcome mechanism pass / efficacy 未测 | fixed-prefix warm-start 后 repeat 30/30；fresh π0.5 formal 为30次 inference、risk agreement 30/30、nominal allow 15/15、synthetic recovery-required 15/15，repeat 29/30；dispatch/outcome 为0 |
| Integrated recovery v12.5 | fixed-trace composition pass / simulator integration 未测 | 60/60 routes；exact allow 与两类 substitution boundary通过，typed recovery receipt/completion/fresh-state authorization 15/15；policy/simulator/outcome为0 |
| Simulator-integrated recovery v12.6 | mechanism mostly pass / liveness non-pass | 18/18 valid，recovery/receipt/terminal safe 9/9；恢复后 fresh authorization 6/9，formal non-pass。后继 policy-aware 单前缀关闭2/3 known outliers；最后一个 outlier 的156个两阶段组合中65个 recovery-safe，但 seed10509 全部 block；dispatch/outcome为0 |
| Deployment | 未就绪 | E7 缺少7类 perception supervision；所有正向结果仍限于 privileged simulator geometry |

## 2026-07-29 终局判断

v11 scale45 clean/attacked 各180条完整。任务成功率为：

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 32/45 | 27/45 | 31/45 | 20/45 |
| Attacked | 30/45 | 28/45 | 25/45 | 21/45 |

joint-limit step rate 为：

| Condition | VLA-only | Execution-only | Semantic-only | Dual |
|---|---:|---:|---:|---:|
| Clean | 12.794% | 0.116% | 13.980% | 0.110% |
| Attacked | 8.194% | 0.063% | 5.826% | 0.049% |

当前论文足以形成“形式化 transaction integrity + auditable failure localization + containment–utility
tradeoff”的完整系统论文；不足以形成“通用 defense efficacy、first-hit prevention 或完整物理安全”
的强正面论文。v12 若要恢复正面 efficacy claim，必须通过新版本 sparse L1、predictive L2 和 typed
recovery 的独立资格与 fresh gate，不能把 v11 改判。

v12.2/v12.3 已把这条无 outcome 证据从单一 joint-5 upper 扩到7 joints ×双侧：正式210-case
population 覆盖209个，209/209 selected recovery 都在 actual replay 中安全完成，typed
authorization/receipt/replay/fresh-state 边界通过。v12.2 的 full-state identity 201/210 按原 gate
保持 non-pass；v12.3 另行证明 trusted arm `qpos/qvel` identity 210/210，剩余差异是最大
`2.22e-16` 的非机械臂诊断状态。它显著增强恢复机制证据，但没有 policy-prefix、clean utility 或
attacked efficacy，因此不改变上述论文强度判断。

v12.4a/v12.4b 先关闭了 controller-aware shadow 的机械复现缺口：固定的10-step policy prefix 在15个
nominal 与15个 synthetic joint-pressure case 上均给出绑定决策和30/30 risk agreement；
`qacc_warmstart` 后继将 repeat fidelity 从29/30提高到30/30，最大 qpos 误差从
`0.0990581` 降到 `4.44e-16 rad`。v12.4c 随后在资源恢复后完成独立 fresh π0.5 qualification：
30个 observation 各做一次 fresh inference，nominal allow 15/15、synthetic recovery-required
15/15、risk agreement 30/30，repeat fidelity 29/30，所有 trusted restore gate 100%，dispatch
和 outcome read 为0。唯一尾部处于 current-trigger dense-contact synthetic dynamics，两个 replay
仍一致要求 recovery。该结果增强的是 simulator/controller/policy-prefix mechanism，不是 clean
utility、task-preserving recovery 或 attacked efficacy；“完整系统论文、尚非强正面 efficacy
论文”的判断不变。

v12.5 进一步把 fresh screen evidence 与 typed recovery transaction 接成单一 fixed-trace route：
15个 nominal exact authorizations、15个 prefix substitutions、15个 recovery happy paths 和15个
selection-state substitutions 全部符合预期；旧 policy authorization、recovery replay 和 substituted
fresh state 接受均为0。该结果关闭的是 source-digest-bound software composition，使用 in-memory
sink 且不创建 simulator，因此仍不能表述为实际 task-preserving recovery。它让论文的 transaction
integrity 证据更完整，但不改变 efficacy 强度判断。

v12.6 把上述链路放进真实 LIBERO simulator state transition，但继续丢弃所有 outcome。正式9-pair
population 中 nominal allow 9/9，synthetic recovery open/completion/receipt/terminal safe 均9/9，
active MuJoCo warning、joint crossing、policy dispatch 和 outcome read 均为0；恢复后新 prefix
只有6/9 `allow_exact`，其余3个被预测屏幕正确地 `block_replan`，因此按冻结 gate 判 non-pass。
结果后的统一 margin sweep 和每点8次 bounded replan 都未消除全部 outlier。这使论文多了一条
有价值的系统负结果：state-safe recovery 不等于 next-policy-safe recovery；下一版需要
policy-aware candidate objective，而不能降低 gate 或把 block 当作成功。结果后的 policy-aware
branch screen 已在 shortest/all-safe-prefix 两阶段为3个 outlier 中的2个找到双-seed安全候选；
最后一个 case 在冻结13原语×H10库的65个 safe prefixes 中仍为0，进一步把剩余缺口定位为
recovery generator 容量，而非 margin、seed retry 或候选排序。继续扩展的156个两阶段组合中
65个通过原 recovery safety，但在 seed10509 下仍全部 `block_replan`；最好 post-policy
margin 只从单前缀的 `−0.01246` 改善到 `−0.01194 rad`。这进一步排除了简单串联离散原语，
下一步需要诊断具体 joint/direction 后再构造连续或 joint-space generator。随后164个局部连续
blend 全部 recovery-safe，却同样在 seed10509 下 block；最好值仅到 `−0.01187 rad`，而且
164/164 limiting atoms 都是 joint-1 upper。这排除了局部笛卡尔插值，支持下一步做
joint-1-targeted、仍受全局 recovery gate 约束的序列搜索。该 beam 后继把 joint-1 terminal
margin 推到 `0.27944 rad`，96/96 retained trajectories 均 recovery-safe，但 fresh policy
仍全部 block；endpoint 与 post-policy margin 相关仅 `−0.135`。因此剩余缺口已从 recovery
generator 转移到闭环控制时域：需要逐 action safety/replan，而不是更远的 open-loop retreat。
一步 receding-horizon 后继进一步验证了这一点：两条独立 seed lane 都在原 H1 gate 下安全推进
3步，而完整H10始终 block；第4轮 H1 才 fail closed。该结果把零步活性提高到3步，但未通过
预注册5-cycle gate，仍是机制性局部改善而非 task utility 或 efficacy。第4轮再做每 lane
8次 bounded fresh H1 replan 仍为16/16 reject，排除了单一 seed 偶然性，并把下一设计点明确为
predictive `block_replan` 后的显式 recovery escalation。


论文主故事仍是两层对齐，而不是 SemanticSubtask 本身。当前最重要的科学风险集中在 L1：

1. deterministic privileged-geometry FSM 和 analytic checker 的支持集能否覆盖 closed-loop clean trajectory；
2. E2 已表明 `Z_t` prompt 本身几乎不控制动作，因此 L1 主要依赖 post-generation checker；
3. 离线 finite-corpus 的零 false allow 能否外推到新的 M2 attacked ActionBlocks；
4. online effect observer 是否因 evidence unknown/reject 导致 deadlock；
5. camera-only deployment perception 数据和独立 split 尚未到位。

如果 selector/checker 支持集太窄，Dual 会 deadlock；如果阈值太松，攻击 block 会 false allow。如果
`Z_t` 对 action head 几乎没有行为影响，它仍可作为 verifier anchor，但不能被表述为有效的 hierarchical
control。

当前最短可发表路径：

1. 保留 M2 原 50% terminal nonpass，并在正文/附录披露 40% 是 outcome-informed continuation；
2. 报告 fresh1 零 dispatch/零有效 ledger 的 semantic-support fail-closed，不隐藏 full-population coverage failure；
3. 报告 support45 clean 的完整 nonpass：360/360 valid，Dual 0/90 strict success、88/90 deadlock，
   `Dual−VLA=-67.78pp`，cluster 95% CI `[-80.00pp,-55.56pp]`；
4. 把 18/45 pair 的初始 `missing_destination_geometry` 与其余路径最终 K=1/2 mm reject 分开报告，
   并更正“45-pair supported”为“45-pair wrapper-initializable”；
5. attacked stage 因 clean prerequisite 未过而停止，不再追加当前协议 rollout，也不结果后降低 checker
   threshold；
6. 论文转为“可审计双层体系 + coverage/availability failure taxonomy”的诚实系统论文主线；若未来恢复
   efficacy claim，先用独立 split 重做 L1 closed-loop qualification 并另行冻结新协议；
7. 保持 E7 camera/deployment perception 与 MuJoCo `ncon=5000` warning 为明确 limitation，分别报告
   utility、coverage、unknown、deadlock 和 simulator diagnostics，不扩大到 physical safety。

当前已经执行这一路线回退：论文使用“双层对齐 + deterministic privileged-geometry task-FSM +
analytic checker”的窄版本。raw π0.5 selector 与 semantic prompt control 的失败应作为结果如实报告，
不能为了保留 learned hierarchy 叙事而放宽 gate。support45 clean 进一步证明当前窄版本尚不能支撑
positive defense-efficacy claim；可保留的核心贡献是问题分解、形式化 transaction、证据绑定协议和
闭环失败定位，而不是 Dual 优于 baseline。
