import streamlit as st
import streamlit.components.v1 as components

from extractor import extract_from_url, image_to_base64
from ai_processor import extract_from_text, extract_from_image
from knowledge_store import add_knowledge, get_all, get_stats
from mindmap_renderer import render_mindmap_html, kb_to_text_outline, kb_to_markdown

st.set_page_config(
    page_title="KnowledgeFlow",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 KnowledgeFlow")
st.caption("把你刷到的内容，变成自己的知识框架")

# ── 顶部统计 ─────────────────────────────────────────────────────
stats = get_stats()
c1, c2, c3, c4 = st.columns(4)
c1.metric("已处理内容", stats["total_items"])
c2.metric("知识主题", stats["total_topics"])
c3.metric("知识维度", stats["total_dimensions"])
c4.metric("知识要点", stats["total_points"])

st.divider()

# ── 主界面：左侧输入 + 右侧知识库 ────────────────────────────────
left, right = st.columns([1, 1.6])

with left:
    st.subheader("➕ 添加内容")

    input_type = st.radio(
        "内容来源",
        ["🔗 粘贴链接（公众号）", "🖼️ 上传截图（小红书）", "📝 粘贴文字"],
        horizontal=False,
    )

    # —— 输入方式 1：URL ——————————————————————————
    if input_type == "🔗 粘贴链接（公众号）":
        url = st.text_input("文章链接", placeholder="粘贴公众号文章链接...")
        if st.button("提取并添加", type="primary", disabled=not url):
            with st.spinner("正在抓取文章内容..."):
                raw = extract_from_url(url)

            if "error" in raw:
                st.error(raw["error"])
            else:
                with st.spinner("AI 正在提取知识结构..."):
                    knowledge = extract_from_text(raw["text"], raw.get("title", ""))

                if "error" in knowledge:
                    st.error(knowledge["error"])
                else:
                    result = add_knowledge(knowledge, {
                        "title": raw.get("title", "未知标题"),
                        "url": url,
                        "platform": "微信公众号",
                    })
                    st.success(result["message"])
                    st.session_state["last_knowledge"] = knowledge
                    st.rerun()

    # —— 输入方式 2：图片 ——————————————————————————
    elif input_type == "🖼️ 上传截图（小红书）":
        uploaded = st.file_uploader(
            "上传截图",
            type=["jpg", "jpeg", "png"],
            help="支持小红书帖子截图、视频号截图",
        )
        if uploaded and st.button("提取并添加", type="primary"):
            with st.spinner("正在读取图片内容..."):
                img_b64 = image_to_base64(uploaded)

            with st.spinner("AI 正在提取知识结构..."):
                knowledge = extract_from_image(img_b64)

            if "error" in knowledge:
                st.error(knowledge["error"])
            else:
                result = add_knowledge(knowledge, {
                    "title": knowledge.get("summary", "小红书内容"),
                    "url": "",
                    "platform": "小红书",
                })
                st.success(result["message"])
                st.session_state["last_knowledge"] = knowledge
                st.rerun()

    # —— 输入方式 3：粘贴文字 ——————————————————————
    else:
        text_input = st.text_area(
            "粘贴文字内容",
            height=200,
            placeholder="复制文章正文或笔记内容粘贴到这里...",
        )
        source_title = st.text_input("来源标题（选填）", placeholder="文章或视频标题...")
        if st.button("提取并添加", type="primary", disabled=not text_input):
            with st.spinner("AI 正在提取知识结构..."):
                knowledge = extract_from_text(text_input, source_title)

            if "error" in knowledge:
                st.error(knowledge["error"])
            else:
                result = add_knowledge(knowledge, {
                    "title": source_title or "手动输入",
                    "url": "",
                    "platform": "手动",
                })
                st.success(result["message"])
                st.session_state["last_knowledge"] = knowledge
                st.rerun()

    # —— 上次提取预览 ——————————————————————————————
    if "last_knowledge" in st.session_state:
        k = st.session_state["last_knowledge"]
        with st.expander("上次提取结果", expanded=False):
            st.write(f"**主题**：{k.get('topic', '-')}")
            st.write(f"**维度**：{k.get('dimension', '-')}")
            st.write("**要点**：")
            for p in k.get("key_points", []):
                st.write(f"- {p}")

with right:
    st.subheader("🗺️ 我的知识框架")

    kb = get_all()

    if not kb.get("topics"):
        st.info("还没有内容，在左侧添加第一篇文章吧！")
    else:
        view_type = st.radio("视图", ["思维导图", "文字大纲"], horizontal=True)

        if view_type == "思维导图":
            md_content = kb_to_markdown(kb)
            html_content = render_mindmap_html(md_content)
            components.html(html_content, height=540, scrolling=False)
        else:
            st.markdown(kb_to_text_outline(kb))
