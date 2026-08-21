# ProofAlign LaTeX 写作源

本目录是论文的**唯一正文源**。后续写作、引用修改、数字更新和结构调整先在这里完成；Overleaf 只在本地
检查通过后做阶段性同步，不在两边并行修改同一文件。

## 与 Overleaf 的同构关系

| 本地 | Overleaf | 作用 |
|---|---|---|
| `paper_ndss.tex` | `paper_ndss.tex` | IEEEtran 主入口与章节顺序 |
| `IEEEtran.cls` | `IEEEtran.cls` | NDSS 官方模板要求的 IEEEtran V1.8b 类 |
| `macro.tex` | `macro.tex` | 论文宏 |
| `paper.bib` | `paper.bib` | 唯一参考文献库 |
| `sections/*.tex` | `sections/*.tex` | 分章节正文、结论与附录 |
| `figures/` | `figures/` | 最终图表资源 |

投稿格式、匿名性和证据审计统一记录在 `ndss2027_readiness.md`；未关闭的项目不能在 Overleaf 预览无
错误后被误判为“已可投稿”。

本地与 Overleaf 都固定使用 NDSS 官方模板要求的同一份 IEEEtran V1.8b 类；不要静默切换到其他同名类，
以免首页 publication block、边距或分页在两端发生漂移。
旧的 `paper_ccs.tex` 不属于当前 ProofAlign 主线，也不作为本地同步目标。Overleaf History 是远端恢复机制，
Git 是本地版本历史。

## 固定工作流

1. 只编辑本目录中的 LaTeX/BibTeX/figure source；
2. 运行 `ruby scripts/check_source.rb`；
3. 在仓库根目录运行 `python3 scripts/audit_ndss2027_paper_claims.py`，从冻结 trace 重算并核对论文数字；
4. 用 `tectonic -X compile paper_ndss.tex --outdir build --keep-intermediates --keep-logs` 编译，消除
   LaTeX error、undefined citation/reference 和 overfull box；
5. 检查 PDF 首页、字体嵌入、系统图、主结果表、参考文献和附录长标识符；
6. 将 manifest 中的文件批量同步到 Overleaf；
7. 对每个文件做完整字节回读，并在 Overleaf 重新编译；
8. 只有在远端无 error/undefined reference 且 PDF 版面核查后，才把远端视为本地版本的预览副本。

当前工作树可用仓库根目录下的统一入口复验上述本地门：

```sh
python3 scripts/check_ndss2027_submission.py
```

该命令不构建匿名实验 artifact。提交系统给出 paper number 且 AI disclosure 的模型标签最终确认后，
使用 `--final` 让这两类占位项也转为硬失败。

## 同步边界

- 不把实验日志、内部路径、凭据或未冻结结果上传到 Overleaf；
- 不从 Overleaf 反向覆盖本地，除非先人工确认远端确有需要保留的协作者修改；
- 新增章节或图片时，先更新 `sync_manifest.txt`；
- 结果数字的唯一证据入口仍是仓库内冻结 artifacts，LaTeX 只转录已核对的结果；
- `paper_draft_zh.md` 和 `paper_narrative_zh.md` 是论证辅助稿，不直接覆盖英文 LaTeX。

当前远端项目：<https://www.overleaf.com/project/689d40dac69864befac0e1fc>。远端目前仍显示历史项目名
`Secure MCP via Compartmentalization - SP 2027`；该共享工程的当前编辑权限不能改写显示名，因此后续以
项目 ID `689d40dac69864befac0e1fc` 和本目录中的 `paper_ndss.tex` 为准。显示名不影响主文档或编译结果。
