import trafilatura
import base64
import requests
from io import BytesIO
from PIL import Image

# 公众号等文章平台通常需要浏览器 UA，否则返回 403 或空内容
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def extract_from_url(url: str) -> dict:
    """
    从 URL 提取文章正文。
    支持公众号（mp.weixin.qq.com）及大多数静态文章页。
    返回 {"title": str, "text": str, "url": str} 或 {"error": str}
    """
    try:
        # trafilatura.fetch_url 不支持自定义 headers，改用 requests 先下载
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=True,      # 提高召回率，减少漏提取
        )

        metadata = trafilatura.extract_metadata(html)
        title = metadata.title if metadata and metadata.title else "未知标题"

        if not text or len(text) < 50:
            return {
                "error": (
                    "提取内容过短，可能是动态渲染页面（需登录或 JS 渲染）。"
                    "请改用「粘贴文字」方式，手动复制正文。"
                )
            }

        # 截断至 8000 字符，避免超出模型 token 限制
        return {"title": title, "text": text[:8000], "url": url}

    except requests.HTTPError as e:
        return {"error": f"HTTP 请求失败（{e.response.status_code}），该链接可能需要登录"}
    except Exception as e:
        return {"error": f"提取失败：{str(e)}"}


def image_to_base64(image_file) -> str:
    """
    将 Streamlit file_uploader 返回的图片文件转为 base64 字符串（JPEG 格式）。
    超过 1200px 宽度时等比缩放，以节省 token。
    """
    img = Image.open(image_file)

    max_width = 1200
    if img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)

    buffer = BytesIO()
    img.convert("RGB").save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
