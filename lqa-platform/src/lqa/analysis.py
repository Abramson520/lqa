# -*- coding: utf-8 -*-
"""本地需求拆解：抽出需求点与模块信号。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RequirementPoint:
    module: str
    text: str
    index: int


@dataclass
class AnalysisResult:
    raw_text: str
    points: list[RequirementPoint] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"需求点 {len(self.points)} 条 · 模块 {len(self.modules)} 个"


_HEADING = re.compile(r"^(#{1,6}\s+.+|\d+(\.\d+)*\s+\S+|第[一二三四五六七八九十\d]+[章节]|【.+】)")
# 仅收纳「功能模块」候选；不含"文案/界面/UI/系统/本地化"等含量词，
# 否则逐行嗅探会把"语言切换入口文案"错归到模块"文案"。
_MODULE_CANDIDATES = [
    "商城", "商店", "邮件", "背包", "角色", "英雄", "武器", "技能", "成就", "任务",
    "活动", "签到", "通行证", "设置", "登录", "主界面", "战斗", "剧情", "公告",
    "聊天", "好友", "公会", "帮会", "排行", "图鉴", "时装", "宠物", "载具",
    "枪械", "地图", "新手", "引导", "充值", "礼包", "兑换", "仓库", "组队",
]


def _guess_module(line: str, current: str) -> str:
    for m in _MODULE_CANDIDATES:
        if m in line:
            return m
    return current


def split_requirements(text: str, max_points: int = 80) -> AnalysisResult:
    text = (text or "").strip()
    result = AnalysisResult(raw_text=text)
    if not text:
        return result

    current_module = "通用"
    idx = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _HEADING.match(line):
            title = re.sub(r"^#+\s*", "", line)
            title = re.sub(r"^\d+(\.\d+)*\s+", "", title).strip("：: ")
            title_core = title.strip("【】[] ")
            current_module = _guess_module(title_core, current_module)[:32]
            # 纯章节/系统标题不当作需求点
            is_section = bool(
                re.match(r"^【.+】$", title)
                or re.match(r"^第[一二三四五六七八九十\d]+[章节]", title)
                or title.endswith(("章", "节", "系统", "模块", "功能"))
                or len(title_core) < 8
            )
            if (not is_section) and len(title) >= 8:
                if idx >= max_points:
                    break
                idx += 1
                result.points.append(
                    RequirementPoint(current_module, title, idx)
                )
            continue

        # 列表项 / 整句
        cleaned = re.sub(r"^[-*•·]\s+", "", line)
        cleaned = re.sub(r"^\d+[\.、)]\s*", "", cleaned).strip()
        if len(cleaned) < 4:
            continue
        mod = _guess_module(cleaned, current_module)
        idx += 1
        result.points.append(RequirementPoint(mod, cleaned, idx))
        if idx >= max_points:
            break

    # 去重模块列表
    seen = set()
    for p in result.points:
        if p.module not in seen:
            seen.add(p.module)
            result.modules.append(p.module)
    return result
