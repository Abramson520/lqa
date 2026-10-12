# -*- coding: utf-8 -*-
"""规则路径冒烟 + 质量门禁回归。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lqa.analysis import split_requirements
from lqa.categories import BUILTIN_FEW_SHOT
from lqa.exporters import cases_to_dataframe, to_xlsx_bytes
from lqa.generate import generate
from lqa.llm import build_system_prompt, extract_json_payload
from lqa.parsers import merge_sources, parse_txt
from lqa.quality import dedupe, gate_report, merge_cases, normalize_case, score_case
from lqa.rules import build_rule_cases
from lqa.config import load_settings


SAMPLE = """
【商城系统】
1. 商店主界面展示限时礼包标题与价格
2. 礼包详情页展示道具列表与购买按钮
3. 售罄商品置灰并显示「已售罄」

【邮件系统】
- 系统补偿邮件：You received {amount} diamonds
- 附件领取后按钮状态变更
- 过期邮件自动清理提示

【设置】
- Workspace 入口按钮与帮助中心译文需保持一致
"""


def test_parse_and_split():
    text = parse_txt(SAMPLE)
    a = split_requirements(text)
    assert len(a.points) >= 4
    assert any("商城" in m or "邮件" in m for m in a.modules)


def test_rules_quality():
    a = split_requirements(parse_txt(SAMPLE))
    cases = build_rule_cases(
        a,
        source_lang="en-US",
        target_lang="de-DE",
        categories=["TEXT_OVERFLOW", "PLACEHOLDER", "LAYOUT", "TERMINOLOGY"],
        max_cases=16,
    )
    assert len(cases) >= 4
    assert all(c.get("steps") and c.get("expected") for c in cases)
    assert all("正常显示" not in (c.get("expected") or "") for c in cases)
    # 步骤应模块化，不是统一模板
    assert any("商城" in (c.get("module") or "") or "邮件" in (c.get("module") or "") for c in cases)
    ph = [c for c in cases if c.get("category") == "PLACEHOLDER"]
    if ph:
        assert any("{" in (c.get("source_text") or "") or "占位" in (c.get("expected") or "") for c in ph)
    scores = [int(c.get("quality_score") or 0) for c in cases]
    avg = sum(scores) / len(scores)
    assert avg >= 48, f"规则骨架平均分过低: {avg:.1f}"
    assert avg <= 85, f"规则骨架评分虚高: {avg:.1f}"
    # 不得把写作规范写进 steps
    assert all("检查要点：" not in (c.get("steps") or "") for c in cases)
    report = gate_report(cases)
    assert report["count"] == len(cases)
    df = cases_to_dataframe(cases)
    assert len(df) == len(cases)
    data = to_xlsx_bytes(cases)
    assert data[:2] == b"PK"


def test_normalize_score_merge():
    item = {
        "module": "商店",
        "feature": "限时礼包标题·文案显示检查",
        "category": "文本溢出/截断",
        "priority": "p0",
        "source_text": "Limited Offer",
        "target_text": "Zeitlich begrenztes Angebot",
        "preconditions": "语言 de-DE，商城可进入",
        "steps": "1. 切换 de-DE\n2. 打开商城\n3. 观察礼包标题是否截断\n4. 截图",
        "expected": "标题完整显示，无省略号，不压到价格控件",
        "notes": "德语长文案高风险",
    }
    n = normalize_case(item, source_lang="en-US", target_lang="de-DE")
    assert n and n["category"] == "TEXT_OVERFLOW" and n["priority"] == "P0"
    assert n["quality_score"] >= 70, n["quality_score"]

    vague = dict(item, expected="正常显示")
    assert normalize_case(vague, source_lang="en-US", target_lang="de-DE") is None

    rules = [
        {
            "module": "邮件",
            "feature": "补偿邮件占位符",
            "category": "PLACEHOLDER",
            "priority": "P0",
            "source_lang": "en-US",
            "target_lang": "de-DE",
            "source_text": "You received {amount} diamonds",
            "target_text": "",
            "preconditions": "语言 de-DE",
            "steps": "1. 切换语言\n2. 打开邮件\n3. 查看正文占位符",
            "expected": "{amount} 被替换为实际数量",
            "notes": "规则打底",
            "source": "rules",
        }
    ]
    rules[0]["quality_score"] = score_case(rules[0])
    merged = merge_cases([n], rules, count=5)
    assert len(merged) == 2
    assert merged[0]["quality_score"] >= merged[1]["quality_score"]
    assert len(dedupe([n, dict(n)])) == 1
    merged_text = merge_sources("A文档", "B粘贴")
    assert "A文档" in merged_text and "B粘贴" in merged_text


def test_generate_rules_path():
    a = split_requirements(parse_txt(SAMPLE))
    settings = load_settings(provider="deepseek", api_key="")
    result = generate(
        settings,
        a,
        source_lang="en-US",
        target_lang="de-DE",
        modules=a.modules,
        categories=["TEXT_OVERFLOW", "PLACEHOLDER", "TERMINOLOGY"],
        extra="优先商店与邮件",
        use_ai=False,
        count=12,
        case_library=ROOT / "case_library",
    )
    assert result["generator"] == "rules"
    assert len(result["cases"]) >= 4
    assert 45 <= result["avg_score"] <= 85, result["avg_score"]
    assert all(c.get("quality_score", 0) >= 40 for c in result["cases"])
    assert all("检查要点：" not in (c.get("steps") or "") for c in result["cases"])


def test_prompt_and_json():
    sys_prompt = build_system_prompt(ROOT / "case_library")
    assert "LQA" in sys_prompt
    assert "TEXT_OVERFLOW" in sys_prompt
    assert "cases" in sys_prompt
    assert len(BUILTIN_FEW_SHOT) >= 2
    data = extract_json_payload('```json\n{"cases":[{"module":"x"}]}\n```')
    assert isinstance(data.get("cases"), list)
    data2 = extract_json_payload('[{"module":"y","feature":"f","steps":"1. a","expected":"b"}]')
    assert "cases" in data2


def test_rule_steps_tail_step_varies_by_category():
    """回归：步骤末句须给出该类别专属的判定动作，不得全用例共用同一句样板。

    背景：此前 `_steps_for` 第二步固定为「记录实际文案/布局并截图，作为判定依据」，
    导致用例末句 100% 重复（样板率 100%——用 `scripts` 侧 A/B 脚本实测确认），
    步骤实际未随类别/功能变化。此处锁定「末句因类别而异」这一行为。
    """
    a = split_requirements(parse_txt(SAMPLE))
    cases = build_rule_cases(
        a,
        source_lang="en-US",
        target_lang="de-DE",
        categories=["TEXT_OVERFLOW", "PLACEHOLDER", "LAYOUT", "TERMINOLOGY", "ENCODING"],
        max_cases=16,
    )
    assert len(cases) >= 4

    tails: list[str] = []
    for c in cases:
        lines = [l.strip() for l in str(c.get("steps") or "").splitlines() if l.strip()]
        tails.append(lines[-1] if lines else "")
    assert all(tails), "每条用例都应有非空的末步"

    counts: dict[str, int] = {}
    for t in tails:
        counts[t] = counts.get(t, 0) + 1
    top = max(counts.values())
    # 末句重复率必须低于 100%：不同类别应有各自的专属判定动作
    assert top < len(cases), f"末句仍是样板：重复最多的末句占 {top}/{len(cases)} -> {list(counts)[0][:60]}"


if __name__ == "__main__":
    test_parse_and_split()
    test_rules_quality()
    test_normalize_score_merge()
    test_generate_rules_path()
    test_prompt_and_json()
    test_rule_steps_tail_step_varies_by_category()
    print("ALL PASS")
