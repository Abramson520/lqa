# -*- coding: utf-8 -*-
"""规范化、质量评分与门禁。"""
from __future__ import annotations

import re
from typing import Any

from .categories import (
    BILINGUAL_REQUIRED,
    DEFAULT_STATUS,
    PRIORITIES,
    resolve_category,
)

_VAGUE_EXPECTED = re.compile(
    r"^(正常|正常显示|显示正常|无异常|表现正常|界面正常|功能正常)[。.!！]?$"
)
_TEMPLATE_STEPS = re.compile(
    r"截图记录实际表现\s*$"
)
_NUMBERED = re.compile(r"(?m)^\s*\d+[\.、]")


def _clean(s: Any) -> str:
    if s is None:
        return ""
    return re.sub(r"[ \t]+", " ", str(s)).strip()


def normalize_case(item: dict, *, source_lang: str, target_lang: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    raw_cat = _clean(item.get("category"))
    category = resolve_category(raw_cat)
    priority = _clean(item.get("priority")).upper()
    if priority not in PRIORITIES:
        priority = "P1"

    module = _clean(item.get("module"))
    feature = _clean(item.get("feature"))
    steps = str(item.get("steps") or "").replace("\r\n", "\n").strip()
    expected = str(item.get("expected") or "").strip()
    source_text = _clean(item.get("source_text"))
    target_text = _clean(item.get("target_text"))
    preconditions = str(item.get("preconditions") or "").strip()

    if not module or not feature or not steps or not expected:
        return None
    if _VAGUE_EXPECTED.match(expected):
        return None
    if not _NUMBERED.search(steps):
        # 自动补编号，避免 AI 偶发丢序号导致整条丢弃
        lines = [ln.strip() for ln in steps.split("\n") if ln.strip()]
        steps = "\n".join(
            ln if _NUMBERED.search(ln) else f"{i}. {re.sub(r'^\d+[\.、)]\s*', '', ln)}"
            for i, ln in enumerate(lines, 1)
        )

    case = {
        "module": module[:64],
        "feature": feature[:80],
        "category": category,
        "priority": priority,
        "source_lang": _clean(item.get("source_lang")) or source_lang,
        "target_lang": _clean(item.get("target_lang")) or target_lang,
        "source_text": source_text[:500],
        "target_text": target_text[:500],
        "requirement_source": _clean(item.get("requirement_source"))[:64],
        "preconditions": preconditions[:500],
        "steps": steps[:2000],
        "expected": expected[:500],
        "actual": "",
        "status": DEFAULT_STATUS,
        "notes": str(item.get("notes") or "").strip()[:500],
        "source": _clean(item.get("source")) or "ai",
    }
    case["quality_score"] = score_case(case)
    return case


def score_case(c: dict) -> int:
    """0-100 质量分：越高越可交付；用于排序与门禁，不追求虚高。"""
    score = 40
    cat = c.get("category") or ""
    steps = c.get("steps") or ""
    expected = c.get("expected") or ""
    feature = c.get("feature") or ""
    src = c.get("source_text") or ""
    tgt = c.get("target_text") or ""
    pre = c.get("preconditions") or ""
    notes = c.get("notes") or ""
    source = c.get("source") or ""

    step_lines = [ln for ln in steps.split("\n") if ln.strip()]
    if len(step_lines) >= 4:
        score += 8
    elif len(step_lines) >= 3:
        score += 5
    if _NUMBERED.search(steps):
        score += 4
    if re.search(r"进入|打开|点击|切换|定位|对照|检查|观察|播放|检索|触发", steps):
        score += 6
    if re.search(r"截图|记录|对照源语言|切换回", steps):
        score += 4
    if re.search(r"检查要点：", steps):
        score -= 6  # 写作规范泄漏到用例步骤
    if _TEMPLATE_STEPS.search(steps) and len(step_lines) <= 4:
        score -= 6

    # 预期可判定
    if len(expected) >= 35:
        score += 8
    elif len(expected) >= 20:
        score += 5
    elif len(expected) >= 12:
        score += 2
    if re.search(r"无|不|一致|完整|正确|替换|显示为|判定|失败|通过", expected):
        score += 5
    if re.search(r"截断|溢出|乱码|豆腐|混用|字面量|不一致|重叠|省略|镜像|断行", expected):
        score += 5
    if _VAGUE_EXPECTED.match(expected.strip()):
        score -= 30

    # 功能点具体性
    if 6 <= len(feature) <= 36:
        score += 5
    elif len(feature) > 48:
        score -= 3
    if re.search(r"按钮|标题|邮件|商店|技能|公告|字幕|占位|术语|日期|布局|礼包", feature):
        score += 3

    # 双语文案
    if cat in BILINGUAL_REQUIRED:
        if src and tgt:
            score += 14
        elif src or tgt:
            score += 5
        else:
            score -= 12
            if source == "ai":
                score -= 6
    else:
        if src and tgt:
            score += 4

    if len(pre) >= 15:
        score += 4
    if notes and not notes.startswith("规则打底"):
        score += 3
    elif notes.startswith("规则打底"):
        score -= 3

    if cat == "PLACEHOLDER" and re.search(r"\{[a-zA-Z_]+\}|占位|变量|数量", steps + expected + src + tgt):
        score += 6
    if cat == "TERMINOLOGY" and re.search(r"对照|一致|术语|混用|两处", steps + expected):
        score += 5
    if cat == "DATE_FORMAT" and re.search(r"时间|日期|倒计时|戳", steps + expected):
        score += 3
    if cat in ("TEXT_OVERFLOW", "LAYOUT") and re.search(r"控件|按钮|标题|卡片|布局|溢出|截断|价格", steps + expected):
        score += 3

    # 规则骨架天花板：无双语文案时不宜接近满分
    if source == "rules" and cat in BILINGUAL_REQUIRED and not (src and tgt):
        score = min(score, 72)

    return max(0, min(100, score))


def gate_report(cases: list[dict]) -> dict:
    issues: list[str] = []
    scores: list[int] = []
    for i, c in enumerate(cases, 1):
        score = int(c.get("quality_score") or score_case(c))
        scores.append(score)
        if not _NUMBERED.search(c.get("steps") or ""):
            issues.append(f"#{i} steps 非编号")
        # 注：自定义类别（非内置 code）为合法，不再判为非法
        exp = c.get("expected") or ""
        if not exp or _VAGUE_EXPECTED.match(exp.strip()):
            issues.append(f"#{i} expected 空泛")
        cat = c.get("category") or ""
        if cat in BILINGUAL_REQUIRED and not (c.get("source_text") or c.get("target_text")):
            if (c.get("source") or "") == "ai":
                issues.append(f"#{i} 缺双语文案")
        if score < 55:
            issues.append(f"#{i} 质量分偏低({score})")
        if len(c.get("feature") or "") < 4:
            issues.append(f"#{i} 功能点过短")

    avg = int(sum(scores) / len(scores)) if scores else 0
    low = sum(1 for s in scores if s < 55)
    return {
        "count": len(cases),
        "issue_count": len(issues),
        "issues": issues[:30],
        "pass": len(issues) == 0,
        "avg_score": avg,
        "low_score_count": low,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
    }


def dedupe(cases: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for c in cases:
        key = (
            c.get("module"),
            re.sub(r"\s+", "", c.get("feature") or "")[:24],
            c.get("category"),
            (c.get("target_text") or c.get("source_text") or c.get("expected") or "")[:30],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def merge_cases(ai_cases: list[dict], rule_cases: list[dict], *, count: int | None = None) -> list[dict]:
    """按质量分合并：AI 高分优先，规则补齐；不再整批丢弃 AI。

    count 为 None 或 <=0 表示不限制，返回全部合并结果。
    """
    ai = sorted(ai_cases, key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    rules = sorted(rule_cases, key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    merged = dedupe(ai + rules)
    # 高分优先，同分保持 AI 在前（dedupe 已保序）
    merged.sort(key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    if not count or count <= 0:
        return merged
    return merged[:count]
