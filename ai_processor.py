import json
import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from taxonomy import format_taxonomy_for_prompt, validate_classification

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

# 动态注入分类体系到 Prompt
_TAXONOMY_TEXT = format_taxonomy_for_prompt()

EXTRACTION_SYSTEM_PROMPT = f"""你是用户最懂他的朋友，帮他把刷到的好文章"翻译"成自己的知识库笔记。

━━━ 核心任务 ━━━
把一篇文章拆分成 1～N 个"知识条目"，每个条目归入知识体系中一个精确的节点。

━━━ 何时拆分为多个条目 ━━━
✅ 文章讨论了明显不同的两件事（如：推荐工具 + 讲一个方法框架）
✅ 清单里有不同类型/用途的内容，可以按类别归类
✅ 内容跨越不同领域，分开存放更好找
❌ 不要为了拆而拆，紧密相关的内容放一个条目就好

━━━ 分类体系（受控词表，必须从中选择）━━━

{_TAXONOMY_TEXT}

━━━ 分类规则 ━━━
1. topic 和 dimension 必须严格从上方词表中选择原文，禁止自创近义词
2. 仅当所有领域都不合适时，topic 填"其他"，dimension 写简短的具体方向
3. 分类标准：一个月后想找回这条内容时脑中会浮现什么词？
4. 归类歧义时看核心价值驱动力，而非表面涉及的领域
   例：用 AI 写代码的工具 → AI与大模型 > AI辅助编程（核心是 AI 能力）
   例：Python 语法教程 → 软件工程 > 编程语言与框架（核心是语言本身）
5. content_form 描述内容的表达形式，与领域正交独立

━━━ 要点提炼规则 ━━━

写作风格（最重要）：
  · 像朋友推荐一样写，让人一眼就想看下去
  · 禁止书面腔："该工具具备……功能""本文介绍了……"这类的不要写
  · 每条读完让人觉得"哦，这个有用！"

【工具清单】原文有几条写几条，一条都不能少
  格式：「名称 — 用大白话说它帮你解决什么问题，为什么值得一试」
  好示例：「Cursor — 写代码时 AI 实时补全和改 bug，速度快到不像话」
  差示例：「Cursor — 一款具备AI辅助功能的代码编辑器」

【原理解析】拆清楚一个已有系统/机制为什么这样设计
  适用：架构设计、上下文压缩、权限模型、记忆机制
  好示例：「4级压缩不是为了省 token 本身，而是让真正重要的上下文别被新消息挤掉」

【实践方法】提炼 3-5 个可直接照着用的方法、流程或判断框架
  适用：怎么做、如何落地、应该遵循哪些原则
  好示例：「做 Agent 记忆时先区分短期上下文和长期知识库，别全塞进同一层」

【观点洞察】提炼 3-5 个判断、反思或认知翻转
  适用：作者在表达立场、判断、经验感受，而不是教步骤或拆系统
  好示例：「很多所谓 Agent 问题，本质不是模型不够强，而是上下文管理太乱」

【案例复盘】围绕一个具体案例，说明发生了什么、踩了什么坑、学到了什么
  适用：项目复盘、事故复盘、创业经历、具体实践案例

【产品拆解】围绕一个具体产品/框架做全面拆解
  适用：介绍一个新框架、拆解一个产品的核心功能和架构特点
  要求：标题必须包含产品名（如 DeerFlow、Claude Code）
  格式：功能点 — 用大白话说它干什么、为什么值得关注

【教程步骤】提炼关键步骤，写成"你去做"的语气

【行业动态】说清楚发生了什么、对你有什么影响

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
      "topic": "从领域词表中选（如 AI与大模型）",
      "dimension": "从子领域词表中选（如 AI辅助编程）",
      "content_form": "从内容形式中选（如 工具清单）",
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


def _validate_entries(entries: list[dict]) -> str | None:
    for idx, entry in enumerate(entries, start=1):
        topic = (entry.get("topic") or "").strip()
        dimension = (entry.get("dimension") or "").strip()
        content_form = (entry.get("content_form") or "").strip()
        error = validate_classification(topic, dimension, content_form)
        if error:
            return f"第 {idx} 个条目分类无效：{error}"
    return None


def _validate_extracted_payload(payload: dict) -> dict:
    entries = payload.get("entries")
    if not isinstance(entries, list) or not entries:
        return {"error": "AI 返回缺少 entries，无法保存"}

    error = _validate_entries(entries)
    if error:
        return {"error": error}
    return payload


def _validate_reclassified_payload(payload: dict) -> dict:
    topic = (payload.get("topic") or "").strip()
    dimension = (payload.get("dimension") or "").strip()
    content_form = (payload.get("content_form") or "").strip()
    error = validate_classification(topic, dimension, content_form)
    if error:
        return {"error": error}
    return {
        "topic": topic,
        "dimension": dimension,
        "content_form": content_form,
    }


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
        return _validate_extracted_payload(_parse_json_safely(raw))
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回格式异常，请重试。详情：{str(e)}"}
    except Exception as e:
        return {"error": f"AI 处理失败：{str(e)}"}


_RECLASSIFY_PROMPT = f"""你是知识分类专家。根据下方分类体系，为已有知识条目重新分配 topic、dimension、content_form。

{_TAXONOMY_TEXT}

分类规则：
1. topic 和 dimension 必须严格从词表中选择原文
2. 仅当所有领域都不合适时，topic 填"其他"
3. 看核心价值驱动力，而非表面涉及的领域
4. content_form 描述内容形式，与领域正交
5. 区分内容形式时，优先按下面标准判断：
   - 原理解析：在解释一个已有系统/机制为什么这样设计
   - 实践方法：在给一套可复用的方法、步骤或判断框架
   - 观点洞察：在表达判断、反思、认知翻转，不是教程也不是系统拆解
   - 案例复盘：在围绕一个具体案例总结过程、得失和启发

只返回 JSON，不要任何其他文字"""


def reclassify_entry(title: str, summary: str, key_points: list[str]) -> dict:
    """对已有条目重新分类（只改分类，不改内容）"""
    points_text = "\n".join(f"  · {p}" for p in key_points) if key_points else "（无要点）"
    user_msg = (
        f"标题：{title or '（无标题）'}\n"
        f"摘要：{summary or '（无摘要）'}\n"
        f"要点：\n{points_text}\n\n"
        f'返回 JSON：{{"topic": "...", "dimension": "...", "content_form": "..."}}'
    )
    try:
        raw = _chat(
            model=TEXT_MODEL,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _RECLASSIFY_PROMPT},
                {"role": "user", "content": user_msg},
            ],
        )
        return _validate_reclassified_payload(_parse_json_safely(raw))
    except Exception as e:
        return {"error": str(e)}


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
        return _validate_extracted_payload(_parse_json_safely(raw))
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回格式异常，请重试。详情：{str(e)}"}
    except Exception as e:
        return {"error": f"AI 处理失败：{str(e)}"}
