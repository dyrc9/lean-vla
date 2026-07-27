# 论文就绪度评估

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
| Support-conditioned successor | clean 已授权、等待 GPU | 45 pairs / 90 units / 360 episodes；M2 subset 30/67=`44.78%`；one-shot launcher 等待两张 `<1024 MiB` GPU |

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
3. 已冻结 45-pair support-conditioned fresh2；两张 GPU 合格后执行 360 clean episodes；
4. 不为 affordance suite 虚构 part geometry，也不从 M2 artifact 伪造 fixed-trace shadow；
5. support-conditioned clean gate 通过后，才另行授权同一支持集的 attacked exploratory stage；
5. 保持 E7 camera/deployment perception 为独立未关闭 claim，不混入 benchmark 结果；
6. 分别报告 safety、utility、coverage、unknown 和 deadlock，不扩大到 physical safety。

当前已经执行这一路线回退：论文使用“双层对齐 + deterministic privileged-geometry task-FSM +
analytic checker”的窄版本。raw π0.5 selector 与 semantic prompt control 的失败应作为结果如实报告，
不能为了保留 learned hierarchy 叙事而放宽 gate。
