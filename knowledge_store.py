import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# Railway 部署时设置 DATA_DIR=/data（挂载持久磁盘）
# 本地运行时默认使用项目内 data/ 目录
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DB_PATH = os.path.join(DATA_DIR, "knowledge_base.db")

_DDL = """
CREATE TABLE IF NOT EXISTS points (
    topic     TEXT NOT NULL,
    dimension TEXT NOT NULL,
    point     TEXT NOT NULL,
    PRIMARY KEY (topic, dimension, point)
);

CREATE TABLE IF NOT EXISTS sources (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    topic     TEXT NOT NULL,
    dimension TEXT NOT NULL,
    title     TEXT DEFAULT '',
    url       TEXT DEFAULT '',
    platform  TEXT DEFAULT '',
    summary   TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
"""


def _init():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_DDL)
    conn.commit()
    return conn


@contextmanager
def _conn():
    conn = _init()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_knowledge(extracted: dict, source_info: dict) -> dict:
    """
    将 AI 提取结果合并进知识库。
    接口与原 JSON 版本完全兼容。
    """
    topic = extracted.get("topic", "未分类")
    dimension = extracted.get("dimension", "通用")
    key_points = extracted.get("key_points", [])
    summary = extracted.get("summary", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    with _conn() as conn:
        existing_topics = {r[0] for r in conn.execute("SELECT DISTINCT topic FROM points")}
        existing_dims = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT dimension FROM points WHERE topic=?", (topic,)
            )
        }

        # 写入来源记录
        conn.execute(
            "INSERT INTO sources (topic, dimension, title, url, platform, summary, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                topic, dimension,
                source_info.get("title", ""),
                source_info.get("url", ""),
                source_info.get("platform", ""),
                summary, now,
            ),
        )

        # 合并要点（IGNORE 处理去重）
        new_points = []
        for point in key_points:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO points (topic, dimension, point) VALUES (?, ?, ?)",
                (topic, dimension, point),
            )
            if cursor.rowcount:
                new_points.append(point)

    if topic not in existing_topics:
        action = "created_topic"
        msg = f"✨ 新建主题「{topic}」并添加维度「{dimension}」"
    elif dimension not in existing_dims:
        action = "created_dimension"
        msg = f"📂 在「{topic}」下新建维度「{dimension}」"
    else:
        action = "merged"
        msg = f"🔗 已合并到「{topic} → {dimension}」，新增 {len(new_points)} 个要点"

    return {
        "action": action,
        "message": msg,
        "topic": topic,
        "dimension": dimension,
        "new_points_count": len(new_points),
    }


def get_all() -> dict:
    """
    返回与原 JSON 版本相同结构的 dict，
    确保 mindmap_renderer.py 和 app.py 无需修改。
    """
    with _conn() as conn:
        points_rows = conn.execute(
            "SELECT topic, dimension, point FROM points ORDER BY topic, dimension"
        ).fetchall()
        sources_rows = conn.execute(
            "SELECT topic, dimension, title, url, platform, summary, created_at"
            " FROM sources ORDER BY created_at"
        ).fetchall()
        total_items = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

    topics: dict = {}

    for row in points_rows:
        t, d, p = row["topic"], row["dimension"], row["point"]
        topics.setdefault(t, {"dimensions": {}})
        topics[t]["dimensions"].setdefault(d, {"points": [], "sources": []})
        topics[t]["dimensions"][d]["points"].append(p)

    for row in sources_rows:
        t, d = row["topic"], row["dimension"]
        topics.setdefault(t, {"dimensions": {}})
        topics[t]["dimensions"].setdefault(d, {"points": [], "sources": []})
        topics[t]["dimensions"][d]["sources"].append({
            "title": row["title"],
            "url": row["url"],
            "platform": row["platform"],
            "summary": row["summary"],
            "date": row["created_at"][:10],
        })

    return {
        "topics": topics,
        "total_items": total_items,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_stats() -> dict:
    with _conn() as conn:
        total_items = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        total_topics = conn.execute("SELECT COUNT(DISTINCT topic) FROM points").fetchone()[0]
        total_dims = conn.execute(
            "SELECT COUNT(DISTINCT topic || '|' || dimension) FROM points"
        ).fetchone()[0]
        total_points = conn.execute("SELECT COUNT(*) FROM points").fetchone()[0]

    return {
        "total_items": total_items,
        "total_topics": total_topics,
        "total_dimensions": total_dims,
        "total_points": total_points,
    }
