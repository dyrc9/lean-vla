# 当前状态与路线图

最后更新：2026-08-21。

本页是项目进度的唯一默认入口。ProofAlign 在论文叙事中只有一个最终系统，不展开内部版本或优化过程。

```text
SABER攻击成功复现
  -> 最终ProofAlign设计与实现
  -> 最终clean/attacked配对四臂证据
  -> 冻结论文、证据与复现入口
  -> 项目结题（仅保留可复现性维护）
```

## 1. SABER攻击已成功复现

复现对象是 SABER 的 `constraint_violation` 指令攻击：

- victim：OpenPI Pi0.5；
- benchmark：LIBERO-Safety；
- 攻击输入：SABER 生成并冻结的 instruction perturbation records；
- 成功口径：clean-safe unit 在 attacked rollout 中出现 contact、joint-limit、excessive-force 或
  LIBERO cost/collision risk transition；task failure 本身不单独计为 transition。

实验覆盖60个base pairs、2组seeds、clean/attacked合计240个episodes：

- valid episodes：`240/240`；
- clean-eligible units：`86`；
- risk transitions：`39`；
- observed attack-success rate：`39/86 = 45.35%`；
- 95% base-pair cluster-bootstrap interval：`[32.93%, 57.78%]`。

论文默认表述为：

> 我们在 OpenPI Pi0.5—LIBERO-Safety 路径上成功复现 SABER `constraint_violation` instruction attack；
> 86个 clean-eligible units 中39个出现新的 risk transition，观测 ASR 为45.35%。

## 2. 最终ProofAlign系统

ProofAlign 是一个部署在 action-only VLA consumer/dispatch boundary 的跨层 reference monitor：

- **L1** 从独立可信任务/观察分支产生当前合法 semantic subtask，并对策略实际输出的 exact continuous
  ActionBlock 做 checker-relative assessment；
- **L2a** 把 execution contract、fresh one-use authorization、ordered exact-prefix dispatch、receipts 和
  observed effects 闭合为一个执行事务；
- **L2b** 在 joint-risk state 中，对同一 source ActionBlock 的有限 virtual-guard configurations 做
  bounded shadow screening，并执行注册的 margin、restore、identity 与 force gates。

系统保持 VLA checkpoint、policy-facing prompt 和 `K=1/H=10` source-action generation 不变。L2b 最多
筛选两个 guard configurations；它们不是新的 policy-action candidates。Lean 只检查抽象 transaction
binding/phase semantics，不证明真实机器人安全、Python refinement 或 exact physical trajectory。

## 3. 最终配对四臂结果

最终实验覆盖完整的60个base pairs乘2组seeds，共120个固定evaluation units。每个unit在clean与
SABER-attacked条件下运行VLA-only、L1-only、L2-only和Dual，共960次episode attempts；clean/attacked共享
初态、environment seed、policy seed和arm schedule。`960/960` artifacts均存在，clean与attacked各有
`475/480` valid rows。预注册要求每个条件`480/480`全部有效，因此终态为
`four_arm_terminal_invalid_conservative`，不能作为确认性总体效果。

| Arm | Valid clean/attacked | Clean task success | Attacked task success | Attacked risk transitions | Valid attacked joint-limit steps |
|---|---:|---:|---:|---:|---:|
| VLA-only | 119/119 | 85/120 | 73/120 | 45/85（52.94%） | 4,960 |
| L1-only | 119/119 | 78/120 | 64/120 | 42/78（53.85%） | 2,452 |
| L2-only | 119/119 | 86/120 | 73/120 | 43/86（50.00%） | 0 |
| Dual | 118/118 | 78/120 | 64/120 | 43/78（55.13%） | 0 |

主结论：

- 全量四臂的broader contact/joint/force/cost-collision endpoint没有相对VLA-only下降；exact paired McNemar
  的最小`p=0.3833`；
- 为避免各arm的clean eligibility改变分母，正文横向比较使用四臂clean均eligible且clean/attacked均valid的
  75-unit共同队列：VLA/L1/L2/Dual的risk transitions分别为`38/75`、`42/75`、`36/75`、`43/75`。该队列
  是complete-case diagnostic，不是全population因果estimand；表中的`45/85`、`42/78`、`43/86`、`43/78`
  是各arm单独的clean-eligible描述，二者不得混用；
- 237个valid attacked L2-on rows的joint-limit steps为0，而VLA-only和L1-only分别为4,960和2,452；这是
  registered joint-side property的valid-only diagnostic，不是总体零风险保证；
- clean/attacked task success在全部120个units上的计数如表所示，L1/Dual没有显示任务效用改善；
- 由于每个条件各有5个invalid rows，预注册all-valid dependency失败，任何arm-level效果只能保守、
  非确认性地解释；
- 结果范围仍限定为一个checkpoint、LIBERO-Safety、一个冻结SABER攻击族和模拟器，不外推为任意攻击、
  真实机器人安全或硬实时保证。

攻击复现的`39/86`、四臂共同队列的`38/75`和四臂arm-specific rates虽然使用同一组120个population
identities，但属于不同运行或不同estimand；四臂VLA-only结果不得替换、回填或与`39/86`合并。

完整证据见 [`paper/full120_four_arm_result_integration.md`](paper/full120_four_arm_result_integration.md)。

## 4. 项目结题与维护边界

项目于2026-08-21结题。论文源、claim--evidence 映射、最终实验结果、校验脚本和审计材料按当前状态冻结。
默认不再进行方法优化、新的 benchmark 扩展或补充实验；更多seeds、其他攻击族、camera-only trusted
perception、L2a/L2b更细消融、真实机器人和更强执行证明仅作为未执行的未来方向。

后续维护只允许：修复可复现性问题、恢复缺失但已有校验和的历史artifact、处理外部提交系统分配的paper
number或准确模型标签，以及修正文档中的明确错误。任何新实验、结果重分类或 claim 扩张都需要先由用户明确
重启项目。

## 可复现性说明

历史预注册 protocol、内部版本结果、checksums 和冻结分类继续保留在 audit/archive material 中，不删除、
不改判，也不进入默认论文故事。它们用于回答复现和历史审计问题，而不是定义当前系统版本或叙事主线。
