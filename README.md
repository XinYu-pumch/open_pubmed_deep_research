# Open Pubmed Deep Research

当前正式版本：`V1.0`（打包版本号 `1.0.0`）

一个面向医学与生命科学文献综述场景的 Python 桌面应用。  
它以 PubMed 检索为入口，把“检索、下载、清洗、向量化、RAG 写作、导出”串成一条完整流水线。

当前应用形态是：
- 开发模式：`Streamlit` Web 界面
- macOS 发行版：`pywebview + Streamlit` 打包成 `.app`

## 主要功能

- PubMed 检索与 XML 元数据保存
- 多次检索结果合并与去重
- 摘要提取与摘要合集生成
- 基于摘要的综述框架生成
- PMC 文献优先从 Europe PMC 下载 PDF
- 非 PMC 文献通过 Sci-Hub 镜像尝试下载
- 下载失败时自动退化为摘要 `.md` 备份
- PDF 批量转 Markdown
- Markdown 分段切块并写入 ChromaDB 向量库
- 一键串联全文下载、Markdown 转换、向量化
- 基于 RAG 的分章节自动写作、引用作用域校验与局部修复
- 导出 Word 综述文档
- 导出可点击 PMID 的交互式 HTML 综述
- 中英文综述模式分别保存框架、片段与导出结果
- LLM 配置预设保存、下拉切换、连接测试与模型列表拉取
- 工作区切换、英文日志查看、配置保存、数据库清理

## 当前工作流

应用界面按 7 个模块组织：

1. 项目集合
   输入集合名，系统会在工作区下创建独立目录。
2. 文献检索与管理
   按关键词、数量、排序、日期范围从 PubMed 拉取 XML。
3. 综述框架生成
   读取摘要合集，调用 LLM 输出多级标题 CSV 框架；中文与英文模式分别保存。
4. 原文下载及处理
   下载 PDF，转换 Markdown，做向量化；也可以使用“一键三连”按顺序完成三步。
5. 内容撰写
   按综述框架构建自然写作单元，对对应末级节点做向量检索，再调用 LLM 生成正文。
6. 导出成品
   按当前语言模式合并章节并导出 Word / HTML。
7. 调试工具
   清理向量库，导出调试文件。

## 写作与引用控制

V1.0 的综述撰写不再简单按一级章节整段生成，而是先从框架 CSV 中确定自然写作单元：

- 对只有直接子节点的分支，父节点和子节点会在同一个写作单元中生成。
- 对较复杂的多级分支，会按结构拆成多个写作单元，降低跨小节引用漂移。
- 每个小节只允许引用其 RAG 检索作用域内的 PMID。
- 生成后会自动检查引用是否越界；如发现漂移，会对对应小节做局部修复。
- PMID 引文在保存前会统一为英文半角格式，例如 `(PMID: 12345678, 23456789)`。

HTML 与 Word 导出优先读取章节 JSON 中的结构化 `sections`、`citation_scopes` 和 `reference_materials`，旧版 `prompt_section_*.txt` 只作为兼容回退。

## 下载逻辑

### PMC 文献

- `PMCID` 从 PubMed XML 的文章自身 `PubmedData > ArticleIdList` 中解析。
- 下载时优先通过 Europe PMC REST 查询文章元数据与 `fullTextUrlList`。
- 优先尝试 Europe PMC 官方 PDF 链接。
- 如有需要，再回退到 `https://europepmc.org/articles/PMCxxxx?pdf=render` 和旧的 `ptpmcrender.fcgi` 路径。
- 下载日志会显示候选 URL、HTTP 状态、内容类型、最终跳转地址和文件大小。

### 非 PMC 文献

- 如果有 `DOI`，会测试 Sci-Hub 镜像并并发下载。
- 每个 worker 使用不同镜像顺序，减少单镜像波动的影响。
- 如果无法拿到 PDF，会生成该文献的摘要 `.md` 备份，后续仍可进入向量化与写作流程。

### 重试行为

- 已有 `.pdf` 的条目会跳过。
- 只有 `.md` 兜底文件但仍具备 `PMCID` 或 `DOI` 的条目，会继续重试 PDF 下载。
- 成功补下 PDF 后，会自动删除旧的 `.md` 兜底文件。

## 输出文件

每个集合目录通常位于：

```text
{workspace}/content/{collection_name}/
```

常见产物包括：

- `pubmed_results.xml`
  PubMed 原始或合并后的 XML
- `abstract_combined.txt`
  摘要文本合集
- `prompt.txt`
  框架生成时实际发送给 LLM 的提示词
- `review_framework_cn.csv` / `review_framework_eng.csv`
  中文 / 英文综述框架 CSV
- `*.pdf`
  下载到的全文 PDF
- `*.md`
  下载失败时保留的摘要 Markdown，或 PDF 转换后的 Markdown
- `downloaded_literature.zip`
  当前集合所有 PDF / MD 的打包文件
- `literature_without_pdf.txt`
  未成功获取 PDF 的 PMID 列表
- `review_parts_cn/section_*.json` / `review_parts_eng/section_*.json`
  中文 / 英文分章节生成结果
- `review_parts_cn/prompt_section_*.txt` / `review_parts_eng/prompt_section_*.txt`
  各写作单元实际发送给 LLM 的完整 RAG 写作提示词
- `review_parts_cn/{collection_name}_Review.docx` / `review_parts_eng/{collection_name}_Review.docx`
  当前语言模式下的最终 Word 导出
- `review_parts_cn/{collection_name}_Review.html` / `review_parts_eng/{collection_name}_Review.html`
  当前语言模式下的最终交互式 HTML 导出

旧项目中的 `reveiw_framework.csv` 和 `review_parts/` 仍可作为兼容回退读取，但 V1.0 新生成的文件会使用上面的新命名。

## 配置与工作区

### 开发模式

- 配置文件：`./config.json`
- 内容目录：`./content`

### 打包后的 macOS App

- 配置文件：`~/Library/Application Support/PubmedResearch/config.json`
- 工作区配置：`~/Library/Application Support/PubmedResearch/workspace_config.json`
- 日志目录：`~/Library/Application Support/PubmedResearch/logs`

首次启动 macOS `.app` 时，应用会要求用户选择工作区目录。  
实际文献数据、PDF、导出文档都保存在你选择的工作区下，而不是写入 app bundle。

## 模型配置

应用支持在设置页配置两类接口：

- LLM
  用于框架生成、分章节写作、连接测试、模型列表拉取
- Embedding
  用于向量化与 RAG 检索

默认配置定义在 [config_manager.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/config_manager.py)：

- LLM 默认基于 OpenAI 兼容接口
- Embedding 默认示例为 SiliconFlow 的 embedding 接口
- LLM 默认使用流式请求，减少长输出时被上游网关断开的概率
- `LLM Preset` 下拉菜单选择某个预设后会立即生效
- `Save Preset` 会把当前 LLM 表单保存为一个命名预设，包括 API Key
- `Save Config` 会保存当前正在使用的 LLM 与 Embedding 配置

只要接口兼容当前请求格式，就可以替换为你自己的服务。

## 运行方式

### 开发模式

在项目根目录准备虚拟环境并安装依赖后，可直接运行：

```bash
streamlit run app.py
```

也可以运行桌面壳：

```bash
python desktop_app.py
```

这会启动：
- 主进程：`desktop_app.py`
- 子进程：`streamlit_server.py`

## 打包 macOS App

当前打包脚本面向：

- macOS
- Apple Silicon `arm64`

执行命令：

```bash
bash build_app.sh
```

脚本会：

1. 校验打包环境和依赖
2. 生成图标
3. 清理旧产物
4. 运行 PyInstaller
5. 验证 `.app` 结构
6. 生成 `.dmg`
7. 清理 PyInstaller 收集目录、构建缓存和 DMG staging 目录

打包产物位于 `dist/`：

- `Open Pubmed Deep Research.app`
- `Open_Pubmed_Deep_Research-1.0.0-arm64.dmg`

## 关键代码结构

- [app.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/app.py)
  Streamlit 主界面，负责参数输入、按钮流程、实时日志
- [core_logic.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/core_logic.py)
  核心业务逻辑，包括 PubMed、Europe PMC、Sci-Hub、向量化、RAG、导出
- [desktop_app.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/desktop_app.py)
  macOS 桌面入口，负责 pywebview 窗口和 Streamlit 子进程
- [streamlit_server.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/streamlit_server.py)
  被桌面壳拉起的 Streamlit 服务端入口
- [workspace_manager.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/workspace_manager.py)
  工作区、配置路径、日志路径、bundle 资源路径管理
- [config_manager.py](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/config_manager.py)
  LLM / Embedding 配置读写
- [build_app.sh](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/build_app.sh)
  macOS 打包脚本
- [build_macos.spec](/Users/yuxin/AI_developing/BADR专业/BADR_重构0518/build_macos.spec)
  PyInstaller macOS 打包定义

## 当前已修正的重要行为

- PubMed XML 解析现在只读取文章自身的 `PMID / DOI / PMCID`
- 不再错误读取参考文献里的 `ArticleId`
- PMC 下载现在优先通过 Europe PMC REST 解析官方全文链接
- 只有 `.md` 兜底文件的条目支持重新尝试 PDF 下载
- 成功补下 PDF 后会自动清理旧 `.md`
- 全文下载、Markdown 转换、向量化可以通过“一键三连”连续执行
- LLM 调用默认使用流式请求，框架生成和综述撰写共用同一调用路径
- 综述框架文件名修正为 `review_framework_cn.csv` / `review_framework_eng.csv`
- 综述片段与导出结果按语言写入 `review_parts_cn/` 或 `review_parts_eng/`
- 章节 JSON 保存结构化小节、引用作用域、引用素材与引用校验结果
- HTML 引用详情优先从结构化章节 JSON 构建，不再依赖 prompt 文本反推
- 界面实时日志和运行日志统一使用英文输出，降低编码和乱码问题

## 已知说明

- 能否拿到全文取决于 Europe PMC / PMC 收录情况、Sci-Hub 镜像可用性和目标站点访问情况。
- 某些文章即使没有 PDF，也仍可通过摘要 `.md` 继续进入后续流程。
- `Marker` 转换、Embedding 和章节写作在大集合上耗时可能较长。
- Word / HTML 导出依赖当前语言模式下已生成的章节 JSON 和框架 CSV。
- HTML 导出中的 PMID 详情来自章节 JSON 中保存的结构化素材；旧项目会回退解析章节提示词。

## 面向发行的建议

- 发行给普通 macOS 用户时，优先提供 `.dmg`
- 首次运行时提醒用户：
  - 先设置工作区
  - 再填写 LLM 与 Embedding 配置
  - 第一次大批量 PDF 转换和模型加载会比较慢

## 许可证与合规

本项目包含对 PubMed / Europe PMC / Sci-Hub / 第三方模型与接口的调用逻辑。  
在对外发布和实际使用前，请自行确认目标环境中的服务条款、版权约束和网络合规要求。
