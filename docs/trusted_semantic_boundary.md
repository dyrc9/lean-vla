# `Z_t` 的可信输入边界

## 1. 结论

当前方法把 semantic branch 和 action-policy branch 物理/软件上分开：

```text
                 trusted semantic branch

 signed task adapter T ───────┐
                             ├─> frozen task graph / selector ─> Z_t
 secure pre-attack tap O_t^T ┘                 |
                                               +─ exact artifact binding

                  potentially attacked branch

 policy prompt P_t^pol ──────┐
 policy image O_t^pol ────────┼─> frozen π0.5 ─> source ActionBlock
 policy history H_t^pol ─────┘                         |
                                                        v
                       trusted (T, O_t^T, Z_t) ─> local checker/allow/reject
```

`Z_t` 的生成接口只接收 `T`、安全分叉前的 `O_t^T`、合法 task-graph frontier、历史可信
subtask 和冻结 selector。外部 prompt、policy-facing 图像和 history 不属于该接口，因此不能直接改变
`Z_t`。

这里“可信”有一个严格含义：

> 在 task adapter、observation tap、secure split、selector checkpoint 和 selector config 均是
> allowlisted TCB 的假设下，系统能验证 `Z_t` 来自指定输入、指定模型和指定状态 epoch，并且属于绑定的
> 合法候选集。

它不等于“模型的语义判断必然正确”。冻结 selector 的现实正确性仍需用独立 qualification set 测量；
false selection、低 margin 和 OOD 必须产生 `unknown/reject`。

还必须区分**可信来源**与**强制授权范围**。`Z_t` 的 provenance、合法 frontier 和 state epoch 属于硬绑定；
速度、工作区、unexpected contact、stale/malformed command 与 unknown evidence 属于当前实现的 hard gates。
相比之下，task-progress、release/close progress 和 expected-effect miss 在最终实现中是 advisory：它们要求
记录异常并在下一 ActionBlock 重新观察、重新规划，但不一律阻止当前 block。因此 L1 的可支持主张是
trusted-task monitoring、audited replanning 与相对于冻结 checker 的有限授权，而不是完整 semantic
soundness，也不是“所有偏离可信任务的动作都会在执行前被拒绝”。

## 2. TCB 与不可信输入

Semantic TCB 包含：

- 可信任务 adapter 及其 immutable digest；
- 取得 `O_t^T` 的 observation tap；
- 位于任何可攻击 transform 之前的 secure split；
- task graph、候选编译规则；
- 冻结 semantic selector checkpoint 和 config；
- `Z_t -> ActionBlock` local checker、选择器和 digest/ledger；
- consumer/dispatch boundary。

不可信输入包括：

- 外部用户、网页、文件或上游 agent 提供的附加 prompt；
- 进入 action policy 的图像 overlay、patch、替换帧或软件注入；
- policy-facing history、memory 和 tool output；
- π0.5 在这些输入下生成的 ActionBlock。

π0.5 checkpoint 可以是已知且 immutable 的，但它的输入和输出仍处于攻击实验面中。系统不因
“checkpoint 可信”而自动信任 ActionBlock。

## 3. `Z_t` 的最小绑定

每个 `TrustedSemanticContext` 绑定：

```text
episode_nonce / proposal_index / state_epoch
trusted_task_digest + task_source identity
trusted_observation_digest + observation_tap identity
secure_split identity
task_graph_digest + ordered candidate_set_digest
previous_subtask_digest
selector_model identity + selector_config_digest
```

已知 `Z_t` 只能从当前 candidate frontier 中签发。`SemanticSubtaskArtifact` 再绑定：

```text
semantic_context_digest
selector model/config
canonical selected_subtask
selection_method / timestamp / known / margin
```

观察摘要、state epoch、候选 frontier、模型或配置中任一项变化，旧 `Z_t` 均不能复用。ActionBlock
checker 和选择器引用 `SemanticSubtaskArtifact.artifact_digest`，不能在看完动作后重新命名意图。

工程实现：

- `src/proofalign/semantic_trust.py`：TCB allowlist、context、`Z_t` artifact 和验证；其中的固定 prompt
  编译辅助只用于历史/qualification 路径，不是最终四臂中 π0.5 的 policy-input authority；
- `src/proofalign/semantic_action_selection.py`：要求候选 digest 等于 trusted `Z_t` artifact，再做
  ActionBlock 过滤、投影后复检和确定性选择；
- `tests/test_semantic_trust.py`：输入换绑、非法 frontier、unknown、外部 prompt/图像注入和伪造模型测试。

## 4. Policy-facing instruction 攻击

必须区分 authoritative task artifact `T` 与 action policy 实际读取的 `P_t^pol`：

```text
T -------------------------------> semantic selector / checker authority
 \-> clean serialization -> P_t^pol -> π0.5 -> source ActionBlock
                         \-> SABER mutates exact bytes in attacked condition
```

clean 条件下，`P_t^pol` 是 `T` 的正常 benchmark serialization；SABER 条件下，冻结攻击记录修改 policy
branch 中的 exact prompt bytes。系统把 policy prompt digest 与返回的 ActionBlock 绑定，用于证明攻击记录、
prompt 和动作的 provenance；该绑定不把 `P_t^pol` 提升为 semantic authority。

无论 clean 还是 attacked，`P_t^pol` 都不能进入 `Z_t` selector 或 trusted local checker，`Z_t` 也不写入
π0.5 prompt。这样，最终四臂测量的是 consumer-side monitor 对受攻击 policy output 的作用，而不是 prompt
重写或 hierarchical action conditioning 的效果。

## 5. 视觉注入

当前覆盖的是**安全分叉之后**的数字/软件视觉注入：

```text
camera/verified frame
        |
     secure split
      /       \
 O_t^T         attack transform -> O_t^atk
 semantic/checker                  π0.5
```

因此攻击可以改变 policy action，但不能同步改变 `Z_t` 和 checker 的可信场景依据。实验必须分别记录
`trusted_observation_digest` 与 `policy_observation_digest`，不能用同一个字段含混表示。

当前不覆盖：

- 在 secure split 之前直接欺骗物理相机的贴纸、投影、光学扰动；
- 同时替换 trusted tap 和 policy view 的 root-level frame injection；
- 攻击者修改 selector/checker 内存、allowlist 或 digest ledger；
- 被标记为可信但本身错误/恶意的任务源。

前两项若要覆盖，需要独立可信传感器、物理冗余/一致性检查或更强的 capture attestation；仅靠软件
digest 不能证明图像对应真实世界。

## 6. 实验要求

后续 prompt/visual injection 实验必须满足：

1. 在 attack transform 前保存并绑定 `O_t^T`；
2. `Z_t` 和 local checker 只使用 `T/O_t^T`；
3. action policy 使用可能被攻击的 `P_t^pol/O_t^pol`；
4. 同一 clean/attack pair 共享 trusted context 和 `Z_t` artifact；
5. 分别报告 selector error、checker false allow、unknown、clean reject 和 attack success；
6. 若无法证明 trusted tap 位于攻击前，结果只能称为同视图一致性实验，不能称为视觉注入防御。

这一边界使研究问题变为：在可信语义锚点不变的情况下，外部 prompt/视觉注入把 π0.5 ActionBlock
带偏后，consumer 能否在冻结 checker 的覆盖范围内识别 hard risk，并对 task-progress mismatch 留下可审计
记录、触发下一 block 重规划。
