# NDSS 2027 投稿就绪清单

最后更新：2026-08-18。官方依据：
[NDSS 2027 Call for Papers](https://www.ndss-symposium.org/ndss2027/submissions/call-for-papers/)
与 [NDSS 2027 Templates](https://www.ndss-symposium.org/ndss2027/submissions/templates/)。

本清单只审计可投稿性，不改变冻结实验的 protocol、结果或历史分类。当前论文把SABER作为完整攻击评测协议
上的风险测量，报告观测ASR为45.35%；不再把“是否复现成功”作为正文故事。历史分类仅留在
claim--evidence与冻结protocol审计中。

## 已满足或已落实

- [x] 论文以英文、US Letter、双栏 `IEEEtran` 排版，并采用 NDSS 2027 官方首页 publication block。
- [x] 初审稿不包含作者姓名和单位；正文不使用第一人称指代既往作者工作。
- [x] Ethics Considerations 紧接参考文献之前。
- [x] 按实际辅助范围加入 Generative-AI Disclosure，明确产品、模型家族、访问时间，并覆盖全部论文小节与
      Figs. 1--3 的 LaTeX/TikZ 图稿；若投稿界面届时提供更细的可见模型标签，再据实补充，不虚构未暴露的内部版本号。
- [x] 论文主线明确落在系统安全：不把贡献写成纯 VLA/控制算法，不宣称硬件证明或真实机器人安全。
- [x] SABER 攻击在正文中统一写为完整120-unit协议上的风险测量，报告 `39/86=45.35%` 及CI；历史
      reproduction分类仅在audit material中保留。
- [x] 当前18-pair四臂数字与冻结证据一致，且不与120-unit攻击风险口径混算；正文不出现内部版本号。
- [x] 已用 NDSS 官方 `bare_conf_NDSS2027.tex` 要求的 `IEEEtran` 1.8b 接口、首页 block 和页码规则核对；
      本地已纳入与 Overleaf 全文相同的官方 IEEEtran 1.8b 类（仅行尾终止符规范化），不再依赖发行版隐式版本；
      本地 Tectonic 生成 US Letter、双栏、完整 14 页 PDF，技术正文与 Conclusion 在第 13 页内结束；第 14 页
      仅含参考文献尾部和不计入正文限制的 Appendix，满足官方“技术正文最多 13 页，Ethics/References/Appendix
      不计”的要求。
- [x] 正文嵌入 TeX Gyre Termes（Times-compatible）与 NewTX 数学字体；统一预检现在调用 Poppler 字体表，
      硬性检查全部字体 embedded/subset，并防止正文字体或数学字体在重编译中静默漂移。
- [x] 参考文献 40/40 均有定义并已核验主要作者、会议、年份与稳定入口；closest-work 对比已覆盖
      SEAL、CoVer、CaMeL、ACE、MATE、ToolHijacker、ObliInjection、Les Dissonances，以及 USENIX Security 2026 的自适应攻击评估警示；
      最新安全四大定位还纳入 USENIX Security 2026 agent-security SoK 与 IEEE S&P 2026 的第三方
      chatbot-plugin prompt-injection 实证，补足 agent 大图景及 conversation-history/trust separation 依据，
      并明确区分 candidate ranking、数字代理控制流和 trusted-task/execution transaction；补充 Schneider 的
      reference-monitor/complete-mediation 与 execution-monitoring 基础，明确 complete mediation 依赖 TCB
      无旁路，而不是 Lean 已证明的部署事实。
- [x] 完成 IEEEtran/BibTeX 参考文献排版校对，对 LLM、AI、ICS、SCADA 等必须保留大写的缩写以及标题中的
      单字母代词加花括号保护，避免 bibliography style 将其误降为 `llm`、`ai`、`ics`、`scada` 或 `i`。
- [x] 核验 VLMPC 的 RSS 2024 官方 proceedings：DOI 中的 `XX` 是官方卷号而非占位符；保留官方 DOI 并在
      BibTeX 中补入 `roboticsproceedings.org/rss20/p106.html` 稳定入口，避免与首页待替换的 `24xxxx` 混淆。
- [x] 已加入系统/证明边界表、L1 verdict 表、closest-work 表，以及系统信任边界、L2a 事务状态、
      双研究口径和四臂结果四张可复现矢量图；图表在黑白打印下仍可区分。
- [x] 系统总览图已按真实 runtime 顺序重绘：L2a 作为跨越 contract、条件 L2b screening、一次性授权、
      exact dispatch 与 evidence closure 的事务边界；同一 canonical source-action identity 在各阶段保持绑定。
      重绘后逐页渲染复核并消除节点重叠。
- [x] 已完成 figure--prose--implementation 顺序审计：正文、Fig. 1、Fig. 2 与 runtime integration 统一为
      assessment → contract → 条件 L2b screen → fresh authorization → exact dispatch → receipts/effects；
      明确 guard screening 不消费或追认 authorization，且 Python guard audit 尚未被误写为 Lean typed binding。
      统一预检新增顺序回归断言；修订后复核方法页和附录末页。
- [x] 18-pair 结果报告 Wilson 区间、paired bootstrap、双向 paired transitions 和小样本边界；正文明确
      `-0.20` noninferiority margin 是预先冻结的最多 20 个百分点机制资格容忍度，不是部署级效用标准。
- [x] Evaluation 已明确 baseline/ablation 逻辑：VLA-only 是不修改运行时的基线，L1-only/L2-only 是机制
      消融，Dual 是组合；SafeVLA、SAFE、SEAL 与 CoVer 因训练干预、所需 plan/candidate 接口或估计对象不同，
      不被误写为可直接替换的同协议数值基线，也不宣称全面优于所有 VLA safety system。
- [x] `scripts/audit_ndss2027_paper_claims.py` 从冻结 trace 重算主表并核对完整性、开销与 warning，
      同时逐项验证附录列出的 10 个 theorem 名称与 Lean 源码一致；当前通过。
- [x] L2a 的 stale evidence、substitution、replay、cross-proposal、incomplete evidence 与 TCB-limit
      等负向完整性用例已完成聚焦回归（69/69 通过），并在正文中单独报告其证据边界。
- [x] 动作身份主张已与实现对齐：正文明确 SHA-256 绑定的是 schema-tagged canonical numeric JSON
      与 proposal shape，而不是 NumPy dtype、endianness、内存字节或物理轨迹；L2-only 也明确不携带
      L1 trusted-task semantic authorization。
- [x] receipt 主张已与增强后的形式模型对齐：Python runtime 检查连续 step index 及每步 digest 与
      `authorization.action_at(i)` 的对应；Lean 现在同时绑定 whole command、typed ordered digest list、
      receipt index 与 applied-step digest。Python canonical tuple/serializer refinement 仍明确列为未证明。
- [x] 摘要、系统图、结果图、Discussion 与 Conclusion 已统一这一证据层级：runtime gate 不再称为
      formal gate，四臂结果明确为 sample outcome 而非 population effect，Lean 只称为 abstract
      binding/phase semantics。
- [x] 完成 novelty/orthogonality 审稿式精修：Introduction 现在把新颖性明确落在在线VLA source ActionBlock的
      protected object 与跨层 preservation chain，而非单个 checker/nonce/shield；Design 明确给出
      L1、L2a、L2b 不能互相替代的反例，并把 closest-work 表中的 L1 对象收窄为 trusted context 加
      checker verdict，而非无条件的 trusted-task authorization。
- [x] Introduction 已加入一个不新增实验结果的具体 motivating pair：权威任务为把 soda 移到 plate，
      冻结 SABER record 则向策略注入“move to the farthest fixture”；Evaluation 明确标注该 pair 仅作
      post-hoc 机制说明，不构成额外 estimand，避免把示例误读成独立实验或补充结果。
- [x] 完成 checker-relative 术语审计：System Model 将 L1 明确命名为 assessment；Introduction、Design
      与 Related Work 区分 L1 task verdict 和 L2a dispatch authorization；同一 motivating pair 贯穿
      Design 的三层职责解释，且 Evaluation 明确所有推断仍来自完整 paired sample。
- [x] HotCRP 纯文本摘要已与 LaTeX 摘要逐句对齐，统一 covered hard failures、runtime identity 和
      abstract finite binding/phase relations 等限定；匿名性扫描仅保留提交时必须替换的 DOI paper-number
      占位符，未发现作者、机构、邮箱或本地路径泄漏。
- [x] 威胁模型区分设计范围与经验覆盖：当前实验证据只覆盖 post-split instruction modification 和
      modeled transaction faults，不把 visual-input 或 policy-history 通道写成已验证鲁棒性。
- [x] Ethics 明确说明 \texttt{human\_safety} 是纯模拟场景，不涉及 human subjects、个人数据或未披露的
      真实系统漏洞，避免由 benchmark 命名产生伦理范围歧义。
- [x] 源文件与 PDF 已扫描作者/机构/邮箱/本地路径；PDF metadata 不含 Author、Title 或身份字段。
- [x] 最新 14 页版本已再次逐页渲染复核，无裁切、重叠、孤立标题、越界链接、未定义引用或
      overfull box；Introduction/Design 增补后的后续分页和 Conclusion/Disclosure/Ethics 过渡均保持完整。
- [x] 主结果表已将原先容易与分数斜杠混淆的 `C/A` 合并单元格拆成 Clean/Attacked 独立列，并把
      violation episode、crossing step、joint-limit step 明确归入 attacked joint-limit outcomes；数字未变。
- [x] 本地 21 个同步文件已纳入 manifest；此前 20 个正文/图稿文件已逐一从 Overleaf 全选复制回读并与
      本地全文精确比较；模板类也已核对为相同正文（Overleaf 仅省略末尾换行）。修复了编辑器曾遗留的
      章节尾部和 `\end{document}` 后旧内容。本轮 reviewer-audit 修订后的正文/图稿精确回读已通过，
      当前本地重新编译为14页，其中技术正文与Conclusion结束于第13页；投稿预检与逐页视觉复核通过。

## 投稿前必须关闭

- [ ] 按统一120-unit评测集补齐clean/attacked四臂，使各arm采用与45.35%相同的risk-transition定义；在结果
      回来前，正文必须继续明确现有四臂是独立18-pair机制研究，不能把它写成已完成的全集防御实验。
      运行与回填口径见 `docs/paper/full120_four_arm_result_integration.md`；现有冻结调度与分析契约只证明
      历史schema和统计方法，不代表outcome已被观察。由于Lean形式化源已经增强，旧v4协议的source binding
      当前会fail closed；正式执行前还必须签发绑定最终源码的新successor protocol，不能改写历史checksum。
- [ ] 若提交时 Codex 界面暴露比“GPT-5 model family”更精确的模型标签，据实更新 disclosure；若未暴露，
      保留当前产品、模型家族与访问时间，不猜测内部构建版本。
- [ ] 提交系统开放并获得 paper number 后，把首页 DOI 的 `24xxxx` 替换为实际 Fall-cycle 编号。

## 最后阶段：匿名 artifact

- [ ] 按用户指定在论文版本稳定后再做：把 runtime、Lean 文件、协议、冻结 summary 与校验脚本整理为
      匿名 artifact package，并写复现入口。当前还需恢复缺失的 M2 producer/victim raw fresh roots，并清除
      raw episode metadata 中的绝对路径。NDSS 2027 的 artifact evaluation 在论文通知后进行，因此它不阻塞
      Fall paper upload，但仍是项目最终交付的一部分。

统一复验入口：`python3 scripts/check_ndss2027_submission.py`。当前普通模式允许以上两项提交时变量并以
`PENDING` 报告；真正提交前运行 `--final`，任何未替换项都会硬失败。该入口还检查摘要、引言贡献、
Evaluation 和结论中的主结果/claim boundary 一致性，检查 HotCRP 元数据表的标题、主结果 token 与 AI
图稿披露没有和正文漂移，并验证 PDF 页数、纸张、匿名 metadata、字体和编译日志；不执行 artifact 打包。

HotCRP 可复制元数据、官方 topic 选择、topic-fit/ethics/AI 摘要，以及必须人工冻结的作者与冲突项，维护在
`docs/paper/ndss2027_submission_metadata.md`；该文件不上传 Overleaf。

模拟 Round-1 评分、主要拒稿意见与现有证据回答维护在
`docs/paper/ndss2027_mock_review.md`；该文件仅用于内部投稿审计。

## 当前主要审稿风险

1. **证据范围偏窄。** 最终主实验只有一个 checkpoint、一个 benchmark、一个攻击族和 18 个 pair，且
   SABER records 未针对 ProofAlign 做 defense-aware 自适应优化；论文必须保持 simulator-qualified、
   attack-family-specific、non-adaptive-evaluation 的结论。
2. **L2 归因不完全。** 四臂只识别 combined L2a+L2b；L2a 依赖负例测试和 Lean 事务语义，不能从
   四臂表宣称独立因果效果。
3. **L1 语义保证有限。** task-progress mismatch 是 advisory；L1 是 checker-relative trusted-task
   monitor，而不是 complete semantic verifier。
4. **形式化与 runtime 有 refinement gap。** 当前 Lean contract 未独立证明 Python receipt-authorized
   digest 到 ordered per-step command list 的 refinement，也未 type-bind guard/controller configuration；
   精确 canonical command identity 不等于精确物理轨迹。
5. **Artifact 完整性。** claim--evidence map 和自动审计已经完成，但原始 M2 fresh roots 不在当前 checkout；
   在恢复、checksum 验证和匿名路径清理之前，不能承诺 RQ1-complete artifact。

## 截止日期

Fall cycle 论文截止：2026-08-19 11:59 PM AoE。官方 CFP 已更新：Fall submission site 将于
2026-08-15 开放，入口为 <https://ndss27-fall.hotcrp.com/>。
