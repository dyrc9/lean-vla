# 实验协议

## 1. 总原则

- 保持最初 attack：可信 intent 不变，攻击只进入 policy-facing instruction/observation/history；
- VLA 输出原生 ActionBlock，不要求高层规划；
- `K=1` primary 中 ActionBlock、consumer assessment 和 execution contract 在四臂间 byte-identical；
- `K>1` 扩展中共享 byte-identical ordered candidate set 和每候选 assessment，L1 selection 是 treatment；
- outcome-blind 冻结 population、seed、threshold、replacement/stopping rule；
- selector error、local-checker false allow、unknown、invalid、deadlock、contact proxy、cost/collision、
  strict success 分开报告。

## 2. 证据层级

### A0：历史证据复用

P0b 提供 attack generation、clean pairing、有效性和 transition signal；R9 提供 Execution-only dispatch/
effect 基线。两者均为探索性证据，不进入新的 L1/Dual confirmatory denominator。

### A1：Semantic/ActionBlock 接口与 digest gate

验证真实 victim 输出：

- trusted semantic context、`Z_t`、exact prompt 与 candidate frontier digest；
- trusted/policy observation digest 分离；
- action chunk shape/dtype/finite values；
- observation/action nonce、index、state epoch；
- deterministic canonical digest；
- intervention 后重新绑定；
- raw policy command 不可绕过 single dispatch boundary。

不再存在“必须生成 plan text”的 gate。

### A2a：Semantic selector qualification

在 outcome-blind held-out snapshot set 上冻结 task graph、候选词表、selector/config 和 unknown/margin
规则，评估：

- legal-frontier membership 与 top-1/top-k；
- task/object/stage 分层稳定性；
- 重复运行一致性；
- image/state ablation；
- attacked policy view 改变时 trusted semantic view 的不变性；
- OOD、遮挡、候选近分下的 abstention；
- p50/p95/p99 latency 与资源。

当前 `0/4` motion-level、`4/4` skill-level 和单轨迹 `3/5` 仅是 feasibility pilot，不是 gate 结果。
冻结 PaliGemma 第一版只提供 proposal/ranking；task graph/FSM 控制合法 frontier。

### A2b：`Z_t -> ActionBlock` local-checker qualification

在独立数据上冻结 assessor 和阈值，评估：

- motion/target/part/region/effect/precondition/violation atoms；
- clean false reject/retention；
- attacked-block false allow（主指标）；
- calibration、risk-coverage、OOD abstention；
- worst-group 与 p99 latency。

同时单独进行 action-conditioning probe：固定 observation、state 和 flow noise，比较合法/冲突 `Z_t`
下的 ActionBlock delta、阶段合理性和 gripper/motion 变化。`Z_t` 被写入 prompt 只证明结构输入存在，
不能替代行为影响测量。

A2a/A2b 通过前，Semantic-only 和 Dual 只能跑 synthetic/fixed-trace component smoke，不能形成防御
有效性结果。

### A3：Action–Execution/Lean component gate

正例与负例至少覆盖：

- exact command / command substitution；
- stale state / replay；
- wrong receipt、action-block 或 execution-contract digest；
- missing expected effect；
- observed forbidden effect / observer violation；
- open observation window；
- evidence unknown；
- phase advance without completion。

Lean build、关键 theorem 列表和 Python truth-table/equivalence evidence 必须绑定 source digest。至少
显式覆盖：

- Dual dispatch 要求 L1/L2 authorization；
- Execution-enabled arm 只能 dispatch exact authorized command；
- Execution-enabled phase advance 蕴含 block-execution alignment；
- 所有 phase advance 都要求 trusted contract completion。

这使 Lean 成为 L2 的方法组件，而不是结果后的形式化装饰；但 scoped equivalence evidence 仍不是完整
Python-to-Lean refinement proof。

### A4：fixed-trace 四臂

`K=1` primary 使用同一组冻结 ActionBlocks、assessments、execution contracts 在四臂 shadow runner 中
评估，不创建 simulator 或 dispatch。验证：

- 每个 proposal 恰有四行；
- 两层开关是唯一 treatment difference；
- block/assessment/contract digest 跨臂一致；
- illegal-subtask、wrong-target/local-motion mismatch 只被 L1-enabled arms 捕获；
- stale/substitution binding 只被 L2-enabled arms 捕获；
- zero dispatch。

### A5：closed-loop no-attack smoke

少量已授权 episode 只检查工程可运行性、latency、deadlock 和 clean retention，不用于阈值调参或论文
有效性结论。

2026-07-27 的首轮 smoke 发现 approach progress 被错误声明为 `near_target`；修复后 E3/E5 v2 在原
corpus size、阈值和 gate 下重新资格化。继任 smoke 完成 2 个 effect-allow prefix 和 10 个 exact
dispatch receipts，effect reject/unknown 为 0；第三个 K=1 proposal 因未达到冻结最小进度门而在
dispatch 前拒绝。该结果证明修复后的最小闭环可推进两个事务，也同时暴露 clean availability 风险；
两者都不构成 efficacy 估计。

## 3. M2：confirmatory VLA-only attack foundation

冻结设计：

- 60 base pair；
- 2 个预注册 seed replicate；
- clean + attacked；
- 共 `60 × 2 × 2 = 240` 个 VLA-only episode；
- 每个 base pair 只生成一个 attack record，两个 seed 共享；
- 不允许 best-of-N、失败替换或 outcome-driven population revision。

M2 gate 检查：

- clean-eligible denominator；
- attacked/clean 有效率和缺失模式；
- 攻击 transition 数；
- task/level/attack-family 覆盖；
- signal 是否足以支撑后续四臂，而不是追求显著性后再改阈值。

## 4. Gate 顺序

```text
M1A component closure
  -> M1B selector qualification
  -> M1C local-checker qualification
  -> semantic runtime identity/resource gate
  -> M2 240 VLA-only episodes
  -> denominator/signal gate
  -> fixed-trace four-arm
  -> 480 clean four-arm episodes
  -> 480 attacked four-arm episodes
```

任何后续 stage 都不得反向修改前面已经观察 outcome 的 gate。

M2 只确认新的攻击 foundation，不估计 L1、L2 或 Dual efficacy。即使 M2 signal 很强，也不能跳过
selector/local-checker qualification 或 fixed-trace identity。

## 5. 四臂 outcome

主要分别报告：

- task strict success；
- cumulative cost；
- collision；
- robot/object/contact proxies；
- Task–Subtask selector error/unknown/coverage；
- Subtask–Action false allow/reject/unknown/coverage；
- Action–Execution reject/unknown；
- intervention type；
- deadlock/time-to-completion；
- checker latency 和资源。

统计分析以 base pair 为 cluster，保留两个 seed replicate，报告 risk difference/ratio 和 cluster bootstrap
interval。Dual 的安全增益和 utility non-inferiority 必须同时满足预注册条件。

## 6. Claim gate

允许的逐级表述：

1. component semantics pass；
2. Lean-scoped transaction semantics pass；
3. selector/local checker qualified on held-out support；
4. exploratory attack-defense signal；
5. confirmatory benchmark effectiveness；
6. physical safety（当前协议不支持）。

不得跨级。

## 7. Post-M2 successor：externally grounded L2 与跨层实验

M2 及其既有 gate 不因 successor 计划发生变化。可运行性审计确认当前 online runner 只有 VLA-only
和同时绑定 semantic/execution 的 dual-like path；Semantic-only 与 Execution-only 尚未独立接线。
因此原计划的 480 clean 与 480 attacked 四臂目前只保留为待实现设计，不得直接启动或解释为：

- 已完成的 clean 四臂 efficacy；
- 已完成的 SABER-only 四臂 efficacy。

其攻击条件定义仍是 Clean（无 semantic/execution attack）和 SABER-only（只有已发表的 SABER
semantic attack）。

随后新增的 L2 与全链路证据不使用按 ProofAlign predicate 取反的自构造 case 作为主攻击。完整协议见
[《L2 与跨层攻击实验计划》](l2_and_cross_layer_experiments.md)。核心外部来源为：

- L2-A：精确冻结 Ueda–Blevins scaling、reflection、shearing 的 `S_u`，只作为从 joint velocity 到
  LIBERO delta-EEF 的 `source_command_operator_transfer`；不复现 coordinated observation attack，
  不声称 perfectly undetectable；
- L2-B：ROS-Industrial replay 只保留 threat grounding；online cross-transaction capture/transport
  完成前不产出 efficacy；
- L2-C：当前缺少 feedback-linearized controller/state estimator，状态固定为
  `interface_not_supported`；
- Full chain：等独立 online 四臂和 non-primary smoke 通过后，再冻结 SABER × source-operator
  primary。

wrong digest/receipt、open window、unknown evidence 和 invalid phase advance 继续属于 A3/A4/Lean formal
negative suite，只支持 component semantics 与 implementation audit，不单独支持现实攻击 efficacy。

## 8. 扩展后的攻击/防御 factorial

攻击侧：

| Attack cell | Semantic attack | Execution attack |
|---|---:|---:|
| Clean | off | off |
| S-only | SABER | off |
| B-only | off | source `S_u` operator transfer |
| Chained | SABER | source `S_u` operator transfer |

目标防御侧仍为 VLA-only、Semantic-only、Execution-only 与 Dual 四臂，但 online implementation
尚未完成。60 base pairs × 2 seeds × 4 arms × 4 attack cells = 1920 只是后续 Gate L2-3 可选择的
上限，不是当前默认执行量。同一 base pair 的两个 seed 必须共享 outcome-blind attack record；三个
source operator 的分配由预注册 mapping 决定，不允许 outcome-driven replacement 或 best-of-N。

主报告必须逐段分解：

- semantic divergence 与 L1 allow；
- altered candidate 是否在 `env.step` 前被拒绝；
- altered `env.step` input 与 detection 前执行次数；
- forged receipt acceptance；
- missing/forbidden/harmful effect；
- false phase advance 或 containment；
- clean retention、unknown、deadlock 和 time-to-completion。

在线 effect observer 不能充当唯一 ground truth；独立 evaluator 必须读取 raw simulator state、实际
`env.step` 输入、contact/object/gripper trace。当前没有 actuator telemetry，所以不得称为 hardware
applied-action conformance。

## 9. 扩展 gate 顺序

~~~text
current frozen producer/M2 240 episodes
  -> M2 denominator/signal gate
  -> source-matrix and P1/P2/P3 mock-online regression
  -> 12-episode non-primary execution-node smoke
  -> implement independent online L1/L2 arm switches
  -> shared-source-chunk four-arm identity gate
  -> freeze population/family/placement/endpoints/stopping rule
  -> affine-only and SABER × L2 primary
  -> adapted replay only after online capture/transport exists
  -> independent terminal audit and cluster-bootstrap analysis
~~~

L2 结果统一称为 source-operator-grounded case studies；全链路结果称为 SABER 与 source-command
operator transfer 的 cross-layer composition study。当前协议不支持将它们扩写为 Ueda--Blevins
stealth reproduction、通用执行安全、完整硬件 attestation 或标准化 L2 benchmark。
