# ProofAlign 失败实验与踩坑记录

更新日期：2026-07-24

## 1. 文档用途

本文记录已经发生过的实验失败、无效运行、科学 gate nonpass 和工程踩坑，目的是避免后续重复消耗
GPU、污染正式分母或扩大不成立的结论。

本文不是旧方案的恢复入口：

- 已废弃代码和旧 runner 不回到当前主线；
- frozen protocol/status 只用于审计，不得 resume；
- 重新尝试必须使用新版本、新 protocol、clean commit 和 fresh output root；
- 历史负结果必须保留，但不能与新实验合并计算。

## 2. 先区分五种失败

| 类型 | 含义 | 结果能否进入科学统计 |
|---|---|---:|
| `terminal-invalid` | schema、binding、环境或 validator 破坏了实验有效性 | 否 |
| `stopped-before-outcome` | 在 policy、probe 或 episode 前 fail closed | 否 |
| `partial/nonterminal` | 有部分文件，但没有 terminal manifest/完整矩阵 | 否 |
| `terminal nonpass` | 实验有效，但预注册科学 gate 未通过 | 可以报告 nonpass，不能升级为 positive |
| `valid exploratory` | 数据有效，但 population、统计或设计不支持确认性结论 | 只能作 scoped exploratory evidence |

以后写 summary 时必须先给出上述分类，再报告 task/safety 数字。不能用“程序跑完了”代替实验有效性，
也不能用“观察到一些正样本”代替预注册 gate。

## 3. 方法与 clean utility 踩坑

### 3.1 E1 v1：CUDA/EGL 绑定错误

- 现象：environment construction 前失败，没有有效 episode。
- 根因：把配置中的 GPU 编号当成实际 compute/graphics context，没有验证运行时物理设备。
- 教训：环境变量不是运行时证据。正式启动前后都要核验 JAX/CUDA compute context、EGL graphics
  context 和进程 PID 对应的物理 GPU。
- 防复发规则：GPU preflight 必须包含“配置值、visible index、EGL ordinal、physical index、PID
  context”五者的显式映射。

### 3.2 E1 v2：真实 policy metadata 无法序列化

- 现象：真实 policy output 中的 nested metadata 被旧 serializer 拒绝，dispatch 前终止。
- 根因：只用简化 fixture 测过 schema，没有用真实 first policy chunk 做 serialization probe。
- 教训：schema 测试必须覆盖真实模型输出的嵌套类型、NumPy/JAX scalar、array、tuple 和 optional 字段。
- 防复发规则：正式 rollout 前保存并往返解析一个真实但不 dispatch 的 policy output；失败时不得进入
  episode。

### 3.3 E1 v3：两个 arm 的 initial-state schema 不一致

- 现象：24 个 episode 都写出，但 12/12 pair 无效。
- 根因：Full arm 在第一次 observation 前安装了 contact query，VLA-only 没有，导致 initial-state
  digest schema 不同。
- 教训：paired causal experiment 中，treatment switch 之外的 observer、hook、schema 和 digest 必须
  完全一致。
- 防复发规则：四臂在 episode 0 前做 byte-equivalent state/observer audit；任一 arm 多字段、少字段或
  provenance 不同，整组不得启动。

### 3.4 CTDA v1：形式路径通过，但 clean operational utility 为零

- 有效结果：VLA-only `8/12` task/safe success，Full CTDA `0/12`，retention `0`；Full arm
  `12/12` block、`12/12` deadlock、`0` phase completion。
- 归因：9 个 episode 耗尽 semantic-contract wall-clock coverage，3 个耗尽 bounded-stutter
  no-progress limit；全部停在 `approach`。
- 根因：把 fail-closed mechanism correctness 当成方法可用性，contract lifetime 和 progress rule
  没有先经过 clean liveness gate。
- 教训：proof/parity 通过不等于系统有用；“全部安全停止”也不等于 defense success。
- 防复发规则：任何新方法先跑 clean utility，预注册 retention、phase completion、deadlock 和 unknown
  gate；clean gate 不过，不进入 attack-defense。

### 3.5 Lean 延迟不适合作为逐步实时 authority

- 现象：单 stage 约 `0.9–1.3 s`，历史 `100 ms/50 ms` deadline 多次 miss。
- 教训：当前 Lean 只能描述为 offline/shadow/slow-interlock assurance。
- 防复发规则：在线使用确定性 fast checker；只有建立实际 serialization/checker 与 Lean core 的
  refinement/equivalence 后，才允许写 “Lean-backed online judgment”，仍不能自动写成 real-time。

## 4. Schema、receipt 与 validator 踩坑

### 4.1 E3 post-dispatch：行为 fail closed，但 primary label 仍是 unknown

- 现象：12/12 episode 都在 observation blackout 后保持 phase、replan 并 exact zero-hold；恢复后
  oracle 为负，但正式分类仍是 `0 contained / 0 failed / 12 unknown`。
- 根因：冻结 classifier 要求 typed receipt schema 中不存在的顶层 `integrity_verified` 字段。
- 教训：runner、receipt schema 和 labeler 必须在冻结前做 contract test；行为看起来正确不能后验修改
  primary label。
- 防复发规则：用实际 receipt fixture 跑 classifier，逐字段验证 required/optional/derived 边界；冻结后
  只允许解释，不允许重标。

### 4.2 E4 v1：timeout 数值类型与 wire schema 不兼容

- 现象：第三个 fault case 写记录时 terminal-invalid。
- 根因：float timeout 进入只接受离散时间编码的 wire serializer。
- 修复经验：后续版本只改为整数纳秒，case、预期 verdict 和 classifier 均未改变。
- 防复发规则：时间、计数、索引和 digest 等边界字段使用唯一 canonical 类型；协议冻结前跑最小值、
  最大值、零值和非整数负例。

### 4.3 Action-envelope R7：validator 收到了错误对象

- 现象：96 个 binding probe 已通过，也产生了第一个 80-step episode JSON，但 ledger 为 0，run
  terminal-invalid。
- 根因：execution loop 把 frozen pair metadata 传给 validator，而 validator 要求完整 validated attack
  record。
- 教训：字段相似不代表对象可替换；validator 的输入身份必须和 protocol binding 一致。
- 防复发规则：在 GPU rollout 前，用第一条真实 record 完成端到端 validator dry-run；validator 函数使用
  typed 参数或显式字段名，禁止传递无类型 `dict` 后靠约定区分。

## 5. Attack qualification 踩坑

### 5.1 Phantom：discovery signal 没有通过 held-out gate

- discovery 中 strong laser 出现 `3/3` task failure；
- held-out 只有 `1/4` independent cost/collision transition，低于冻结 `2/4`；
- 唯一 unsafe 发生在 action 132，超出当时 conditional main 的 100-action window。

教训：

- discovery 与 held-out population 必须不相交；
- task failure 不能代替 independent safety transition；
- horizon/window 必须事前冻结，不能看到 late event 后扩窗；
- discovery 正结果不得直接升级为攻击复现成功。

### 5.2 早期 SABER diagnostic：不是 official-agent reproduction

- 手工 attack record 得到的数字只能作为 diagnostic；
- 非精确配对的 `dual_lean` 不能作为 Full method defense arm；
- official R1 在第一条 record artifact gate 就 fail closed，因此 attack efficacy 是
  `not_evaluated`，不是 0。

防复发规则：published attack claim 必须绑定官方 producer/source/model、outcome-blind record、
immutable record digest 和独立 victim run；人工样例不能混入正式分母。

### 5.3 SABER 中间运行：LIBERO config 生命周期和 mandatory-wait binding

- 一个版本在 LIBERO config 生命周期处理上失败；
- 另一个版本把 zero-step frame 与 mandatory-wait 后的 first policy frame 混用；
- 两者都没有进入可用科学分母。

防复发规则：

- config 路径必须绑定选定 checkout，runner 生命周期内不得被其他初始化覆盖；
- 明确区分 reset frame、zero-step binding frame、wait frame 和 first policy frame；
- frame digest、action chunk 和 episode identity 必须绑定到同一个 policy call。

### 5.4 SABER P0 R7：有效实验，但 attack gate nonpass

- `8/8` episode valid；
- 4 个 clean-eligible pair 中只有 `1/4 = 0.25` typed transition；
- 低于冻结的 count `>=2` 和 rate `>=0.5`。

教训：这是 terminal nonpass，不是实验无效，也不能据此泛化为 “SABER 无效”。正确动作是停止 defense
实验、保留结果、用独立新 population 重新设计，而不是调 threshold 或挑 pair。

### 5.5 P0b fresh1：用错 Python 环境

- 现象：在根 `.venv` 启动需要 OpenPI runtime 的 producer/victim 路径，正式 record 前 terminal。
- 教训：`python --version` 不足以证明环境正确；必须验证 interpreter 路径、关键 import 来源、
  checkpoint loader 和 GPU backend。
- 防复发规则：protocol 绑定 interpreter、environment digest 和关键 package/source path；先做
  no-outcome import/model probe。

### 5.6 P0b fresh2：transition 很多，但 denominator 不够

- `48` immutable record，clean/attacked `96/96` valid；
- clean-eligible pair `23 < 26`；
- 其中 `15/23` 有 typed transition。

教训：条件 transition rate 不能弥补 clean denominator 不足。正式分类必须保持
`p0b_blocked_insufficient_clean_baseline`，不能看到 15 个 signal 后后验升级 qualification。

## 6. Action-envelope R2–R9 资源与运行链

| Revision | 终止点 | 根因 | 永久规则 |
|---|---|---|---|
| R2 | attacked rollout 前 | policy command 出现 non-finite value | proposal 构造前做 finite check；non-finite 只能进入可审计 zero-brake |
| R3 | binding probe 前 | GPU resource contention，且 graphics context 落到意外 GPU | 启动后验证 PID compute/graphics context；外部占用出现即 terminal stop |
| R4 | policy load 前 | launcher/protocol 未提交，被 clean-worktree gate 拒绝 | runner、protocol、validator 必须先 commit，再启动 |
| R5 | binding probe 前 | 把 `MUJOCO_EGL_DEVICE_ID` 当 physical index；实际是 EGL ordinal | 从 `EGL_NV_device_cuda` 解析 ordinal→physical mapping |
| R6 | policy load 前 | `CUDA_VISIBLE_DEVICES` 下 EGL 返回 visible index，却直接与 physical index 比较 | visible index 必须经过 ordered visible-device list 转回 physical index |
| R7 | 首个未验证 episode 后 | validator 绑定 pair metadata，而不是完整 attack record | rollout 前执行真实 record 的端到端 validator dry-run |
| R8 | 最后一个 binding 前 | EGL GPU 出现外部 compute process | binding probe 全有或全无；外部 process 出现时不保留部分通过结果 |
| R9 | terminal complete | 修复上述边界后完成 | root 冻结，只读保存，不 resume、不覆盖 |

这一串失败说明：GPU 空闲快照、环境变量和单元测试都不够。正式 runner 必须把资源身份、数据身份和
validator 身份放在同一个 runtime gate 中。

## 7. 外部 baseline 的未完成陷阱

- EDPA P1a 在 OpenPI CLI parsing 阶段、policy/simulator/episode 前终止，因此没有 efficacy 数字；
- SAFE partial 没有 terminal manifest，也没有完成 detector training；
- FIPER fresh1 没有 terminal manifest；fresh2 被明确停止，只有 30 个 partial pickle，不覆盖完整
  seed/task/method/window matrix。

永久规则：

1. partial 文件不等于结果；
2. 没有 terminal manifest、完整 unit registry、missing/invalid accounting 和 checksum，不进入表格；
3. 被停止的 service/root 不 resume；
4. baseline 必须与主方法共享 proposal、population、oracle、fallback、horizon 和 endpoint；
5. detector alarm、task failure 和 method block 都不能替代 independent unsafe label。

## 8. 新实验启动前检查清单

### 代码与协议

- runner、protocol、validator、schema 全部已提交，工作区干净；
- output root 不存在；
- protocol 绑定 commit、source、checkpoint、interpreter、camera、population 和 validator digest；
- representative real policy output、receipt 和 attack record 已完成 serialization/validator dry-run。

### 四臂一致性

- observer、state schema、dispatch、intervention、seed、horizon 和 validator 完全一致；
- treatment switch 只有 Intent–Plan / Plan–Execution enabled flag；
- fixed-trace 下 proposal byte-identical；
- episode 0 前 state/observer digest parity 通过。

### GPU 与环境

- 记录 physical GPU inventory 和 ordered `CUDA_VISIBLE_DEVICES`；
- 显式解析 EGL ordinal、visible index 与 physical index；
- policy load 和 env create 后读取实际 PID compute/graphics context；
- binding/episode 期间监控外部 compute process；
- interpreter 与关键 import path 符合 protocol。

### 统计与 terminality

- denominator、transition、clean utility、bootstrap 和停止 gate 已冻结；
- invalid/missing 不替换；
- gate nonpass 不补样、不换 pair、不调 threshold；
- protocol、manifest、ledger、per-episode artifact、summary 和 SHA-256 齐全后才算 terminal。

## 9. 审计入口

当前仍保留的机器入口：

- [`action-envelope terminal summary`](../experiments/saber_integrity_action_envelope_terminal_summary.json)
- [`P0b status`](../experiments/saber_threat_replication_p0b_status.json)
- [`action-envelope failure taxonomy`](../experiments/action_envelope_failure_taxonomy.json)
- [`项目进展与规划`](progress_and_plan.md)

Action-envelope R3–R8 的 status JSON 仍在 `experiments/`。更早、已从工作树删除的长文档和 artifact 可从
Git 历史恢复，例如：

```bash
git show 079723992c7d69f793b121928f39d84e2010927a:docs/evaluation_results.md
git show 079723992c7d69f793b121928f39d84e2010927a:docs/attack_reproduction_evidence_audit.md
```

恢复只用于审计；不要把历史 runner 或 root 重新作为当前执行入口。
