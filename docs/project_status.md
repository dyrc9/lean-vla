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
无效诊断样本，不进入 calibration 或论文统计。

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
- 当前全量为 208 passed / 1 skipped，Lean `lake build ProofAlign` 为 12 jobs 成功。
- 纯攻击 runner 与 defense runner 已解耦，适合在远程机器上产生版本化 workload 后配对评估。
- `remote_gpu_preflight.py` 会 fail closed 检查独立 Git top-level、模型、GPU physical id、版本、
  选定 LIBERO-Safety 的五个 config path 和本地 verification；`run_remote_gpu_smoke.sh` 显式绑定
  同一隔离 LIBERO config，并生成 SHA-256 artifact manifest。
- 固定 `affordance/task 2/init 0` witness 的 observation postcondition 已在真实 GPU rollout 中验证：
  required observations 为 `collision,cost`，observation complete，mission/distance conditions hold，
  issue list 为空。

## 尚未闭合

1. SABER、Phantom Menace、SAFE 和 FIPER 的官方 pipeline 尚未在远程 GPU 环境复现；当前
   `reproduction_targets.json` 均为 `planned`，不能写成已有攻击/防御结果。
2. 当前 Lean evaluator 为每个 request 生成并编译 replay source；远程单-prefix四阶段也约为
   0.9--1.3 s/stage。Lean verification 与 fallback switch 都不满足 real-time claim，后续只按
   slow interlock/offline audit 报告并保留完整 latency distribution。
3. 远程 GPU 上首次 5-prefix 尝试只到 prefix 2，但事后证明 selected init state 被 runner 二次
   reset 替换，因此该 episode 无效。initialized-observation handoff 已修复并有回归测试；仍需在
   clean commit + strict preflight 后按相同冻结配置重跑，才能评估 clean retention、unknown/
   deadlock 和 evaluator tax。
4. 旧 notes 中的 60-episode baseline、12-episode Dual Lean、SABER 和 EDPA 结果没有完整 raw
   artifact 保存在当前 checkout，不能仅凭叙述重建主表。
5. 当前本地旧 heuristic artifact 出现极高 false rejection，且 synthetic golden corpus 没有独立
   ground truth，说明 clean abstraction/calibration gate 尚未通过。
6. 当前 simulator receipt、运动学界和 zero-hold 只能支持带假设的 simulator trace 结论，不能
   支持硬件、连续动力学或 verified recovery claim。

## 当前唯一优先级

1. 将 initialized-observation handoff 修复形成 clean checkout，严格重跑 GPU + CPU/Lean
   preflight；
2. 在固定 witness、不移动时间戳的条件下重跑 3--5 prefix clean slow-interlock calibration；只有
   artifact 明确记录 selected init 已应用、runner 未二次 reset，且 benchmark-init observed-state
   digest 与 CTDA initial-state digest 一致时样本才有效。继续保存 raw episode、四阶段 Lean
   replay、fallback latency 分解和 checksum；
3. 仅在 clean false-block/unknown/deadlock 信号可接受后，按
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

不可写：

- 当前 Lean path 是 real-time enforcement；
- fallback 满足固定 50 ms worst-case switch bound，或 latency gate 已通过；
- mission 已被密码学认证；
- raw action 的 semantic contract 已被独立证明；
- 系统证明真实机器人或连续动力学安全；
- 防御已经优于 baseline 或能够防御某个攻击。
