# -*- coding: utf-8 -*-
"""生成后本地质量门禁（借鉴 plasA review_rules.run_rule_checks）。

确定性规则引擎，不依赖模型。每条规则输出统一 Issue 结构：
    {case_id, requirement_id, dimension, severity, description, source}
source="rule" 表示由确定性规则产出（区别于模型层）。

规则注册于 RULES 元组，新增规则只需在此登记，编排层无需改动。
阈值/词表来自本模块常量，支持 .env 覆盖（空字符串停用对应规则）。
"""
from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any, Iterable

from .analysis import AnalysisResult

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"


def _texts(value: Any) -> list[str]:
    """把字段规范为非空字符串列表（非 str 元素跳过，避免误判「有步骤」）。"""
    if isinstance(value, str):
        items = value.splitlines()
    elif isinstance(value, Iterable):
        items = list(value)
    else:
        items = []
    return [t.strip() for t in items if isinstance(t, str) and t.strip()]


def _issue(case_id="", requirement_id="", dimension="", severity=SEVERITY_MEDIUM, description="") -> dict:
    return {
        "case_id": case_id,
        "requirement_id": requirement_id,
        "dimension": dimension,
        "severity": severity,
        "description": description,
        "source": "rule",
    }


def _split_src(value: str) -> list[str]:
    return [s.strip() for s in str(value or "").replace("+", ",").split(",") if s.strip()]


def _grams(text: str) -> set:
    """抽取可比对词面单元：拉丁/数字串整体保留，CJK 取重叠二元组。

    注意：不能用 '[一-龥]{2,}' 整段匹配——纯中文需求点会被当成一个 token，
    导致 len(grams) 偏小、步骤-需求绑定判定失效。这里对 CJK 取重叠 bigram。
    """
    text = str(text or "")
    grams = set(re.findall(r"[A-Za-z0-9]{2,}", text))
    for seg in re.findall(r"[一-龥]+", text):
        for i in range(len(seg) - 1):
            grams.add(seg[i:i + 2])
    return grams


# 阈值与词表：来自常量，可 .env 覆盖；置空字符串停用对应规则
_PLACEHOLDER_TERMS = [
    t for t in os.getenv(
        "LQA_QG_PLACEHOLDER_TERMS",
        "待补充,待填写,TODO,xxx,XX,某,某某,相关功能,对应功能,XX功能",
    ).split(",") if t
]
_VAGUE_STEP_TERMS = [
    t for t in os.getenv(
        "LQA_QG_VAGUE_STEPS",
        "按需求执行,按需求测试,相关功能,相应功能,对应功能,功能正常,正常测试,进行验证,进行查看,逐项检查",
    ).split(",") if t
]
_SOFT_EXPECTED_TERMS = [
    t for t in os.getenv(
        "LQA_QG_SOFT_EXPECTED",
        "正常,显示正常,表现正常,无异常,符合预期,正常显示,无问题,正确显示",
    ).split(",") if t
]
_MIN_STEPS = int(os.getenv("LQA_QG_MIN_STEPS", "2"))
_MAX_VAGUE_STEPS = int(os.getenv("LQA_QG_MAX_VAGUE_STEPS", "0"))  # 0 = 不限制


def rule_structure(cases: list[dict]) -> list[dict]:
    found: list[dict] = []
    for idx, c in enumerate(cases, 1):
        cid = f"#{idx}"
        steps = _texts(c.get("steps"))
        if not steps:
            found.append(_issue(cid, dimension="structure", severity=SEVERITY_HIGH,
                                description="用例缺少测试步骤，无法执行"))
        elif len(steps) < _MIN_STEPS:
            found.append(_issue(cid, dimension="structure", severity=SEVERITY_HIGH,
                                description=f"测试步骤过少（{len(steps)} 步，低于下限 {_MIN_STEPS}），缺少可执行操作序列"))
    return found


def rule_placeholder_steps(cases: list[dict]) -> list[dict]:
    if not _PLACEHOLDER_TERMS:
        return []
    pat = re.compile("|".join(re.escape(t) for t in _PLACEHOLDER_TERMS), re.I)
    found: list[dict] = []
    for idx, c in enumerate(cases, 1):
        cid = f"#{idx}"
        for step in _texts(c.get("steps")):
            hit = pat.search(step)
            if hit:
                found.append(_issue(cid, dimension="specificity", severity=SEVERITY_HIGH,
                                    description=f"步骤含占位词「{hit.group(0)}」，不可执行"))
                break
    return found


def rule_vague_steps(cases: list[dict]) -> list[dict]:
    if not _VAGUE_STEP_TERMS or _MAX_VAGUE_STEPS <= 0:
        return []
    pat = re.compile("|".join(re.escape(t) for t in _VAGUE_STEP_TERMS), re.I)
    found: list[dict] = []
    for idx, c in enumerate(cases, 1):
        cid = f"#{idx}"
        vague_n, sample = 0, ""
        for step in _texts(c.get("steps")):
            if pat.search(step):
                vague_n += 1
                sample = sample or step
        if vague_n > _MAX_VAGUE_STEPS:
            found.append(_issue(cid, dimension="specificity", severity=SEVERITY_MEDIUM,
                                description=f"空话步骤过多（{vague_n} 条），例：「{sample[:40]}」——需写明对象/数据/控件"))
    return found


def rule_soft_expected(cases: list[dict]) -> list[dict]:
    if not _SOFT_EXPECTED_TERMS:
        return []
    pat = re.compile("|".join(re.escape(t) for t in _SOFT_EXPECTED_TERMS), re.I)
    found: list[dict] = []
    for idx, c in enumerate(cases, 1):
        cid = f"#{idx}"
        expected = _texts(c.get("expected"))
        if not expected:
            continue
        soft = [e for e in expected if pat.search(e)]
        if soft:
            found.append(_issue(cid, dimension="specificity", severity=SEVERITY_MEDIUM,
                                description=f"软空话预期：{soft[0][:40]} —— 预期须写明可观察结果（数量/状态/提示）"))
    return found


def rule_step_requirement_binding(cases: list[dict], analysis: AnalysisResult | None = None) -> list[dict]:
    """步骤与本条需求零词面重叠 = 疑似串味/错模块。"""
    if analysis is None:
        return []
    ref_text: dict[str, set] = {}
    for p in analysis.points:
        ref_text[f"R{p.index:03d}"] = _grams(p.text or "")
    found: list[dict] = []
    for idx, c in enumerate(cases, 1):
        cid = f"#{idx}"
        srcs = _split_src(c.get("requirement_source") or "")
        ref_grams: set = set()
        for s in srcs:
            ref_grams |= ref_text.get(s, set())
        if not ref_grams:
            continue
        step_blob = " ".join(_texts(c.get("steps")))
        step_grams = _grams(step_blob)
        if not step_grams:
            continue
        if not (ref_grams & step_grams) and len(ref_grams) >= 4 and len(step_grams) >= 4:
            found.append(_issue(cid, dimension="on_target", severity=SEVERITY_HIGH,
                                description="步骤与本条需求/需求点词面完全无重叠，疑似跨需求步骤串味（错模块）"))
    return found


def rule_priority_distribution(cases: list[dict]) -> list[dict]:
    """优先级分布单一（如全 P0）失效检测。"""
    if not cases:
        return []
    dist = Counter(str(c.get("priority") or "").strip().upper() for c in cases)
    found: list[dict] = []
    if len(dist) == 1 and len(cases) > 1:
        only = next(iter(dist))
        found.append(_issue(dimension="priority", severity=SEVERITY_LOW,
                            description=f"优先级分布单一（全部 {only}），关键用例未分级，排期失效"))
    return found


def rule_coverage(cases: list[dict], analysis: AnalysisResult | None = None) -> list[dict]:
    """需求点无用例关联（honest：仅统计带 requirement_source 的用例）。"""
    if analysis is None:
        return []
    req_ids = {f"R{p.index:03d}" for p in analysis.points}
    covered: set = set()
    for c in cases:
        for s in _split_src(c.get("requirement_source") or ""):
            if s in req_ids:
                covered.add(s)
    found: list[dict] = []
    for rid in sorted(req_ids):
        if rid not in covered:
            found.append(_issue(requirement_id=rid, dimension="coverage", severity=SEVERITY_HIGH,
                                description=f"需求点 {rid} 未被任何用例覆盖"))
    return found


# 规则注册表：新增规则在此登记，编排层无需改动
RULES = (
    rule_structure,
    rule_placeholder_steps,
    rule_vague_steps,
    rule_soft_expected,
    rule_step_requirement_binding,
    rule_priority_distribution,
    rule_coverage,
)


def run_rule_checks(cases, analysis: AnalysisResult | None = None) -> list[dict]:
    """执行全部规则，返回统一 Issue 列表。单条规则异常不中断整批。"""
    raw = list(cases or [])
    valid = [c for c in raw if isinstance(c, dict)]
    issues: list[dict] = []
    if len(valid) != len(raw):
        issues.append(_issue(dimension="structure", severity=SEVERITY_HIGH,
                            description="存在非法用例条目，已跳过"))
    for rule in RULES:
        try:
            if rule is rule_coverage or rule is rule_step_requirement_binding:
                issues.extend(rule(valid, analysis))
            else:
                issues.extend(rule(valid))
        except Exception:
            # 单条规则异常不应中断整批校验
            continue
    return issues


def render_quality_markdown(issues: list[dict]) -> str:
    if not issues:
        return "质量门禁：未发现确定性质量问题。"
    n_high = sum(1 for i in issues if i.get("severity") == "high")
    n_med = sum(1 for i in issues if i.get("severity") == "medium")
    lines = ["# 本地质量门禁报告", "", f"- 问题数：{len(issues)}（高 {n_high} / 中 {n_med}）", ""]
    for it in issues[:40]:
        lines.append(
            f"- [{it.get('severity')}] {it.get('case_id') or ''} "
            f"{it.get('dimension')}: {it.get('description')}"
        )
    lines.append("")
    return "\n".join(lines)
