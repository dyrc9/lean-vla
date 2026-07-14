# ProofAlign GPU 实验交接

起始版本：`230e32937a194530054616f9232adb7f9973586c`

最新更新：2026-07-14，当前 ProofAlign committed HEAD
`f736637`；bounded-stutter 代码、测试与规范更新仍在本地工作树，尚未提交。

## 当前状态

- 当前工作树全量测试：212 passed / 1 skipped；Lean build 12 jobs 成功。bounded-stutter 相关
  CTDA/runner 定向测试为 85 passed。
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
  fail-closed，但不再让 latency gate 阻塞 slow-interlock/offline 实验；删除 real-time
  enforcement claim。
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
- 用户已授权最小 bounded-stutter 扩展。当前实现只允许 Pick/approach 非闭合微动作，复用
  `model_error_m=0.0001 m`，六维 motion-command norm bound `0.002`，每合同一次并受 deadline
  约束；candidate/witness 绑定 flag/index/budget，观测 progress 时 phase 更新前 fail closed。

关键 artifact：

- `results/remote_gpu_probe_20260714_b0f3d14_v2/`
- `results/remote_gpu_probe_20260714_b0f3d14_repeat3/`
- `results/gate_audit_20260714_b0f3d14/`
- `results/remote_gpu_clean_prefix5_20260714_7bab2d9/`（无效 init-handoff diagnostic）
- `results/remote_gpu_clean_prefix5_20260714_2c532ca/`（错误 uv project，零 prefix，保留为启动失败）
- `results/remote_gpu_clean_prefix5_20260714_2c532ca_v2/`（valid-init clean binder blocker）

## 下一步只做什么

1. 审查并提交当前 bounded-stutter 代码、测试和规范文档；不 push、不建 PR。
2. clean checkout 后重跑 strict preflight，并在启动前重新检查 GPU。
3. 只按同一冻结 task/init/seed/witness 重跑 3--5 prefix calibration，重点验收 stutter count、
   safe-pending、零 phase advance、四阶段 parity 和 observed kinematic diagnostics。
4. 该 gate 通过前仍不运行 60-episode 或攻击主实验。

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
