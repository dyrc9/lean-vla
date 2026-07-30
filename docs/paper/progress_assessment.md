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
> [`../v12_policy_prefix_shadow_checkpoint.md`](../v12_policy_prefix_shadow_checkpoint.md)。

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
