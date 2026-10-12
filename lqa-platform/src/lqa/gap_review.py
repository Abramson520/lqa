# -*- coding: utf-8 -*-
"""生成前需求缺口审查（借鉴 plasA review_requirement_gaps）。

纯正则、不依赖模型、不硬编码业务词表。阈值/词表来自本模块常量，支持 .env 覆盖。

在生成前扫描需求点，标出「拆不出可执行用例」的源头问题：
- vague_point    ：需求点过泛，缺具体对象/操作/结果
- no_bound       ：无数字/边界语义，等价类与边界值易落空
- no_exception   ：无失败/异常线索，异常用例只能靠猜
- no_precondition：无前置/资源/权限线索
- no_acceptance  ：无「显示/提示/状态」等可观察验收词
- image_only     ：仅图片占位、文字侧无法核对
- low_testability：上述信号缺 3 项以上，整体可测性不足
"""
from __future__ import annotations

import os
import re
from typing import Any

from .analysis import AnalysisResult


# 阈值与词表：集中于此，支持通过环境变量覆盖（空字符串可停用对应判定）
_MIN_POINT_LEN = int(os.getenv("LQA_GAP_MIN_POINT_LEN", "8"))
_VAGUE_PREFIX = re.compile(
    r"^(?:进行|完成|实现|支持|提供|优化|提升|完善|相关|若干|等)|(?:等相关|等等|之类)$"
)
_NUM_OR_BOUND = re.compile(
    r"\d|[%％]|上限|下限|至少|至多|不超过|不低于|次数|概率|比例|秒|ms|级|颗|次|个|元|金币|钻石"
)
_EXC_HINT = re.compile(
    r"失败|异常|错误|拒绝|拦截|超时|不足|非法|越权|重复|断网|为空|上限|溢出|乱码|缺字|豆腐|报错"
)
_PRE_HINT = re.compile(
    r"已|前置|条件|满足|拥有|解锁|等级|权限|准备|存在|登录|充值|领取|购买"
)
_ACCEPT_HINT = re.compile(
    r"显示|提示|置灰|弹窗|到账|扣减|跳转|返回|记录|日志|状态|展示|完整|正确|替换|一致|展示"
)
_IMG_MARK = re.compile(r"\[需求图片|!\[[^\]]*\]|\.png|\.jpg|\.jpeg|\.gif|\.webp", re.I)


def _point_id(p) -> str:
    return f"R{p.index:03d}"


def review_requirement_gaps(
    analysis: AnalysisResult | None,
    requirement_text: str = "",
    max_report: int = 20,
) -> list[dict[str, Any]]:
    """扫描原子需求点，返回缺口列表。

    每个缺口：{requirement_id, type, severity, detail}。severity ∈ high/medium/info。
    """
    gaps: list[dict[str, Any]] = []
    text = str(requirement_text or "")
    img_n = len(_IMG_MARK.findall(text))
    points = list((analysis or AnalysisResult(raw_text="")).points)

    for p in points:
        rid = _point_id(p)
        point = (p.text or "").strip()
        if not point:
            gaps.append({
                "requirement_id": rid, "type": "empty_point", "severity": "high",
                "detail": "需求点正文为空，无法生成可执行用例",
            })
            continue
        # 图片占位单独成点且无其它描述
        stripped = re.sub(r"\[需求图片\d+\]|!\[[^\]]*\]", "", point).strip()
        if _IMG_MARK.search(point) and len(stripped) < 8:
            gaps.append({
                "requirement_id": rid, "type": "image_only", "severity": "high",
                "detail": f"「{point[:40]}」以图片占位为主，请补充文字规则或启用视觉分析",
            })
            continue
        if len(point) < _MIN_POINT_LEN or _VAGUE_PREFIX.search(point):
            gaps.append({
                "requirement_id": rid, "type": "vague_point", "severity": "medium",
                "detail": f"需求点过泛：{point[:40]} — 缺少具体对象/操作/结果",
            })
        flags = []
        if not _NUM_OR_BOUND.search(point):
            flags.append("no_bound")
        if not _EXC_HINT.search(point):
            flags.append("no_exception")
        if not _PRE_HINT.search(point):
            flags.append("no_precondition")
        if not _ACCEPT_HINT.search(point):
            flags.append("no_acceptance")
        # 至少要有一类可测信号，否则报缺口
        if len(flags) >= 3:
            gaps.append({
                "requirement_id": rid, "type": "low_testability", "severity": "medium",
                "detail": (
                    f"可测性不足（缺 {','.join(flags)}）：{point[:36]} — "
                    "建议补充验收标准、异常与前置条件"
                ),
            })

    if img_n and not any(g["type"] == "image_only" for g in gaps):
        gaps.append({
            "requirement_id": "", "type": "has_images", "severity": "info",
            "detail": f"文档含 {img_n} 张图片占位；已配置视觉模型则会自动分析，否则请人工核对",
        })
    return gaps[:max_report]


def format_gap_summary(gaps: list[dict[str, Any]]) -> str:
    if not gaps:
        return "生成前缺口审查：未发现明显可测性缺口。"
    n_high = sum(1 for g in gaps if g.get("severity") == "high")
    n_med = sum(1 for g in gaps if g.get("severity") == "medium")
    lines = [f"生成前缺口审查：{len(gaps)} 项（高优 {n_high} / 中优 {n_med}）"]
    for g in gaps[:10]:
        lines.append(f"- [{g.get('type')}] {g.get('requirement_id') or '-'} {g.get('detail')}")
    return "\n".join(lines)
