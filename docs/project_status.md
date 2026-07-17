# Project Status

更新日期：2026-07-17

## 当前状态

| 工作线 | 状态 | 当前结论 | 下一步 |
|---|---|---|---|
| CTDA 方法 | complete for scoped prototype | mission-rooted contract、raw-prefix binding、Lean staged evaluator 和 persistent monitor 已闭环 | 方法语义保持冻结 |
| E0 support | complete | 12 个 affordance/init0 non-real-time supported unit | 新实验不得越过支持范围，除非先做新 support audit |
| E1 utility | not evaluated | v1/v2/v3 均 terminal-invalid；无有效 clean pair | 新建不同 policy-seed 的 paired pilot，先统一两臂 observer schema |
| E3 safety | scoped evidence complete | clean 12/12 preserved；post-dispatch 行为 fail closed，但正式 primary 12 unknown | 不改写旧分类；新的独立 challenge 才能增加 containment 证据 |
| E4 robustness | complete | 35/35 frozen fault case fail closed | 只保留 scoped component claim |
| timing | negative/deferred | Lean 0.9--1.3 s/stage，不满足实时控制 | 不优化，不恢复 real-time claim |
| external baselines | blocked/running | Phantom/SABER gates 已关闭；SAFE 未复现；FIPER fresh2 在 GPU 1 后台运行 | 等 FIPER terminal manifest；不干扰 GPU 1 |

完整数字见 [`evaluation_results.md`](evaluation_results.md)。

## 当前可以写

- 在固定 simulator task slice 上，Full CTDA clean safety observation 为 12/12 preserved；
- 在固定 CPU/Lean fault matrix 上，35/35 fault case fail closed；
- Lean unavailable/timeout、关键 binding tamper 和 typed fallback evidence 不足时，当前实现不会静默
  回退到 Python 授权；
- 当前系统是 slow-interlock/offline prototype。

## 当前不能写

- Full CTDA 保留了多少 task completion；
- post-dispatch containment 已正式建立；
- 对发布攻击有总体 defense efficacy；
- physical/hardware/continuous-dynamics safety；
- verified recovery、availability 或 real-time enforcement。

## 当前唯一主任务

执行一个新的 clean paired utility pilot：

1. 在 VLA-only 和 Full CTDA 两臂初态 observation 前安装完全相同的 task-bound contact query；
2. 用 fake-env/unit test 证明同 task/init 的两臂 initial-state digest 完全相同，同时 baseline 仍无
   ProofAlign action gate；
3. 使用 E0 的 12 个 task/init0，但换成未执行过的 `policy_seed=1`，形成与 E1-v3 不同的 paired unit；
4. 事前冻结 protocol、source hash、pair order、labels、failure policy 和 fresh output root；
5. GPU 1 继续专供 FIPER；正式 pilot 使用 preflight 时确认空闲的其他 GPU；
6. 只报告 valid pair 上的 task success、safe success、retention、block/deadlock 和 method-attributable
   utility loss。closed-loop block 不自动叫 false positive。

可直接交接的执行说明见 [`next_experiment_prompt.md`](next_experiment_prompt.md)。

## 仓库状态规则

- 已终止的 protocol/result 不 resume、不覆盖、不重新分类；
- 所有正式执行必须先在 clean commit 冻结 protocol，再使用 fresh absent output root；
- timing 保留原始记录但不是下一实验 gate；
- raw artifact、ledger、manifest 和 terminal summary 必须一起保存；
- archive 只用于历史追溯，不作为当前方法或 CLI 来源。
