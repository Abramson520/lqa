# -*- coding: utf-8 -*-
"""LQA 类别体系与检查点。"""

CATEGORIES: dict[str, str] = {
    "TEXT_OVERFLOW": "文本溢出/截断",
    "LAYOUT": "UI 布局适配",
    "FONT": "字体字形异常",
    "ENCODING": "编码/乱码",
    "TERMINOLOGY": "术语一致性",
    "PUNCTUATION": "标点空格规范",
    "DATE_FORMAT": "日期数字格式",
    "CULTURAL": "文化合规",
    "PLACEHOLDER": "占位符/变量",
    "IMAGE_TEXT": "图内文字/硬编码",
    "VOICE_SUB": "语音字幕对齐",
    "RTL": "RTL 语言布局",
    "FONT_MISSING": "字体缺失回退",
    "LINE_BREAK": "换行断句",
    "OTHER": "其他",
}

CATEGORY_FOCUS: dict[str, str] = {
    "TEXT_OVERFLOW": "具体 UI 容器 + 截断/省略表现；德/俄等长文案优先",
    "LAYOUT": "控件相对位移/重叠，不得只写“布局错乱”",
    "FONT": "缺失字形或 tofu（□），写清具体字符",
    "ENCODING": "乱码形态（??? / mojibake）",
    "TERMINOLOGY": "同一概念两处不一致译法对照",
    "PUNCTUATION": "正确 vs 错误标点/空格对照",
    "DATE_FORMAT": "目标语言正确格式 vs 错误格式",
    "CULTURAL": "敏感元素与目标市场合规点（宗教/政治/军事/分级/禁忌/刻板印象等）",
    "PLACEHOLDER": "占位符原文 {xxx} 是否被替换",
    "IMAGE_TEXT": "图内/硬编码文案位置",
    "VOICE_SUB": "字幕与语音时长/内容错位",
    "RTL": "镜像方向、图标位置错误",
    "FONT_MISSING": "弱网/未装字体包回退表现",
    "LINE_BREAK": "错误断行断点（含日文禁则）",
    "OTHER": "模块、步骤与可观察预期",
}

#: 反向映射：中文标签 -> 英文 code（用于接受中文标签输入）
_LABEL_TO_CODE: dict[str, str] = {v: k for k, v in CATEGORIES.items()}


def resolve_category(text: object) -> str:
    """把任意类别输入归一化为规范 code；无法识别则保留用户原文。

    - 命中内置 code（大小写/空格不敏感）或中文标签 -> 返回内置 code
    - 否则保留用户原文（支持自定义类别，不再强制回退 OTHER）
    """
    raw = str(text or "").strip()
    if not raw:
        return "OTHER"
    cand = raw.upper().replace(" ", "_")
    if cand in CATEGORIES:
        return cand
    if raw in _LABEL_TO_CODE:
        return _LABEL_TO_CODE[raw]
    if raw.replace(" ", "") in _LABEL_TO_CODE:
        return _LABEL_TO_CODE[raw.replace(" ", "")]
    return raw


def category_label(code: object) -> str:
    """展示用：内置类别返回中文标签，自定义类别原样返回。"""
    key = str(code or "").strip()
    return CATEGORIES.get(key, key)

# AI 强制要求双语文案的类别（否则质量分扣重）
BILINGUAL_REQUIRED = {
    "TEXT_OVERFLOW",
    "TERMINOLOGY",
    "ENCODING",
    "PUNCTUATION",
    "DATE_FORMAT",
    "PLACEHOLDER",
    "FONT",
    "CULTURAL",
    "LINE_BREAK",
    "IMAGE_TEXT",
}

# 步骤必须落到具体 UI/文案，禁止空泛模板
STEP_QUALITY_HINTS = {
    "TEXT_OVERFLOW": "步骤必须点名控件（按钮/标题/Tab/Toast）与目标语言切换路径",
    "LAYOUT": "步骤必须写出对比对象（如商店页 vs 详情页）与观察点",
    "FONT": "步骤必须包含含特殊字符/变音符的界面位置",
    "ENCODING": "步骤必须进入含长文本的界面（公告/邮件/剧情）",
    "TERMINOLOGY": "步骤必须指出两处对照位置（主界面 vs 详情/技能说明）",
    "PUNCTUATION": "步骤必须对照数字/单位/标点出现处",
    "DATE_FORMAT": "步骤必须进入时间/倒计时/邮件时间戳界面",
    "CULTURAL": "步骤必须点名可能违规的视觉/文案元素",
    "PLACEHOLDER": "步骤必须触发变量替换场景（数量/玩家名/道具名）",
    "IMAGE_TEXT": "步骤必须指出硬编码/图内文案位置",
    "VOICE_SUB": "步骤必须播放语音并同步对照字幕",
    "RTL": "步骤必须切换 RTL 语言并观察镜像布局",
    "FONT_MISSING": "步骤需模拟字体包缺失或弱网首次加载",
    "LINE_BREAK": "步骤必须打开长文案详情/技能说明",
    "OTHER": "步骤必须可复现，写出路径与观察点",
}

# 规则打底时默认优先展开的类别（全量可选）
CORE_CATEGORIES = [
    "TEXT_OVERFLOW",
    "LAYOUT",
    "ENCODING",
    "TERMINOLOGY",
    "PLACEHOLDER",
    "LINE_BREAK",
    "DATE_FORMAT",
    "PUNCTUATION",
]

PRIORITIES = ("P0", "P1", "P2", "P3")
DEFAULT_STATUS = "待审"

CASE_FIELDS = [
    "module",
    "feature",
    "category",
    "priority",
    "source_lang",
    "target_lang",
    "source_text",
    "target_text",
    "preconditions",
    "steps",
    "expected",
    "notes",
]

# 内置高质量 few-shot（可被 case_library 覆盖增强）
BUILTIN_FEW_SHOT: list[dict] = [
    {
        "module": "商城",
        "feature": "限时礼包标题按钮文案溢出",
        "category": "TEXT_OVERFLOW",
        "priority": "P0",
        "source_lang": "en-US",
        "target_lang": "de-DE",
        "source_text": "Limited Offer",
        "target_text": "Zeitlich begrenztes Angebot",
        "preconditions": "客户端语言设置为 de-DE；账号可进入商城；礼包处于上架期",
        "steps": (
            "1. 启动游戏并将语言切换为 de-DE\n"
            "2. 主界面点击「商店/Shop」进入商城主页\n"
            "3. 定位限时礼包卡片顶部标题「Limited Offer」\n"
            "4. 观察标题是否完整显示、是否出现省略号/换行压到价格\n"
            "5. 进入礼包详情页，再观察购买按钮文案宽度\n"
            "6. 截图对比 en-US 与 de-DE 同一控件"
        ),
        "expected": (
            "de-DE 标题完整显示为「Zeitlich begrenztes Angebot」，无截断/省略号；"
            "价格与按钮不被挤出卡片；购买按钮可点击且文案不溢出边框"
        ),
        "notes": "德语长文案是商城按钮/标题的高发风险点",
    },
    {
        "module": "邮件",
        "feature": "补偿邮件数量占位符替换",
        "category": "PLACEHOLDER",
        "priority": "P0",
        "source_lang": "en-US",
        "target_lang": "de-DE",
        "source_text": "You received {amount} diamonds",
        "target_text": "Du hast {amount} Diamanten erhalten",
        "preconditions": "语言 de-DE；存在含 {amount} 的系统补偿邮件",
        "steps": (
            "1. 语言切换为 de-DE\n"
            "2. 打开邮件系统\n"
            "3. 打开系统补偿邮件正文\n"
            "4. 检查 {amount} 是否被替换为实际数值\n"
            "5. 领取附件后再查看领取成功提示\n"
            "6. 对照背包钻石增量是否与邮件数值一致"
        ),
        "expected": (
            "邮件正文与提示均显示实际数量（如 500），"
            "不出现字面量 {amount}/{AMOUNT}；数值与附件领取结果一致"
        ),
        "notes": "占位符未替换会直接导致资损类投诉",
    },
    {
        "module": "设置",
        "feature": "同一术语按钮与详情页不一致",
        "category": "TERMINOLOGY",
        "priority": "P1",
        "source_lang": "en-US",
        "target_lang": "ja-JP",
        "source_text": "Workspace / Workspace",
        "target_text": "ワークスペース / 作業領域",
        "preconditions": "语言 ja-JP；已登录；设置页与工作台入口均可用",
        "steps": (
            "1. 语言切换为 ja-JP\n"
            "2. 打开设置页，记录「Workspace」对应译文\n"
            "3. 返回主界面进入工作台/工作区入口\n"
            "4. 对照同一概念在按钮、标题、帮助文案中的译法\n"
            "5. 检索技能/邮件/公告中同源词\n"
            "6. 记录所有不一致译法并截图"
        ),
        "expected": (
            "同一概念全局仅使用一种日文译法（术语表值）；"
            "若出现「ワークスペース」与「作業領域」混用则判定失败"
        ),
        "notes": "术语不一致是 LQA 常见中等级缺陷，需对照术语表",
    },
]
