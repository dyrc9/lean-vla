# ProofAlign GPU 实验交接

起始版本：`230e32937a194530054616f9232adb7f9973586c`

最新更新：2026-07-14。历史一次性 run 使用 `e2e4d47`；本轮累计 bounded-stutter 真实 GPU run
使用 committed HEAD `74152a9492298155810244ddcbb6509f22d47241`，run 后 canonical 结论另作本地
文档 commit，均未 push。

## 当前状态

- `e2e4d47` strict preflight：212 passed / 1 skipped；Lean build 12 jobs 成功；零
  blocker/warning，三个独立 checkout 都 clean。
- OpenPI checkout：`15a9616a00943ada6c20a0f158e3adb39df2ccac`，clean。
- LIBERO-Safety checkout：`ef0f79b70fc50c5fb612a1bbc1cf8b6c033a702a`，clean standalone
  Git top-level，tracked runtime files 与官方 checkout 差异为 0。
- 10 Hz single-prefix slow-interlock 的四个 Lean stage 为
  `proven/proven/proven/safe_pending`，全部 parity match、proof verified。
- observation-completeness 修复已由真实 GPU rollout 验证：affordance task 2 只要求
  `collision,cost`，observation complete，mission/distance postconditions hold，issues 为空。
- 固定 50 ms fallback switch gate 未稳定通过：三次完整 OpenPI + Lean repeat 为 2/3；延迟为
  46.949、51.205、46.704 ms。25 次 zero-hold 诊断 median 41.769 ms、p95 45.776 ms、
  max 59.435 ms。
- 当前决策：不放宽 witness、不改变 control frequency、不移动 `observed_at`。保留超时
  strict receipt 和完整 miss；在显式 `slow-interlock-diagnostic-v1` 下不再让纯 latency SLA 阻塞
  method-validity 实验；删除 real-time enforcement claim。authorization/contract deadline、
  trace horizon 与所有安全/完整性条件仍 fail closed。
- `7bab2d9` clean checkout 的 strict preflight 已通过（206 passed / 1 skipped、Lean 12 jobs、
  `ready=true`）。随后 5-prefix 尝试发现 selected benchmark init 0 被 online runner 二次 reset
  替换；episode 初始 digest 为
  `4da02fda6246ba22cd7b39d22bc71cfa61935ca5af20b8222c6ec2aebcf00ad0`，而 intended init digest 为
  `f866ea35d3243f4dc9400fe169f63acd8ec735b1e1ebce248e9bae29078eb9b8`。因此该 run
  无效，不进入 calibration 或阈值调整。修复已保留 `set_init_state` 返回的观测并写出可核验的
  initialization provenance。
- `2c532ca` strict preflight 再次通过：`ready=true`、零 blocker/warning、208 passed / 1 skipped、
  Lean 12 jobs。corrected run 的 selected init provenance 与 digest gate 全部通过，两个 digest 均为
  `f866ea35d3243f4dc9400fe169f63acd8ec735b1e1ebce248e9bae29078eb9b8`。
- corrected run 的首个 clean proposal 在 semantic Lean `proven` 后被 raw binder pre-dispatch
  refute（`moves away from the mission target`），零 `env.step`、零 fallback。预测平移约 2.835
  微米、目标距离增加约 2.735 微米；这是 blocking/abstraction signal，不是独立 ground-truth
  false positive。3--5 prefix gate 未通过。
- 历史 `e2e4d47` 一次性 bounded-stutter 只允许 Pick/approach 非闭合微动作，复用
  `model_error_m=0.0001 m`，六维 motion-command norm bound `0.002`，每合同一次并受 deadline
  约束；candidate/witness 绑定 flag/index/budget，观测 progress 时 phase 更新前 fail closed。
- `e2e4d47` 真实 GPU 重跑使用 policy GPU 1 / EGL GPU 5；启动前两卡均为 3 MiB、0%。registered
  init gate 与 digest 通过。首 proposal 被分类为 bounded stutter 并执行一次：四阶段 Lean
  `proven/proven/proven/safe_pending`，全部 proof/parity true，count `0 -> 1`，phase 保持
  `approach`，观测位移 65.119 µm，limit 102.835 µm，margin 37.716 µm。
- 观测后 fresh OpenPI inference 产生第二个 envelope 内微动作，但一次性 budget 已耗尽，故在新
  Lean prefix-pre 和 `env.step` 前 replan。只执行 1/5 prefix；3--5 gate 仍失败。第二 trace entry
  的四个 wire artifacts 是 session history 重复，不是第二轮证明。零 fallback，因此不增加 50 ms
  latency evidence。
- 本轮已获授权并实现 `mission-raw-binder-libero-panda-v4-cumulative-stutter`：同 active contract
  的累计 predicted translation path `<=0.0001 m`、累计六维 command-path norm `<=0.002`；授权时
  扣减，reset/replan 不退款，保留第一次 stutter 的 deadline，并沿用既有
  `no_progress_patience=3`。OpenPI/episode artifact 还会保存完整归一化 chunk、policy-call ID、实际
  policy actions 与丢弃 tail。该实现尚待 clean-commit strict preflight 和一次相同配置的 3--5
  prefix GPU calibration。
- `74152a9` strict preflight：`ready=true`、零 blocker/warning、216 passed / 1 skipped、Lean 12
  jobs，三套 checkout clean。policy GPU 1 被其他用户占用，因此记录并使用同型号空闲 GPU 3；EGL
  仍为 GPU 5。
- 唯一一次累计版本 run 的 registered-init gate 通过；首个 prefix 的 predicted translation 3.617
  µm、六维 command-path norm `9.3073e-05`、observed kinematic margin 25.754 µm，完整 10-action
  chunk/call/executed/tail 均落盘。但 dispatch-to-observation 104.926 ms 超过 100 ms authorized
  duration 4.926 ms，observed-prefix 被 Python/Lean 一致 refute；fallback postcondition 成立但
  56.910 ms 超过 50 ms，最终 `safe_stop`。只执行 1 prefix，未追加 episode，gate 仍失败。
- `7587c47` timing-policy 版本 strict preflight 为 220 passed / 1 skipped、Lean 12 jobs、零
  blocker/warning。固定重跑的首 prefix 在 109.034 ms observation miss 下仍得到
  `proven/proven/proven/safe_pending`；第二 prefix 在 71.265 ms（无 timing miss）时因观测位移
  1.335 mm 超过记录 limit 0.150 mm 被一致 refute。fallback 安全集成立，strict receipt 因
  52.819 ms > 50 ms 仍失败，但在 slow policy 下仅该 latency miss 不升级。
- frozen `OSC_POSE` config 的 translation scale 是 2.0，CTDA hard-code 是 0.05。source-grounded
  重算覆盖两次观测，但也使首 prefix predicted translation 0.127 mm 超过现有 stutter budget 0.1 mm；
  这需要新的预算决策，不能按样本直接放宽。
- `f01a98f` 已绑定 live controller 并由 normalized command budget 派生 4 mm translation budget；
  227 passed / 1 skipped、Lean 12 jobs、strict preflight 通过。PATH-only corrected calibration 完成
  五个 `proven/safe_pending` prefix，五个 tube margin 全正，16 个 Lean request proof/parity 全 true。
  前两步累计 stutter 后三步 normal approach；五步上限以 zero-hold/replan 收束。一次 111.279 ms
  prefix miss 和 76.205 ms fallback miss 保持为性能负结果。

关键 artifact：

- `results/remote_gpu_probe_20260714_b0f3d14_v2/`
- `results/remote_gpu_probe_20260714_b0f3d14_repeat3/`
- `results/gate_audit_20260714_b0f3d14/`
- `results/remote_gpu_clean_prefix5_20260714_7bab2d9/`（无效 init-handoff diagnostic）
- `results/remote_gpu_clean_prefix5_20260714_2c532ca/`（错误 uv project，零 prefix，保留为启动失败）
- `results/remote_gpu_clean_prefix5_20260714_2c532ca_v2/`（valid-init clean binder blocker）
- `results/remote_gpu_clean_prefix5_20260714_e2e4d47/`（bounded-stutter 首 prefix 通过、第二 proposal
  budget exhausted；gate 未通过）
- `results/remote_gpu_clean_prefix3_20260714_74152a9/`（累计合同 strict preflight 通过；首 prefix
  authorized-duration 与 fallback-latency fail closed；gate 未通过）
- `results/remote_gpu_clean_prefix3_20260714_7587c47/`（timing policy 目标通过；第二 prefix 暴露
  live-controller scale mismatch；38 个 artifact checksums 已验证）
- `results/remote_gpu_clean_prefix3_20260714_f01a98f/`（Lean `PATH` 缺失的无效启动；零 dispatch）
- `results/remote_gpu_clean_prefix3_20260714_f01a98f_pathfix/`（五-prefix method-validity gate 通过；
  task/realtime gate 未通过；全部 artifact checksums 已验证）
- `results/phantom_menace_r0_20260714/`（Phantom 9 组 CPU transform smoke 通过；官方 WebSocket
  闭环通过；fresh-RNG task 0/1 clean baseline 均失败，R0 未通过）

Phantom Menace 上游固定为 `a0e4c8b2a661ea2fe64bdb9055353b2e12575729`，本地最小运行限制补丁为
`9ceb030f0313ded029acedb1c5a8f76e57c654bc`。机器记录见
`experiments/phantom_menace_r0_status.json`。注意当前 `external/LIBERO` 有进入本轮前就存在的修改，
而 OpenPI 环境把 robosuite 解析到 `external/LIBERO-Safety/third_party/robosuite-1.4`；后续不能把这两条
clean failure 写成官方 baseline，必须先建独立 clean standard-LIBERO 环境。所有本轮 GPU server
已停止。保存前全量校验为 239 passed / 1 skipped，Lean build 12 jobs 成功，Phantom 结果目录的
5 项 SHA-256 全部复核通过。

## 下一步只做什么

1. 保留全部历史 failure 与 checksum；不回写 verdict。
2. 登记并核验现有 SABER official LoRA/OpenPI R0 records；只把 constraint-violation 写成方向成立，
   action-inflation 写成较弱，task-failure 写成未复现强效果。
3. Phantom deterministic transform 已通过；下一次先隔离 clean standard-LIBERO 环境并补结构化
   outcome/frame-digest 日志，再继续官方 clean + camera-transform R0。
4. Phantom R0 通过后才生成 exact-task R1 workload；此前不运行 60 episodes 或 paired pilot。
   whole-chunk authorization 仍不在范围内。

本次下一步仍不是 60-episode、SABER 或 Phantom 主实验。不要把 slow-interlock 结果描述成实时
执行，也不要用 CTDA verdict 自己生成 ground-truth TPR/FPR。

## GPU 环境需求

- 修改代码和跑单元测试：不需要 GPU。
- 完成交接验收和生成新 rollout artifact：需要 GPU。
- 推荐两张 GPU：一张 OpenPI policy，一张 MuJoCo EGL；显存足够时可以同卡，但必须记录。

已知环境：

- Conda：`proofalign-libero`
- uv：`/home/ldx/.conda/envs/proofalign-libero/bin/uv`
- uv cache：`/data0/ldx/uv-cache`
- checkpoint：`/data0/ldx/libero_safety_models/pi05_libero_safety`
- Hugging Face 镜像：`https://hf-mirror.com`
- `/data0/ldx` 只存模型、数据和缓存，代码工作区仍是本仓库。

## 交付

- 修复代码和测试；
- 新的 dated result 目录、run notes 和 SHA256SUMS；
- pytest / Lean build 结果；
- Git commit SHA 和剩余 blocker。
