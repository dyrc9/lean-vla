# Implementation Notes

更新日期：2026-07-20

方法语义见 [`method.md`](method.md)，环境命令见 [`remote_execution.md`](remote_execution.md)。

实现阅读时只认两层 method：`trusted intent -> planned action` 与
`accepted planned action -> applied/observed action`。下面的 digest、Ed25519、source-bound geometry 与
AEGIS filter 都是保证测试对象绑定正确的 plumbing/可选 intervention，不是额外 alignment layer。

## 主要代码入口

- `src/proofalign/integrity_models.py`：`proofalign-integrity-v1` 独立 domain types；核心 transaction 对象、
  VLA-only/Intent-only/Execution-only/Dual arm 和统一 verdict；
- `src/proofalign/integrity_checker.py`：deterministic fast checker 与 exact-prefix authorizer；Intent 层检查
  typed skill/target/part/region，Execution 层检查 fresh state、monitor/proposal 与 final command binding；
- `src/proofalign/integrity_intervention.py`：pass、project/brake、replan、hard block 可替换 policy；filter
  输出不能继承 nominal authorization；
- `src/proofalign/integrity_runtime.py`：`FrozenMissionAdapter`、`PersistentContractMonitor`、
  `SingleDispatchBoundary`、`EffectObserverUpdater` 和三 transaction facade；当前只有 in-memory no-action
  sink；
- `src/proofalign/ctda.py`：typed contract/receipt/trace、digest、reference checker；
- `src/proofalign/ctda_runtime.py`：contract activation、prefix transaction、monitor、fallback receipt；
- `src/proofalign/ctda_wire.py`：strict canonical wire；
- `src/proofalign/ctda_evaluator.py`：Python reference、Lean kernel、shadow evaluator；
- `src/proofalign/ctda_shadow.py`：CPU replay；
- `src/proofalign/ctda_v2.py`：独立 v2 certificate/rebind lease、intervention、post-filter authorization、
  receipt replay guard 和 authenticated progress ledger reference checker；
- `src/proofalign/ctda_v2_wire.py`：六阶段 strict canonical `ctda-wire-v2`；拒绝
  v1/default-fill/extra/duplicate/noncanonical/digest/request-id tamper；
- `src/proofalign/ctda_v2_evaluator.py`：离线 Python reference、Lean kernel 与永不授权的 shadow parity；
- `src/proofalign/ctda_v2_golden.py`：冻结 21-case/6-stage outcome-blind parity corpus；
- `src/proofalign/benchmark/libero_online_runner.py`：Full CTDA environment/runner；
- `src/proofalign/benchmark/libero_e1_runner.py`：unguarded VLA-only observational arm；
- `src/proofalign/benchmark/libero_online_wrapper.py`：dispatch transaction；
- `src/proofalign/benchmark/libero_task_manifest.py`：BDDL-bound task/contact manifest；
- `src/proofalign/benchmark/safelibero_foundation.py`：官方 SafeLIBERO source/data inventory、obstacle
  displacement collision oracle、typed safety provenance、四象限与 CAR/TSR/ETS/cost/RET 汇总；
- `scripts/safelibero_aegis_readiness.py`：无 execute 模式的 source/data/environment 只读 preflight；
- `src/proofalign/benchmark/aegis_runtime.py`：双 Python environment、完整 distribution inventory、
  source identity、SafeLIBERO 注册和模型资产 digest 的 static runtime gate；
- `scripts/safelibero_aegis_runtime_preflight.py`：禁止 policy/simulator 构造、socket、推理和
  `env.step` 的 R1 runner；
- `scripts/safelibero_aegis_model_load_probe.py`：R2 顺序加载离线 GroundingDINO 与标准 pi0.5，
  禁止推理、socket、simulator 与 action；
- `scripts/safelibero_aegis_scene_probe.py`：R3 单场景 init/observation serialization；对 robosuite
  `MujocoEnv.step` 安装硬失败守卫；
- `src/proofalign/benchmark/safelibero_ctda_support.py`：exact On/In goal parser、32/32 source-bound mission
  template、typed state/progress/collision adapter、retained E1 与 exact-unit support audit；
- `src/proofalign/benchmark/safelibero_open_region.py`：固定官方 wooden-cabinet top-drawer joint source、
  `qpos < -0.14 m` strict predicate、typed state augmentation/progress claim；wrong source fail closed；
- `src/proofalign/benchmark/safelibero_ctda_v2_no_dispatch.py`：source/state-bound progress attestation、
  consumer-derived 7D command、fresh filter witness、adjusted-command membership/authorization 与
  non-refundable recovery ledger；无 env/policy/action/dispatch 接口；
- `src/proofalign/evidence_crypto.py`：exact producer/version Ed25519 message authentication；支撑性 TCB；
- `src/proofalign/benchmark/aegis_cbf_filter.py`：pinned AEGIS single-halfspace QP 等价投影、signed result 与
  no-dispatch CTDA filter adapter；可选低层 intervention；
- `src/proofalign/benchmark/aegis_cbf_geometry.py`：signed typed ellipsoid 输入到 CBF coefficient 的源码等价
  派生；raw perception 仍是外部假设；
- `scripts/ctda_v2_safelibero_state_coverage.py`：32/1600 no-step exact observation/site/collision-source gate；
- `scripts/ctda_v2_open_region_coverage_cpu_r2.py`：CPU OSMesa 50-init source/range/predicate no-step gate；
- `scripts/ctda_v2_no_dispatch_adapter_audit.py`：固定实现/前置 artifact hash、AST capability boundary 与
  6-case unit/fake-observation adapter gate；
- `scripts/ctda_v2_open_region_threshold_probe.py`：CPU OSMesa 直接注入五个事前固定 qpos，验证两类与
  exact strict boundary；只 `sim.forward()`，硬禁 `env.step`；
- `lean/ProofAlign/CTDAWire.lean`：四阶段 Lean checker。
- `lean/ProofAlign/CTDAV2.lean`：v2 post-proof freshness、context/lease、dual dispatch、pass digest 和 replan
  non-refund 初始 theorem；
- `lean/ProofAlign/CTDAV2Wire.lean`：六阶段 normalized wire 判定与 authorization/receipt 辅助 theorem。
- `lean/ProofAlign/IntegrityCore.lean`：最小四臂 semantics、dual authorization、exact execution command 与
  checked completion theorem；未声称已经 refinement 到 Python checker。

## 当前必须保持的不变量

1. minimal contract authority 只来自 `TrustedTaskArtifact -> MissionRoot -> ActiveContract`，不来自 policy
   prompt/metadata；
2. 四个 arm 共用同一 authorizer/boundary/updater，通过 `MethodArm` 开关 layer judgment；
3. Dual dispatch 必须同时具有 proven Intent 与 Execution pre-check；
4. Execution-only/Dual 的 applied command 必须等于 authorization 中的 exact final command；
5. adjusted command 必须重新进入 authorizer，不能消费 nominal command 的旧授权；
6. authorization one-use，receipt/effect/episode/proposal/monitor binding 不一致时不提交 monitor；
7. `pending`、`unknown`、violation 或缺 completion atoms 都不得推进 phase；
8. monitor transition 使用 compare-before-digest 原子提交，失败不产生部分状态；
9. current sink 必须保持 in-memory/no-action，不接 simulator/GPU/socket/hardware；
10. Python fast checker 与 Lean core 未有 refinement artifact 前，不得写 Lean-backed online authority。

历史 v1/v2 路径还必须保持：

1. semantic/prefix proof 前零 dispatch；
2. observed/monitor proof 前零 phase advance/next dispatch；
3. Lean failure 不回退 Python 授权；
4. shadow 永不授权；
5. fallback success 必须同时绑定 requested/applied command、actuator attestation、post-state 和完整
   postcondition；
6. canonical wire 使用 UTF-8、strict fields、finite typed values 和 integer nanoseconds；
7. v2 proof wall time 不消耗 semantic control-epoch lease，但 proof 后未 fresh rebind 仍不得 dispatch；
8. v2 `project_or_brake` 必须对 adjusted command 新做 membership，receipt 只能消费一次 authorization；
9. progress/replan 不退还 cumulative translation/motion，unknown provenance 不能解释为 safe。

## E1 shared-observer 实现（已完成）

E1-v3 的 paired-validity blocker 是 observation schema 非对称：Full CTDA 在初态 observation 前
安装 `task_manifest.contact_query`，VLA-only 没有。当前 `run_vla_only_episode_with_plugins()` 已显式
接受同一个 frozen task manifest，并在第一次
`state_observer.observe()` 前设置：

```python
wrapper.state_observer.contact_part_queries = (task_manifest.contact_query,)
```

这只是 observer schema 对齐；baseline 仍使用 `UnguardedObservationChecker`，没有 CTDA/legacy action
gate。新 runner 同时把实际 OpenPI RNG 绑定到 `policy_seed=1`，而不是只把 seed 写入 episode id。
测试和真实 no-dispatch probe 已证明：

- shared initialized observation -> identical digest；
- different query/manifest -> digest mismatch and preflight block；
- VLA-only trace 无 CTDA records，checker 始终 observational allow；
- Full CTDA 初态 digest 仍匹配 frozen E0 init0 digest；
- real policy output probe 24/24 arm 不调用 `env.step()`；
- 12/12 pair 的 initial digest、first chunk 和 E0 frozen digest 匹配。

独立入口为 `scripts/run_proofalign_e1_clean_utility.py` 与
`experiments/proofalign_e1_clean_utility_protocol.json`。共享 VLA-only module 只增加 frozen manifest
observer-schema 支持；旧 E1-v1/v2/v3 protocol 和 result 未被修改或续接。

## 验证

当前无实验验证结果：本轮只完成本地 no-action 验证，`tests/test_integrity_prototype.py` 为 28/28，
全量 suite 为 499 passed/1 skipped，`lake build ProofAlign` 通过。

```bash
export PATH=/home/ldx/lean-vla/.tools/lean-4.24.0-linux/bin:$PATH
export PYTHONPATH=/home/ldx/lean-vla/src:/home/ldx/lean-vla

.venv/bin/pytest -q \
  tests/test_integrity_prototype.py \
  tests/test_ctda_evaluator.py \
  tests/test_ctda_runtime.py \
  tests/test_libero_online_wrapper.py \
  tests/test_libero_online_runner.py
(cd lean && lake build ProofAlign)
git diff --check
```

以下是已冻结安全实验基础的历史复核入口，实验暂停期间不运行：

```bash
.venv/bin/pytest -q tests/test_safelibero_foundation.py
.venv/bin/python scripts/safelibero_aegis_readiness.py
.venv/bin/pytest -q tests/test_aegis_runtime.py
.venv/bin/python scripts/safelibero_aegis_runtime_preflight.py
.venv/bin/python scripts/safelibero_aegis_model_load_probe.py
.venv/bin/python scripts/safelibero_aegis_scene_probe.py
.venv/bin/pytest -q tests/test_ctda_v2.py tests/test_ctda_v2_wire_parity.py \
  tests/test_safelibero_ctda_support.py \
  tests/test_ctda_v2_state_coverage.py
.venv/bin/python scripts/ctda_v2_wire_parity_audit.py
.venv/bin/python scripts/ctda_v2_safelibero_state_coverage.py \
  --protocol experiments/ctda_v2_safelibero_state_coverage_protocol_r1.json
.venv/bin/python scripts/ctda_v2_open_region_coverage_cpu_r2.py
.venv/bin/python scripts/ctda_v2_no_dispatch_adapter_audit.py
.venv/bin/python scripts/ctda_v2_open_region_threshold_probe.py
```

第二条命令只建立 R0 foundation readiness，仍预期 `aegis_runtime_ready=false`。第四条命令建立独立
R1 static runtime readiness；当前预期 `static_runtime_ready=true`、五类禁止操作 counter 为 0、
`formal_rollout_authorized=false`。双环境与资产不复用仓库 OpenPI `.venv`，并显式区分标准
`pi05_libero` 与 safety-tuned `pi05_libero_safety`。后两条默认只复核 R2/R3 protocol；终态已是
`model_load_ready=true`、`scene_ready=true`、`env.step_count=0`，不要无理由再次加 `--execute`。
wire parity 命令默认只验证冻结 protocol；已封存 summary/artifact，不要对同一路径再次加 `--execute`。
原 `ctda_v2_support_audit_summary.json` 是 parity 前的 M0 support 快照，不应用当前源码覆盖。全量 state
r1 已封存为 1600/1600 state-key 和
1600/1600 collision-source coverage；不要为复核重跑 `--execute`，r0 的 1250/1600 负结果也不得覆盖。
OpenRegion R2 已封存为 50/50 exact joint source、finite range 和 strict predicate agreement；只运行上面的
默认 dry-run/hash preflight，不对已有 summary 再加 `--execute`。R0 因全部 GPU 占用在 sim 前停止，R1
因 wrapper 属性路径在 init read 前停止，二者均无 summary。R2 的 50 个 qpos 都为 `0.0 m`/closed，不能
据此声称 positive-state/transition 或 online producer 已验证。
adapter R0 已封存为 6/6 test、AST no simulator/socket/step/dispatch 和全零禁止操作 counter；默认命令仅
复核 protocol/hash，不对已有 summary 再加 `--execute`。当前 `ExactAllowlistEvidenceIssuer` 明确是
simulator/test TCB，不得写成 production signature、raw sensor authenticity、physical filter correctness 或
verified recovery controller。
strict-threshold R0 已封存为五点 requested/read-back exact、official/reference 5/5，精确 `-0.14 m`
为 closed；默认命令只验证 protocol/hash，已有 summary 不得重跑覆盖。直接 qpos injection 不得写成自然
drawer motion、transition dynamics 或 production sensor evidence。

`external/fiper/data` symlink 会使 generic baseline preflight 正确输出 `source_ready=false`；全量测试把
该状态作为预期 fail-closed 结果。不要为得到 ready preflight 而删除或改动 FIPER 数据绑定。历史
E0/E1/E3 execution protocol 的 source hash 仍不可变；当前源码只做 retained-artifact 离线分类验证，
不得用当前 runner 重新执行旧 protocol。

## Artifact 纪律

- runner 默认 read-only preflight；正式 mutation 需要显式 `--execute`；
- protocol pin source/checkpoint/external commit；
- fresh root、append-only ledger、per-episode hash、terminal manifest；
- invalid/unknown record 保留，不按 outcome 替换；
- 文档只更新 canonical 入口和 `evaluation_results.md`，阶段长报告进入 archive。
