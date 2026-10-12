# -*- coding: utf-8 -*-
"""需求-用例覆盖率报告（借鉴 plasA coverage.build_coverage_report）。

纯函数，不依赖重库。计算需求点↔用例覆盖率、模块统计、高风险缺口，并渲染 Markdown。
需求点 id 取 R001（= RequirementPoint.index）；用例通过 requirement_source 关联。
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from .analysis import AnalysisResult

# 涉及这些维度的未覆盖需求点标记为高风险缺口（支付/账号/合规敏感）
_HIGH_RISK_KEYWORDS = re.compile(
    r"支付|充值|购买|领取|兑换|账号|登录|权限|宗教|政治|军事|分级|禁忌|赌博|博彩|烟酒"
    r"|未成年|隐私|数据|暴力|色情|乱码|缺字|溢出"
)


def _split_src(value: str) -> list[str]:
    return [s.strip() for s in str(value or "").replace("+", ",").split(",") if s.strip()]


def _norm_id(value: str) -> str:
    """id 归一化键——去连字符/下划线 + 大小写折叠，吸收 AI 书写变体。"""
    return "".join(ch for ch in str(value) if ch not in "-_ \t").upper()


def build_coverage_report(analysis: AnalysisResult, cases: list[dict]) -> dict[str, Any]:
    """计算需求-用例覆盖率报告。"""
    points = list((analysis or AnalysisResult(raw_text="")).points)
    req_index = {f"R{p.index:03d}": p for p in points}
    # 别名归一（r001/R-001 -> R001）；同一归一键对应多个不同 id 时置 None 放弃别名匹配
    alias: dict[str, str | None] = {}
    for rid in req_index:
        key = _norm_id(rid)
        if key in alias:
            alias[key] = None
        else:
            alias[key] = rid

    def resolve(pid: str) -> str | None:
        if pid in req_index:
            return pid
        return alias.get(_norm_id(pid))

    req_cases: dict[str, list[str]] = defaultdict(list)
    unlinked: list[str] = []
    for i, c in enumerate(cases or [], 1):
        cid = f"#{i}"
        ids = _split_src(c.get("requirement_source") or "")
        valid = [r for r in (resolve(pid) for pid in ids) if r]
        if not valid:
            if ids:
                unlinked.append(cid)
            continue
        for pid in valid:
            req_cases[pid].append(cid)

    items: list[dict[str, Any]] = []
    for p in points:
        rid = f"R{p.index:03d}"
        case_ids = sorted(set(req_cases.get(rid, [])))
        covered = bool(case_ids)
        items.append({
            "id": rid,
            "module": (p.module or "").strip(),
            "point": (p.text or "").strip(),
            "covered": covered,
            "case_count": len(case_ids),
            "case_ids": case_ids,
            "risk": (not covered) and bool(_HIGH_RISK_KEYWORDS.search(p.text or "")),
        })

    uncovered = [it for it in items if not it["covered"]]
    high_risk = [
        {"id": it["id"], "module": it["module"], "point": it["point"]}
        for it in uncovered if it["risk"]
    ]

    module_agg: dict[str, dict[str, int]] = defaultdict(
        lambda: {"requirements": 0, "covered_requirements": 0, "cases": 0}
    )
    for it in items:
        agg = module_agg[it["module"] or "未归类"]
        agg["requirements"] += 1
        if it["covered"]:
            agg["covered_requirements"] += 1
        agg["cases"] += it["case_count"]
    module_stats = []
    for module, agg in sorted(module_agg.items()):
        total = agg["requirements"]
        covered_reqs = agg["covered_requirements"]
        module_stats.append({
            "module": module,
            "requirements": total,
            "covered_requirements": covered_reqs,
            "cases": agg["cases"],
            "coverage_rate": round(covered_reqs / total * 100, 1) if total else 0.0,
        })

    total_reqs = len(items)
    covered_reqs = total_reqs - len(uncovered)
    linked = len(cases or []) - len(set(unlinked))
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_requirements": total_reqs,
        "covered_requirements": covered_reqs,
        "uncovered_count": len(uncovered),
        "coverage_rate": round(covered_reqs / total_reqs * 100, 1) if total_reqs else None,
        "total_cases": len(cases or []),
        "linked_cases": linked,
        "unlinked_cases": unlinked,
        "high_risk_gaps": high_risk,
        "requirements": items,
        "module_stats": module_stats,
    }


def render_coverage_markdown(report: dict[str, Any]) -> str:
    """把覆盖率报告渲染为 Markdown。"""
    total = report.get("total_requirements") or 0
    covered = report.get("covered_requirements") or 0
    rate = report.get("coverage_rate")
    rate_text = f"{rate}%" if rate is not None else "—"

    lines = ["# 需求-用例覆盖率报告", ""]
    lines.append(f"- 生成时间：{report.get('generated_at', '')}")
    lines.append(f"- 需求覆盖率：**{rate_text}**（{covered}/{total} 个原子需求点）")
    lines.append(
        f"- 用例总数：{report.get('total_cases', 0)}"
        f"（其中 {report.get('linked_cases', 0)} 条已关联需求点）"
    )

    unlinked = report.get("unlinked_cases") or []
    if unlinked:
        shown = "、".join(unlinked[:20])
        more = f" 等 {len(unlinked)} 条" if len(unlinked) > 20 else ""
        lines.append(f"- ⚠️ 未关联需求点的用例：{shown}{more}")

    module_stats = report.get("module_stats") or []
    if module_stats:
        lines += [
            "", "## 模块覆盖统计", "",
            "| 模块 | 需求点 | 已覆盖 | 覆盖率 | 关联用例数 |",
            "|------|--------|--------|--------|------------|",
        ]
        for row in module_stats:
            lines.append(
                f"| {row['module']} | {row['requirements']} | "
                f"{row['covered_requirements']} | {row['coverage_rate']}% | {row['cases']} |"
            )

    high_risk = report.get("high_risk_gaps") or []
    gaps = [it for it in (report.get("requirements") or []) if not it["covered"]]
    if high_risk:
        lines += ["", "## ⚠️ 高风险覆盖缺口（涉及支付/账号/合规等敏感维度）", ""]
        for it in high_risk:
            lines.append(f"- **{it['id']}** [{it['module']}] {it['point']}")
            lines.append("  - 建议：补充针对该需求点的正向与异常用例后再交付。")

    if gaps:
        lines += [
            "", f"## 覆盖缺口清单（共 {len(gaps)} 个）", "",
            "| 需求ID | 模块 | 需求点 | 风险 |",
            "|--------|------|--------|------|",
        ]
        for it in gaps:
            risk = "⚠️ 高" if it.get("risk") else ""
            point = str(it.get("point") or "").replace("|", "\\|")
            lines.append(f"| {it['id']} | {it['module']} | {point} | {risk} |")
    elif total:
        lines += ["", "## ✅ 覆盖结论", "", "全部原子需求点均已被用例覆盖，无缺口。"]

    lines.append("")
    return "\n".join(lines)
