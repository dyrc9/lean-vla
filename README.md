# ProofAlign: VLA ActionBlock 跨层完整性

ProofAlign 面向只暴露连续数值动作的 action-only VLA。系统在 consumer/dispatch boundary 保护同一个
source ActionBlock 从可信任务判断到实际执行证据的身份连续性：

- **L1（Trusted-context assessment）**：从独立可信任务与观察分支产生当前合法子任务，并对 VLA 实际
  输出的 exact ActionBlock 做 checker-relative assessment；
- **L2a（Execution transaction）**：把 contract、一次性 authorization、ordered dispatch、receipt 和
  observed effects 绑定为同一事务；
- **L2b（Covered containment）**：在接近关节边界时，对同一 source ActionBlock 的有限 guard
  configurations 做有界 screening。

主实验采用同一 runner 上的两个机制开关：

| Arm | L1 | L2a+L2b |
|---|---:|---:|
| VLA-only | off | off |
| L1-only | on | off |
| L2-only | off | on |
| Dual | on | on |

## 当前主线

唯一状态入口是 [`docs/current_status_and_roadmap.md`](docs/current_status_and_roadmap.md)。默认只讲一个
最终系统，不叙述内部版本演进。

1. **SABER 攻击已成功复现**：OpenPI Pi0.5 与 LIBERO-Safety 上的冻结
   `constraint_violation` instruction records 共完成240个有效 episodes；86个 clean-eligible units 中有
   39个产生新的 risk transition，观测 ASR 为 `39/86 = 45.35%`，95% base-pair cluster-bootstrap CI 为
   `[32.93%, 57.78%]`。
2. **最终 ProofAlign 已完成配对四臂实验**：18个 held-out pairs、clean/attacked 共144个 episodes。
   attacked task success 为 VLA/L1/L2/Dual `11/18、13/18、11/18、13/18`，violation episodes 为
   `4/18、1/18、0/18、0/18`。Dual 同时得到 `13/18` task success 和 `0/18` observed violation episodes。
3. **当前重心是论文初版**：先固定 Introduction、Background、Problem Definition/Threat Model、Method 和
   Evaluation 的完整叙事，再根据初稿暴露的证据缺口选择补充实验。
4. **补充实验后置**：更多 seeds、其他攻击族、camera-only trusted perception、真实机器人或更强的
   execution attestation 都属于初稿之后的定向扩展，不作为当前写作的前置条件。

## 文档

- [当前状态与路线图](docs/current_status_and_roadmap.md)
- [中文论文叙事母稿](docs/paper/paper_narrative_zh.md)
- [方法与 claim boundary](docs/method.md)
- [最终四臂结果](docs/paper/final_four_arm_results.md)
- [ActionBlock长度与候选采样数消融](docs/paper/actionblock_sampling_ablation.md)
- [相关工作定位](docs/paper/related_work.md)
- [文档导航](docs/README.md)
- [历史审计归档](docs/archive/README.md)

## 验证

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" lake --dir lean build ProofAlign
bash scripts/check_all.sh
```

历史协议、内部版本、开发过程和冻结分类继续保留用于审计与复现，但不进入默认论文叙事。
