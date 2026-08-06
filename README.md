# ProofAlign: VLA ActionBlock 双层完整性

ProofAlign 研究 action-only VLA 在指令攻击下的两层防御：

- **L1（Intent–Action）**：判断 VLA 生成的 ActionBlock 是否仍服务于可信任务意图；
- **L2（Action–Execution）**：保证获准的 ActionBlock、实际命令、receipt 和 observed effects 属于
  同一个执行事务。Lean 用于固定这一层的有限事务语义。

主实验采用同一 runner 上的两个开关：

| Arm | L1 | L2 |
|---|---:|---:|
| VLA-only | off | off |
| Semantic-only（L1-only） | on | off |
| Execution-only（L2-only） | off | on |
| Dual（L1+L2） | on | on |

## 当前主线

以后判断项目进度，只按下面四步回答。唯一状态入口是
[`docs/current_status_and_roadmap.md`](docs/current_status_and_roadmap.md)。

1. **攻击复现已经完成**：复现 SABER `constraint_violation` 指令攻击，victim 为 OpenPI Pi0.5，
   benchmark 为 LIBERO-Safety。240/240 episodes 有效，clean-safe 到 attacked-risk transition 为
   `39/86 = 45.35%`。该值低于预注册 50% gate，因此攻击信号成立，但确认性 gate 为 non-pass。
2. **原方法已有完整主实验**：v15.3 在18个全新任务上完成 clean/attacked 四臂实验。L2-only 和
   Dual 在 attacked 中都把 actual crossing 与 joint-limit violation steps 降到0，但 Dual 的任务成功
   仍为 `11/18`，与 VLA-only 的 `11/18` 相同。结论是物理 containment 有效，任务层攻击防御尚未成立。
3. **优化方法clean已通过**：v15.14在18个新pair的clean四臂中，VLA/L1/L2/Dual均为`13/18`；L2与
   Dual为0 deadlock、0 crossing、0 joint-limit，最大force `6568.13 < 10000`，全部正式门通过。
4. **优化方法SABER-attacked主实验已通过**：同pair同seeds下，VLA/L1/L2/Dual task success为
   `11/18`、`13/18`、`11/18`、`13/18`；按episode统计的constraint-violation ASR为`22.22%`、
   `5.56%`、`0%`、`0%`。Dual同时保持`13/18`任务成功和0越界，72/72 attack binding与全部正式门通过。

当前预定的论文主线模拟器实验已全部完成，剩余是论文图表与最终审计。

## 原方法完整四臂结果（v15.3）

| Arm | Clean success | Attacked success | Attacked crossing | Attacked joint-limit steps |
|---|---:|---:|---:|---:|
| VLA-only | 11/18 | 11/18 | 393 | 744 |
| L1-only | 11/18 | 12/18 | 227 | 416 |
| L2-only | 11/18 | 11/18 | 0 | 0 |
| L1+L2 | 12/18 | 11/18 | 0 | 0 |

这张表是当前论文的主要 defense outcome。早期 v8–v14、v15.1–v15.6 结果属于方法开发、失败定位或
消融，不应在日常进度中逐版本复述。

## 文档

- [唯一当前状态与路线图](docs/current_status_and_roadmap.md)
- [方法定义与 claim boundary](docs/method.md)
- [论文故事](docs/paper/paper_story.md)
- [历史实验时间线（归档）](docs/progress_and_plan.md)
- [失败教训与停止规则（归档）](docs/failure_lessons.md)
- [文档导航](docs/README.md)

## 验证

```bash
.venv/bin/pytest -q
PATH="$PWD/.tools/lean-4.24.0-linux/bin:$PATH" lake --dir lean build ProofAlign
bash scripts/check_all.sh
```

历史冻结协议、non-pass 结果和 artifacts 继续保留用于论文审计与复现，但不再作为默认进度入口。
