# Open PubMed Deep Research (OPDR)

当前正式版本：`V1.0`

**撰写详尽的、高质量的、有明确引文出处的生物医学论文**

## 一、核心特色

### 1. PubMed 文献集合驱动

OPDR 调用 PubMed 检索api，建立本地文献库。

### 2. 全文优先，摘要兜底

对于有 PMCID 的文献，OPDR 优先通过 Europe PMC / PMC 路径获取全文 PDF。  
对于没有开放全文的文献，会尝试通过 DOI 获取原文；若仍无法获得 PDF，则自动生成摘要 Markdown 作为备用材料，后续仍可进入向量化和写作流程。

### 3. 综述框架统领多上下文写作

OPDR 不让模型一次性生成完整长文，而是先生成多级综述大纲，再把长篇综述拆成多个自然写作单元。  
每个写作单元都在相对独立的上下文中生成，最后再按照原始框架合并成完整综述。

### 4. 用文献片段填补每个章节

写某一节之前，系统会先从已处理的文献库中检索与该章节相关的原文片段，再把这些证据片段交给 LLM 生成正文。  
这样正文不是单纯依赖模型记忆，而是围绕当前章节对应的文献证据展开。

### 5. PMID 引用来源检查

生成后，OPDR 会检查小节正文中的 PMID 是否来自当前章节使用过的文献材料。  
如果发现引用漂移，会对对应小节进行局部修复，减少“张冠李戴”的引用问题。

### 软件界面

<p align="center">
  <img src="https://github.com/XinYu-pumch/open_pubmed_deep_research/blob/main/demo/app_screanshot2.png" alt="软件界面" width="100%">
</p>

<p align="center"><em>工作区、设置面板与实时日志集中在一个桌面应用中。</em></p>

### 输出的综述

<p align="center">
  <img src="https://github.com/XinYu-pumch/open_pubmed_deep_research/blob/main/demo/review_screanshot.png" alt="软件界面" width="100%">
</p>

<p align="center"><em> 完整版可见https://github.com/XinYu-pumch/open_pubmed_deep_research/blob/main/demo/demo0522_Review.html。</em></p>

## 二、下载方式

OPDR 当前提供三种使用方式：

1. WebUI 版：适合开发者或希望自行运行 Streamlit 的用户。
2. macOS 打包版：下载后直接运行 `.app` / `.dmg`。
3. Windows 打包版：下载后直接运行 Windows 版本。

### 1. WebUI 版

WebUI 版通过 Git 克隆本仓库运行：

```bash
git clone <your-repo-url>
cd <repo-folder>
```

由于 PDF 转 Markdown 依赖 Marker 相关模型文件，仓库中不直接包含大型 `marker_config` 目录。  
请先下载 `marker_config` 压缩包，解压后放到项目工作目录下，使目录结构类似：

```text
<repo-folder>/
├── app.py
├── core_logic.py
├── requirements.txt
├── marker_config/
│   ├── layout/
│   ├── text_detection/
│   ├── text_recognition/
│   └── ...
└── ...
```

`marker_config` 下载地址：

| 来源 | 链接 |
| --- | --- |
| 夸克网盘 | https://pan.quark.cn/s/7e8c9049a1c6 |
| Google Drive | 待提供 |

### 2. macOS 打包版

macOS 打包版下载后可直接运行。首次运行时，系统可能会因为来源校验阻止打开。  
如果出现“已损坏”“无法验证开发者”等提示，可在终端中对 app 执行：

```bash
sudo xattr -rd com.apple.quarantine "/Applications/Open Pubmed Deep Research.app"
```

如果你的 app 不在 `/Applications`，请把命令中的路径替换成实际 `.app` 路径。

macOS 打包版下载地址：

| 来源 | 链接 |
| --- | --- |
| 夸克网盘 | https://pan.quark.cn/s/a63c70d2e069 |
| Google Drive | 待提供 |

### 3. Windows 打包版

Windows 打包版下载后直接运行即可。

Windows 打包版下载地址：

| 来源 | 链接 |
| --- | --- |
| 夸克网盘 | https://pan.quark.cn/s/f130906555a4 |
| Google Drive | 待提供 |

## 三、使用方式

### 1. WebUI 版运行命令

建议使用 Python 3.12。首次运行前安装依赖：

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

启动 Streamlit WebUI：

```bash
streamlit run app.py
```

也可以启动桌面壳：

```bash
python desktop_app.py
```

桌面壳会启动两个进程：

- 主进程：`desktop_app.py`
- 子进程：`streamlit_server.py`

### 2. 初次使用配置

进入应用后，建议先完成模型配置：

- LLM：用于生成综述大纲和撰写正文。
  - 推荐：DeepSeek V4 Pro 或其他 OpenAI 兼容接口模型。
- Embedding：用于文献片段检索。
  - 推荐：硅基流动 `BAAI/bge-m3`，速度较快且有免费额度。

只要接口兼容当前 OpenAI 风格请求格式，就可以替换成你自己的服务。

### 3. 推荐工作流程

应用界面按 7 个模块组织：

1. **项目集合**  
   输入集合名，系统会在工作区下创建独立目录。

2. **文献检索与管理**  
   设计 PubMed 检索词，按关键词、数量、排序、日期范围拉取 XML。  
   根据 OPDR 的逻辑，前期检索建议优先“查全”，后续再由大纲、章节检索和引用检查控制范围。

3. **综述框架生成**  
   读取检索到的摘要合集，调用 LLM 生成多级标题 CSV 框架。  
   这一步非常重要，大纲会直接决定后续章节拆分、写作边界和最终质量。  
   如果自动生成的大纲不合适，可以按照 CSV 格式手动修改框架文件。

4. **原文下载及处理**  
   系统优先通过 PMC / Europe PMC 下载全文 PDF；非开放文献会尝试通过 DOI 获取。  
   如果没有 PDF 原文，会生成摘要 Markdown 作为替代。  
   应用会提供没有 PDF 原文的 PMID 列表；如果你有条件获取原文，可以手动把对应 PDF 放入项目目录，用原文替换摘要材料。  
   这是一个常见限速步骤。

5. **Markdown 转换**  
   使用 Marker 将 PDF 原文转换为 Markdown。普通电脑也可以运行，但在文献数量多或 PDF 较复杂时会比较耗时。  
   这是另一个常见限速步骤。

6. **向量化存储**  
   将 Markdown 文献内容分段切块，调用 Embedding 模型生成向量，并写入 ChromaDB 文献库。

7. **内容撰写与导出**  
   OPDR 按综述框架构建自然写作单元，为每个章节检索相关文献片段，再调用 LLM 生成正文。  
   最终可以导出：
   - HTML：适合阅读、检查 PMID 引用和查看对应文献片段；
   - Word：适合后续修改、投稿和发表。

## 四、主要功能

- PubMed 检索与 XML 元数据保存
- 多次检索结果合并与去重
- 摘要提取与摘要合集生成
- 基于摘要的综述框架生成
- PMC 文献优先从 Europe PMC 下载 PDF
- 非 PMC 文献通过 DOI / Sci-Hub 镜像尝试下载
- 下载失败时自动退化为摘要 `.md` 备份
- PDF 批量转 Markdown
- Markdown 分段切块并写入 ChromaDB 向量库
- 一键串联全文下载、Markdown 转换、向量化
- 基于文献片段检索的分章节自动写作
- 引用作用域校验与局部修复
- 导出 Word 综述文档
- 导出可点击 PMID 的交互式 HTML 综述
- 中英文综述模式分别保存框架、片段与导出结果
- LLM 配置预设保存、下拉切换、连接测试与模型列表拉取
- 工作区切换、英文日志查看、配置保存、数据库清理

## 五、写作与引用控制

V1.0 的综述撰写不再简单按一级章节整段生成，而是先从框架 CSV 中确定自然写作单元：

- 对只有直接子节点的分支，父节点和子节点会在同一个写作单元中生成。
- 对较复杂的多级分支，会按结构拆成多个写作单元，降低跨小节引用漂移。
- 每个小节只允许引用其检索到的文献片段对应 PMID。
- 生成后会自动检查引用是否越界；如发现漂移，会对对应小节做局部修复。
- PMID 引文在保存前会统一为英文半角格式，例如 `(PMID: 12345678, 23456789)`。

HTML 与 Word 导出优先读取章节 JSON 中的结构化 `sections`、`citation_scopes` 和 `reference_materials`，旧版 `prompt_section_*.txt` 只作为兼容回退。

## 六、下载逻辑

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

## 七、输出文件

每个集合目录通常位于：

```text
{workspace}/content/{collection_name}/
```

常见产物包括：

- `pubmed_results.xml`：PubMed 原始或合并后的 XML
- `abstract_combined.txt`：摘要文本合集
- `prompt.txt`：框架生成时实际发送给 LLM 的提示词
- `review_framework_cn.csv` / `review_framework_eng.csv`：中文 / 英文综述框架 CSV
- `*.pdf`：下载到的全文 PDF
- `*.md`：下载失败时保留的摘要 Markdown，或 PDF 转换后的 Markdown
- `downloaded_literature.zip`：当前集合所有 PDF / MD 的打包文件
- `literature_without_pdf.txt`：未成功获取 PDF 的 PMID 列表
- `review_parts_cn/section_*.json` / `review_parts_eng/section_*.json`：中文 / 英文分章节生成结果
- `review_parts_cn/prompt_section_*.txt` / `review_parts_eng/prompt_section_*.txt`：各写作单元实际发送给 LLM 的完整写作提示词
- `review_parts_cn/{collection_name}_Review.docx` / `review_parts_eng/{collection_name}_Review.docx`：当前语言模式下的最终 Word 导出
- `review_parts_cn/{collection_name}_Review.html` / `review_parts_eng/{collection_name}_Review.html`：当前语言模式下的最终交互式 HTML 导出

旧项目中的 `reveiw_framework.csv` 和 `review_parts/` 仍可作为兼容回退读取，但 V1.0 新生成的文件会使用上面的新命名。

## 八、配置与工作区

### WebUI / 开发模式

- 配置文件：`./config.json`
- 默认内容目录：`./content`

### 打包后的 macOS App

- 配置文件：`~/Library/Application Support/PubmedResearch/config.json`
- 工作区配置：`~/Library/Application Support/PubmedResearch/workspace_config.json`
- 日志目录：`~/Library/Application Support/PubmedResearch/logs`

首次启动 macOS `.app` 时，应用会要求用户选择工作区目录。  
实际文献数据、PDF、导出文档都保存在你选择的工作区下，而不是写入 app bundle。

## 九、关键代码结构

- `app.py`  
  Streamlit 主界面，负责参数输入、按钮流程、实时日志。
- `core_logic.py`  
  核心业务逻辑，包括 PubMed、Europe PMC、Sci-Hub、向量化、分章节写作、导出。
- `desktop_app.py`  
  macOS 桌面入口，负责 pywebview 窗口和 Streamlit 子进程。
- `streamlit_server.py`  
  被桌面壳拉起的 Streamlit 服务端入口。
- `workspace_manager.py`  
  工作区、配置路径、日志路径、bundle 资源路径管理。
- `config_manager.py`  
  LLM / Embedding 配置读写。
- `convert_same_directory.py`  
  PDF 同目录批量转换 Markdown 的入口。
- `build_app.sh` / `build_macos.spec`  
  macOS 打包脚本与 PyInstaller 配置。
- `win/`  
  Windows 版本相关入口与打包脚本。

## 十、当前已修正的重要行为

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

## 十一、已知说明

- 能否拿到全文取决于 Europe PMC / PMC 收录情况、目标站点访问情况以及相关镜像可用性。
- 某些文章即使没有 PDF，也仍可通过摘要 `.md` 继续进入后续流程。
- 原文下载、Marker 转换、Embedding 和章节写作在大集合上耗时可能较长。
- Word / HTML 导出依赖当前语言模式下已生成的章节 JSON 和框架 CSV。
- HTML 导出中的 PMID 详情来自章节 JSON 中保存的结构化素材；旧项目会回退解析章节提示词。

## 十二、许可证与合规

本项目包含对 PubMed / Europe PMC / Sci-Hub / 第三方模型与接口的调用逻辑。  
在对外发布和实际使用前，请自行确认目标环境中的服务条款、版权约束和网络合规要求。  
请仅在合法、合规、符合所在机构政策的前提下使用全文下载与文献处理功能。
