def kb_to_markdown(kb: dict) -> str:
    """将知识库转为 Markdown 层级（供 MCP 工具文字回复使用）"""
    lines = ["# 我的知识框架"]
    for topic, topic_data in kb.get("topics", {}).items():
        lines.append(f"\n## {topic}")
        for dim, dim_data in topic_data.get("dimensions", {}).items():
            lines.append(f"\n### {dim}")
            for form, form_data in dim_data.get("forms", {}).items():
                lines.append(f"\n#### [{form}]")
                for point in form_data.get("points", []):
                    lines.append(f"\n- {point}")
                for src in form_data.get("sources", []):
                    lines.append(f"\n  > 来源：{src.get('title', '')}")
    return "\n".join(lines)


# 主题左边框颜色（绿色系循环）
_TOPIC_COLORS = [
    "#52b788", "#2d6a4f", "#40916c", "#74c69d",
    "#1b4332", "#95d5b2", "#27ae60", "#b7e4c7",
]


def kb_to_html_tree(kb: dict) -> str:
    """
    将知识库渲染为纯 HTML 可折叠树。
    无 JS、无 CDN 依赖，原生 <details>/<summary> 实现折叠，
    完整展示：主题 → 维度 → 要点（编号列表）+ 来源链接。
    """
    topics = kb.get("topics", {})
    if not topics:
        return '<p class="empty-tip">还没有内容<br><strong>发给龙虾一篇文章链接</strong>，知识树就会长出来 🌱</p>'

    blocks = []
    for idx, (topic, topic_data) in enumerate(topics.items()):
        color = _TOPIC_COLORS[idx % len(_TOPIC_COLORS)]
        dims = topic_data.get("dimensions", {})

        # 统计：需要深入到 forms 层
        total_pts = sum(
            len(f["points"])
            for d in dims.values()
            for f in d.get("forms", {}).values()
        )
        total_src = sum(
            len(f["sources"])
            for d in dims.values()
            for f in d.get("forms", {}).values()
        )

        dim_blocks = []
        for dim, dim_data in dims.items():
            forms = dim_data.get("forms", {})
            dim_total_pts = sum(len(f["points"]) for f in forms.values())
            dim_total_src = sum(len(f["sources"]) for f in forms.values())

            form_blocks = []
            for form, form_data in forms.items():
                points = form_data.get("points", [])
                sources = form_data.get("sources", [])

                # 要点列表
                pts_html = ("<ol class='points'>" + "".join(
                    f"<li>{_esc(p)}</li>" for p in points
                ) + "</ol>") if points else ""

                # 来源链接
                src_items = []
                for s in sources:
                    url = s.get("url", "")
                    title = _esc(s.get("title") or "未知标题")
                    date = s.get("date", "")
                    if url:
                        src_items.append(
                            f'<a href="{_esc(url)}" target="_blank" class="src-link">'
                            f'{title}</a><span class="src-date">{date}</span>'
                        )
                    else:
                        src_items.append(
                            f'<span class="src-nolink">{title}</span>'
                            f'<span class="src-date">{date}</span>'
                        )

                src_html = (
                    '<div class="sources"><span class="src-label">📎 来源</span>'
                    + " &nbsp;·&nbsp; ".join(src_items)
                    + "</div>"
                ) if src_items else ""

                fc = _form_class(form)
                form_blocks.append(f"""
<details class="form-block">
  <summary class="form-summary">
    <span class="form-name form-tag form-{fc}">{_esc(form)}</span>
    <span class="form-meta">{len(sources)} 篇来源 · {len(points)} 个要点</span>
  </summary>
  <div class="form-body">
    {pts_html}
    {src_html}
  </div>
</details>""")

            dim_blocks.append(f"""
<details class="dim-block">
  <summary class="dim-summary">
    <span class="dim-name">{_esc(dim)}</span>
    <span class="dim-meta">{len(forms)} 种形式 · {dim_total_pts} 个要点 · {dim_total_src} 篇来源</span>
  </summary>
  <div class="dim-body">
    {"".join(form_blocks)}
  </div>
</details>""")

        blocks.append(f"""
<details class="topic-block" open>
  <summary class="topic-summary" style="border-left:4px solid {color}">
    <span class="topic-name">{_esc(topic)}</span>
    <span class="topic-meta">{len(dims)} 个方向 · {total_pts} 个要点 · {total_src} 篇来源</span>
  </summary>
  <div class="topic-body">
    {"".join(dim_blocks)}
  </div>
</details>""")

    return "\n".join(blocks)


_FORM_CLASS_MAP = {
    "工具清单": "tools",
    "方法论":   "method",
    "教程步骤": "tutorial",
    "行业动态": "news",
    "观点洞察": "insight",
    "案例故事": "story",
}


def _form_class(form: str) -> str:
    """将内容形式映射为 CSS 类名"""
    return _FORM_CLASS_MAP.get(form, "default")


def _esc(s: str) -> str:
    """最小化 HTML 转义"""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
