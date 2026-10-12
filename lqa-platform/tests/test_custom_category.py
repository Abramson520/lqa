# -*- coding: utf-8 -*-
"""自定义关注类别 + 目标条数不限制 的回归测试（通用能力，不依赖具体业务）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lqa.analysis import split_requirements
from lqa.categories import category_label, resolve_category
from lqa.config import load_settings
from lqa.exporters import _localization_checks
from lqa.generate import _balanced_top, generate
from lqa.parsers import parse_txt
from lqa.quality import gate_report, merge_cases, normalize_case
from lqa.rules import build_rule_cases

SAMPLE = """
【商城系统】
1. 商店主界面展示限时礼包标题与价格
2. 礼包详情页展示道具列表与购买按钮
3. 售罄商品置灰并显示「已售罄」
"""


def test_resolve_category_builtin_code():
    assert resolve_category("text_overflow") == "TEXT_OVERFLOW"
    assert resolve_category("CULTURAL") == "CULTURAL"


def test_resolve_category_chinese_label():
    assert resolve_category("文本溢出/截断") == "TEXT_OVERFLOW"
    assert resolve_category("文化合规") == "CULTURAL"


def test_resolve_category_custom_preserved():
    # 自定义类别不再被强转 OTHER
    assert resolve_category("未成年人保护") == "未成年人保护"
    assert resolve_category("") == "OTHER"


def test_category_label():
    assert category_label("TEXT_OVERFLOW") == "文本溢出/截断"
    assert category_label("未成年人保护") == "未成年人保护"


def test_normalize_case_preserves_custom_category():
    c = normalize_case(
        {
            "module": "商城",
            "feature": "未成年人消费提示",
            "category": "未成年人保护",
            "priority": "P1",
            "steps": "1. 进入商城\n2. 检查消费确认弹窗",
            "expected": "目标语言下消费确认弹窗显示未成年人保护提示，无缺失",
        },
        source_lang="en-US",
        target_lang="zh-CN",
    )
    assert c is not None
    assert c["category"] == "未成年人保护"
    assert c["category"] != "OTHER"


def test_gate_report_allows_custom_category():
    cases = [
        {
            "module": "M",
            "feature": "f",
            "category": "自定义合规维度",
            "priority": "P1",
            "steps": "1. 进入界面\n2. 观察表现",
            "expected": "目标语言下表现符合预期，无异常",
            "quality_score": 70,
        }
    ]
    g = gate_report(cases)
    # 自定义类别不应被判为「category 非法」
    assert not any("非法" in i for i in g["issues"]), g["issues"]


def test_balanced_top_unlimited_returns_all():
    cases = [{"module": f"M{i}", "category": f"C{i}", "quality_score": i} for i in range(10)]
    out = _balanced_top(cases, None)
    assert len(out) == 10
    out2 = _balanced_top(cases, 0)
    assert len(out2) == 10


def test_merge_cases_unlimited_returns_all():
    ai = [{"module": "A", "feature": "fa", "category": "X", "quality_score": 80}]
    rules = [{"module": "B", "feature": "fb", "category": "Y", "quality_score": 60}]
    assert len(merge_cases(ai, rules, count=None)) == 2
    assert len(merge_cases(ai, rules, count=0)) == 2
    assert len(merge_cases(ai, rules, count=1)) == 1


def test_cultural_export_checks_broadened():
    checks = _localization_checks("CULTURAL")
    # 拓宽后应包含多条通用合规维度，而非单一描述
    assert "无宗教/政治/军事等敏感元素" in checks
    assert "符合目标市场年龄分级与内容审查" in checks
    # 通用 4 条仍保留
    assert "文案翻译准确，无硬编码字符串" in checks


def test_rules_emit_custom_category_case():
    a = split_requirements(parse_txt(SAMPLE))
    cases = build_rule_cases(
        a,
        source_lang="en-US",
        target_lang="zh-CN",
        categories=["未成年人保护"],
        max_cases=30,
    )
    assert any(c["category"] == "未成年人保护" for c in cases), [
        c["category"] for c in cases
    ]


def test_generate_count_zero_is_unlimited():
    settings = load_settings()
    a = split_requirements(parse_txt(SAMPLE))
    capped = generate(
        settings, a,
        source_lang="en-US", target_lang="zh-CN",
        modules=a.modules, categories=[], extra="",
        use_ai=False, count=2,
    )
    unlimited = generate(
        settings, a,
        source_lang="en-US", target_lang="zh-CN",
        modules=a.modules, categories=[], extra="",
        use_ai=False, count=0,
    )
    # 不限制时覆盖的用例数应不少于受限时（同一份需求）
    assert len(unlimited["cases"]) >= len(capped["cases"])
    assert len(unlimited["cases"]) > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
