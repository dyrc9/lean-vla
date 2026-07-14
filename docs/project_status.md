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
prefix。本轮已在 `74152a9` 实现合同级累计预算与完整 chunk audit；strict preflight 为
`ready=true`、216 passed / 1 skipped、Lean 12 jobs。随后唯一一次相同 task/init/seed/witness 的
重跑在第一个 prefix 失败：pre-dispatch proven，累计 path 与观测运动学均有正 margin，但 observation
比 100 ms authorized prefix duration 晚 4.926 ms，observed-prefix 被 Lean/Python 一致 refute；
zero-hold postcondition 成立但 56.910 ms switch latency 超过 50 ms，最终 `safe_stop`。只执行 1 个
policy prefix，未追加 episode。用户随后授权优先验证 method validity：runtime 现显式区分严格实时
与 slow-interlock 时序策略。慢速策略仍记录上述两个 miss 和严格 receipt 失败，但不让纯性能 SLA
单独否决方法；authorization/contract deadline、trace horizon、运动学/不变量、累计预算、
completion/progress、actuation/postcondition 与 proof/parity 仍 fail closed。新的固定配置 calibration
已在 clean `7587c47` 上执行：preflight 为 220 passed / 1 skipped、Lean 12 jobs、零 blocker/warning。
首 prefix 即使 109.034 ms 超过 100 ms SLA，仍按慢速策略得到四阶段
`proven/proven/proven/safe_pending`；第二 prefix 则因观测位移 1.335 mm 超过记录的 0.150 mm
kinematic limit 被 Python/Lean 一致 refute。冻结的 LIBERO-Safety `OSC_POSE` config 显示有效
translation scale 是 2.0，而 CTDA 硬编码为 0.05，存在 40 倍模型错配。该 gate 因方法模型而非性能
失败。用户现已授权以预先存在的归一化六维 command-path budget `0.002` 作为独立依据：物理平移
预算由 live scale 相乘派生，当前为 `0.004 m`。runner 已移除 `0.05` 硬编码，并对 live
`OSC_POSE` controller 的 delta mode、六维/零中心/等向 mapping 和 environment bounds 做 fail-closed
绑定。`f01a98f` 已通过 227 passed / 1 skipped、Lean 12 jobs 和 strict preflight。首次 calibration
启动因子进程缺少 Lean `PATH` 在 semantic stage fail closed、零 dispatch；经明确授权仅修正 `PATH`
后的固定重跑完成 5/5 `proven/safe_pending` prefix，16 个唯一 Lean request 全部 proof-verified 且
Python parity 匹配，五个 kinematic margin 全为正。前两步累计 stutter 后三步自然进入正常 approach；
method-validity prefix gate 已通过，但任务未在五步内完成且 realtime SLA 仍未通过。当前开放的是
官方上游复现 gate，不是 60-episode 或主实验。SABER R0 历史记录已完成机器核验；Phantom Menace
上游 commit、三种 deterministic camera transform 及 weak/medium/strong 共 9 组 CPU repeat smoke
也已冻结并通过。官方 WebSocket + pi0.5 + standard-LIBERO 闭环已打通，但 fresh-policy-RNG 的
`libero_spatial` task 0 和 task 1 clean episode 均在 220 步失败；同时当前 standard LIBERO checkout
有预存修改，OpenPI 环境中的 robosuite 实际解析到 LIBERO-Safety。因此 Phantom R0 仍未通过，未启动
attack episode。

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
- 当前全量为 239 passed / 1 skipped，Lean `lake build ProofAlign` 为 12 jobs 成功；`f01a98f`
  calibration 前的 strict preflight 仍按其原始 227 passed / 1 skipped 记录保留。
- cumulative-stutter CPU/fake-env 覆盖累计 path 超界、持久 no-progress、reset 不退款、原 deadline、
  completion/progress fail closed 和零 phase advance；OpenPI/runner 测试覆盖完整 chunk、policy-call
  ID、实际执行 command 与丢弃 tail，控制仍为每次 CTDA 只 dispatch 一个 command。
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
- `74152a9` strict preflight 在 GPU 3/5 上为 `ready=true`、零 blocker/warning，三套 checkout clean，
  216 passed / 1 skipped、Lean 12 jobs；完整 action chunk/call/executed/tail 已在真实 OpenPI artifact
  落盘。
- `7587c47` 将 strict/slow 时序政策分离并绑定进 tube/receipt metadata；同配置真实 GPU run 证明纯
  timing miss 不再阻塞四阶段 method verdict，同时在第二 prefix 对真实运动学模型错配 fail closed。
- `f01a98f` live-controller calibration 在 registered init 上执行五个 policy prefix：前两步累计
  stutter 消耗 2.139 mm / 4 mm 与 `0.001405 / 0.002`，后三步不退款也不再增加 stutter count；
  5/5 tube/model/invariant 通过，完整 action chunk audit 落盘。一步 111.279 ms prefix miss 与
  76.205 ms fallback miss 继续作为性能负结果，不能支持 realtime claim。
- Phantom Menace 上游固定为 `a0e4c8b2a661ea2fe64bdb9055353b2e12575729`，最小 task/init/horizon/
  fail-closed 运行补丁为 `9ceb030f0313ded029acedb1c5a8f76e57c654bc`。ProofAlign observation
  transform plugin 直接加载并校验上游源码，不复制算法；3 种攻击 × 3 档强度的重复输出与 digest
  全部一致，CPU smoke SHA-256 为 `3f3b64de...04880fd`。

## 尚未闭合

1. 历史 SABER 官方 LoRA/OpenPI R0 原始记录已经重新核验：constraint-violation 方向成立，
   action-inflation 较弱，task-failure 未复现强效果；它仍是 standard LIBERO 上游结果，不能冒充
   LIBERO-Safety exact-task R1。Phantom Menace 的 deterministic transform 与闭环环境已就绪，但
   clean task 0/1 均失败，且 standard LIBERO/robosuite 环境未隔离；官方 R0 仍关闭。SAFE 和 FIPER
   尚未完成官方 pipeline。
2. 当前 Lean evaluator 为每个 request 生成并编译 replay source；远程单-prefix四阶段也约为
   0.9--1.3 s/stage。Lean verification 与 fallback switch 都不满足 real-time claim，后续只按
   slow interlock/offline audit 报告并保留完整 latency distribution。
3. `7587c47` method-validity gate 曾暴露 dynamics config mismatch：
   vendored `OSC_POSE` 的 normalized translation scale 为 2.0，代码使用 0.05。按冻结 source 重算，
   两个 prefix 的 command-plus-model-error limit 分别为 0.227 mm 与 2.094 mm，均覆盖实际观测；但
   正确 scale 下首 prefix 的 predicted translation 为 0.127 mm，已超过另行冻结的累计 stutter
   translation budget 0.1 mm。历史结果保持为失败记录；新版本不按该样本拟合，而是复用此前已经
   冻结的归一化六维 command-path budget `0.002`，以 live scale 严格派生 `0.004 m` 平移上界。
   `model_error_m=0.0001 m` 继续只作为 tube 的独立误差 allowance。该 correctness blocker 已由
   `f01a98f` 和五-prefix gate 关闭，但历史失败 verdict 保持不变。
4. `74152a9` 累计合同历史 GPU gate 在第一 prefix 的时序边界失败：dispatch-to-observation
   `104.926095 ms > 100 ms` authorized duration，虽 observed displacement margin 为正，仍正确
   fail closed；fallback postcondition 完整但 `56.909518 ms > 50 ms`，receipt 失败。该结果只验证
   第一次累计扣减和完整 chunk 日志，没有验证 repeated prefix；不能通过移动 timestamp、增加
   duration、改变 control frequency 或重跑样本绕过。后续获授权的 slow-interlock 策略不改这些
   原始值，只将 control-period/fallback latency miss 与方法安全判据分列。raw stutter 分类和墙钟
   timing policy 仍是 Python adapter 语义，不是 Lean raw-action/timing proof。
5. 旧 notes 中的 60-episode baseline、12-episode Dual Lean 和 EDPA 结果没有完整 raw artifact，
   不能仅凭叙述重建主表。SABER R0 records 虽存在，也不能替代 exact-task paired artifacts。
6. 单一 task/init 的 method-validity calibration 已通过，但跨任务 clean utility、false-block 和
   independent ground truth 尚未建立；不能由本次 CTDA verdict 自己生成 TPR/FPR。
7. 当前 simulator receipt、运动学界和 zero-hold 只能支持带假设的 simulator trace 结论，不能
   支持硬件、连续动力学或 verified recovery claim。

## 当前唯一优先级

1. 为 Phantom Menace 建立独立、clean 的 standard LIBERO/robosuite 环境，并让上游 runner 持久化
   structured episode outcome 与 frame digest；
2. 按预先声明的 task 顺序取得合格 clean baseline，再对相同 task/init/fresh policy RNG 运行一个
   deterministic camera attack；不得按攻击结果调强度；
3. Phantom R0 通过后才为 exact LIBERO-Safety task 生成 SABER instruction 与 Phantom camera R1 workload；
4. 补 OpenPI feature/multi-sample、SAFE/FIPER alarm adapter；
5. published-workload 与 baseline readiness gate 通过后才启动最小 paired GPU pilot，仍不上 60 episodes。

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
- live-controller cumulative-stutter 重跑在同一 init/seed/witness 下完成五个 prefix；前两步累计
  stutter 后三步 normal approach，所有四阶段 proof/parity 与运动学 margin 均通过，因此
  method-validity prefix gate 已通过。它仍不是 task-success、clean-retention 或 realtime 证据。
- `74152a9` 真实 run 已证明完整 chunk audit 与第一次累计扣减落盘；它在 observed-duration 和 fallback
  latency 两个冻结时序界 fail closed，未形成 repeated-prefix 证据。
- slow-interlock 的 observation/fallback SLA miss 可以作为性能负结果单独报告；这不代表满足实时
  bound，也不覆盖 authorization expiry、contract deadline 或任何安全/完整性失败。

不可写：

- 当前 Lean path 是 real-time enforcement；
- fallback 满足固定 50 ms worst-case switch bound，或 latency gate 已通过；
- mission 已被密码学认证；
- raw action 的 semantic contract 已被独立证明；
- 累计 bounded stutter 已由 Lean raw-action semantics 独立证明安全；
- 整个 OpenPI chunk 已获授权或被执行；
- 3--5 prefix method-validity calibration 证明了 clean retention/utility；
- 系统证明真实机器人或连续动力学安全；
- 防御已经优于 baseline 或能够防御某个攻击。
