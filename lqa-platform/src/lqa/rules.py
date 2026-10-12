# -*- coding: utf-8 -*-
"""规则打底：无 Key 也能出可执行 LQA 骨架用例。"""
from __future__ import annotations

import re

from .analysis import AnalysisResult, RequirementPoint
from .categories import (
    CATEGORIES,
    CORE_CATEGORIES,
    DEFAULT_STATUS,
)
from .quality import score_case


def _short(text: str, n: int = 48) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _feature_for(text: str, category: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"^【|】$", "", t)
    t = re.sub(r"^\d+[\.、)]\s*", "", t)
    # 截取核心对象，避免整句需求塞进 feature
    core = t
    for sep in ("展示", "显示", "需要", "要求", "进行", "支持"):
        if sep in t:
            core = t.split(sep)[0]
            break
    core = core.strip("，。；; ")
    if len(core) < 4:
        core = t[:24]
    suffix = {
        "TEXT_OVERFLOW": "溢出",
        "LAYOUT": "布局",
        "FONT": "字形",
        "ENCODING": "乱码",
        "TERMINOLOGY": "术语一致",
        "PUNCTUATION": "标点",
        "DATE_FORMAT": "日期格式",
        "CULTURAL": "文化合规",
        "PLACEHOLDER": "占位符",
        "IMAGE_TEXT": "图内文案",
        "VOICE_SUB": "语音字幕",
        "RTL": "RTL布局",
        "FONT_MISSING": "字体回退",
        "LINE_BREAK": "换行",
        "OTHER": "符合性",
    }.get(category, "检查")
    feat = f"{core[:28]}·{suffix}"
    return feat[:80]


def _priority_for(category: str, text: str) -> str:
    """优先级按需求重要度分级，而非按类别一刀切，避免整表全 P0。

    - P0：资损/账号类功能流（领取/充值/购买/支付/登录/删除/重置/兑换/下单）或合规敏感
    - P1：术语一致、编码乱码、占位符替换（可能资损但先看需求内容）
    - P2：纯展示/排版类（溢出/布局/字体/换行/标点/日期/图内/RTL/语音等）
    """
    if re.search(r"登录|支付|充值|购买|删除|重置|领取|交易|账号|兑换|下单", text):
        return "P0"
    if re.search(r"宗教|政治|军事|分级|禁忌|审查|赌博|博彩|烟酒|未成年|色情|暴力", text):
        return "P0"
    base = {
        "CULTURAL": "P1",
        "TERMINOLOGY": "P1",
        "ENCODING": "P1",
        "PLACEHOLDER": "P1",
        "TEXT_OVERFLOW": "P2",
        "LAYOUT": "P2",
        "FONT": "P2",
        "FONT_MISSING": "P2",
        "LINE_BREAK": "P2",
        "PUNCTUATION": "P2",
        "DATE_FORMAT": "P2",
        "IMAGE_TEXT": "P2",
        "VOICE_SUB": "P2",
        "RTL": "P2",
        "OTHER": "P2",
    }
    return base.get(category, "P2")


def _extract_samples(text: str) -> tuple[str, str]:
    """从需求点里尽量抽出源/目标文案样例。"""
    src = ""
    tgt = ""
    # 优先完整抓取 {var} 占位符（含花括号），避免被下方拉丁 token 正则截成 "amount}"
    ph = re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", text)
    if ph:
        src = ph.group(0)
    if not src:
        m = re.search(r"[\"“']([^\"”']{3,80})[\"”']", text)
        if m:
            src = m.group(1)
    if not src:
        # 拉丁 token 字符类刻意排除 '}'，防止吞掉占位符右花括号
        m2 = re.findall(r"[A-Za-z][A-Za-z0-9 _'.\-]{2,60}", text)
        if m2:
            src = m2[0].strip()
    return src, tgt


def _pick_categories(text: str, selected: list[str]) -> list[str]:
    pool = list(selected) if selected else list(CORE_CATEGORIES)
    hits: list[str] = []
    # 注：TERMINOLOGY 置于 TEXT_OVERFLOW 之前，且 TEXT_OVERFLOW 信号已移除"文案"，
    # 避免"文案一致/术语"类需求被贪婪归到文本溢出。
    signals = [
        ("TERMINOLOGY", r"属性|装备|技能名|货币|道具名|词条|工作区|workspace|译文一致|同一概念|多译|帮助中心|一致|术语"),
        ("TEXT_OVERFLOW", r"标题|标签|文本|展示|显示|溢出|截断|省略|礼包标题|价格|置灰并显示|按钮文字|按钮文案"),
        ("LAYOUT", r"布局|错位|重叠|排列|弹窗尺寸|控件位置|卡片位置|适配"),
        ("PLACEHOLDER", r"变量|占位|\{[a-zA-Z_]|数量替换|参数填充|received\s*\{"),
        ("ENCODING", r"公告|邮件正文|剧情|字幕|聊天|乱码|编码"),
        ("DATE_FORMAT", r"时间戳|日期格式|倒计时|有效期|刷新时间"),
        ("LINE_BREAK", r"描述文案|说明文案|对白|长文案|技能说明|断行|换行"),
        ("PUNCTUATION", r"数字单位|标点|空格规范|百分号|×"),
        ("CULTURAL", r"宗教|敏感|节日|国旗|手势|文化合规|政治|地图|军事|烟酒|赌博|博彩|未成年|隐私|数据|暴力|色情|性别|种族|禁忌|审查|分级"),
        ("FONT", r"字体|变音|特殊符号|umlaut|字形"),
        ("IMAGE_TEXT", r"硬编码|图内|图片文字|贴图"),
        ("VOICE_SUB", r"语音|配音|字幕对齐"),
        ("RTL", r"RTL|阿拉伯|希伯来|镜像"),
        ("FONT_MISSING", r"缺字|豆腐|字体包|回退"),
    ]
    fallback = [
        ("TEXT_OVERFLOW", r"按钮|标题|文案|显示|文字"),
        ("LAYOUT", r"界面|弹窗|面板|主界面|详情页"),
        ("OTHER", r"状态|变更|置灰|领取|清理|提示"),
    ]

    for cat, pat in signals:
        if cat in pool and re.search(pat, text, re.I):
            if cat not in hits:
                hits.append(cat)
    if not hits:
        for cat, pat in fallback:
            if cat in pool and re.search(pat, text, re.I):
                if cat not in hits:
                    hits.append(cat)
                if len(hits) >= 2:
                    break
    if not hits:
        for c in ("TEXT_OVERFLOW", "LAYOUT", "OTHER"):
            if c in pool or not selected:
                if c in CATEGORIES and c not in hits:
                    hits.append(c)
                    break
    out: list[str] = []
    for h in hits:
        if h not in out and (h in pool or not selected):
            out.append(h)
    # 用户自定义类别（非内置）始终纳入，至少生成 1 条对应用例
    for c in selected:
        if c not in CATEGORIES and c not in out:
            out.append(c)
            if len(out) >= 3:
                break
    return out[:3]


_SUBJECT_CUT = re.compile(
    r"(需|应|要|须|展示|显示|支持|包含|含|替换|一致|正确|完整|对齐|避免|不被|在|与|为|"
    r"，|,|。|\.|；|;|：|:|（|\(|【|\[)"
)


def _subject_for(text: str) -> str:
    """从需求点抽出被测的具体界面对象（功能主体），让步骤对功能而非模块。"""
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"^【|】$", "", t)
    m = _SUBJECT_CUT.search(t)
    subj = t[: m.start()].strip("，。、 （(【[") if m else t[:16]
    subj = re.sub(r"^【|】$", "", subj)
    if len(subj) < 2:
        subj = t[:16]
    return subj[:24]


def _steps_for(point: RequirementPoint, category: str, source_lang: str, target_lang: str) -> str:
    m = point.module or "相关"
    subj = _subject_for(point.text)
    lang = target_lang or "目标语言"
    # 步骤直接对「功能/被测对象」下指令：不写模块级通用套话、不回声需求句。
    # 语言设置等前置已写入「前置条件」列（见 _preconditions），此处不再重复。
    action = {
        "TEXT_OVERFLOW": f"进入「{m}」，定位「{subj}」，检查其在 {lang} 下是否完整展示、有无截断/溢出或挤出相邻控件",
        "LAYOUT": f"进入「{m}」，定位「{subj}」，检查控件位置、间距、层级有无错位或重叠",
        "PLACEHOLDER": f"进入「{m}」，定位「{subj}」，检查占位符是否被实际数值/名称替换，无字面量残留",
        "ENCODING": f"进入「{m}」，定位「{subj}」长文本，检查 {lang} 下是否乱码/编码异常",
        "TERMINOLOGY": f"进入「{m}」，定位「{subj}」，对比入口与详情页同一概念译文是否一致",
        "DATE_FORMAT": f"进入「{m}」，定位「{subj}」，检查时间戳/倒计时/有效期格式是否符合 {lang} 习惯",
        "LINE_BREAK": f"进入「{m}」，定位「{subj}」长文案，检查断行是否自然、无孤字/半词换行",
        "PUNCTUATION": f"进入「{m}」，定位「{subj}」，检查数字、单位、标点与空格是否符合 {lang} 规范",
        "CULTURAL": f"进入「{m}」，定位「{subj}」，检查视觉与文案是否含目标市场敏感/违规元素",
        "FONT": f"进入「{m}」，定位「{subj}」，检查含特殊字符/变音符的文案渲染是否异常",
        "IMAGE_TEXT": f"进入「{m}」，定位「{subj}」图内/硬编码文案，确认已本地化或可配置替换",
        "VOICE_SUB": f"进入「{m}」，定位「{subj}」，播放语音并对照字幕内容与时长",
        "RTL": f"进入「{m}」，定位「{subj}」，检查布局镜像、图标与文本阅读方向是否正确（{lang} 为 RTL 时）",
        "FONT_MISSING": f"进入「{m}」，定位「{subj}」，临时移除字体包后检查回退是否可读、无空白控件",
        "OTHER": f"进入「{m}」，定位「{subj}」并按需求描述验证界面表现",
    }.get(category, f"进入「{m}」，定位「{subj}」并验证相关本地化表现")
    # 末步（判定/取证）：随类别给出专属动作。此前所有用例共用同一句
    # 「记录实际文案/布局并截图，作为判定依据」，导致末句 100% 重复步骤形式成立
    # 但内容未随类别变化，等于没有真正说明「怎么判、留什么证」。
    verify = {
        "TEXT_OVERFLOW": f"改用 {lang} 下最长的可用文案复看同一处，截图留存有无截断/省略号或压盖相邻控件",
        "LAYOUT": "在最小与最大窗口（或横竖屏）下复看整体布局，截图留存错位/重叠的具体位置",
        "PLACEHOLDER": "用不同数量/名称触发一次真实展示，核对替换结果无裸露变量名，并截图留存",
        "ENCODING": "复看含特殊字符与长段落的部分，确认无问号/豆腐块后截图留存",
        "TERMINOLOGY": "跳转到同一概念的次级页面复看译法，逐处比对无混用后截图留存",
        "DATE_FORMAT": "对照目标市场的日期/时间显示样例逐项核对，截图留存不符合习惯之处",
        "LINE_BREAK": "在最窄宽度下复看换行位置，确认无孤字/错断后截图留存",
        "PUNCTUATION": f"对照 {lang} 标点与空格规范逐符号核对，截图留存不符之处",
        "CULTURAL": "对照目标市场合规清单逐项核对视觉与文案，截图留存风险点",
        "FONT": "专挑含变音符/特殊符号的字符复看字形，确认无缺字后截图留存",
        "IMAGE_TEXT": "拉取资源包原图与运行界面逐张比对，截图留存未本地化之处",
        "VOICE_SUB": "完整播放一遍并对照字幕时间轴，截图留存错句/超时的时间点",
        "RTL": f"在 {lang} 下复看整屏镜像效果，截图留存方向未翻转的元素",
        "FONT_MISSING": "逐一移除可用字体后复看回退表现，截图留存空白或方框处",
        "OTHER": "复现上述场景，逐项核对界面表现并截图留存实际结果",
    }.get(category, "复现上述场景，逐项核对界面表现并截图留存实际结果")
    return (
        f"1. {action}\n"
        f"2. {verify}"
    )


def _expected_for(category: str, target_lang: str, point: RequirementPoint, samples: tuple[str, str]) -> str:
    lang = target_lang or "目标语言"
    src, _tgt = samples
    detail = _short(point.text, 28)
    detail = re.sub(r"^【|】$", "", detail)
    mapping = {
        "TEXT_OVERFLOW": (
            f"{lang} 下「{detail}」相关标题/按钮/标签文案完整显示，"
            f"无截断/省略号/溢出到相邻控件；价格与按钮不出框"
        ),
        "LAYOUT": f"{lang} 下「{detail}」界面控件不重叠、不错位，层级与间距正常，关键按钮可点",
        "FONT": f"{lang} 字符渲染正常，无豆腐块/□/缺字；特殊字符显示正确",
        "ENCODING": f"{lang} 下「{detail}」无乱码（???/mojibake/方框），长文本编码正确",
        "TERMINOLOGY": f"{lang} 与术语表一致，「{detail}」同一概念在入口与详情译法相同，无混用",
        "PUNCTUATION": f"{lang} 数字、单位、标点与空格符合该语言规范",
        "DATE_FORMAT": f"{lang} 日期/时间/倒计时格式符合目标市场习惯，非源语言格式直出",
        "CULTURAL": f"{lang} 内容符合目标市场文化与合规要求（宗教/政治/分级/禁忌等），无敏感元素直出",
        "PLACEHOLDER": (
            f"「{detail}」中占位符均被实际数值/名称替换"
            + (f"（源模板含 {src}）" if src else "")
            + "，正文与提示不出现字面量 {var}"
        ),
        "IMAGE_TEXT": "图内/硬编码文案已本地化或可配置替换，无源语言残留",
        "VOICE_SUB": "字幕与语音内容、时长对齐，无错位/缺句",
        "RTL": "RTL 布局镜像正确，图标与文本阅读方向一致",
        "FONT_MISSING": "字体缺失时回退可读，无空白控件或方框",
        "LINE_BREAK": "换行断句自然，无孤字/错误断行/半词换行",
        "OTHER": f"「{detail}」在 {lang} 下表现与需求一致，可观察、可判定",
    }
    return mapping.get(category, mapping["OTHER"])


def _preconditions(module: str, target_lang: str, text: str) -> str:
    lang = target_lang or "目标语言"
    parts = [f"客户端语言设置为 {lang}"]
    if module and module != "通用":
        parts.append(f"可正常进入「{module}」")
    if re.search(r"登录|账号|充值|购买|邮件|附件", text):
        parts.append("已登录测试账号，且相关功能数据可用")
    if re.search(r"活动|限时|倒计时|礼包", text):
        parts.append("活动/商品处于可展示状态")
    return "；".join(parts)


def build_rule_cases(
    analysis: AnalysisResult,
    *,
    source_lang: str,
    target_lang: str,
    categories: list[str] | None = None,
    max_cases: int = 30,
) -> list[dict]:
    cases: list[dict] = []
    if not analysis.points:
        return cases

    selected = [c for c in (categories or []) if c]
    for p in analysis.points:
        cats = _pick_categories(p.text, selected or [])
        samples = _extract_samples(p.text)
        for cat in cats[:2]:
            priority = _priority_for(cat, p.text)
            case = {
                "module": (p.module or "通用")[:64],
                "feature": _feature_for(p.text, cat),
                "category": cat,
                "priority": priority,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "source_text": samples[0][:500],
                "target_text": samples[1][:500],
                "requirement_source": f"R{p.index:03d}",
                "preconditions": _preconditions(p.module, target_lang, p.text),
                "steps": _steps_for(p, cat, source_lang, target_lang),
                "expected": _expected_for(cat, target_lang, p, samples),
                "notes": f"规则打底·需求点#{p.index}·{_short(p.text, 24)}",
                "actual": "",
                "status": DEFAULT_STATUS,
                "source": "rules",
            }
            case["quality_score"] = score_case(case)
            cases.append(case)
            if len(cases) >= max_cases:
                cases.sort(key=lambda c: int(c.get("quality_score") or 0), reverse=True)
                return cases
    cases.sort(key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    return cases
