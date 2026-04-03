"""
KnowledgeFlow 分类体系（受控词表）

设计原则：
- 分面分类法：领域 × 子领域 × 内容形式，三个维度正交独立
- 高频内容拆细，低频内容保持克制，避免“看起来完整，实际不好用”
- 关键词尽量全局唯一，减少模型在跨域场景下的犹豫
- boundary 用正向定义 + 例子，告诉模型“该放哪”，而不只是“别放哪”
"""

from typing import Optional


DOMAINS: dict[str, dict] = {
    "AI与大模型": {
        "subdomains": [
            "AI产品与插件评测",
            "Prompt工程与技巧",
            "AI辅助编程",
            "Agent核心架构",
            "Agent记忆与上下文",
            "Agent安全与权限",
            "多Agent协作",
            "模型与行业事件",
        ],
        "boundary": (
            "核心价值由 AI / 大模型能力驱动。例：用 AI 写代码、评测 AI 插件、设计 Agent 机制 → 这里；"
            "Python 语法、传统微服务架构本身 → 软件工程。"
        ),
    },
    "软件工程": {
        "subdomains": [
            "编程语言与框架",
            "系统架构设计",
            "工程规范与构建",
            "运维与基础设施",
            "数据存储与处理",
        ],
        "boundary": (
            "不依赖 AI 能力的传统软件技术。例：Python、React、数据库、CI/CD、监控告警 → 这里；"
            "Agent Loop、上下文压缩、工具调用权限 → AI与大模型。"
        ),
    },
    "产品与增长": {
        "subdomains": [
            "产品策略与规划",
            "用户体验与交互",
            "增长与数据运营",
        ],
        "boundary": (
            "关注产品从需求、体验到增长的全过程。例：路线图、功能优先级、A/B 测试、留存分析 → 这里；"
            "品牌传播、市场定位、商业模式 → 商业与创业。"
        ),
    },
    "商业与创业": {
        "subdomains": [
            "商业模式与战略",
            "创业实战复盘",
            "营销与品牌传播",
            "组织管理与协作",
        ],
        "boundary": (
            "关注商业运作、创业落地、组织协作。例：盈利模式、竞争战略、内容营销、个人品牌、团队管理 → 这里；"
            "产品留存和实验设计 → 产品与增长。"
        ),
    },
    "思维与方法": {
        "subdomains": [
            "思维模型与决策",
            "效率系统与工作流",
            "知识管理与学习法",
        ],
        "boundary": (
            "跨行业通用的思维方式和做事方法。例：第一性原理、GTD、PKM、学习法 → 这里；"
            "若方法只服务于某个具体 AI 系统设计，则归对应专业领域。"
        ),
    },
    "职业发展": {
        "subdomains": [
            "能力进阶与学习路径",
            "职场生存与软技能",
            "求职与职业规划",
        ],
        "boundary": "关注个人职业路径、能力提升、求职和职场协作。",
    },
    "投资理财": {
        "subdomains": [
            "投资策略与市场研判",
            "个人财务规划",
        ],
        "boundary": "关注投资判断、资产配置、保险税务等个人财务决策。",
    },
    "生活与成长": {
        "subdomains": [
            "健康与运动",
            "心理与认知提升",
            "阅读写作与表达",
            "兴趣与生活方式",
        ],
        "boundary": "关注工作之外的生活质量、精神成长与长期习惯。",
    },
}

CONTENT_FORMS: dict[str, str] = {
    "工具清单": "推荐一组工具、插件、资源或产品",
    "原理解析": "拆解一个已有系统、机制或方案为什么这样设计",
    "实践方法": "给出可复用的做事方法、流程或判断框架",
    "教程步骤": "手把手教操作步骤",
    "行业动态": "新闻事件、产品发布或行业趋势",
    "观点洞察": "表达判断、反思、认知翻转，不以步骤或系统拆解为主",
    "案例复盘": "围绕一个具体案例总结过程、得失和启发",
}


def format_taxonomy_for_prompt() -> str:
    """将分类体系格式化为 Prompt 注入文本。"""
    lines = []
    for domain, info in DOMAINS.items():
        subs = " | ".join(info["subdomains"])
        lines.append(f"  {domain} → {subs}")
        lines.append(f"    边界：{info['boundary']}")

    domain_text = "\n".join(lines)
    forms = " | ".join(f"{k}（{v}）" for k, v in CONTENT_FORMS.items())

    return (
        f"【领域 → 子领域】（必须从中选择）\n"
        f"{domain_text}\n"
        f"  其他 → （仅当以上领域都不合适时使用，dimension 写具体方向）\n\n"
        f"【内容形式】（必须从中选择一种）\n"
        f"  {forms}"
    )


def get_valid_domains() -> set[str]:
    """返回所有合法领域名。"""
    return set(DOMAINS.keys()) | {"其他"}


def get_valid_subdomains(topic: Optional[str] = None) -> set[str]:
    """返回某个领域下的合法子领域；不传 topic 时返回全集。"""
    if topic:
        info = DOMAINS.get(topic)
        return set(info["subdomains"]) if info else set()

    subdomains: set[str] = set()
    for info in DOMAINS.values():
        subdomains.update(info["subdomains"])
    return subdomains


def get_valid_forms() -> set[str]:
    """返回所有合法内容形式。"""
    return set(CONTENT_FORMS.keys())


def validate_classification(topic: str, dimension: str, content_form: str) -> Optional[str]:
    """校验分类是否合法；合法返回 None，否则返回错误信息。"""
    if topic not in get_valid_domains():
        return f"非法 topic：{topic}"

    if topic == "其他":
        if not (dimension or "").strip():
            return "topic 为“其他”时，dimension 不能为空"
    elif dimension not in get_valid_subdomains(topic):
        return f"非法 dimension：{topic} 下不存在 {dimension}"

    if content_form not in get_valid_forms():
        return f"非法 content_form：{content_form}"

    return None
