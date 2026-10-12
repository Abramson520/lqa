# -*- coding: utf-8 -*-
"""质量层（借鉴 plasA）回归测试：缺口审查 / 质量门禁 / 覆盖率报告。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lqa.analysis import AnalysisResult, RequirementPoint
from lqa.config import Settings
from lqa.coverage import build_coverage_report, render_coverage_markdown
from lqa.gap_review import format_gap_summary, review_requirement_gaps
from lqa.generate import generate
from lqa.quality_gate import render_quality_markdown, run_rule_checks


def _analysis(points):
    return AnalysisResult(
        raw_text="\n".join(p.text for p in points),
        points=points,
        modules=sorted({p.module for p in points}),
    )


def test_gap_review_flags_vague_point():
    a = _analysis([
        RequirementPoint("商城", "进行相关功能优化", 1),
        RequirementPoint("邮件", "补偿邮件含 {amount} 占位符，金额不超过100元，若数量不足则报错，需替换为实际数量并显示到账提示", 2),
    ])
    gaps = review_requirement_gaps(a, requirement_text=a.raw_text)
    types = {g["type"] for g in gaps}
    assert "vague_point" in types  # 第 1 条过泛
    # 第 2 条带数字边界(100元)/异常(不足报错)/验收(显示/提示/替换/到账)信号，不应被判 low_testability
    assert all(
        not (g["requirement_id"] == "R002" and g["type"] == "low_testability")
        for g in gaps
    )
    assert isinstance(format_gap_summary(gaps), str)


def test_gap_review_low_testability_on_missing_signals():
    a = _analysis([
        RequirementPoint("商城", "礼包价格需正确显示", 1),
    ])
    gaps = review_requirement_gaps(a, requirement_text=a.raw_text)
    # 无数字边界、无异常、无前置、无验收词 → 缺 >=3 项 → low_testability
    assert any(g["type"] == "low_testability" for g in gaps)


def test_quality_gate_placeholder_and_priority():
    cases = [
        {"module": "商城", "feature": "礼包标题", "category": "TEXT_OVERFLOW",
         "priority": "P0", "requirement_source": "R001",
         "steps": "1.进入「商城」\n2.检查待补充标题是否完整", "expected": "标题完整显示无截断"},
        {"module": "邮件", "feature": "补偿邮件", "category": "PLACEHOLDER",
         "priority": "P0", "requirement_source": "R002",
         "steps": "1.进入「邮件」\n2.检查占位符替换", "expected": "变量被实际数量替换"},
    ]
    a = _analysis([RequirementPoint("商城", "礼包标题", 1), RequirementPoint("邮件", "补偿邮件", 2)])
    issues = run_rule_checks(cases, a)
    dims = {(i["dimension"], i["description"]) for i in issues}
    # 占位词「待补充」
    assert any("待补充" in d for _d, d in dims)
    # 全 P0 → 优先级分布单一
    assert any(i["dimension"] == "priority" for i in issues)


def test_quality_gate_step_requirement_binding():
    cases = [
        {"module": "商城", "feature": "礼包标题", "category": "TEXT_OVERFLOW",
         "priority": "P1", "requirement_source": "R001",
         "steps": "1.进入「设置」\n2.检查语言切换入口文案", "expected": "完整显示"},
    ]
    a = _analysis([RequirementPoint("商城", "限时礼包价格数值需正确显示", 1)])
    issues = run_rule_checks(cases, a)
    # 步骤写的是「设置/语言切换」，与需求点「限时礼包价格数值」零词面重叠 → on_target
    assert any(i["dimension"] == "on_target" for i in issues)


def test_coverage_report_and_markdown():
    a = _analysis([
        RequirementPoint("商城", "礼包标题", 1),
        RequirementPoint("邮件", "补偿邮件", 2),
        RequirementPoint("公告", "系统公告", 3),
    ])
    cases = [
        {"requirement_source": "R001"},
        {"requirement_source": "R002"},
    ]
    rep = build_coverage_report(a, cases)
    assert rep["total_requirements"] == 3
    assert rep["covered_requirements"] == 2
    assert rep["coverage_rate"] == 66.7
    # R003 未覆盖
    assert any(it["id"] == "R003" and not it["covered"] for it in rep["requirements"])
    md = render_coverage_markdown(rep)
    assert "覆盖率报告" in md and "66.7%" in md
    assert isinstance(render_quality_markdown([]), str)


def test_generate_returns_quality_layer():
    settings = Settings(provider="deepseek", base_url="x", api_key="", model="deepseek-chat")
    prd = (
        "# 商城系统\n## 限时礼包\n限时礼包标题按钮文案需完整展示，德语文案较长易溢出\n"
        "礼包价格需正确显示，不被挤出卡片\n## 邮件系统\n补偿邮件含 {amount} 占位符，需替换为实际数量\n"
    )
    from lqa.analysis import split_requirements
    analysis = split_requirements(prd)
    result = generate(
        settings, analysis, source_lang="en-US", target_lang="de-DE",
        modules=[], categories=[], extra="", use_ai=False, count=16,
    )
    assert isinstance(result.get("gap_review"), list)
    assert isinstance(result.get("quality_issues"), list)
    cov = result.get("coverage")
    assert isinstance(cov, dict) and "coverage_rate" in cov
    assert isinstance(result.get("coverage_markdown"), str) and result["coverage_markdown"]
    assert isinstance(result.get("quality_markdown"), str)
    # 规则用例已带 requirement_source，覆盖率应 > 0
    assert cov["coverage_rate"] is not None and cov["coverage_rate"] > 0


def _one_case(expected: str) -> list[dict]:
    return [{
        "module": "商城", "feature": "礼包标题", "category": "TEXT_OVERFLOW",
        "priority": "P1", "requirement_source": "R001",
        "steps": "1.进入「商城」\n2.查看礼包卡片",
        "expected": expected,
    }]


def _soft_issues(cases: list[dict]) -> list[dict]:
    return [i for i in run_rule_checks(cases) if "软空话预期" in i["description"]]


def test_soft_expected_ignores_quoted_requirement_fragment():
    """预期引用需求原文（原文含软词）但主体为可观察判定 → 不应误报。"""
    expected = (
        "德文下「礼包价格需正确显示」相关标题/按钮/标签文案完整显示，"
        "无截断/省略号/溢出到相邻控件；价格与按钮不出框"
    )
    assert not _soft_issues(_one_case(expected)), "引用原文片段不应触发软预期误报"


def test_soft_expected_still_flags_pure_soft():
    """整条预期即软话 → 必须报。"""
    assert _soft_issues(_one_case("正确显示")), "纯软预期必须上报"


def test_soft_expected_still_flags_short_residue():
    """剥离软词后仅剩主语、无可观察内容 → 必须报。"""
    assert _soft_issues(_one_case("文本正常显示")), "残留内容不足仍须上报"


def test_rule_expected_templates_free_of_soft_terms():
    """规则生成侧：全部类别 expected 模板过门禁零软预期 issue。"""
    from lqa.categories import CATEGORIES
    from lqa.rules import _expected_for
    point = RequirementPoint("商城", "测试文案", 1)
    for cat in CATEGORIES:
        expected = _expected_for(cat, "德语", point, ("源文案", "目标文案"))
        assert not _soft_issues(_one_case(expected)), f"模板 {cat} 自带软词：{expected}"
