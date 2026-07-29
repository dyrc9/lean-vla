# v12 无 outcome 资格实验 checkpoint

> 状态：2026-07-29 terminal。该 checkpoint 是 outcome-informed v12/v12.1 工程证据，
> 不覆盖 v11，也不授权 clean、attacked 或任何读取任务 outcome 的 rollout。

## 1. 已实现

v12 第一阶段把原来的“typed trigger 后立即结束 episode”拆为：

```text
Sparse L1 exact passthrough / hard reject
  -> bound shadow joint assessment
  -> deterministic escape selection
  -> independent RecoveryAuthorization
  -> revoke old policy authorization
  -> recover, re-observe, fresh replan
```

代码已包含：

- 稀疏 L1 的 hard/advisory/replan 决策和无风险 exact passthrough；
- 带 epoch、来源和 digest 的 trusted joint state；
- 绑定 state/action 的 shadow joint trajectory；
- deterministic recovery selection；
- old-policy authorization 永久失效、独立 recovery authorization/consume/complete；
- v12.1 controlled-escape selector：允许候选从 trigger region 内开始，但不得越过硬限位、不得超过
  冻结的瞬时 margin loss，并必须到达 safe margin。

## 2. 纯 contract qualification

冻结协议：
`experiments/proofalign_recoverable_alignment_v12_contract_qualification_protocol.json`。

| 子实验 | Cases | 主要结果 |
|---|---:|---|
| Q1 Sparse L1 | 315 | clean exact passthrough 100%；targeted reject 100%；action rewrite 0 |
| Q2 Analytic shadow contract | 220 | risk recall 100%；false trigger 0；binding mismatch fail-closed 100% |
| Q3 Recovery transaction | 120 | candidate coverage/completion/identity 100%；旧授权接受 0 |
| 合计 | 655 | 所有冻结 gate 通过 |

执行边界为 simulator create、`env.step`、policy load、dispatch、outcome read 全部为 0。该结果只证明纯
contract finite cases，不证明模拟器中的 recovery availability。

## 3. v12.1 simulator-reset preflight

冻结协议：
`experiments/proofalign_escape_recovery_v12_simulator_preflight_protocol.json`。它使用与 v11 scale45
outcome population 零重叠的 45 个 task/init pair；每个环境只注入 joint 5 的
`upper_limit - 0.05 rad` 合成状态，对 13 个固定 7D 原语做 10 步 shadow evaluation。

| 指标 | 结果 |
|---|---:|
| Valid pairs | 45/45 |
| Baseline model trigger | 45/45 |
| Recovery candidate coverage | 45/45 |
| Worst-suite coverage | 15/15 |
| Selected terminal safe | 45/45 |
| Selected hard-limit crossing | 0 |
| Selected transient-loss violation | 0 |
| Recovery completion | 45/45 |
| Old-policy authorization accepted | 0 |
| Simulator state restore identity | 45/45 |
| Policy load / policy dispatch / outcome read | 0 / 0 / 0 |

终态分类为 `escape_recovery_v12_simulator_preflight_pass`。这只授权下一步的 runtime integration 和
zero-policy fixed-trace transaction qualification。

## 4. 必须披露的限制

1. 协议冻结前做过一个不读 outcome 的 `human_safety task0/init1` 工程 pilot；它促使 v12.1 将
   “从 trigger region 内受控逃逸”与“轨迹全程位于 trigger region 外”分开。该 pilot 已在协议中披露。
2. 45/45 最终都选择 `negative_ry`，因此当前证据只覆盖一个合成 joint-5/upper-limit 模式，不证明
   其他 joint、lower-limit、速度/接触复合风险或 recovery library 多样性。
3. 相同初态和命令的 selected replay 只有 2/45 与 shadow qpos 序列逐浮点 bitwise 相同；但
   45/45 replay 都在无硬限位越界的情况下清除 model trigger。下一阶段必须冻结数值 tolerance、
   transaction receipt 和恢复后 fresh-policy 边界。
4. 运行中出现 MuJoCo `ncon=5000` contact-capacity warning，未产生记录到的 runtime exception，
   但必须作为 simulator diagnostic limitation 保留。
5. 本轮未加载 VLA、未派发 policy action、未读取 reward/success/cost/collision；不能据此判断 task
   utility、attacked efficacy、部署能力或真实物理安全。

## 5. 后续计划

按以下顺序推进，前一步 nonpass 即冻结并停止：

1. 把 typed escape recovery 接到 v12 L2 runtime，但只运行 zero-policy fixed trace；
2. 资格化 old-policy revoke、独立 recovery receipt、one-use、command identity、恢复后 fresh epoch；
3. 扩展合成 corpus 到 7 joints × upper/lower limit，并加入 qvel、workspace/contact hard gate；
4. 做不读取 outcome 的 policy-prefix predictive shadow qualification；
5. 上述 gate 全部通过后，另行冻结 fresh clean 四臂协议；
6. clean non-inferiority 通过后才允许分层 attacked cells。
