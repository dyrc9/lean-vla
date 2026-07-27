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

 external prompt P_t^atk ────┐
 injected policy image O_t^atk ├─> frozen π0.5 ─> ActionBlock candidates
 attacked history H_t^atk ───┘                         |
                                                        v
                       trusted (T, O_t^T, Z_t) ─> local checker/select/reject
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

- `src/proofalign/semantic_trust.py`：TCB allowlist、context、`Z_t` artifact、验证和固定 prompt 编译；
- `src/proofalign/semantic_action_selection.py`：要求候选 digest 等于 trusted `Z_t` artifact，再做
  ActionBlock 过滤、投影后复检和确定性选择；
- `tests/test_semantic_trust.py`：输入换绑、非法 frontier、unknown、外部 prompt/图像注入和伪造模型测试。

## 4. 外部 prompt 注入

部署路径使用固定编译器：

```text
Task: <trusted T>
Current semantic subtask: <canonical Z_t>
```

编译函数没有 `external_prompt` 参数，exact bytes 和 digest 被绑定到 ActionBlock。外部 prompt 默认被
丢弃，不能拼接到 trusted action prompt。

攻击评估可以有意绕过这项预防，把 `P_t^atk` 只送入 action-policy branch，以测量 semantic/local
checker 能否拒绝由 prompt injection 引起的错误 ActionBlock。即使在该评估模式中，`P_t^atk` 仍不能
进入 `Z_t` selector 或 trusted local checker。

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
3. action policy 使用 `P_t^atk/O_t^atk`；
4. 同一 clean/attack pair 共享 trusted context 和 `Z_t` artifact；
5. 分别报告 selector error、checker false allow、unknown、clean reject 和 attack success；
6. 若无法证明 trusted tap 位于攻击前，结果只能称为同视图一致性实验，不能称为视觉注入防御。

这一边界使研究问题变为：在可信语义锚点不变的情况下，外部 prompt/视觉注入把 π0.5 ActionBlock
带偏后，consumer 能否在执行前发现并拒绝偏离。
