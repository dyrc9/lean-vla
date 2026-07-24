# 失败教训与停止规则

## 1. 不把不可观察变量当作实验接口

只输出数值动作的 VLA 没有可审计的 policy plan。不能从 action 唯一反推 latent intent，也不能让外部
模型事后生成一句话再称为 VLA witness。主线应定义在可观察的 ActionBlock 与后果上。

## 2. 语义标签必须说明是谁生成的

`predicted_skill/target/effects` 是 consumer assessor 的预测，不是模型自报意图。必须记录 assessor
provenance、support、unknown 和校准；oracle/test labels 只能做负控，不能进入 efficacy estimate。

## 3. Lean 不能补偿世界模型误差

Lean 可以证明 digest/receipt/effect predicates 推出 phase-gating 性质；不能证明 learned predictor、
observer 或 simulator 对物理世界正确。每个 formal claim 都要同时列出 trusted assumptions。

## 4. 修改 action 后旧证据失效

projection、brake 或其他 intervention 产生新 ActionBlock/final command 时，必须重新 assessment、重新
编译 execution contract 并重新 authorization。沿用旧 digest 会把安全 filter 变成未审计旁路。

## 5. Unknown 不是安全

unknown/abstain 应阻止启用层的 allow，但必须作为 coverage/deadlock 代价报告。高拒绝率不能被包装成高
防御率。

## 6. 接触代理不能被 cost/collision 吞掉

R9 的 signal subset 在 cost/collision 上从 `15/15` 降到 `0/15`，但仍有 `11/15` residual contact
proxy。不同 observer endpoint 必须分别报告，不能据此声称完整物理安全。

## 7. Denominator gate 不能事后放宽

P0b 的 clean-eligible pair 为 23，低于预注册 26。即便趋势强，也只能是探索性结果。M2 population、
replacement、invalid 和 stopping rule 必须在 outcome 前冻结。

## 8. Fixed trace 必须真正共享输入

四臂不应各自调用随机 VLA 或 assessor。相同 proposal index 的 ActionBlock、assessment 和 execution
contract digest 必须完全一致；只有两层开关可不同。

## 9. 历史协议不覆盖新 estimand

旧 CTDA、PlanWitness、R9 和 preregistration artifacts 保留用于审计。可以复用 population、attack、
runner 或统计设计，但不能通过改名把旧 outcome 变成新 L1/Dual 证据。

## 10. GPU rollout 的停止规则

在以下条件满足前不运行新 outcome：

- M1 validator 通过；
- producer/victim/runner/digest/预算冻结；
- assessor qualification protocol 冻结；
- 用户明确授权；
- fresh output path 不存在；
- 没有隐式 replacement 或 threshold tuning。

## 11. SemanticSubtask 不取代双层问题

`Z_t` 是 L1 的结构化分解，不是新的第三个 alignment layer。论文不能从“直接 consequence assessor”摆到
“semantic hierarchy”后就丢掉原始 motivation：需要分别回答 ActionBlock 是否服务 trusted intent，以及
获准 ActionBlock 是否对应实际 execution/effects。

## 12. Prompt wiring 不等于 action control

把 `Z_t` 写入 prompt 并绑定 digest，只证明它在动作生成前成为显式输入。若固定 observation/noise 后动作
几乎不变，就不能声称形成可靠 hierarchical control；此时 `Z_t` 最多作为 verifier anchor，仍需 local
checker qualification。

## 13. Lean 卖点必须和 claim boundary 同时出现

Lean 不是事后形式化装饰：exact dispatch、transaction binding 和 phase-gating theorem 是 L2 的核心方法
贡献。但每次展示 Lean 结果时也必须同时声明 selector/assessor、Python refinement、sensor/observer 和
现实物理不在证明范围内。扩大 claim 会损害本来可辩护的形式化贡献。
