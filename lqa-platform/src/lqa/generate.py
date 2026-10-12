# -*- coding: utf-8 -*-
"""生成编排：规则打底 → 可选 LLM 补强 → 质量分合并。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .analysis import AnalysisResult
from .categories import CATEGORIES, CATEGORY_FOCUS
from .config import Settings
from .coverage import build_coverage_report, render_coverage_markdown
from .gap_review import format_gap_summary, review_requirement_gaps
from .llm import LLMError, build_system_prompt, chat_json
from .quality import dedupe, gate_report, merge_cases, normalize_case
from .quality_gate import render_quality_markdown, run_rule_checks
from .rules import build_rule_cases
from .skills import render_skills_block


def build_user_prompt(
    analysis: AnalysisResult,
    *,
    count: int,
    modules: list[str],
    categories: list[str],
    source_lang: str,
    target_lang: str,
    extra: str,
    skeleton: list[dict],
    avoid: list[dict] | None = None,
    selected_skills: list[dict] | None = None,
) -> str:
    focus = {c: CATEGORY_FOCUS.get(c, "") for c in categories if c in CATEGORIES}
    points = [
        {"module": p.module, "text": p.text}
        for p in analysis.points[:50]
    ]
    # 骨架里已有字段可以复用，但去掉系统内部字段
    slim_skeleton = []
    for c in skeleton[:20]:
        slim_skeleton.append(
            {
                "module": c.get("module"),
                "feature": c.get("feature"),
                "category": c.get("category"),
                "priority": c.get("priority"),
                "source_text": c.get("source_text"),
                "target_text": c.get("target_text"),
                "preconditions": c.get("preconditions"),
                "steps": c.get("steps"),
                "expected": c.get("expected"),
                "notes": c.get("notes"),
            }
        )
    payload = {
        "project_context": {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "modules": modules or analysis.modules,
            "game_style_hint": "SLG/手游客户端 UI + 系统文案",
        },
        "requirement_points": points,
        "generate": {
            "count": count,
            "categories": categories or list(CATEGORIES.keys()),
            "category_focus": focus,
            "extra_requirements": extra,
            "mode": "enhance_skeleton" if skeleton else "from_scratch",
            "quality_bar": (
                "每条用例必须：具体 feature、编号 steps、可判定 expected、"
                "高风险类别带双语文案；覆盖多个模块；禁止模板空话"
            ),
        },
        "skeleton_cases": slim_skeleton,
        "avoid_duplicates": avoid or [],
    }
    head = (
        "请为该游戏本地化项目生成 LQA 测试用例，严格输出 JSON。\n"
        "要求：在骨架上补强或按需求点重写；输出必须满足 quality_bar。"
    )
    # 用户选定的领域知识包作为独立段落给出，避免被 JSON 结构稀释
    block = render_skills_block(selected_skills or [])
    if block:
        head = f"{head}\n\n{block}"
    return head + "\n" + json.dumps(payload, ensure_ascii=False, default=str)


def _balanced_top(cases: list[dict], count: int | None = None) -> list[dict]:
    """覆盖优先排序：每模块 / 类别至少保留 1 条（取组内最高分），剩余按质量分补满。

    count 为 None 或 <=0 表示不限制——返回全部用例（覆盖优先排序，不做截断）。
    count > 0 时在该上限内优先保证覆盖，覆盖项本身超过上限则在上限内按质量取。
    """
    if not cases:
        return []
    ordered = sorted(cases, key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    if not count or count <= 0:
        return ordered
    must: list = []
    seen_ids: set = set()
    for key_fn in (lambda c: c.get("module"), lambda c: c.get("category")):
        groups: dict = {}
        for c in ordered:
            groups.setdefault(key_fn(c), []).append(c)
        for grp in groups.values():
            top = grp[0]
            cid = id(top)
            if cid not in seen_ids:
                seen_ids.add(cid)
                must.append(top)
    if len(must) >= count:
        return sorted(must, key=lambda c: int(c.get("quality_score") or 0), reverse=True)[:count]
    rest = [c for c in ordered if id(c) not in seen_ids]
    out = list(must)
    for c in rest:
        if len(out) >= count:
            break
        out.append(c)
    return out


def generate(
    settings: Settings,
    analysis: AnalysisResult,
    *,
    source_lang: str,
    target_lang: str,
    modules: list[str],
    categories: list[str],
    extra: str,
    use_ai: bool,
    count: int = 16,
    on_progress: Callable[[str], None] | None = None,
    case_library: Path | None = None,
    selected_skills: list[dict] | None = None,
) -> dict:
    def note(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    count = int(count or 0)
    unlimited = count <= 0
    cap = None if unlimited else count
    cats = [c for c in categories if c] or list(CATEGORIES.keys())

    # 生成前缺口审查：在拆分后的需求点上扫描不可测信号（不依赖 AI）
    gap_review = review_requirement_gaps(analysis, requirement_text=analysis.raw_text)
    note("规则打底中…")
    rule_cases = build_rule_cases(
        analysis,
        source_lang=source_lang,
        target_lang=target_lang,
        categories=cats,
        max_cases=2000 if unlimited else max(count, 8),
    )
    result_cases = rule_cases
    generator = "rules"
    ai_error = ""
    gate = gate_report(result_cases)

    if use_ai:
        if not settings.has_key:
            raise LLMError("未配置 API Key，无法启用 AI 补强")
        note("调用 LLM 补强…")
        # 不限制时给 LLM 一个充分覆盖的提示数（不约束最终输出上限）
        prompt_count = count if not unlimited else min(80, max(12, len(analysis.points) * 2))
        try:
            user = build_user_prompt(
                analysis,
                count=prompt_count,
                modules=modules or analysis.modules,
                categories=cats,
                source_lang=source_lang,
                target_lang=target_lang,
                extra=extra,
                skeleton=rule_cases,
                selected_skills=selected_skills,
            )
            system = build_system_prompt(case_library, selected_skills=selected_skills)
            data = chat_json(settings, user, system=system)
            items = data.get("cases") if isinstance(data, dict) else data
            if not isinstance(items, list):
                raise LLMError("LLM JSON 缺少 cases 数组")
            normalized = []
            for it in items:
                n = normalize_case(
                    it, source_lang=source_lang, target_lang=target_lang
                )
                if n:
                    n["source"] = "ai"
                    # 高质量门禁：AI 条目 expected 过短则丢弃
                    if len(n.get("expected") or "") < 12:
                        continue
                    normalized.append(n)

            if not normalized:
                raise LLMError("AI 输出均未通过基础质量校验")

            # 按质量分合并，保留有效 AI 条目 + 规则补齐
            merged = merge_cases(normalized, rule_cases, count=cap)
            # 若 AI 高分条目足够，标记引擎；否则仍合并但注明
            high_ai = [c for c in normalized if int(c.get("quality_score") or 0) >= 65]
            if high_ai:
                generator = "llm+rules"
                if len(high_ai) < count // 2:
                    ai_error = f"AI 高分 {len(high_ai)} 条，其余由规则补齐"
            else:
                generator = "llm+rules"
                ai_error = "AI 输出质量分偏低，已与规则骨架择优合并"
            result_cases = merged
        except LLMError as e:
            ai_error = str(e)
            note(f"AI 失败，保留规则骨架: {e}")
            result_cases = rule_cases
            generator = "rules"

    result_cases = _balanced_top(dedupe(result_cases), cap)
    # 再按质量分排序输出
    result_cases.sort(key=lambda c: int(c.get("quality_score") or 0), reverse=True)
    gate = gate_report(result_cases)

    # 生成后质量门禁：确定性规则扫描（占位词/空话步骤/步骤-需求绑定/全 P0/覆盖缺口）
    quality_issues = run_rule_checks(result_cases, analysis)
    # 覆盖率报告：需求点 ↔ 用例
    coverage = build_coverage_report(analysis, result_cases)
    coverage_md = render_coverage_markdown(coverage)
    quality_md = render_quality_markdown(quality_issues)
    return {
        "cases": result_cases,
        "generator": generator,
        "ai_error": ai_error,
        "analysis_summary": analysis.summary(),
        "model": settings.model if use_ai else "",
        "gate": gate,
        "avg_score": gate.get("avg_score", 0),
        "gap_review": gap_review,
        "gap_review_summary": format_gap_summary(gap_review),
        "quality_issues": quality_issues,
        "quality_markdown": quality_md,
        "coverage": coverage,
        "coverage_markdown": coverage_md,
    }
