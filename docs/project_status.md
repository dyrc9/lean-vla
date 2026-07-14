# Project Status

更新日期：2026-07-14

## 一句话状态

本地 first sprint 的有限闭环已经完成：paper CTDA 合同来自 frozen mission/phase/residual
obligation，raw binder 不读取 policy metadata，`ctda-wire-v1` 的四个 stage 可由 Lean kernel
实际检查，并有零 mismatch golden/shadow corpus。真实 OpenPI + LIBERO-Safety GPU probe 已关闭
affordance fallback 的 observation-completeness blocker；但固定 50 ms switch gate 只通过 2/3，
25-step 诊断最大值为 59.435 ms。项目据此删除 real-time enforcement 前提，将当前实现固定描述为
fail-closed slow interlock/offline audit。该 latency 负结果继续完整报告，但不再阻塞非实时的 3--5
prefix clean calibration；它仍然禁止把 receipt 或系统描述成满足 50 ms worst-case bound。首次
5-prefix 尝试又发现 runner 在应用 benchmark init state 后发生二次 reset，因此该 episode 已标为
无效诊断样本，不进入 calibration 或论文统计。`2c532ca` 修复后的 valid-init clean run 已证明
handoff gate 生效，但首个 OpenPI proposal 被旧 raw binder 在 dispatch 前 refute。随后形成 clean
`e2e4d47` bounded-stutter commit 并通过 strict preflight；真实 GPU 重跑成功授权、执行并观测了第一
个微动作，四阶段 Lean 为 `proven/proven/proven/safe_pending`，phase 保持 `approach`。第二次新
OpenPI 推理仍是微动作，但一次性 stutter budget 已耗尽，故在 dispatch 前 replan。只执行了 1/5
prefix，3--5 prefix calibration 仍未通过，后续大实验继续关闭。

## 已验证资产

- pi0.5/OpenPI、LIBERO-Safety、在线 wrapper 和 attack-record 接口已经存在。
- Python 已有 typed CTDA reference objects、persistent monitor、prefix transaction、replay/
  stale/cross-episode rejection 和 simulator fallback trace。
- Lean 已有 CTDA staged checker、finite-prefix monitor、`CTDAWire` 四阶段 checker 和 replay
  artifact。
- paper path 已切断 attacked prompt/`proofalign_action` 对 contract/verdict 的授权影响；有限
  Pick/Place template 与独立 raw binder 已有回归测试。
- semantic、prefix-pre、observed-prefix 和 monitor-step 均可在 `ctda-lean-kernel` mode 实际经
  Lean `by decide` 检查；unavailable/tampered request fail closed。
- 27-case CPU golden/shadow corpus 为 0 Python/Lean mismatch；无独立 ground truth 时 false block/
  TPR/FPR 明确输出 `not_evaluated`。
- 当前全量为 212 passed / 1 skipped，Lean `lake build ProofAlign` 为 12 jobs 成功。
- 纯攻击 runner 与 defense runner 已解耦，适合在远程机器上产生版本化 workload 后配对评估。
- `remote_gpu_preflight.py` 会 fail closed 检查独立 Git top-level、模型、GPU physical id、版本、
  选定 LIBERO-Safety 的五个 config path 和本地 verification；`run_remote_gpu_smoke.sh` 显式绑定
  同一隔离 LIBERO config，并生成 SHA-256 artifact manifest。
- 固定 `affordance/task 2/init 0` witness 的 observation postcondition 已在真实 GPU rollout 中验证：
  required observations 为 `collision,cost`，observation complete，mission/distance conditions hold，
  issue list 为空。
- `e2e4d47` strict preflight 在三个独立 clean Git roots 上通过：212 passed / 1 skipped、Lean 12 jobs、
  零 blocker/warning；registered init 0 的 provenance 与两个 state digest 一致。
- 同配置真实 GPU 重跑验证了一次 bounded Pick/approach stutter：count `0 -> 1`，观测位移
  `65.119 µm` 小于带 model error 的 `102.835 µm` limit，margin `37.716 µm`，monitor
  `safe_pending`，phase 不推进，零 collision/cost/fallback。

## 尚未闭合

1. SABER、Phantom Menace、SAFE 和 FIPER 的官方 pipeline 尚未在远程 GPU 环境复现；当前
   `reproduction_targets.json` 均为 `planned`，不能写成已有攻击/防御结果。
2. 当前 Lean evaluator 为每个 request 生成并编译 replay source；远程单-prefix四阶段也约为
   0.9--1.3 s/stage。Lean verification 与 fallback switch 都不满足 real-time claim，后续只按
   slow interlock/offline audit 报告并保留完整 latency distribution。
3. `e2e4d47` bounded-stutter 重跑关闭了首个 2.835 微米 proposal 的 pre-dispatch blocker，但第二次
   新 OpenPI 推理也落在 stutter amplitude envelope 内；每合同一次的预算已耗尽，因此第二 proposal
   在任何新 Lean prefix-pre evaluation 和 `env.step` 前 refute。结果只有 1 个 executed prefix，不能
   评估 3--5 prefix clean retention、unknown/deadlock 或任务 utility。把预算提高到 2/5、改 chunking
   或把整个 OpenPI chunk 纳入合同都是新的方法扩展，尚未获授权；不能为了当前样本通过而修改。
   该分类仍是 consumer-side Python binder，不是 Lean 对 raw action 的独立语义证明。第二 trace entry
   中的四个 `wire_artifacts` 是 session history 的重复序列，不是第二 proposal 的新 Lean proofs。
4. 旧 notes 中的 60-episode baseline、12-episode Dual Lean、SABER 和 EDPA 结果没有完整 raw
   artifact 保存在当前 checkout，不能仅凭叙述重建主表。
5. 当前本地旧 heuristic artifact 出现极高 false rejection，且 synthetic golden corpus 没有独立
   ground truth，说明 clean abstraction/calibration gate 尚未通过。
6. 当前 simulator receipt、运动学界和 zero-hold 只能支持带假设的 simulator trace 结论，不能
   支持硬件、连续动力学或 verified recovery claim。

## 当前唯一优先级

1. 保留 `e2e4d47` 的 clean preflight、raw episode、四阶段 replay、proposal diagnostic、gate
   validation、run notes 和 checksums；当前 gate 明确为失败，不追加 episode 稀释 1/2 proposal
   blocker；
2. 在继续 GPU 前先决定是否单独研究“重复微动作/整 chunk binding”的合同语义；任何扩展必须先给出
   独立预算依据、累计运动界、deadline/phase 语义和 fail-closed tests，不能直接把 retry budget 改大；
3. 仅在新的 clean 3--5 prefix gate 真正通过后，按
   [`reproduction_plan.md`](reproduction_plan.md) 复现 SABER、Phantom Menace、SAFE 和 FIPER 的
   官方 pipeline；
4. 补 observation-attack、OpenPI feature/multi-sample、SAFE/FIPER alarm adapter；
5. calibration 与 published-workload gate 通过后才启动最小 paired GPU pilot。

## 当前可写与不可写

可写：

- frozen Pick/Place mission-rooted contract 与 consumer-side raw binder 已接 simulator loop；
- 共同支持的四个 stage 在 `ctda-lean-kernel` mode 确实由 Lean kernel 检查；
- fake-env 已证明 pre-stage Lean proven 前零 dispatch，observed/monitor 失败时零 phase advance；
- golden corpus 为零 Python/Lean mismatch；
- 攻击与防御 runner 可以通过版本化 artifact 解耦。
- 在固定 task/witness 的真实 GPU diagnostic 中，observation completeness 已通过，但 50 ms
  fallback latency 仅通过 2/3；系统因此按 slow interlock/offline audit 继续评估。
- 首次 5-prefix 尝试暴露了 init-state handoff 缺陷并已被判为无效样本；它不能支持 clean
  calibration、阈值调整或 utility/security 结论。
- corrected run 已验证 selected init 被保留且 digest 一致；首个 clean proposal 在 semantic Lean
  proven 后由 raw binder pre-dispatch refute，零 simulator action。
- bounded-stutter 重跑在同一 init/seed/witness 下执行了一个微动作；四阶段 Lean proof/parity 全部
  通过，观测位移在 simulator kinematic limit 内，phase 保持 `approach`。第二个新微动作因一次性
  budget 耗尽而在 dispatch 前 replan，因此 gate 仍关闭。

不可写：

- 当前 Lean path 是 real-time enforcement；
- fallback 满足固定 50 ms worst-case switch bound，或 latency gate 已通过；
- mission 已被密码学认证；
- raw action 的 semantic contract 已被独立证明；
- 重复 bounded stutter 或整个 OpenPI chunk 已被证明安全；
- 3--5 clean-prefix calibration 已通过，或 clean retention/utility 已知；
- 系统证明真实机器人或连续动力学安全；
- 防御已经优于 baseline 或能够防御某个攻击。
