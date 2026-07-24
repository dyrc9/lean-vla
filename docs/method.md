# ProofAlign 方法定义

更新日期：2026-07-24

本文是当前方法与 claim boundary 的规范性来源。ProofAlign 只研究两个不能互相推出的完整性关系：

```text
trusted task intent
  -- Intent–Plan Integrity --> accepted planned action
  -- Plan–Execution Integrity --> applied and observed action
```

## 1. 研究问题

VLA 的语言、视觉、历史和输出 action chunk 都可能被攻击或发生故障，由此产生两类偏移：

1. **Intent–plan mismatch**：proposal 对受攻击输入自洽，但偏离可信任务的对象、阶段、顺序或剩余
   obligation；
2. **Plan–execution mismatch**：proposal 被接受后，filter、dispatch、applied command、receipt 或
   observed effect 与被授权的 exact command 不一致。

语义 gate 不能证明被接受的动作真正执行；低层 filter 也不能判断一个局部可行动作是否符合原始任务。
ProofAlign 的目标是在明确的 trusted computing base（TCB）内，对两个边界进行 complete mediation。
它不证明一般机器人安全、完整连续动力学、硬件诚实或实时控制正确性。

## 2. 方法核心

### 2.1 两个不变量

```text
No dispatch without dual authorization:

Dispatch(u_i)
  => Refines(ActiveContract_i, MissionRoot, phase_i)
     and AuthorizedExactPrefix(u_i, state_i, monitor_i, ActiveContract_i)
```

```text
No phase advance without checked completion:

Advance(phase_i, phase_i+1)
  => CheckedCompletion(accepted_history ++ observed_prefix,
                       ActiveContract_i,
                       required_post_evidence)
```

### 2.2 五类对象

| 对象 | 职责 |
|---|---|
| `MissionRoot` | 从可信 task artifact 冻结任务、phase、target 和 obligation |
| `ActiveContract` | 表达当前 phase 允许做什么、何时算完成 |
| `ActionProposal` | VLA 提出的 raw command/prefix |
| `PrefixAuthorization` | 对 fresh state 下一个 exact final command 的短时、单次授权 |
| `ExecutionEvidence` | 绑定 authorization、dispatch receipt、observed command/effect 与 completion |

跨 proposal 的 phase、history、last proposal index 和 contract 状态由 persistent monitor 保存；monitor
不是第三个 alignment layer。

### 2.3 三个 transaction

1. `MissionRoot + monitor -> ActiveContract`
   - contract 只能由可信 mission root 导出；
   - policy prompt、RGB 或自报 contract metadata 无权改变 contract；
   - unsupported/ambiguous 输入必须返回 `unknown`。
2. `contract + fresh state + monitor + proposal -> PrefixAuthorization`
   - authorization 绑定 mission、contract、episode、state、monitor、proposal index 和 final command；
   - filter 修改 nominal command 后，必须授权修改后的 command；
   - stale、replay、cross-episode 或 evidence 不足时不 dispatch。
3. `authorization + receipt + observed effect -> monitor update`
   - receipt 和 observation 必须绑定同一 authorization 与 applied command；
   - `pending` 不等于完成；
   - 只有 checked completion 才能原子推进 phase，失败不能留下部分状态更新。

## 3. Verdict、intervention 与四臂

外部 verdict：

- `allow`：形成可 dispatch 的 exact、fresh、单次 authorization；
- `pending`：prefix 已检查，但 contract 尚未完成；
- `complete`：completion evidence 完整，可推进 phase；
- `reject`：已知违反 contract、binding 或 hard invariant；
- `unknown`：输入、observer、checker 或 TCB evidence 不足。

`pass`、`project_or_brake`、`replan`、`hard_block` 是 intervention，不是新的逻辑层。projection 后的
command 必须重新进入 exact-command authorization。

四臂只切换两个完整性层：

| Arm | Intent–Plan | Plan–Execution |
|---|---:|---:|
| VLA-only | 否 | 否 |
| Intent-only | 是 | 否 |
| Execution-only | 否 | 是 |
| Dual | 是 | 是 |

四臂必须共享 victim、population、seed、observer、dispatch、intervention、schema 和 validator，避免把
runner 差异误当成方法增益。

## 4. 威胁模型与 TCB

不可信范围包括 policy-facing instruction/RGB/history、VLA proposal、自报 symbolic effect/completion、
stale 或 cross-episode artifact、command substitution 和伪 completion。

当前 TCB 包括：

- benchmark-owned task/init artifact 和 trusted instruction 的冻结结果；
- reference monitor、persistent state 与唯一 dispatch boundary；
- 声明为可信的 simulator state/receipt adapter；
- 具体 fast checker 与输入序列化。

当前不抵抗 mission authority/reference monitor 被攻陷、同 host/UID 任意代码执行、恶意硬件信号、未
建模的接触动力学，或 policy 与 monitor 共用被攻陷 observer 的确定性失效。SHA-256 digest 证明对象
身份与绑定，不证明 producer 诚实或物理事实为真。

## 5. Lean 的角色

[`IntegrityCore.lean`](../lean/ProofAlign/IntegrityCore.lean) 形式化两个不变量和四臂语义；Python
`DeterministicFastChecker` 是当前在线 reference checker。二者尚无 machine-checked refinement，因此
允许的表述是“Lean specification + Python reference runtime”，不能写成“Lean-backed realtime
authority”。

下一阶段要补的是对实际 schema、serialization 和 checker decision 的 equivalence/refinement evidence，
而不是增加更多公开协议层。

## 6. 当前证据边界

R9 只实证评估了 Execution-only action-envelope intervention。它表明固定 workload 上 execution-time
projection 具有探索性缓解效果，但不能推出 Intent-only 或 Dual 有效，也不能推出一般攻击防御和完整
物理安全。

下一轮必须先确认独立 attack population，再按 fixed-trace、clean closed-loop、attacked closed-loop 的
顺序做四臂因果比较。具体 gate 见 [实验规则](experiments.md) 和
[项目规划](progress_and_plan.md)。
