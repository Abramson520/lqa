# -*- coding: utf-8 -*-
"""A/B 对照实验：同一份 PRD 下 规则引擎(rules) vs AI 增强(llm+rules) 的用例质量对比。

用法（在项目根目录执行）：
    # 方式1：环境变量
    set LQA_API_KEY=sk-xxx
    python scripts/ab_compare.py
    # 方式2：命令行（不落盘，仅内存中使用）
    python scripts/ab_compare.py --key sk-xxx
    # 方式3：只跑规则基线（无 Key）
    python scripts/ab_compare.py

对比维度（全部可量化）：
    质量门禁问题数(高/中)、平均质量分、步骤样板率、步骤去重数、类别多样性、
    步骤/预期平均长度、需求覆盖率、缺口审查项数

注：产出默认写入 outputs/_ab/<时间戳>_AB_<engine>/，含 xlsx 与三份质量报告。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lqa.config import load_settings
from lqa.analysis import split_requirements
from lqa.generate import generate
from lqa.exporters import save_output
from lqa.llm import LLMError

PRD = """# 商城系统
## 限时礼包
限时礼包标题按钮文案需完整展示，德语文案较长易溢出卡片
礼包价格需正确显示，不被挤出卡片边界
## 邮件系统
补偿邮件含 {amount} 占位符，需替换为玩家实际获得数量并显示到账提示
## 公告系统
系统公告支持多语言切换，需完整显示跳转按钮文案
## 支付系统
商城内购支付需正确跳转，金额不超过单笔上限，若余额不足则报错提示
## 活动系统
进行相关功能优化
"""

TAIL_LEN = 40


def metrics(result: dict) -> dict:
    """从 generate() 结果计算可量化质量指标。"""
    cases = result["cases"] or []
    n = len(cases) or 1
    scores = [int(c.get("quality_score") or 0) for c in cases]

    # 步骤末行样板率：出现次数最多的末行 / 用例数（越高越模板化）
    tails: Counter = Counter()
    steps_set: set = set()
    for c in cases:
        lines = [l.strip() for l in str(c.get("steps") or "").splitlines() if l.strip()]
        if lines:
            tail = re.sub(r"^\d+[.、)]\s*", "", lines[-1])[:TAIL_LEN]
            tails[tail] += 1
        steps_set.add(str(c.get("steps") or "").strip())
    boiler = (max(tails.values()) / len(cases)) if cases and tails else 0.0

    cats = Counter(str(c.get("category") or "") for c in cases)
    prios = Counter(str(c.get("priority") or "") for c in cases)

    issues = result.get("quality_issues") or []
    high = sum(1 for i in issues if i.get("severity") == "high")
    med = sum(1 for i in issues if i.get("severity") == "medium")

    step_lens = [len(str(c.get("steps") or "")) for c in cases]
    exp_lens = [len(str(c.get("expected") or "")) for c in cases]

    return {
        "用例数": len(cases),
        "平均分": round(sum(scores) / n, 1),
        "门禁问题(总/高/中)": f"{len(issues)}/{high}/{med}",
        "步骤样板率": f"{boiler:.0%}",
        "步骤去重数": len(steps_set),
        "类别数/最大占比": (
            f"{len(cats)}/{max(cats.values()) / n:.0%}" if cats else "0/0%"
        ),
        "优先级分布": dict(prios),
        "步骤均长": round(sum(step_lens) / n, 1),
        "预期均长": round(sum(exp_lens) / n, 1),
        "覆盖率": f"{result['coverage']['coverage_rate']}%",
        "缺口审查": len(result.get("gap_review") or []),
    }


def run(engine: str, settings, analysis, count: int, use_ai: bool):
    print(f"\n===== 运行 {engine} =====")
    result = generate(
        settings, analysis, source_lang="en-US", target_lang="de-DE",
        modules=[], categories=[], extra="", use_ai=use_ai, count=count,
    )
    if result.get("ai_error"):
        print(f"[AI 回退] {result['ai_error']}")
    folder = save_output(
        result["cases"], name=f"AB_{engine}", out_root=ROOT / "outputs" / "_ab",
        reports={
            "coverage_markdown": result["coverage_markdown"],
            "gap_review_summary": result["gap_review_summary"],
            "quality_markdown": result["quality_markdown"],
        },
    )
    print(f"[export] {folder}")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="", help="DeepSeek API Key（不传则读环境变量）")
    ap.add_argument("--count", type=int, default=60)
    ap.add_argument("--model", default="deepseek-chat")
    args = ap.parse_args()

    if args.key:
        os.environ["LQA_API_KEY"] = args.key
    settings = load_settings(provider="deepseek", model=args.model)
    print(f"[settings] provider={settings.provider} model={settings.model} "
          f"has_key={settings.has_key} key={settings.masked_key()}")

    analysis = split_requirements(PRD)
    print(f"[analysis] 需求点={len(analysis.points)}")

    base = run("rules", settings, analysis, args.count, use_ai=False)
    base_m = metrics(base)

    ai_m = None
    if not settings.has_key:
        print("\n[跳过 AI] 未配置 API Key，无法运行 AI 增强对照。")
    else:
        try:
            ai = run("ai", settings, analysis, args.count, use_ai=True)
            ai_m = metrics(ai)
        except LLMError as e:
            print(f"\n[AI 失败] {e}")
        except Exception as e:  # 网络/配额等异常不应中断对照
            print(f"\n[AI 异常] {type(e).__name__}: {e}")

    print("\n================ A/B 对照结果 ================")
    keys = list(base_m.keys())
    w = max(len(k) for k in keys) + 2
    print(f"{'指标'.ljust(w)}{'rules':>18}{'ai':>18}")
    print("-" * (w + 36))
    for k in keys:
        a = str(base_m[k])
        b = str(ai_m[k]) if ai_m else "—"
        print(f"{k.ljust(w)}{a:>18}{b:>18}")

    print("\n--- 样例步骤（各引擎首条）---")
    if base["cases"]:
        print(f"rules: {str(base['cases'][0].get('steps'))[:100]}")
    print("\nAB_DONE")


if __name__ == "__main__":
    main()
