# 当前进展与执行计划

## 1. 2026-07-24 对齐结论

主线已进一步改为：

```text
L1: TrustedIntent -> frozen SemanticSubtask -> checked ActionBlock
L2: authorized ActionBlock -> exact dispatch/receipt/observed effects
```

顶层故事仍是 Intent→ActionBlock 与 ActionBlock→Execution 双层对齐。`SemanticSubtask` 是 L1 的当前
结构化机制，不是新的第三层，也不是恢复旧的自由文本 PlanWitness。它来自有限 task graph，在动作生成前
成为显式 π0.5 输入并与返回 block 绑定；第一版不训练模型。其行为控制力必须实验测量，不能从 prompt
wiring 本身推出。

当前第一关键 blocker 变成：

> 当前冻结 π0.5/PaliGemma 或其他零训练 selector 能否稳定选择合法 `Z_t`，以及 `Z_t` 条件化是否改善
> ActionBlock 的可解释约束而不破坏 clean utility？

当前公开 OpenPI 只开放 flow-matching action head，因此需要 consumer-side inference wrapper；不能把
论文版 π0.5 的 semantic head 当作已存在的本地接口。

`Z_t` 的 trusted-input boundary 已落地为双视图：

- semantic branch 只读取 trusted `T/O_t^T`，并 allowlist task source、observation tap、secure split、
  selector checkpoint/config；
- 外部 prompt、被注入图像和 history 只属于 action-policy branch；
- `Z_t` artifact 绑定合法 frontier、state epoch 和完整 semantic context；
- hardened action prompt 只从 trusted `T + Z_t` 固定编译；
- 当前只覆盖 secure split 后的数字/软件注入，不覆盖同时欺骗 trusted tap 的分叉前物理光学攻击。

实现与边界见 [`trusted_semantic_boundary.md`](trusted_semantic_boundary.md)。

2026-07-24 零训练 GPU pilot 的当前结论：

- motion-level `approach/grasp/...` 初始选择为 `0/4`；
- π0.5 skill-level `pick_up/move/place/...` 初始选择为 `4/4`；
- 单条轨迹阶段切换名义为 `3/5`，两个错误均在人工标签边界；
- 不同 `Z_t` prompt 会改变 ActionBlock，但差异很小，不能视为可靠 action control。

详见 [`semantic_subtask_pilot.md`](semantic_subtask_pilot.md)。

动作选择已经形式化为 `Z_t` 先固定、π0.5 后提议、consumer 再过滤/小幅投影/复检。确定性 best-of-K
选择边界和单元测试已实现于 `semantic_action_selection.py`；它尚未接入在线 LIBERO runner，当前 runner
仍是单 chunk、clip、执行前五步。

可信 semantic context、`Z_t` artifact、外部攻击视图隔离和固定 prompt 编译已实现于
`semantic_trust.py`；相关 trust-boundary 与 action-selection 定向测试共 22 个通过。下一工程步骤是把
这两个边界接入 LIBERO runner，并实现 `Z_t -> executable prefix` local checker。

## 2. 已完成

- ActionProposal 已成为原生 ActionBlock，不再含 `plan_digest`；
- 新增 `ActionBlockAssessment` 和 `BlockExecutionContract`；
- authorization、dispatch receipt、execution evidence 已绑定 block/assessment/contract digests；
- shared four-arm runner 改为 Intent–Action / Action–Execution 两个开关；
- Lean core 改为 action-block execution transaction semantics；
- L2 支持 exact command、one-use authorization、freshness、expected/forbidden effects、phase gating；
- P0b/R9 历史结果及冻结协议仍保留审计边界。

## 3. 历史实验怎么复用

完整的逐字段映射、post-hoc replay 规则和 confirmatory 禁止项见
[`experiment_reuse.md`](experiment_reuse.md)。

### P0b

可直接复用：

- 原始攻击机制和 threat model；
- clean/attacked pairing；
- valid episode 与 clean-eligible denominator 逻辑；
- transition signal 和缺失/替换规则。

不可复用：

- 新 L1 assessment；
- 四臂 causal effect；
- confirmatory denominator（`23 < 26`）。

### R9 Execution-only

可直接复用：

- action envelope/intervention；
- exact dispatch 和 episode ledger；
- cost/collision、strict success、contact proxy；
- clean retention 和 attacked recovery 的 exploratory baseline。

需要迁移：

- 将旧 transport/audit 映射为 ActionBlock/contract/receipt v3；
- 不把旧 effect verdict 当作完整物理安全；
- 不把 R9 称为 Dual。

## 4. 当前 blocker 排序

1. **Runtime schema/integration**：trusted semantic context、exact `Z_t`、prompt、candidate、
   executable prefix、assessment 与 contract 的端到端绑定；
2. **Local checker qualification**：`Z_t -> ActionBlock` 的 false-allow、coverage 和 OOD；
3. **Zero-training selector qualification**：合法率、阶段合理性、稳定性、margin 和 unknown；
4. **Lean/runtime evidence refresh**：semantic digests 接入后重新生成 fixed-trace、theorem/source digest 和
   scoped Python-equivalence evidence；
5. **资源预算**：selector/checker 与四臂 latency/GPU memory；
6. **observer adequacy、clean commit binding 和 M2 execution authorization**。

M1 producer/victim、shared runner、fixed-trace exporter、validator 和 outcome-blind ActionBlock prefix adapter
已经完成；adapter 只读取 policy-call audit 与实际消费的 raw actions，不读取 reward/success/cost/collision，
也不伪造未执行的 chunk tail。

## 5. 下一里程碑

### M1A：component closure

- 全部 Python/Lean tests 通过；
- 新 ActionBlock fixed-trace smoke artifact 当前；
- M1 readiness validator 不再引用 PlanWitness；
- frozen legacy protocol 明确标注 audit-only，v3 schema 不改写历史结果，semantic-bound successor 使用
  新版本 schema。

### M1B：semantic hierarchy no-outcome qualification

- 冻结 task graph、subtask vocabulary 和 prompt template；
- 探测当前 checkpoint 的 PaliGemma constrained selection；
- 冻结 `unknown`/margin 规则；
- 只做离线 observation/action probe，不看 M2 outcome。

### M1C：local checker no-outcome qualification protocol

- 冻结训练/qualification split；
- 冻结 finite atom vocabulary；
- 冻结 threshold、abstention 和 worst-group；
- 只允许 offline transition label，不看 M2 victim outcome。

### M1D：semantic runtime 与 Lean identity closure

- 把 semantic context、`Z_t`、trusted prompt 和 executable-prefix digest 接入 ActionProposal/assessment/
  execution contract；
- projection/intervention 后重新 assessment、contract 和 authorization；
- `K=1` fixed-trace 四臂共享 exact proposal；`K>1` 只作为另行冻结的扩展；
- 更新 Lean source binding、关键 theorem inventory 和 scoped Python-equivalence artifact；
- 完成 zero-dispatch fixed-trace、latency/resource smoke 和 fresh-root validator。

### M2：240 episode

仅在用户/项目负责人明确授权 GPU rollout 后运行。先完成 VLA-only attack foundation，gate 通过后再跑
fixed-trace 和 480+480 四臂。

## 6. 当前可声称与不可声称

可声称：

- 双层问题已定义在 action-only VLA 可观察接口上；
- L2 的有限 transaction semantics 已由 Lean 检查；
- P0b/R9 给出强探索性攻击/Execution-only 信号；
- component runner 可验证两层开关和 digest identity。

不可声称：

- L1 assessor 已对真实 π0.5 资格化；
- frozen semantic selector 已达到可用标准；
- secure split 或 trusted camera tap 已在真实部署环境得到硬件级 attestation；
- 一般防御有效；
- Dual 已验证；
- 完整物理安全；
- Lean 证明 learned predictions 或真实世界。

## 7. 立即推进顺序

具体接口、测试、artifact 和停止条件见
[`implementation_and_experiment_readiness.md`](implementation_and_experiment_readiness.md)。执行顺序固定为：

```text
C1 semantic digest schema
  -> C2 trusted prompt/policy wrapper
  -> C3 executable-prefix local checker
  -> C4 post-intervention rebind
  -> C5 shared-trace/Lean evidence refresh
  -> E1 selector snapshot qualification
  -> E2 local-checker qualification
  -> E3 no-dispatch four-arm
  -> authorized no-attack smoke
  -> M2
```

在 C1–C5 与 E1–E3 完成前，不运行新的 efficacy outcome。若 zero-training selector 不通过，允许按预注册
回退到 deterministic task-FSM L1；不允许用 M2/four-arm outcome 反向调整 selector/checker。
