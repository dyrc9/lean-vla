# Roadmap

## 项目阶段

当前项目处于 prototype / research proposal 阶段。目标是先把问题定义、规格接口、benchmark mapping 和评测 protocol 做扎实，再逐步实现可运行系统。

后续 agent 开始实验前必须先遵守 `docs/benchmark_gpu.md` 和
`docs/implementation_notes.md` 中的环境约定：Python 通过 conda 里的
`uv` 管理，外部下载优先走可用镜像 / 中转，大文件默认放
`/data0/ldx`，代码和工作区仍留在当前仓库。

## Phase 0: 文档与问题收敛

目标：

- 明确论文核心故事。
- 确定双层 alignment 的形式化定义。
- 定义 Lean 规格边界。
- 建立与 LIBERO-Safety 五类任务的 mapping。
- 固定 baseline 和 metrics。

交付：

- `paper_story.md`
- `method.md`
- `lean_spec_design.md`
- `system_architecture.md`
- `experiments.md`
- `related_work.md`

完成标准：

- 每个安全 failure mode 都能映射到 IntentAlign、EffectAlign 或外部 certificate。
- 不夸大 Lean 能力，明确连续世界假设边界。

## Phase 1: Minimal Lean Specification

目标：

- 实现最小 typed symbolic world。
- 定义 Object、Region、Relation、WorldState、Action、TaskIntent、SafetySpec。
- 实现少量核心 predicates。
- 支持 AAG 和 TSA 的最小检查。

建议范围：

- `Pick`
- `Place`
- `MoveThrough`
- `InRegion`
- `Holding`
- `ForbiddenObject`
- `SafeGraspPart`
- `NoContact`
- `FrameCondition`

完成标准：

- 能对手写 world state 和 action 返回 accepted / rejected / unknown。
- 能解释至少三类 violation：抓错物体、错误 affordance、移动禁止对象。

## Phase 2: Certificate Interface

目标：

- 设计 JSON 或 typed serialization schema。
- 将外部 perception / planner 的输出转成 Lean 可检查 facts。
- 区分 oracle certificate 与 noisy certificate。

建议 certificate：

- ObjectIdentityCert
- AffordanceCert
- CollisionFreeCert
- RegionOccupancyCert
- StateTransitionCert
- HumanClearanceCert

完成标准：

- 每个 certificate 都有 schema、validity check 和对应 Lean obligation。
- 缺失或过期 certificate 会产生 `unknown`。

## Phase 3: LIBERO-Safety Integration

目标：

- 将 LIBERO-Safety 的任务 annotation 映射为 `TaskIntent` 和 `SafetySpec`。
- 从仿真状态抽取 `WorldState`。
- 从 VLA action chunk 抽象出 symbolic action。
- 运行 baselines。

优先顺序：

1. AAG：最适合验证 affordance 和 object-part spec。
2. TSA：适合验证 region、path 和 frame condition。
3. SSR：适合验证 semantic safety spec。
4. FSHOA：需要更强 runtime monitor。
5. HRI：需要更细人手和 handover state abstraction。

完成标准：

- 每类至少有可复现实验脚本。
- 每个 episode 记录 action-level proof result。
- 能输出 violation breakdown。

当前状态：

- 已接通 LIBERO-Safety 原生 `OffScreenRenderEnv` / robosuite / MuJoCo 后端。
- 已配置 fixed init state，并确认真实 `env.reset`、`env.set_init_state`、`env.step(raw_action)` 可运行。
- 已下载 LIBERO-Safety assets，并将大资源放在 `/data0/ldx/libero_safety_assets`，通过 symlink 接入当前 checkout。
- 已生成在线 smoke / replay 结果到 `results/libero_online/`。
- `smoke_affordance_task2_init0.json` 证明真实 `OffScreenRenderEnv.step` 和 ProofAlign effect check 已执行。
- `replay_*` 结果只使用 `Stop + zero raw action` 的 action-file replay，用于证明在线链路，不可作为 VLA 指标。
- 已新增 `experiments/libero_vla_plugin.py`，支持通过 runner 加载 OpenVLA-OFT / OpenVLA policy，并默认把 Hugging Face 大文件缓存到 `/data0/ldx/huggingface`。
- 已用 conda 环境 `proofalign-libero` 中的 `uv` 固定 VLA 依赖到 `pyproject.toml` 的 `vla` extra 和 `uv.lock`，包括 OpenVLA-OFT `transformers` fork、`torch==2.2.0+cu121`、`protobuf==3.20.3`、`tensorflow-metadata==1.14.0`、`wandb==0.16.6`。
- 已将 OpenVLA-OFT 源码放在 `external/openvla-oft`，模型权重和 Hugging Face cache 放在 `/data0/ldx/huggingface`，uv wheel cache 放在 `/data0/ldx/uv-cache`。`/data0/ldx` 只放共享大文件，不作为代码工作区。
- 已跑通 OpenVLA-OFT standalone smoke：`scripts/smoke_openvla.py` 成功加载 `moojink/openvla-7b-oft-finetuned-libero-spatial` 并生成 8-step raw action chunk。
- 已跑通真实在线 VLA smoke：`results/libero_online/affordance_task2_init0_openvla_oft_smoke.json`。该 run 使用 LIBERO-Safety `affordance` task 2 / init 0，OpenVLA-OFT 输出 raw action，经保守 action abstractor 映射为 `MoveTo(fork_1, region=plate)`，ProofAlign intent/effect 均 `allow`。

论文数据缺口：

- 真实 VLA policy plugin 和单步 online smoke 已跑通，但还没有跑最小可报告规模的多 suite / 多 task rollout。
- action abstraction 已有保守初版：先将连续 VLA 控制映射为中间 `MoveTo`，接近目标并检测到 gripper close 后再升级为 terminal `Pick`；仍需用多步真实 rollout 校准阈值与 suite-specific contract，尤其是 `Place`、handover、pour、semantic unsafe tasks。
- 还没有 VLA only、collision checker、Intent only、Effect only、Dual Alignment 的同任务同 init state 对照实验。
- 还没有 task success、oracle unsafe label、false rejection、recovery、runtime overhead 等论文指标。
- 当前在线结果的 `lean_mode` 仍是 `mock`，需要安装 Lean / Lake 并让 checker 输出真实 `lean` 模式。
- 当前 rule-based intent parser 覆盖不足，很多 LIBERO-Safety 指令会被判为 unsupported，需扩展后才能报告 false rejection。

## Phase 4: Dual Alignment Ablations

目标：

- 对比 VLA only、collision checker、LLM verifier、Intent only、Effect only、Dual Lean。
- 量化每一层贡献。
- 分析 false rejection 和 runtime overhead。

完成标准：

- 每类任务有表格和 case study。
- 证明 Dual Alignment 的增益来自不同 failure mode，而不是简单更保守。

## Phase 5: Paper Draft

目标：

- 写成完整论文结构。
- 补充 theorem statements、implementation details 和实验结果。
- 明确 limitations。

建议结构：

1. Introduction
2. Related Work
3. Problem Formulation
4. Dual Lean Alignment
5. System Architecture
6. Experiments
7. Limitations
8. Conclusion

## 风险与缓解

### 风险 1: Spec 过强导致 false rejection

缓解：

- 报告 False Rejection Rate。
- 使用 spec strictness ablation。
- 将 hard constraints 与 preferences 分离。

### 风险 2: 上游 perception certificate 不可靠

缓解：

- 使用 oracle / simulator / noisy 三种 certificate 设置。
- 将 `unknown` 与 `rejected` 区分。
- 分析 state uncertainty 对系统行为的影响。

### 风险 3: Lean checking overhead 太高

缓解：

- 限制 action chunk 级检查范围。
- 缓存静态 domain theorem。
- 将连续计算留给外部模块。
- 报告 Lean checking time 与 certificate generation time。

### 风险 4: Novelty 被认为只是安全过滤器

缓解：

- 强调双层 alignment formulation。
- 展示 Intent only 与 Effect only 的互补性。
- 用 case study 展示 collision checker / LLM verifier 漏掉的问题。

### 风险 5: 过度 claim 真实机器人安全

缓解：

- 明确 prototype/research proposal。
- 强调 Lean 只检查离散抽象和 certificate。
- 在 limitations 中说明硬件安全和连续动力学不由本框架单独保证。

## 开放问题

1. 如何从自然语言稳定编译出 `TaskIntent`，并处理歧义？
2. 如何设计不过度保守但足够安全的 frame conditions？
3. action chunk 的最佳检查粒度是什么？
4. 当 Lean 返回 `unknown` 时，应该 re-observe、ask human、还是 safe stop？
5. 如何把 proof failure report 转化为 VLA 可用的 repair prompt？
6. 如何对 post-execution semantic hazard 做可靠 state abstraction？
7. 如何将 learned perception uncertainty 纳入 symbolic proof obligation？

## 近期 TODO

### P0: 生成可报告的 LIBERO-Safety VLA 数据

- 基于已接通的真实 VLA policy plugin `experiments/libero_vla_plugin.py` 跑批量 online rollout。
- 保留 `scripts/smoke_openvla.py` 和 `results/libero_online/affordance_task2_init0_openvla_oft_smoke.json` 作为 VLA 链路 smoke，不作为论文指标。
- 每个 step 必须包含真实 `raw_action` 和可信 `proofalign_action`，不能从裸连续动作硬猜 symbolic contract。
- 跑最小可报告规模：5 suites × 15 tasks × init0。
- 若时间允许，扩展到多个 init states，例如 5 suites × 15 tasks × 5 init states。
- 保存所有在线输出到 `results/libero_online/`，文件名使用 `<suite>_task<id>_init<id>_<method>.json`。

### P0: 补齐 baselines 和 ablations

- VLA only：直接执行 raw action，只记录 task success、collision/cost、runtime。
- Collision checker：加入几何 clearance / collision pre-check。
- Intent only：只启用执行前 ProofAlign check。
- Effect only：只启用执行后 ProofAlign audit。
- Dual Alignment：启用 intent + effect 两层。
- 所有方法必须使用相同 suites、tasks、init states 和 VLA action source。

### P0: 指标与汇总

- 在 online result 中记录 task success / `env.check_success()`。
- 记录 LIBERO-Safety `info["cost"]`、collision、人手距离、障碍物距离。
- 汇总 total episodes、success rate、collision rate、rejection rate、spec violation rate。
- 标注 unsafe / safe oracle labels，用于 unsafe action rejection rate 和 false rejection rate。
- 记录 per-step runtime，拆分 policy、abstraction、intent check、env step、effect check。
- 输出论文表格用 `results/libero_online/summary.json` 和 per-suite breakdown。

### P0: Lean 真实检查模式

- 安装 Lean / Lake toolchain。
- 确认 `uv run pytest` 和 online run 的 trace 中 `lean_mode` 为 `lean`，不是 `mock`。
- 若 Lean build 失败，先修复 `lean/ProofAlign`，再重新跑实验。

### P1: Action abstraction 与 parser 覆盖

- 支持 LIBERO-Safety 常见指令：`bring`、`pass`、`deliver`、`put both`、`pour ... to/onto`、handover、人手 plate、semantic unsafe verbs。
- 定义从 VLA metadata / skill label / detector 输出到 ProofAlign action 的 schema。
- 为 unsupported instruction 统计单独指标，避免把 parser 缺口误报为 safety gain。

### P1: Spec 和 certificate

- 为 AAG 写 5 个 concrete spec examples。
- 为 TSA 写 region and frame condition examples。
- 定义 oracle certificate format。
- 设计并落地 `ViolationReport` schema。
- 增加 certificate quality ablation：oracle / simulator / noisy / missing。

### P2: 写作

- 草拟 paper introduction。
- 将真实 LIBERO-Safety online 结果整理成主表和 per-suite case study。
- 在 limitations 中明确：Lean 检查离散 symbolic contract，不证明连续动力学和感知真值。
