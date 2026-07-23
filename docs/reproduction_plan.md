# External Reproduction Plan

更新日期：2026-07-23

SABER P0 R7 未通过 4-pair held-out gate。P0b fresh2 随后完成 48 record 与 96/96 valid episode，但
clean-eligible `23 < 26`，保持 `p0b_blocked_insufficient_clean_baseline`。当前唯一优先级是 exploratory
Execution-only action-envelope successor；Full CTDA、AEGIS、SAFE、FIPER、EDPA 和最终 E5 仍冻结。

## 当前状态

| 线 | 状态 | 处置 |
|---|---|---|
| Phantom Menace | held-out signal gate failed | R1 仅 1/4 independent cost/collision transition；不调攻击、不换 pair、不运行 scoped main |
| SABER | R7 nonpass；P0b complete/nonqualified | P0b 48 record、96 episode、23 eligible `<26`、15/23 transition；不改写 qualification |
| action-envelope | current priority | clean R1 22/23；R2 invalid；R3 resource-stopped，准备 resource-isolated successor |
| SAFE | not reproduced | 335/500 partial corpus 无 terminal manifest；只保留审计 |
| FIPER fresh1 | not reproduced | `pretzel/rnd_a` 后无 terminal manifest；partial 保留 |
| FIPER fresh2 | stopped/not reproduced | 用户于 2026-07-17 要求停止；service inactive/dead，manifest `started`，partial 不计结果 |
| SafeLIBERO/AEGIS | readiness frozen | 只复用已冻结的独立 safety oracle 定义；不运行 AEGIS 或 CTDA support audit |
| EDPA + SafeLIBERO | terminal before probe | OpenPI CLI contract failure，0 policy/simulator/episode；次要冻结 |

详细 FIPER 操作见 [`safe_fiper_r0_runbook.md`](safe_fiper_r0_runbook.md)。

## E5 开放条件（当前冻结）

当前不启动最终 comparison。以下历史条件即使满足也不能自动开放 E5，必须等待用户重新授权：

1. baseline 官方复现有 terminal manifest、完整 denominator、validator pass 和 output digest；
2. 发布 workload 在 held-out unit 上产生独立 collision/cost/authorization signal，不只是 task failure；
3. comparison 的 task/init/seed/checkpoint/workload/metric 在 outcome 前冻结；
4. ProofAlign 自身 clean utility/safety trade-off 已有有效 paired result；
5. 不复用或改写已关闭的 Phantom/SABER unit；
6. 四臂 fixed-trace gate 与 Dual clean utility gate 已通过，attack 与新 method support population 完全
   重合。

## 永久规则

- 不优化攻击强度或按结果选择 pair；
- task failure 与 unsafe event 分开；
- synthetic prompt/camera mutation 不自动构成 attack efficacy；
- partial log、active process 和模型成功加载都不是 reproduction pass；
- external baseline 不能替代 ProofAlign 自身 ablation/utility 评估；当前也不运行这些评估；
- 旧外部实验全部保持停止；只允许按 [`optimization_plan.md`](optimization_plan.md) 开展 resource-isolated
  action-envelope successor。任何 GPU 正式执行都需要新 protocol/root、fresh inventory、稳定双 GPU 和
  runtime device mapping gate。

## 新 P0/P1 顺序

1. SABER R7 已冻结为 `1/4 = 0.25`；P0b fresh2 完成 48 record 与 96 episode，但只有 23 eligible，
   未达到 26-pair gate；
2. P0 的 R4--R7 root 和 record/pair/seed/checkpoint 均冻结，不得续接、调攻击或以 outcome 替换 pair；
3. 用户已独立授权 exploratory action-envelope successor；EDPA 保持 terminal/secondary；
4. 不做 CTDA support overlap或完整四臂 matrix；只运行 resource-isolated Execution-only successor。

旧 SABER exact-task R1 的 producer failure 只作诊断，不禁止在新 protocol/root/unit 上修复官方 producer；
但不得续接旧 ledger、record 或 victim run。

## SABER R7 的终态边界

R7 是一次完整的 scoped official SABER replication：record artifact、unguarded victim、pair validity、
independent typed oracle 和 terminal artifact 都已完成。其 `1/4` transition 低于预注册 gate，只支持“该
冻结 population 未复现 gate”的结论；它既不证明 SABER 对 LIBERO-Safety 普遍无效，也不构成
ProofAlign defense 结论。

不得以 R7 结果为依据修改 prompt、record、attack strength、checkpoint、pair、task、init 或 seed 后继续
R7。未来可启动新的独立 SABER replication，但它必须：

1. 在 outcome 前提交新的 protocol，固定官方生成定义、独立 oracle、样本量和 signal gate；
2. 使用与 R7 不重叠的 task/init/seed population、fresh root、clean/attacked rollout 和完整 artifact；
3. 保留并并列报告 R7，不覆盖、不合并为同一 run，也不按任一结果追加 replacement；
4. 当前已按上述条件冻结 P0b；它必须在 fresh producer/victim root 完成，且与 R7 并列报告。

## FIPER terminal 检查

```bash
systemctl --user show proofalign-fiper-r0-fresh2.service \
  --property=ActiveState,SubState,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
```

service 退出后仍不能直接写 pass。必须按 runbook 检查固定 run directory 的 manifest、expected cells、
validator、artifact inventory 和 hash；任何缺失均保持 `not_reproduced`。

fresh2 已停止且 manifest 仍为 `started`，因此无需继续 terminal validator；停止快照见
[`fiper_r0_stop_20260717.json`](../experiments/fiper_r0_stop_20260717.json)。攻击基础的统一判定见
[`attack_reproduction_evidence_audit.md`](attack_reproduction_evidence_audit.md)。
