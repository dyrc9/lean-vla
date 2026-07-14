# ProofAlign GPU 实验交接

起始版本：`230e32937a194530054616f9232adb7f9973586c`

最新更新：2026-07-14，当前 ProofAlign HEAD
`b0f3d14b5560c4b839a1daed46be566839aa142f`。

## 当前状态

- 全量测试：206 passed / 1 skipped；Lean build 12 jobs 成功。
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

关键 artifact：

- `results/remote_gpu_probe_20260714_b0f3d14_v2/`
- `results/remote_gpu_probe_20260714_b0f3d14_repeat3/`
- `results/gate_audit_20260714_b0f3d14/`

## 下一步只做什么

1. 保留并提交当前三个 preflight/smoke hardening 文件；未经用户明确授权仍不得 commit。
2. clean checkout 后运行严格 preflight，不使用 `--allow-dirty`，并在启动前重新确认 GPU 4/5
   空闲。
3. 运行固定 `affordance/task 2/init 0`、env seed 7、policy seed 0、10 Hz、
   `max_chunk_steps=1`、同一 witness 的
   3--5 prefix clean slow-interlock calibration。
4. 保存 raw episode、run config、四阶段 Lean request/result/replay、每次 fallback latency 分解、
   run notes 和 `SHA256SUMS`；保留全部 timeout/failure prefix。
5. 检查 parity、unknown/deadlock、false-block signal 和 runner failure。只有 clean calibration
   无新 blocker 后才进入下一 readiness gate。

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
