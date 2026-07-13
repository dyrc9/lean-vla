# ProofAlign GPU 实验交接

起始版本：`230e32937a194530054616f9232adb7f9973586c`

## 当前状态

- 全量测试：199 passed / 1 skipped；Lean build 12 jobs 成功。
- clean GPU smoke：0 runner failure，0 cost/collision。
- 20 Hz CTDA：Lean semantic/prefix-pre proven，但 MuJoCo step 约 77 ms，超过 50 ms deadline。
- 10 Hz slow-interlock：四个 Lean stage 全部运行，结果为
  `proven/proven/proven/safe_pending`，全部 parity match、proof verified。
- 现存 blocker：单-prefix 结束时触发 zero-hold fallback；affordance 不需要 human/obstacle
  clearance，但 fallback 仍把相应 unknown notes 当成 observation incomplete。

已有 artifact：`results/remote_gpu_smoke_20260713/`。

## 下一步只做什么

1. 修复 fallback observation completeness：只要求当前 SafetySpec / mission hard invariants
   实际需要的 observation。
2. 保证 human/obstacle suites 缺少相应 observation 时仍 fail closed。
3. 补单元测试，复跑全量 pytest 和 Lean build。
4. 重跑 affordance/task2/init0 的 10 Hz 单-prefix Lean probe，目标是 fallback receipt
   `succeeded=true`。
5. 通过后跑 3--5 prefixes clean calibration，记录 verdict、unknown、stage latency 和 env latency。

不要启动 60-episode、SABER 或 Phantom 主实验。不要通过放宽 20 Hz deadline 声称实时执行。

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
