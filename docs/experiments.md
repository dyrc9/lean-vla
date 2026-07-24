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
