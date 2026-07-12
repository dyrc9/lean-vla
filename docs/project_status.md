# Project Status

更新日期：2026-07-12

## 一句话状态

本地 first sprint 的有限闭环已经完成：paper CTDA 合同来自 frozen mission/phase/residual
obligation，raw binder 不读取 policy metadata，`ctda-wire-v1` 的四个 stage 可由 Lean kernel
实际检查，并有零 mismatch golden/shadow corpus。下一阻塞是 **Lean per-request replay 延迟仍远高于
控制周期**，以及远程 GPU clean/paired calibration 尚未执行。远程 GPU preflight manifest 与
clean/Lean slow-interlock 单 episode smoke 入口已在本地完成；内网 GPU checkout 和实际运行仍需在
可访问远程主机的环境执行。

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
- 本地全量为 189 passed / 1 skipped，Lean `lake build ProofAlign` 为 12 jobs 成功；当前环境没有
  GPU。
- 纯攻击 runner 与 defense runner 已解耦，适合在远程机器上产生版本化 workload 后配对评估。
- `remote_gpu_preflight.py` 会 fail closed 检查 checkout、模型、GPU physical id、版本和本地
  verification；`run_remote_gpu_smoke.sh` 固定先 clean 后 Lean slow-interlock，并生成 SHA-256
  artifact manifest。

## 尚未闭合

1. 当前 Lean evaluator 为每个 request 生成并编译 replay source。一次本地 shadow 的 Lean p99
   为 semantic 1.954 s、prefix 0.657 s、observed 0.646 s、monitor 0.666 s，明显超过 20 Hz
   control period；当前只能主张 slow online interlock/offline audit，不能主张 real-time。
2. 远程 GPU 上尚未用 pi0.5/OpenPI + LIBERO-Safety 验证 clean retention、unknown/deadlock 和
   evaluator tax。
3. 旧 notes 中的 60-episode baseline、12-episode Dual Lean、SABER 和 EDPA 结果没有完整 raw
   artifact 保存在当前 checkout，不能仅凭叙述重建主表。
4. 当前本地旧 heuristic artifact 出现极高 false rejection，且 synthetic golden corpus 没有独立
   ground truth，说明 clean abstraction/calibration gate 尚未通过。
5. 当前 simulator receipt、运动学界和 zero-hold 只能支持带假设的 simulator trace 结论，不能
   支持硬件、连续动力学或 verified recovery claim。

## 当前唯一优先级

1. 把本地代码、fixture 和 replay protocol 迁移到远程环境，先复跑 CPU/Lean preflight；
2. 只运行 clean single-episode shadow/slow-interlock smoke，记录真实 OpenPI/LIBERO latency 与
   false-block 信号；
3. 若 p99 仍超过 control deadline，将 Lean path 固定为 offline audit，不能用放宽授权窗口冒充
   real-time enforcement；
4. calibration gate 通过后才启动最小 paired GPU pilot。

## 当前可写与不可写

可写：

- frozen Pick/Place mission-rooted contract 与 consumer-side raw binder 已接 simulator loop；
- 共同支持的四个 stage 在 `ctda-lean-kernel` mode 确实由 Lean kernel 检查；
- fake-env 已证明 pre-stage Lean proven 前零 dispatch，observed/monitor 失败时零 phase advance；
- golden corpus 为零 Python/Lean mismatch；
- 攻击与防御 runner 可以通过版本化 artifact 解耦。

不可写：

- 当前 Lean path 是 real-time enforcement；
- mission 已被密码学认证；
- raw action 的 semantic contract 已被独立证明；
- 系统证明真实机器人或连续动力学安全；
- 防御已经优于 baseline 或能够防御某个攻击。
