import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── 切换模型供应商，改这里即可 ─────────────────────────────────────
# DeepSeek（推荐，性价比高）：
PROVIDER = "deepseek"
API_KEY_ENV = "DEEPSEEK_API_KEY"
BASE_URL = "https://api.deepseek.com"
TEXT_MODEL = "deepseek-chat"       # DeepSeek-V3
VISION_MODEL = "deepseek-chat"

# 通义千问（有免费额度）：
# PROVIDER = "qwen"
# API_KEY_ENV = "DASHSCOPE_API_KEY"
# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# TEXT_MODEL = "qwen-plus"
# VISION_MODEL = "qwen-vl-plus"

# Claude：
# PROVIDER = "claude"
# API_KEY_ENV = "ANTHROPIC_API_KEY"
# BASE_URL = "https://api.anthropic.com/v1"
# TEXT_MODEL = "claude-sonnet-4-5"
# VISION_MODEL = "claude-sonnet-4-5"
# ──────────────────────────────────────────────────────────────────

client = OpenAI(api_key=os.getenv(API_KEY_ENV), base_url=BASE_URL)

EXTRACTION_SYSTEM_PROMPT = """你是用户最懂他的朋友，帮他把刷到的好文章"翻译"成自己的知识库笔记。

━━━ 核心任务 ━━━
把一篇文章拆分成 1～N 个"知识条目"，每个条目对应一个独立的主题+维度。
当文章涉及多个不同主题时，必须拆成多个条目，分别存入知识树的不同节点。

━━━ 何时拆分为多个条目 ━━━
✅ 文章讨论了明显不同的两件事（如：推荐工具 + 分享方法论）
✅ 清单里有不同类型/用途的内容，可以按类别归类
✅ 内容针对不同场景或人群，分开存放更好找
❌ 不要为了拆而拆，紧密相关的内容放一个条目就好

━━━ 分类规则（以"方便找回"为标准）━━━
- topic（主题）：用户一个月后想找这条内容，会先想到什么大方向？
  例如：AI工具、提示词工程、创业方法、健身计划
- dimension（维度）：这批内容的具体用途是什么？
  例如：编程助手推荐、结构化写法、早期验证、增肌食谱
- 同类内容归入相同 topic，知识越积累越聚合

━━━ 要点提炼规则 ━━━

写作风格（最重要）：
  · 像朋友推荐一样写，让人一眼就想看下去
  · 禁止书面腔："该工具具备……功能""本文介绍了……"这类的不要写
  · 每条读完让人觉得"哦，这个有用！"

【list 清单类】原文有几条写几条，一条都不能少
  格式：「名称 — 用大白话说它帮你解决什么问题，为什么值得一试」
  好示例：「Cursor — 写代码时 AI 实时补全和改 bug，速度快到不像话」
  差示例：「Cursor — 一款具备AI辅助功能的代码编辑器」

【insight 观点类】提炼 3-5 个让你觉得"说得对！"的结论
  好示例：「别把时间花在"看起来忙"上，只盯着能出结果的事做」
  差示例：「应采用结果导向型工作方式替代任务导向型工作模式」

【tutorial 教程类】提炼关键步骤，写成"你去做"的语气

【news 资讯类】说清楚发生了什么、对你有什么影响

━━━ summary 写法 ━━━
一句口语化的话说清楚"这篇对你有什么用"，20字以内。
好示例：「收藏这篇，几个工具装上去效率翻倍」
差示例：「本文介绍了多种提升工作效率的AI工具」

━━━ 输出要求 ━━━
只返回 JSON，不要任何其他文字"""

EXTRACTION_USER_PROMPT = """请分析下面的文章，提取知识并按主题拆分为多个条目：

标题：{title}
链接：{url}

正文：
{content}

返回 JSON（entries 可以有多个，文章涉及多个主题时必须拆分）：
{{
  "summary": "一句口语化总结（20字以内）",
  "entries": [
    {{
      "topic": "主题（大方向，方便一个月后找到）",
      "dimension": "维度（具体用途或类别）",
      "key_points": ["要点1", "要点2", ...]
    }}
  ]
}}"""


def _parse_json_safely(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)


def _chat(model: str, messages: list, max_tokens: int = 1000) -> str:
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.choices[0].message.content


def extract_from_text(text: str, title: str = "", url: str = "") -> dict:
    """从文字内容中提取结构化知识，支持拆分为多个主题条目"""
    try:
        raw = _chat(
            model=TEXT_MODEL,
            max_tokens=2500,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": EXTRACTION_USER_PROMPT.format(
                    title=title or "（无标题）",
                    url=url or "（无链接）",
                    content=text[:8000],
                )},
            ],
        )
        return _parse_json_safely(raw)
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回格式异常，请重试。详情：{str(e)}"}
    except Exception as e:
        return {"error": f"AI 处理失败：{str(e)}"}


def extract_from_image(image_base64: str) -> dict:
    """从图片（小红书截图）中提取结构化知识"""
    try:
        raw = _chat(
            model=VISION_MODEL,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                "这是一张截图，请先完整阅读图片中的所有文字，"
                                "然后按照要求提取结构化知识。\n\n"
                                + EXTRACTION_USER_PROMPT.format(
                                    title="（图片内容）",
                                    url="（截图，无链接）",
                                    content="（见上方图片，请完整提取所有条目）",
                                )
                            ),
                        },
                    ],
                },
            ],
        )
        return _parse_json_safely(raw)
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回格式异常，请重试。详情：{str(e)}"}
    except Exception as e:
        return {"error": f"AI 处理失败：{str(e)}"}
