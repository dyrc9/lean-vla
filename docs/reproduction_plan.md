# External Reproduction Plan

更新日期：2026-07-20

外部 baseline/workload 是 E5，当前不阻塞 ProofAlign 自身 clean utility pilot。

## 当前状态

| 线 | 状态 | 处置 |
|---|---|---|
| Phantom Menace | held-out signal gate failed | R1 仅 1/4 independent cost/collision transition；不调攻击、不换 pair、不运行 scoped main |
| SABER | record generation failed closed | 第一个 record 已产生 invalid ledger/transcript；不修复重跑、不运行 victim/main |
| SAFE | not reproduced | 335/500 partial corpus 无 terminal manifest；只保留审计 |
| FIPER fresh1 | not reproduced | `pretzel/rnd_a` 后无 terminal manifest；partial 保留 |
| FIPER fresh2 | stopped/not reproduced | 用户于 2026-07-17 要求停止；service inactive/dead，manifest `started`，partial 不计结果 |
| EDPA R0 | draft/asset-gated | official source 已 pin，adapter/protocol/preflight/validator 已就绪；训练数据 manifest 和双相机 patch 缺失，victim rollout 未授权 |

详细 FIPER 操作见 [`safe_fiper_r0_runbook.md`](safe_fiper_r0_runbook.md)。

## E5 开放条件

只有同时满足以下条件才启动最终 comparison：

1. baseline 官方复现有 terminal manifest、完整 denominator、validator pass 和 output digest；
2. 发布 workload 在 held-out unit 上产生独立 collision/cost/authorization signal，不只是 task failure；
3. comparison 的 task/init/seed/checkpoint/workload/metric 在 outcome 前冻结；
4. ProofAlign 自身 clean utility/safety trade-off 已有有效 paired result；
5. 不复用或改写已关闭的 Phantom/SABER unit。

## 永久规则

- 不优化攻击强度或按结果选择 pair；
- task failure 与 unsafe event 分开；
- synthetic prompt/camera mutation 不自动构成 attack efficacy；
- partial log、active process 和模型成功加载都不是 reproduction pass；
- external baseline 不能替代 ProofAlign 自身 ablation/utility 评估；
- 当前所有外部 victim 实验暂停；EDPA 只允许离线 asset gate 准备。任何 GPU 重新执行都需要
  资产冻结后的新 execution amendment/授权、fresh root 和 fresh inventory。

## EDPA R0 asset gate

EDPA 是新 published-workload attempt，不是对 Phantom/SABER 的结果驱动重跑。当前预检预期 fail closed，
直到 `/data0/ldx/proofalign-edpa-r0/attack_assets/` 下的 training-data manifest、primary patch 和 wrist
patch 都存在且 digest 被冻结。资产生成后不得查看 victim outcome 再调整 patch、task 或位置。

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
