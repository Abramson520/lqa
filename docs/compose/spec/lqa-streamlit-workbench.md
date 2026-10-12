---
feature: lqa-streamlit-workbench
status: delivered
updated: 2026-09-17
branch: feat/lqa-streamlit-workbench
commits: ea44ae0..HEAD
---

# LQA Streamlit 生成工作台（推倒重做）

## Report

**What was built** — 将 LQA 平台从「项目/用例管理台」推倒为 Streamlit 生成工作台：上传/粘贴需求 → 本地拆解 → 规则打底 → 可选 AI 补强 → 质量门禁 → Excel 下载/落盘。侧栏四页：生成向导 / 参考案例 / 模型配置 / 说明。旧 HTTP 实现归档至 `legacy/`。

**Verification** — `python tests/test_pipeline.py` → ALL PASS；Streamlit `:8787` health=200。AI 实测待用户提供 Key。

**Journey log**
- 用户明确要 plasA 式生成工作台，而非管理台；技术栈选定 Streamlit。
- 本期输入仅文档+文本，无截图、无 XMind、无 SQLite 执行库。

## [S1] Problem
现有 LQA 平台是「项目/用例 CRUD 管理台」，与用户期望的 plasA 形态不一致：用户要的是**需求文档 → 拆解 → LQA 用例生成 → Excel 导出**的生成工作台。旧 HTTP 静态站交互弱、无规则打底、无参考案例、无导出闭环。

## [S2] Design

### 产品定位
本地运行的 **LQA 测试用例生成工作台**（Streamlit），输入本地化需求文档/文本，输出可交付 Excel 用例。

### 技术栈
- Python 3.10+ / Streamlit ≥ 1.43
- OpenAI 兼容 API（DeepSeek / MiMo / Custom）
- python-docx / openpyxl / pandas / python-dotenv
- 本地输出目录 `outputs/`，不强制 SQLite（MVP 无库管）

### 信息架构（侧栏）
| 页 | 作用 |
|----|------|
| 生成向导 | 上传/粘贴需求 → 参数 → 生成 → 预览 → 导出 |
| 参考案例 | 查看/刷新 `case_library/`，勾选主参考 |
| 模型配置 | Provider/BaseURL/Model/Key，连通性测试 |
| 说明 | 使用说明与 LQA 类别说明 |

### 生成链路
1. **解析**：docx/xlsx/md/txt + 粘贴文本 → 统一需求文本
2. **本地拆解**：按段落/标题抽出需求点；识别模块信号
3. **规则打底**：LQA 15 类检查点 × 需求点 → 骨架用例（无 Key 可出草稿）
4. **AI 补强**（有 Key）：语义补全 steps/expected/双语文案，对齐主参考列风格
5. **质量门禁**：必填字段、类别枚举、steps 编号、去重
6. **导出**：`outputs/<ts>_<name>/LQA用例.xlsx`

### LQA 用例 Schema
`module, feature, category, priority, source_lang, target_lang, source_text, target_text, preconditions, steps, expected, notes`

Category 枚举沿用 15 类（TEXT_OVERFLOW…OTHER）。

### 模型配置
- `LQA_PROVIDER`: deepseek | openai | mimo | custom
- UI 可临时覆盖 .env
- 无 Key：规则骨架可用，AI 按钮提示

### Out of Scope（本期不做）
- 截图/图片需求分析
- SQLite 项目/执行状态管理
- XMind 导出
- 分布式/多人协作

## [S3] Out of Scope
见上节。旧 `server.py`/`static/` 保留归档不再作为主入口；`run.bat` 改为启动 Streamlit。

## Tasks
- [ ] T1: 清理并搭建 Streamlit 工程骨架 — acceptance: requirements/run.bat/app.py 可启动空白工作台 (covers: S2)
- [ ] T2: 实现文档解析与需求粘贴 — acceptance: docx/xlsx/md/txt 可提取文本并在 UI 预览 (covers: S2)
- [ ] T3: 实现规则打底 + LLM 补强生成 — acceptance: 无 Key 出骨架；有 Key 出完整用例 JSON (covers: S2)
- [ ] T4: 实现质量门禁与 Excel 导出 — acceptance: 导出 xlsx 字段齐全可打开 (covers: S2)
- [ ] T5: 四页 UI（向导/案例库/模型/说明） — acceptance: 侧栏可切换，主路径可走通 (covers: S2)
- [ ] T6: 本地回归与冒烟 — acceptance: 启动成功，规则路径生成+导出通过 (covers: S2)
