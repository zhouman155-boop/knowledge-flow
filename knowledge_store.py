import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# Railway 部署时设置 DATA_DIR=/data（挂载持久磁盘）
DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
DB_PATH = os.path.join(DATA_DIR, "knowledge_base.db")

# ── v2 表结构 ────────────────────────────────────────────────────────
# kb_entries: 每篇文章 × 每个 topic/dimension 一行
# kb_points:  每个条目的要点，通过 entry_id 关联（CASCADE 删除）
_DDL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kb_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT    NOT NULL DEFAULT '',
    title       TEXT    NOT NULL DEFAULT '',
    platform    TEXT    NOT NULL DEFAULT '',
    summary     TEXT    NOT NULL DEFAULT '',
    topic       TEXT    NOT NULL,
    dimension   TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_points (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id    INTEGER NOT NULL REFERENCES kb_entries(id) ON DELETE CASCADE,
    point       TEXT    NOT NULL
);
"""


@contextmanager
def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_DDL)
    _migrate_v1(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _migrate_v1(conn: sqlite3.Connection):
    """
    将旧版 sources + points 表的数据迁移到 v2 表，只执行一次。
    迁移完成后旧表保留（只读备份），不再使用。
    """
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    if "sources" not in tables:
        return  # 没有旧数据，无需迁移

    already_migrated = conn.execute("SELECT COUNT(*) FROM kb_entries").fetchone()[0]
    if already_migrated > 0:
        return  # 已迁移，跳过

    old_sources = conn.execute(
        "SELECT topic, dimension, title, url, platform, summary, created_at FROM sources"
    ).fetchall()
    if not old_sources:
        return

    old_points = conn.execute("SELECT topic, dimension, point FROM points").fetchall()
    pts_by_td: dict = {}
    for p in old_points:
        key = (p["topic"], p["dimension"])
        pts_by_td.setdefault(key, []).append(p["point"])

    for s in old_sources:
        cursor = conn.execute(
            "INSERT INTO kb_entries (url, title, platform, summary, topic, dimension, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (s["url"], s["title"], s["platform"], s["summary"],
             s["topic"], s["dimension"], s["created_at"]),
        )
        entry_id = cursor.lastrowid
        td_key = (s["topic"], s["dimension"])
        for point in pts_by_td.pop(td_key, []):
            conn.execute(
                "INSERT INTO kb_points (entry_id, point) VALUES (?, ?)",
                (entry_id, point),
            )
    conn.commit()


def _to_entries_list(extracted: dict) -> list[dict]:
    """统一将 AI 返回的新/旧格式都转换为 entries 列表。"""
    if "entries" in extracted:
        return extracted["entries"]
    # 兼容旧格式（单条 topic/dimension）
    return [{
        "topic": extracted.get("topic", "未分类"),
        "dimension": extracted.get("dimension", "通用"),
        "key_points": extracted.get("key_points", []),
    }]


def add_knowledge(extracted: dict, source_info: dict) -> dict:
    """
    保存 AI 提取结果到知识库。
    支持新格式（含 entries 数组）和旧格式（单条）。
    同一 URL 重复提交时，自动覆盖旧数据。
    """
    url = (source_info.get("url") or "").strip()
    title = source_info.get("title") or "未知标题"
    platform = source_info.get("platform") or ""
    summary = extracted.get("summary") or ""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    entries = _to_entries_list(extracted)

    with _conn() as conn:
        is_update = False
        if url:
            old = conn.execute(
                "SELECT COUNT(*) FROM kb_entries WHERE url = ?", (url,)
            ).fetchone()[0]
            if old > 0:
                # 删除旧条目（kb_points 通过 CASCADE 一起删）
                conn.execute("DELETE FROM kb_entries WHERE url = ?", (url,))
                is_update = True

        for entry in entries:
            topic = entry.get("topic") or "未分类"
            dimension = entry.get("dimension") or "通用"
            key_points = entry.get("key_points") or []

            cursor = conn.execute(
                "INSERT INTO kb_entries (url, title, platform, summary, topic, dimension, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (url, title, platform, summary, topic, dimension, now),
            )
            entry_id = cursor.lastrowid
            for point in key_points:
                conn.execute(
                    "INSERT INTO kb_points (entry_id, point) VALUES (?, ?)",
                    (entry_id, point),
                )

    total_pts = sum(len(e.get("key_points") or []) for e in entries)
    n = len(entries)

    if is_update:
        msg = f"🔄 已更新「{title[:20]}」，重新分入 {n} 个主题"
    elif n == 1:
        t, d = entries[0].get("topic", ""), entries[0].get("dimension", "")
        msg = f"✨ 已保存到「{t} › {d}」"
    else:
        topics_str = "、".join(
            f"{e.get('topic','')}" for e in entries[:3]
        ) + ("…" if n > 3 else "")
        msg = f"✨ 已按 {n} 个主题分类保存：{topics_str}"

    return {
        "message": msg,
        "entries": entries,
        "summary": summary,
        "is_update": is_update,
        "total_points": total_pts,
    }


def get_all() -> dict:
    """返回完整知识树，结构：topics → dimensions → {points, sources}"""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT
                e.id, e.topic, e.dimension,
                e.url, e.title, e.summary, e.created_at,
                p.point
            FROM kb_entries e
            LEFT JOIN kb_points p ON p.entry_id = e.id
            ORDER BY e.topic, e.dimension, e.created_at, p.id
        """).fetchall()

        total_items = conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(url,''), CAST(id AS TEXT))) FROM kb_entries"
        ).fetchone()[0]

    topics: dict = {}
    entry_seen: set = set()

    for row in rows:
        t, d, eid = row["topic"], row["dimension"], row["id"]
        topics.setdefault(t, {"dimensions": {}})
        topics[t]["dimensions"].setdefault(d, {"points": [], "sources": []})

        if row["point"] and row["point"] not in topics[t]["dimensions"][d]["points"]:
            topics[t]["dimensions"][d]["points"].append(row["point"])

        if eid not in entry_seen:
            entry_seen.add(eid)
            topics[t]["dimensions"][d]["sources"].append({
                "title": row["title"],
                "url": row["url"] or "",
                "summary": row["summary"] or "",
                "date": (row["created_at"] or "")[:10],
            })

    return {
        "topics": topics,
        "total_items": total_items,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_stats() -> dict:
    with _conn() as conn:
        total_items = conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(url,''), CAST(id AS TEXT))) FROM kb_entries"
        ).fetchone()[0]
        total_topics = conn.execute(
            "SELECT COUNT(DISTINCT topic) FROM kb_entries"
        ).fetchone()[0]
        total_dims = conn.execute(
            "SELECT COUNT(DISTINCT topic || '|' || dimension) FROM kb_entries"
        ).fetchone()[0]
        total_points = conn.execute("SELECT COUNT(*) FROM kb_points").fetchone()[0]

    return {
        "total_items": total_items,
        "total_topics": total_topics,
        "total_dimensions": total_dims,
        "total_points": total_points,
    }
