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
TEXT_MODEL = "deepseek-chat"       # DeepSeek-V3，用于文字提取
VISION_MODEL = "deepseek-chat"     # DeepSeek-V3 支持图片输入

# 通义千问（有免费额度）：取消下面注释并注释上方5行
# PROVIDER = "qwen"
# API_KEY_ENV = "DASHSCOPE_API_KEY"
# BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# TEXT_MODEL = "qwen-plus"
# VISION_MODEL = "qwen-vl-plus"

# Claude（原始配置，需能访问 api.anthropic.com）：
# PROVIDER = "claude"
# API_KEY_ENV = "ANTHROPIC_API_KEY"
# BASE_URL = "https://api.anthropic.com/v1"
# TEXT_MODEL = "claude-sonnet-4-5"
# VISION_MODEL = "claude-sonnet-4-5"
# ──────────────────────────────────────────────────────────────────

client = OpenAI(api_key=os.getenv(API_KEY_ENV), base_url=BASE_URL)

EXTRACTION_SYSTEM_PROMPT = """你是一个知识提取专家。你的任务是从用户提供的内容中提取结构化知识，
帮助用户构建个人知识框架。

【主题分类原则】
- 主题必须是高度概括的大类，如：产品思维、AI技术、市场营销、个人成长、编程开发、健康健身、投资理财、设计创作
- 不要把具体内容作为主题名（比如不要写"ChatGPT使用技巧"，应该写"AI技术"）
- 同一个大方向的内容应归入同一主题

【维度分类原则】
- 维度是主题下的二级分类，比"主题"具体，比"要点"宽泛
- 例：主题=产品思维，维度=用户研究；主题=AI技术，维度=提示词工程
- 维度应该能容纳多篇文章的内容

【要点提取原则】
- 提取 3-5 个真正有用的知识点，不是摘要
- 每个要点是一个独立的、可复用的知识/方法/结论
- 用简洁的一句话表达，15-30字为佳

只返回 JSON，不要有任何其他文字、解释或代码块标记。"""

EXTRACTION_USER_PROMPT = """请分析以下内容，返回结构化知识提取结果：

{content}

返回格式：
{{
  "topic": "一级主题",
  "dimension": "二级维度",
  "key_points": ["要点1", "要点2", "要点3"],
  "summary": "一句话概括这篇内容的核心价值（20字以内）",
  "content_type": "article 或 post 或 video_transcript"
}}"""


def _parse_json_safely(raw: str) -> dict:
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
    return json.loads(raw)


def _chat(model: str, messages: list, max_tokens: int = 1000) -> str:
    """统一的 OpenAI 兼容调用入口"""
    response = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.choices[0].message.content


def extract_from_text(text: str, title: str = "") -> dict:
    """从文字内容中提取结构化知识（公众号文章正文 / 粘贴文字）"""
    content = f"标题：{title}\n\n正文：{text}" if title else text
    try:
        raw = _chat(
            model=TEXT_MODEL,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": EXTRACTION_USER_PROMPT.format(content=content[:6000])},
            ],
        )
        return _parse_json_safely(raw)
    except json.JSONDecodeError as e:
        return {"error": f"AI 返回格式异常，请重试。详情：{str(e)}"}
    except Exception as e:
        return {"error": f"AI 处理失败：{str(e)}"}


def extract_from_image(image_base64: str) -> dict:
    """从图片（小红书截图）中提取结构化知识（Vision 模型）"""
    try:
        raw = _chat(
            model=VISION_MODEL,
            max_tokens=1500,
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
                                "这是一张截图。请先阅读图片中的所有文字内容，"
                                "然后按照要求提取结构化知识。\n\n"
                                + EXTRACTION_USER_PROMPT.format(content="（见上方图片）")
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
