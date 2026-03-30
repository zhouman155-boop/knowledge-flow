def kb_to_markdown(kb: dict) -> str:
    """将知识库转为 Markdown 层级结构（供 markmap 渲染）"""
    lines = ["# 我的知识框架"]
    for topic, topic_data in kb.get("topics", {}).items():
        lines.append(f"\n## {topic}")
        for dim, dim_data in topic_data.get("dimensions", {}).items():
            lines.append(f"\n### {dim}")
            for point in dim_data.get("points", []):
                lines.append(f"\n- {point}")
    return "\n".join(lines)


def kb_to_text_outline(kb: dict) -> str:
    """将知识库转为文字大纲（文字视图展示）"""
    topics = kb.get("topics", {})
    if not topics:
        return "暂无内容，添加第一篇文章开始构建你的知识框架。"

    lines = []
    for topic, topic_data in topics.items():
        lines.append(f"## 📚 {topic}")
        for dim, dim_data in topic_data.get("dimensions", {}).items():
            points = dim_data.get("points", [])
            sources = dim_data.get("sources", [])
            lines.append(f"\n**{dim}** （{len(sources)} 篇来源，{len(points)} 个要点）")
            for i, point in enumerate(points, 1):
                lines.append(f"  {i}. {point}")
        lines.append("")
    return "\n".join(lines)


def render_mindmap_html(markdown_content: str) -> str:
    """
    生成内嵌 markmap 的完整 HTML，供 Streamlit components.html() 渲染。

    注意：使用固定版本 CDN 避免 markmap-lib 与 markmap-view 共用
    window.markmap 命名空间导致的属性覆盖问题（坑点：两者都写 window.markmap，
    后加载的会覆盖先加载的导出，需保证 markmap-lib 在 markmap-view 之后加载）。
    """
    # 转义反引号和 $ 防止 JS 模板字符串语法冲突
    escaped = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ margin: 0; overflow: hidden; background: transparent; }}
  #mindmap {{ width: 100%; height: 520px; }}
  .markmap-node text {{
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  }}
</style>
</head>
<body>
<div id="mindmap"></div>
<!-- 加载顺序：d3 → markmap-view → markmap-lib（不可颠倒）-->
<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markmap-view@0.15.4/dist/browser/index.js"></script>
<script src="https://cdn.jsdelivr.net/npm/markmap-lib@0.15.4/dist/browser/index.js"></script>
<script>
(async () => {{
  const {{ Transformer }} = window.markmap;
  const {{ Markmap }} = window.markmap;
  const transformer = new Transformer();
  const md = `{escaped}`;
  const {{ root }} = transformer.transform(md);
  const mm = Markmap.create('#mindmap', {{
    maxWidth: 300,
    color: (node) => {{
      const colors = ['#7F77DD', '#1D9E75', '#D85A30', '#378ADD', '#BA7517'];
      return colors[node.depth % colors.length];
    }}
  }}, root);
  mm.fit();
}})();
</script>
</body>
</html>"""
