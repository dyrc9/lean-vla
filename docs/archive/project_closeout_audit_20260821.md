# 项目结题审计（2026-08-21）

本记录只说明结题时的验证与维护边界，不改变任何冻结实验的 protocol、checksum、结果或 non-pass 分类。

## 最终发布门禁

- `uv run python scripts/audit_ndss2027_paper_claims.py`：通过。攻击复现、四臂结果、物理机制、运行时声明、
  960个artifact绑定和11个Lean theorem名称均与冻结证据一致。
- `uv run python scripts/check_ndss2027_submission.py --skip-build`：通过。源文件、引用、聚焦测试、Lean
  transaction model、匿名结构和已构建PDF检查均通过。
- 最终PDF为15页US Letter；技术内容在第13页结束，第14--15页仅为参考文献；字体已嵌入，逐页渲染检查未见
  裁切、重叠或溢出。
- 提交系统分配的paper number和准确AI模型标签仍是外部人工字段，未在仓库中猜测填写。

## 历史全库审计

结题时运行 `uv run pytest -q` 的结果为：`646 passed, 12 skipped, 149 failed, 48 errors`。这些非通过项主要是
旧冻结结果对历史源码digest、`*_current_when_present`和source-binding的审计断言；当前论文源码与最终系统
已经前移，因此这些断言继续如实暴露历史绑定状态。

它们不属于最终论文声明的发布门禁，也没有通过改写digest、删除结果或重分类来制造全绿。若未来需要恢复某个
历史checkpoint，应在隔离环境中按其冻结源码与manifest复现，而不是修改本记录中的分类。

## 清理与保留边界

本地已清除可再生的论文临时构建目录、pytest/Python缓存、Lean构建缓存、通用临时目录、重复PDF和未采用的草图
栅格文件。最终PDF单独保存在忽略版本控制的 `output/pdf/` 中。

`results/`、历史protocol、checksums、归档文档和non-pass记录全部保留；`.venv`与本地agent配置也保留，分别
用于复现环境和工作区工具配置。
