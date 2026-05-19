import streamlit as st
import asyncio
import os
import glob
import time
import json
import re
import html
import pandas as pd
from datetime import datetime

# 导入自定义模块
import config_manager
import core_logic
import workspace_manager
from workspace_manager import get_collection_path, is_workspace_configured, is_bundled_app, set_workspace, setup_app_environment, reload_workspace

APP_VERSION_LABEL = "V1.0"

# Setup environment for bundled app
setup_app_environment()

# --- 页面设置 ---
st.set_page_config(page_title=f"Open Pubmed Deep Research {APP_VERSION_LABEL}", page_icon="🧬", layout="wide")

# --- 首次启动工作目录设置 ---
def show_workspace_setup():
    """Show workspace setup wizard for first-time users."""
    st.markdown("""
    <style>
        .setup-container {
            max-width: 600px;
            margin: 100px auto;
            padding: 40px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .setup-title {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 10px;
            text-align: center;
        }
        .setup-subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="setup-title">Welcome to Open Pubmed Deep Research {APP_VERSION_LABEL}</div>', unsafe_allow_html=True)
    st.markdown('<div class="setup-subtitle">Please select a workspace directory to store your research data.</div>', unsafe_allow_html=True)

    st.info("The workspace directory will contain all your research collections, downloaded PDFs, and generated documents.")

    # Input for workspace path
    default_path = os.path.expanduser("~/Documents/PubmedResearch")
    workspace_path = st.text_input(
        "Workspace Directory",
        value=st.session_state.get('setup_workspace_path', default_path),
        help="Choose a directory where your research data will be stored"
    )
    st.session_state['setup_workspace_path'] = workspace_path

    # Folder selection hint
    st.caption("Enter the full path to your desired workspace folder. The folder will be created if it doesn't exist.")

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("📁 Use Default Location", use_container_width=True):
            st.session_state['setup_workspace_path'] = default_path
            st.rerun()

    with col2:
        if st.button("✓ Confirm & Start", type="primary", use_container_width=True):
            if workspace_path:
                if set_workspace(workspace_path):
                    st.success("Workspace configured successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to create workspace directory. Please check the path and permissions.")
            else:
                st.error("Please enter a workspace directory path.")

    st.stop()

# Check if workspace setup is needed (bundled app and not configured)
if is_bundled_app() and not is_workspace_configured():
    show_workspace_setup()

# --- 集合名称验证 ---
COLLECTION_NAME_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9-]{1,60}[a-zA-Z0-9]$')

def validate_collection_name(name: str) -> tuple[bool, str]:
    if not name or not name.strip():
        return False, "empty"
    name = name.strip()
    if len(name) < 3:
        return False, "too_short"
    if len(name) > 63:
        return False, "too_long"
    if not COLLECTION_NAME_PATTERN.match(name):
        return False, "invalid_format"
    return True, "ok"

# --- 状态管理 ---
if 'lang' not in st.session_state: st.session_state['lang'] = 'zh'
if 'log_history' not in st.session_state: st.session_state['log_history'] = []
if 'log_file_sessions' not in st.session_state: st.session_state['log_file_sessions'] = {}
if 'view_mode' not in st.session_state: st.session_state['view_mode'] = '工作区'
if 'sections_data' not in st.session_state: st.session_state['sections_data'] = None
if 'writing_progress' not in st.session_state: st.session_state['writing_progress'] = 0.0

# --- 翻译字典 ---
T = {
    'zh': {
        'title': f"🧬 Open Pubmed Deep Research {APP_VERSION_LABEL}",
        'workspace': "工作区",
        'settings': "设置",
        'lang_zh': "🇨🇳 中文",
        'lang_en': "🇺🇸 English",
        'log_title': "📟 Real-time Logs",
        'clear_log': "🧹 清空日志",
        'project_card': "📁 1. 项目集合",
        'project_guide': "为当前研究创建一个独立的文件夹名称。",
        'coll_name': "集合名称",
        'coll_name_hint': "3-63字符，字母开头，仅限字母/数字/连字符",
        'coll_err_empty': "⚠️ 请输入集合名称",
        'coll_err_short': "⚠️ 集合名称至少3个字符",
        'coll_err_long': "⚠️ 集合名称最多63个字符",
        'coll_err_format': "⚠️ 格式错误：需字母开头，仅限字母/数字/连字符，不能以连字符结尾",
        'lock_msg': "⚠️ 请输入有效的集合名称以解锁下方模块",
        'search_card': "🔍 2. 文献检索与管理",
        'search_guide': "从 Pubmed 检索文献并管理 XML 元数据。",
        'keyword': "Pubmed 主题词",
        'count': "检索数量",
        'sort': "排序方式",
        'sort_rel': "相关性",
        'sort_date': "出版时间",
        'date_range': "📅 高级日期筛选",
        'start_date': "起始日期",
        'end_date': "结束日期",
        'btn_search': "🔍 检索关键词",
        'btn_merge': "🔗 合并结果",
        'btn_extract': "📝 提取摘要TXT",
        'btn_clear_xml': "🗑️ 清除XML",
        'frame_card': "📝 3. 综述框架生成",
        'frame_guide': "基于摘要合集，利用 AI 生成综述的大纲结构。",
        'topic': "综述主题",
        'prompt_custom': "🛠️ 提示词自定义 & 预览",
        'custom_req': "补充要求",
        'btn_gen_frame': "✨ 生成综述框架",
        'btn_load_frame': "📂 加载现有框架",
        'process_card': "⚙️ 4. 原文下载及处理",
        'process_guide': "下载 PDF 全文并将其转化为可检索的向量数据库。",
        'btn_pipeline': "🚀 一键三连",
        'pipeline_help': "Run full-text download, Markdown conversion, and vectorization in sequence.",
        'pipeline_start': "Pipeline 1/3: Downloading full text...",
        'pipeline_marker': "Pipeline 2/3: Converting to Markdown...",
        'pipeline_vector': "Pipeline 3/3: Vectorizing...",
        'pipeline_done': "√ Pipeline finished.",
        'btn_download': "📥 全文下载",
        'worker_label': "Worker (CPU核心)",
        'worker_help': "建议设为您的 CPU 核心数以加快转换速度。",
        'marker_batch_label': "Marker 批大小",
        'marker_batch_help': "每加载一次 Marker 模型后连续处理的 PDF 数量。较大更快，较小更稳。",
        'btn_marker': "📝 Markdown 转化",
        'btn_vector': "🧠 向量化入库",
        'write_card': "✍️ 5. 内容撰写",
        'write_guide': "利用 RAG 技术，针对每个章节自动检索素材并撰写正文。",
        'write_params': "⚙️ 生成参数设置 (RAG & 并发)",
        'write_help': "Top-K: 每个末级节点检索的文献片段数量。并发线程: 同时请求 LLM 的写作包数量。每个写作包会自动完成撰写、引用校验和必要的小节修复。",
        'write_progress_idle': "等待开始撰写。",
        'write_progress_running': "正在处理写作包：{done}/{total}",
        'write_progress_done': "写作包处理完成：{total}/{total}",
        'btn_write': "🚀 开始/继续撰写",
        'btn_retry': "🔄 重试失败项",
        'export_card': "📤 6. 导出成品",
        'export_guide': "将生成的章节内容合并为最终文档。",
        'btn_word': "📄 导出 Word",
        'btn_html': "🌐 导出 HTML",
        'debug_card': "🛠️ 7. 调试工具",
        'debug_guide': "清理数据库或生成内部调试文件。",
        'btn_clear_db': "🗑️ 清空向量数据库",
        'btn_debug_file': "🐞 生成调试文件",
        'log_dl_finish': "√ All download tasks finished."
    },
    'en': {
        'title': f"🧬 Open Pubmed Deep Research {APP_VERSION_LABEL}",
        'workspace': "Workspace",
        'settings': "Settings",
        'lang_zh': "🇨🇳 中文",
        'lang_en': "🇺🇸 English",
        'log_title': "📟 Real-time Logs",
        'clear_log': "🧹 Clear Logs",
        'project_card': "📁 1. Project Collection",
        'project_guide': "Create a unique folder name for your current research.",
        'coll_name': "Collection Name",
        'coll_name_hint': "3-63 chars, start with letter, only letters/numbers/hyphens",
        'coll_err_empty': "⚠️ Please enter a collection name",
        'coll_err_short': "⚠️ Collection name must be at least 3 characters",
        'coll_err_long': "⚠️ Collection name must be at most 63 characters",
        'coll_err_format': "⚠️ Invalid format: must start with letter, only letters/numbers/hyphens, cannot end with hyphen",
        'lock_msg': "⚠️ Please enter a valid collection name to unlock modules.",
        'search_card': "🔍 2. Literature Search",
        'search_guide': "Retrieve metadata from Pubmed and manage XML files.",
        'keyword': "Pubmed Keywords",
        'count': "Result Count",
        'sort': "Sort By",
        'sort_rel': "Relevance",
        'sort_date': "Pub Date",
        'date_range': "📅 Advanced Date Filter",
        'start_date': "Start Date",
        'end_date': "End Date",
        'btn_search': "🔍 Search Keywords",
        'btn_merge': "🔗 Merge Results",
        'btn_extract': "📝 Extract Abstracts",
        'btn_clear_xml': "🗑️ Clear XMLs",
        'frame_card': "📝 3. Framework Generation",
        'frame_guide': "AI generates a review outline based on abstract collections.",
        'topic': "Review Topic",
        'prompt_custom': "🛠️ Prompt Customization & Preview",
        'custom_req': "Custom Requirements",
        'btn_gen_frame': "✨ Generate Framework",
        'btn_load_frame': "📂 Load Framework",
        'process_card': "⚙️ 4. Full-text Processing",
        'process_guide': "Download PDFs and convert them into a vector database.",
        'btn_pipeline': "🚀 Run Pipeline",
        'pipeline_help': "Run full-text download, Markdown conversion, and vectorization in sequence.",
        'pipeline_start': "Pipeline 1/3: Downloading full text...",
        'pipeline_marker': "Pipeline 2/3: Converting to Markdown...",
        'pipeline_vector': "Pipeline 3/3: Vectorizing...",
        'pipeline_done': "√ Pipeline finished.",
        'btn_download': "📥 Download PDFs",
        'worker_label': "Worker (CPU Cores)",
        'worker_help': "Set to your CPU core count for faster conversion.",
        'marker_batch_label': "Marker Batch Size",
        'marker_batch_help': "Number of PDFs processed per Marker model-loading session. Larger is faster; smaller is safer.",
        'btn_marker': "📝 Markdown Convert",
        'btn_vector': "🧠 Vectorize (Embed)",
        'write_card': "✍️ 5. Content Writing",
        'write_guide': "RAG-based automated writing for each section.",
        'write_params': "⚙️ Generation Parameters (RAG & Concurrency)",
        'write_help': "Top-K: chunks per terminal node. Concurrency: parallel writing units. Each writing unit includes drafting, citation validation, and targeted subsection repair when needed.",
        'write_progress_idle': "Waiting to start writing.",
        'write_progress_running': "Processing writing units: {done}/{total}",
        'write_progress_done': "Writing units finished: {total}/{total}",
        'btn_write': "🚀 Start/Continue Writing",
        'btn_retry': "🔄 Retry Failed Items",
        'export_card': "📤 6. Export Results",
        'export_guide': "Merge generated sections into final documents.",
        'btn_word': "📄 Export Word",
        'btn_html': "🌐 Export HTML",
        'debug_card': "🛠️ 7. Debug Tools",
        'debug_guide': "Clean database or generate debug files.",
        'btn_clear_db': "🗑️ Clear Vector DB",
        'btn_debug_file': "🐞 Gen Debug File",
        'log_dl_finish': "√ All download tasks finished."
    }
}

def t(key):
    return T[st.session_state['lang']].get(key, key)

# --- 终极布局 CSS ---
st.markdown("""
<style>
    /* 1. 全局布局重置 */
    .stApp { background-color: #f8f9fa; }
    [data-testid="stHeader"] { display: none; }
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        padding-left: 3rem !important;
        padding-right: 32% !important; /* 右侧留给日志 */
        max-width: 100% !important;
    }

    /* 2. 标题区样式 */
    .main-header { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 2.2rem; 
        font-weight: 800; 
        color: #111; 
        margin-bottom: 0px;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
        font-weight: 400;
    }

    /* 3. 真正的胶囊切换开关 (Pill Toggle) */
    
    /* 容器：深灰底槽 */
    div[role="radiogroup"] {
        background-color: #e5e7eb; /* 稍微加深的灰色底槽，增加对比 */
        padding: 4px;
        border-radius: 9999px !important;
        display: inline-flex;
        border: none !important;
        width: 100% !important;
        min-width: 320px !important;
        height: 50px !important;
    }

    /* 选项标签：默认状态 (未选中) */
    div[role="radiogroup"] label {
        flex: 1;
        text-align: center;
        background-color: transparent;
        padding: 0px 20px !important; 
        border-radius: 9999px !important;
        cursor: pointer;
        transition: all 0.2s ease-in-out;
        color: #6b7280; /* 未选中：中灰色 */
        font-weight: 600;
        font-size: 0.95rem;
        border: none !important;
        margin: 0 !important;
        white-space: nowrap !important;
        overflow: visible !important;
        box-shadow: none !important;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* 隐藏原生圆圈 */
    div[role="radiogroup"] label > div:first-child { display: none !important; }

    /* 选中状态：高亮颜色 (Indigo) */
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #4f46e5 !important; /* 核心修改：使用靛蓝色 */
        color: #ffffff !important; /* 核心修改：白色文字 */
        box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.4), 0 2px 4px -1px rgba(79, 70, 229, 0.2) !important; /* 带颜色的阴影 */
        transform: scale(1.0); /* 保持平整，不缩放 */
    }
    
    /* 悬停微互动 (未选中项) */
    div[role="radiogroup"] label:hover:not([data-checked="true"]) {
        color: #374151; /* 悬停时文字变深一点 */
        background-color: rgba(255,255,255,0.5); /* 微微泛白 */
    }

    /* 开关上方的 Label 小标题 */
    .toggle-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94a3b8;
        font-weight: 700;
        margin-bottom: 8px;
        margin-left: 10px;
    }

    /* 4. 日志面板 (右侧固定) */
    .fixed-log-panel {
        position: fixed !important;
        top: 0 !important;
        right: 0 !important;
        width: 30% !important;
        height: 100vh !important;
        background-color: #ffffff;
        border-left: 1px solid #e1e4e8;
        z-index: 99999;
        padding: 20px;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        box-shadow: -5px 0 15px rgba(0,0,0,0.05);
    }

    /* 5. 卡片容器 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white !important;
        border-radius: 16px !important;
        border: 1px solid #eef2f6 !important;
        padding: 24px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.02) !important;
        margin-bottom: 24px !important;
    }

    /* 6. 终端日志 */
    .live-terminal { 
        background-color: #1e1e1e; 
        color: #00ff9d; 
        font-family: 'JetBrains Mono', 'Consolas', monospace; 
        padding: 15px; 
        border-radius: 8px;
        flex-grow: 1;
        overflow-y: auto; 
        font-size: 12px; 
        line-height: 1.5; 
        border: 1px solid #333;
        margin-bottom: 10px;
        white-space: pre-wrap;
    }

    /* 7. 按钮优化 */
    .stButton>button {
        width: 100% !important;
        height: 42px !important; 
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid #e2e8f0;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        border-color: #cbd5e1;
        background-color: #f8fafc;
    }
    div[data-testid="stNumberInput"] input { height: 42px !important; border-radius: 8px !important; }

    .card-title { font-size: 1.25rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
    .card-guide { font-size: 0.85rem; color: #64748b; margin-bottom: 20px; }
    .log-header { font-size: 1rem; font-weight: 700; color: #334155; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #f1f5f9; }
</style>
""", unsafe_allow_html=True)

# --- 实时日志工具 ---
class RealTimeLogger:
    def __init__(self, container):
        self.container = container

    def _get_collection_log_path(self):
        collection_name = st.session_state.get('saved_collection_name', '').strip()
        is_valid, _ = validate_collection_name(collection_name)
        if not is_valid:
            return None, None

        collection_path = get_collection_path(collection_name)
        os.makedirs(collection_path, exist_ok=True)
        return collection_name, os.path.join(collection_path, "runtime.log")

    def _append_to_collection_log(self, entry):
        collection_name, log_path = self._get_collection_log_path()
        if not log_path:
            return

        session_key = f"{collection_name}:{log_path}"
        try:
            with open(log_path, "a", encoding="utf-8") as log_file:
                if not st.session_state['log_file_sessions'].get(session_key):
                    log_file.write(
                        f"\n=== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} session start ===\n"
                    )
                    st.session_state['log_file_sessions'][session_key] = True
                log_file.write(f"{entry}\n")
        except OSError:
            pass

    def log(self, message):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        st.session_state['log_history'].append(entry)
        if len(st.session_state['log_history']) > 500: st.session_state['log_history'].pop(0)
        self._append_to_collection_log(entry)
        self.render()
    def render(self):
        log_text = "\n".join(st.session_state['log_history'])
        escaped_log_text = html.escape(log_text)
        panel_html = f"""
        <div class="fixed-log-panel">
            <div class="log-header">{t('log_title')}</div>
            <div class="live-terminal" id="log-box">{escaped_log_text}</div>
            <script>
                var el = document.getElementById("log-box"); 
                if(el) el.scrollTop = el.scrollHeight;
            </script>
        </div>
        """
        self.container.markdown(panel_html, unsafe_allow_html=True)

# --- 初始化日志 ---
log_placeholder = st.empty()
logger = RealTimeLogger(log_placeholder)
logger.render()

# ==========================================
# 顶部区域 (Modern Header & Toggle)
# ==========================================

st.markdown(f'<div class="main-header">{t("title")}</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Literature Review & Meta-Analysis Agent</div>', unsafe_allow_html=True)

# 使用 container 包裹
with st.container():
    c_view, c_lang = st.columns(2, gap="large") 
    
    with c_view:
        st.markdown('<div class="toggle-label">View Mode</div>', unsafe_allow_html=True)
        view_mode = st.radio(
            "View Mode Hidden", # 隐藏的 Label
            [t('workspace'), t('settings')], 
            horizontal=True, 
            label_visibility="collapsed", 
            key="view_switch"
        )
        st.session_state['view_mode'] = "Settings" if view_mode == t('settings') else "Workspace"

    with c_lang:
        # 动态提示文案
        lang_hint = "Output: Chinese" if st.session_state['lang'] == 'zh' else "Output: English"
        st.markdown(f'<div class="toggle-label">{lang_hint}</div>', unsafe_allow_html=True)
        
        lang_opts = ["🇨🇳 中文", "🇺🇸 English"]
        current_idx = 0 if st.session_state['lang'] == 'zh' else 1
        
        lang_choice = st.radio(
            "Language Hidden", 
            lang_opts, 
            index=current_idx, 
            horizontal=True, 
            label_visibility="collapsed", 
            key="lang_switch"
        )
        
        new_lang = 'zh' if lang_choice == "🇨🇳 中文" else 'en'
        if new_lang != st.session_state['lang']:
            st.session_state['lang'] = new_lang
            st.rerun()

st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True) # 增加一点间距

# ==========================================
# 主内容区
# ==========================================

if st.session_state['view_mode'] == "Settings":
    with st.container(border=True):
        st.markdown(f'<div class="card-title">⚙️ {t("settings")}</div>', unsafe_allow_html=True)
        config = config_manager.load_config()

        # === Workspace Configuration (available in all modes) ===
        st.markdown("### Workspace Directory")

        # Show current workspace path
        wm = workspace_manager.get_workspace_manager()
        if wm.workspace_path:
            current_workspace = wm.workspace_path
        elif is_bundled_app():
            current_workspace = "Not configured (using default)"
        else:
            # Development mode - show the content directory location
            current_workspace = os.path.abspath(workspace_manager.get_content_dir())

        st.text_input("Current Workspace", value=current_workspace, disabled=True)

        # Default path suggestion
        default_path = os.path.expanduser("~/Documents/PubmedResearch")

        new_workspace = st.text_input(
            "Change Workspace",
            value="",
            placeholder=f"Enter path (e.g., {default_path})",
            help="Change the workspace directory. All new collections will be saved here. Existing data will NOT be moved automatically."
        )

        st.caption("Note: On macOS, you can drag a folder from Finder into this text field to paste its path.")

        if st.button("📁 Update Workspace", use_container_width=True):
            if new_workspace:
                if set_workspace(new_workspace):
                    # Reload workspace manager to pick up new path
                    reload_workspace()
                    st.success(f"Workspace updated to: {new_workspace}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to set workspace. Please check the path and permissions.")
            else:
                st.warning("Please enter a workspace path.")

        st.markdown("---")

        # === LLM 配置 ===
        st.markdown("### LLM Configuration")

        llm_presets = config.get("llm_presets", {})
        preset_names = sorted(llm_presets.keys())

        def set_llm_form_values(llm_config):
            st.session_state["llm_base"] = llm_config.get("base_url", "")
            st.session_state["llm_key"] = llm_config.get("api_key", "")
            st.session_state["llm_model_text"] = llm_config.get("model", "")
            st.session_state["llm_model_select"] = llm_config.get("model", "")

        preset_options = [""] + preset_names
        if st.session_state.get("llm_preset_select", "") not in preset_options:
            st.session_state["llm_preset_select"] = ""
            st.session_state["last_applied_llm_preset"] = ""

        preset_col, delete_col = st.columns([4, 1])
        with preset_col:
            selected_preset = st.selectbox(
                "LLM Preset",
                preset_options,
                format_func=lambda x: x or "Manual / unsaved",
                key="llm_preset_select",
                help="Selecting a preset applies it immediately."
            )

        if selected_preset and selected_preset != st.session_state.get("last_applied_llm_preset"):
            preset_config = llm_presets.get(selected_preset)
            if preset_config:
                config["llm"].update(config_manager.normalize_llm_config(preset_config))
                config_manager.save_config(config)
                set_llm_form_values(config["llm"])
                st.session_state["llm_preset_name"] = selected_preset
                st.session_state["last_applied_llm_preset"] = selected_preset
                st.session_state['llm_models'] = []
                st.toast(f"Applied preset: {selected_preset}")
                st.rerun()

        if not selected_preset:
            st.session_state["last_applied_llm_preset"] = ""

        with delete_col:
            st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if st.button("🗑️ Delete", key="delete_llm_preset", use_container_width=True, disabled=not selected_preset):
                success, msg = config_manager.delete_llm_preset(selected_preset)
                if success:
                    st.success(msg)
                    st.session_state["last_applied_llm_preset"] = ""
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(msg)

        l_base = st.text_input("LLM Base URL", value=config['llm']['base_url'], key="llm_base")
        l_key = st.text_input("LLM API Key", value=config['llm']['api_key'], type="password", key="llm_key")

        # 模型列表管理
        if 'llm_models' not in st.session_state:
            st.session_state['llm_models'] = []
        if 'llm_models_error' not in st.session_state:
            st.session_state['llm_models_error'] = ""

        col_model, col_refresh = st.columns([4, 1])

        with col_model:
            # 如果有拉取的模型列表，显示选择框；否则显示文本输入
            if st.session_state['llm_models']:
                current_model = config['llm']['model']
                options = st.session_state['llm_models']
                # 确保当前模型在列表中
                if current_model and current_model not in options:
                    options = [current_model] + options
                default_idx = options.index(current_model) if current_model in options else 0
                l_model = st.selectbox("LLM Model", options=options, index=default_idx, key="llm_model_select")
            else:
                l_model = st.text_input("LLM Model", value=config['llm']['model'], key="llm_model_text",
                                        help="Click 'Fetch' to auto-load available models")

        with col_refresh:
            st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if st.button("🔄 Fetch", key="fetch_models", use_container_width=True):
                async def fetch_models():
                    temp_config = {"base_url": l_base, "api_key": l_key}
                    success, models, error = await core_logic.fetch_llm_models(temp_config)
                    if success:
                        st.session_state['llm_models'] = models
                        st.session_state['llm_models_error'] = ""
                        st.success(f"Found {len(models)} models")
                    else:
                        st.session_state['llm_models_error'] = error
                        st.error(f"Failed: {error}")
                asyncio.run(fetch_models())
                st.rerun()

        if st.session_state['llm_models_error']:
            st.error(st.session_state['llm_models_error'])

        preset_name_col, preset_save_col = st.columns([4, 1])
        with preset_name_col:
            preset_name = st.text_input("Preset Name", value="", placeholder="e.g., DeepSeek v4 pro", key="llm_preset_name")
        with preset_save_col:
            st.markdown('<div style="height: 28px;"></div>', unsafe_allow_html=True)
            if st.button("💾 Save Preset", key="save_llm_preset", use_container_width=True):
                current_llm_config = dict(config.get('llm', {}))
                current_llm_config.update({"base_url": l_base, "model": l_model, "api_key": l_key})
                success, msg = config_manager.save_llm_preset(preset_name, current_llm_config)
                if success:
                    st.success(msg)
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(msg)

        # 连接测试按钮
        col_test, col_result = st.columns([1, 3])
        with col_test:
            if st.button("🧪 Test Connection", key="test_llm", use_container_width=True):
                async def test_connection():
                    temp_config = {"base_url": l_base, "api_key": l_key, "model": l_model}
                    success, response, elapsed = await core_logic.test_llm_connection(temp_config)
                    return success, response, elapsed
                success, response, elapsed = asyncio.run(test_connection())
                if success:
                    st.session_state['llm_test_result'] = f"✅ Success ({elapsed:.2f}s): {response}"
                else:
                    st.session_state['llm_test_result'] = f"❌ Failed: {response}"

        with col_result:
            if 'llm_test_result' in st.session_state:
                if st.session_state['llm_test_result'].startswith("✅"):
                    st.success(st.session_state['llm_test_result'])
                else:
                    st.error(st.session_state['llm_test_result'])

        st.markdown("---")

        # === Embedding 配置 ===
        st.markdown("### Embedding Configuration")
        e_base = st.text_input("Emb Base URL", value=config['embedding']['base_url'])
        e_model = st.text_input("Emb Model", value=config['embedding']['model_name'])
        e_key = st.text_input("Emb API Key", value=config['embedding']['api_key'], type="password")

        st.markdown("---")

        # 保存按钮
        if st.button("💾 Save Config", type="primary", use_container_width=True):
            config['llm'].update({"base_url": l_base, "model": l_model, "api_key": l_key})
            config['embedding'].update({"base_url": e_base, "model_name": e_model, "api_key": e_key})
            config_manager.save_config(config)
            st.success("✅ Configuration saved!")
else:
    # 模块 1
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("project_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("project_guide")}</div>', unsafe_allow_html=True)
        coll_name = st.text_input(
            t("coll_name"), 
            value=st.session_state.get('saved_collection_name', ""), 
            placeholder="lung_cancer_2024",
            help=t("coll_name_hint")
        )
        st.session_state['saved_collection_name'] = coll_name
        
        is_valid, err_code = validate_collection_name(coll_name)
        is_locked = not is_valid
        
        if not is_valid and coll_name.strip():
            err_map = {
                "too_short": "coll_err_short",
                "too_long": "coll_err_long", 
                "invalid_format": "coll_err_format"
            }
            if err_code in err_map:
                st.error(t(err_map[err_code]))
        elif is_locked:
            st.warning(t("lock_msg"))

    # 模块 2
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("search_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("search_guide")}</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([3, 1, 1])
        kw = c1.text_input(t("keyword"), value=st.session_state.get('saved_keyword', ""), disabled=is_locked)
        st.session_state['saved_keyword'] = kw
        num = c2.number_input(t("count"), 1, 1000, 10, disabled=is_locked)
        sort = c3.selectbox(t("sort"), [t("sort_rel"), t("sort_date")], disabled=is_locked)
        with st.expander(t("date_range")):
            cd1, cd2 = st.columns(2)
            start_d = cd1.date_input(t("start_date"), value=None, disabled=is_locked)
            end_d = cd2.date_input(t("end_date"), value=None, disabled=is_locked)
        st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns(4)
        if b1.button(t("btn_search"), disabled=is_locked):
            async def run_s():
                logger.log(f"Searching: {kw}...")
                save_path = get_collection_path(coll_name)
                os.makedirs(save_path, exist_ok=True)
                from core_logic import get_next_xml_filename
                fn = get_next_xml_filename(save_path)
                res = await core_logic.search_pubmed_and_save_xml(kw, num, "relevance" if sort==t("sort_rel") else "pub_date", start_d, end_d, save_path, fn)
                logger.log(f"Done. Found {len(res)} records.")
            asyncio.run(run_s())
        if b2.button(t("btn_merge"), disabled=is_locked):
            success, msg = core_logic.merge_pubmed_xmls(get_collection_path(coll_name), logger.log)
            logger.log(msg)
        if b3.button(t("btn_extract"), disabled=is_locked):
            success, msg = core_logic.extract_abstracts_to_txt(get_collection_path(coll_name), logger.log)
            logger.log(msg)
        if b4.button(t("btn_clear_xml"), disabled=is_locked):
            logger.log(core_logic.clear_xml_files(get_collection_path(coll_name)))

    # 模块 3
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("frame_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("frame_guide")}</div>', unsafe_allow_html=True)
        topic = st.text_input(t("topic"), value=st.session_state.get('saved_review_topic', ""), disabled=is_locked)
        st.session_state['saved_review_topic'] = topic
        with st.expander(t("prompt_custom")):
            u_req = st.text_area(t("custom_req"), value=st.session_state.get('custom_prompt_reqs', ""), disabled=is_locked)
            st.session_state['custom_prompt_reqs'] = u_req
            # 恢复提示词预览
            if st.session_state['lang'] == 'en':
                preview = f"{core_logic.FRAMEWORK_PROMPT_INTRO_EN}\n{core_logic.FRAMEWORK_PROMPT_BASE_REQS_EN}\n- {u_req}\n{core_logic.FRAMEWORK_PROMPT_OUTPUT_FMT_EN}"
            else:
                preview = f"{core_logic.FRAMEWORK_PROMPT_INTRO_ZH}\n{core_logic.FRAMEWORK_PROMPT_BASE_REQS_ZH}\n- {u_req}\n{core_logic.FRAMEWORK_PROMPT_OUTPUT_FMT_ZH}"
            st.code(preview)

        f1, f2 = st.columns(2)
        if f1.button(t("btn_gen_frame"), type="primary", disabled=is_locked):
            async def run_f():
                cfg = config_manager.load_config()
                await core_logic.generate_review_framework(coll_name, topic, u_req, cfg['llm'], logger.log, lang=st.session_state['lang'])
            asyncio.run(run_f())
        if f2.button(t("btn_load_frame"), disabled=is_locked):
            csv_p = core_logic.get_framework_csv_path(coll_name, st.session_state['lang'], allow_legacy=True)
            if os.path.exists(csv_p):
                st.session_state['sections_data'] = core_logic.parse_framework_to_sections(csv_p)
                logger.log(f"Framework loaded: {csv_p}")
            else: logger.log("File not found.")
        if st.session_state['sections_data']:
            with st.expander("Preview", expanded=False):
                st.table([{"ID": k, "Title": v['title']} for k,v in st.session_state['sections_data'].items()])

    # 模块 4
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("process_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("process_guide")}</div>', unsafe_allow_html=True)
        cp1, cp2, cp3, cp4, cp5 = st.columns([1, 1, 1, 1, 1])
        def label_spacer(): st.markdown('<div style="height: 26px; margin-bottom: 2px;"></div>', unsafe_allow_html=True)
        with cp1:
            label_spacer()
            if st.button(t("btn_download"), disabled=is_locked):
                async def run_d():
                    await core_logic.run_fulltext_download_pipeline(coll_name, logger.log)
                    logger.log(t("log_dl_finish"))

                asyncio.run(run_d())
        with cp2:
            wk = st.number_input(t("worker_label"), 1, 16, 8, disabled=is_locked, help=t("worker_help"))
        with cp3:
            marker_batch_size = st.number_input(
                t("marker_batch_label"),
                min_value=1,
                max_value=200,
                value=10,
                step=1,
                disabled=is_locked,
                help=t("marker_batch_help"),
            )
        with cp4:
            label_spacer()
            if st.button(t("btn_marker"), disabled=is_locked):
                asyncio.run(core_logic.run_marker_conversion(
                    get_collection_path(coll_name),
                    wk,
                    logger.log,
                    marker_batch_size,
                ))
        with cp5:
            label_spacer()
            if st.button(t("btn_vector"), disabled=is_locked):
                async def run_v():
                    cfg = config_manager.load_config()
                    await core_logic.process_vectorization(coll_name, cfg['embedding'], logger.log)
                asyncio.run(run_v())
        if st.button(t("btn_pipeline"), type="primary", disabled=is_locked, help=t("pipeline_help"), use_container_width=True):
            async def run_pipeline():
                logger.log(t("pipeline_start"))
                await core_logic.run_fulltext_download_pipeline(coll_name, logger.log)
                logger.log(t("log_dl_finish"))

                logger.log(t("pipeline_marker"))
                await core_logic.run_marker_conversion(
                    get_collection_path(coll_name),
                    wk,
                    logger.log,
                    marker_batch_size,
                )

                logger.log(t("pipeline_vector"))
                cfg = config_manager.load_config()
                await core_logic.process_vectorization(coll_name, cfg['embedding'], logger.log)
                logger.log(t("pipeline_done"))
            asyncio.run(run_pipeline())

    # 模块 5
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("write_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("write_guide")}</div>', unsafe_allow_html=True)
        with st.expander(t("write_params")):
            st.info(t("write_help"))
            w1, w2 = st.columns([1, 1])
            rk = w1.number_input("RAG Top-K", 1, 20, 7, disabled=is_locked)
            cc = w2.number_input("Concurrency", 1, 10, 3, disabled=is_locked)
        progress_bar = st.progress(st.session_state['writing_progress'])
        progress_text = st.empty()
        progress_text.caption(t("write_progress_idle"))
        wb1, wb2 = st.columns(2)
        def section_needs_retry(parts_dir, key):
            fpath = os.path.join(parts_dir, f"section_{key}.json")
            if not os.path.exists(fpath) or os.path.getsize(fpath) < 50:
                return True
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("citation_validation", {}).get("status") == "failed"
            except Exception:
                return True

        async def run_writing_task(target_ids):
            cfg = config_manager.load_config()
            total = len(target_ids)
            if total == 0: return
            logger.log(f"Starting writing task: {total} writing units, concurrency: {cc}")
            sem = asyncio.Semaphore(cc)
            done_count = 0
            async def wrap(sid):
                nonlocal done_count
                async with sem:
                    progress_text.caption(t("write_progress_running").format(done=done_count, total=total))
                    await core_logic.generate_section_content(coll_name, st.session_state['sections_data'][sid], topic, rk, cfg['llm'], cfg['embedding'], logger.log, lang=st.session_state['lang'])
                    done_count += 1
                    st.session_state['writing_progress'] = done_count / total
                    progress_bar.progress(st.session_state['writing_progress'])
                    progress_text.caption(t("write_progress_running").format(done=done_count, total=total))
            await asyncio.gather(*[wrap(s) for s in target_ids])
            logger.log("Writing task finished.")
            st.session_state['writing_progress'] = 1.0
            progress_bar.progress(1.0)
            progress_text.caption(t("write_progress_done").format(total=total))

        if wb1.button(t("btn_write"), type="primary", disabled=is_locked):
            if not st.session_state['sections_data']: st.error("Load framework first.")
            else:
                parts_dir = core_logic.get_review_parts_dir(coll_name, st.session_state['lang'])
                all_keys = list(st.session_state['sections_data'].keys())
                targets = [k for k in all_keys if section_needs_retry(parts_dir, k)]
                if not targets: logger.log("All writing units exist and passed citation validation.")
                else: asyncio.run(run_writing_task(targets))
        if wb2.button(t("btn_retry"), disabled=is_locked):
            if not st.session_state['sections_data']: st.error("Load framework first.")
            else:
                parts_dir = core_logic.get_review_parts_dir(coll_name, st.session_state['lang'])
                all_keys = list(st.session_state['sections_data'].keys())
                retry_targets = []
                for k in all_keys:
                    if section_needs_retry(parts_dir, k): retry_targets.append(k)
                if not retry_targets: logger.log("No failed items found.")
                else: asyncio.run(run_writing_task(retry_targets))

    # 模块 6
    with st.container(border=True):
        st.markdown(f'<div class="card-title">{t("export_card")}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="card-guide">{t("export_guide")}</div>', unsafe_allow_html=True)
        e1, e2 = st.columns(2)
        if e1.button(t("btn_word"), disabled=is_locked):
            async def run_ex_w():
                path = await core_logic.generate_final_word_doc(coll_name, topic, logger.log, lang=st.session_state['lang'])
                if path: logger.log(f"Word generated: {path}")
            asyncio.run(run_ex_w())
        if e2.button(t("btn_html"), disabled=is_locked):
            async def run_ex_h():
                path = await core_logic.generate_interactive_html_review(coll_name, topic, logger.log, lang=st.session_state['lang'])
                if path: logger.log(f"HTML generated: {path}")
            asyncio.run(run_ex_h())

    # 模块 7
    with st.expander(t("debug_card")):
        with st.container(border=True):
            st.markdown(f'<div class="card-guide">{t("debug_guide")}</div>', unsafe_allow_html=True)
            d1, d2 = st.columns(2)
            if d1.button(t("btn_clear_db")): asyncio.run(core_logic.clear_vector_db(coll_name, logger.log))
            if d2.button(t("btn_debug_file")): asyncio.run(core_logic.generate_debug_file(coll_name, logger.log))

if st.button(t('clear_log'), use_container_width=True):
    st.session_state['log_history'] = []
    st.rerun()
