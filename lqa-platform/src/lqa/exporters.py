# -*- coding: utf-8 -*-
"""Excel 导出：对齐团队测试执行表格式。

参考格式（`三角洲咱俩练练本地化测试用例.xlsx`）为「测试执行表」：
- 14 列，两级模块（主模块 / 子模块），编号 `LOC-001`
- 多行文本统一用 `1. 2. 3.`（点后无空格）编号换行书写
- 「本地化检查项」= 通用 4 条 + 类别特有项
- 执行期字段（截图 / 实际结果 / 测试人 / 不通过原因 / 测试环境）留空，由执行人填写

设计边界：本模块只做**导出层字段映射**，不改变 `src/lqa` 的生成与质量逻辑；
执行期字段一律留空，不臆造执行结果。
"""
from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

import pandas as pd

#: 对齐参考执行表的列结构（顺序即导出顺序，不可随意变更）
LOC_COLUMNS = [
    "用例编号",
    "主模块",
    "子模块",
    "测试说明",
    "前置条件",
    "复现路径",
    "入口截图 / 测试截图",
    "本地化检查项",
    "预期结果",
    "实际结果",
    "测试人",
    "不通过原因",
    "测试环境",
    "备注",
]

#: 每条用例都适用的通用检查项（取自参考表的固定 4 条）
GENERIC_CHECKS = [
    "文案翻译准确，无硬编码字符串",
    "文本无截断/溢出/挤压 UI 控件",
    "标点符号渲染正常",
    "切换客户端语言，文案同步更新",
]

#: 类别特有检查项：由 LQA 类别体系派生，保证与生成逻辑的检查点一致
CATEGORY_CHECKS: dict[str, list[str]] = {
    "TEXT_OVERFLOW": ["长文案下文本截断/省略号表现符合设计"],
    "LAYOUT": ["控件无重叠/错位，布局不破版"],
    "FONT": ["无缺失字形或 tofu（□）方块"],
    "ENCODING": ["无乱码（??? / mojibake）"],
    "TERMINOLOGY": ["同一概念在界面各处译法一致"],
    "PUNCTUATION": ["标点与空格符合目标语言规范"],
    "DATE_FORMAT": ["日期/数字/货币格式符合目标语言习惯"],
    "CULTURAL": [
        "无宗教/政治/军事等敏感元素",
        "无赌博/博彩/烟酒等受限内容直出",
        "符合目标市场年龄分级与内容审查",
        "无地域/种族/性别等歧视或刻板印象",
        "图标/色彩/数字无目标市场禁忌",
    ],
    "PLACEHOLDER": ["{xxx} 占位符已被正确替换"],
    "IMAGE_TEXT": ["图内文字/硬编码文案已本地化"],
    "VOICE_SUB": ["字幕与语音时长及内容对齐"],
    "RTL": ["RTL 镜像方向与图标位置正确"],
    "FONT_MISSING": ["字体缺失时回退表现正常"],
    "LINE_BREAK": ["换行断句符合语言禁则"],
    "OTHER": ["按需求点逐条核对"],
}

_NUMBERED_LINE = re.compile(r"^\s*\d+[.、)]\s*")


def _numbered(value: object) -> str:
    """把多行/多段文本规范成 `1. 2. 3.` 编号换行格式（点后无空格，对齐参考表）。

    已带编号的行原样保留编号；顿号/分号分隔的单行会被拆分为多行。
    """
    text = str(value or "").strip()
    if not text:
        return ""
    # 已是多行格式：逐行清洗，丢弃空行
    if "\n" in text:
        parts = [ln.strip() for ln in text.splitlines() if ln.strip()]
    else:
        # 单行：优先按换行型分隔符拆分，再按分号/顿号兜底
        parts = [p.strip() for p in re.split(r"[；;]\s*|、(?=[^、]{4,})", text) if p.strip()]
    out: list[str] = []
    for i, part in enumerate(parts, 1):
        # 已带编号则去掉原编号，统一由本函数重新编号，避免出现「1. 1. xxx」
        body = _NUMBERED_LINE.sub("", part).strip()
        if body:
            out.append(f"{i}.{body}")
    return "\n".join(out)


def _split_module(module: object) -> tuple[str, str]:
    """把模块串拆成（主模块, 子模块）。

    `娱乐板块-咱俩练练/大厅入口` -> ("娱乐板块-咱俩练练", "大厅入口")
    无分隔符时主模块保持原值、子模块留空（不臆造层级）。
    """
    text = str(module or "").strip()
    if not text:
        return "", ""
    if "/" not in text and "\\" not in text:
        return text, ""
    normalized = text.replace("\\", "/")
    main, _, rest = normalized.partition("/")
    return main.strip(), rest.strip("/").strip()


def _localization_checks(category: object) -> str:
    """生成本地化检查项：通用 4 条 + 类别特有项，统一编号返回。

    未知类别退化为仅通用检查项，不抛异常。
    """
    key = str(category or "").strip().upper()
    items = list(GENERIC_CHECKS)
    items.extend(CATEGORY_CHECKS.get(key, []))
    # 去重但保持顺序
    seen: set[str] = set()
    unique = [it for it in items if not (it in seen or seen.add(it))]
    return "\n".join(f"{i}.{it}" for i, it in enumerate(unique, 1))


def _expected_text(case: dict) -> str:
    """预期结果：保留原编号格式，缺省时回退到本地化检查项。"""
    text = _numbered(case.get("expected"))
    return text or _localization_checks(case.get("category"))


def _test_statement(case: dict) -> str:
    """测试说明：规范化已有描述；缺失时由功能点合成一句可读描述。"""
    text = str(case.get("feature") or "").strip()
    if text:
        return text
    cat = str(case.get("category") or "").strip()
    _, sub = _split_module(case.get("module"))
    return f"校验{sub or '目标界面'}的{cat or '本地化'}显示"


def cases_to_dataframe(cases: list[dict], id_prefix: str = "LOC") -> pd.DataFrame:
    """把内部用例结构映射为参考执行表的 DataFrame。

    执行期字段（截图/实际结果/测试人/不通过原因/测试环境）一律留空，由执行人填写。
    """
    prefix = (id_prefix or "LOC").strip().upper()
    rows = []
    for i, c in enumerate(cases, 1):
        main, sub = _split_module(c.get("module"))
        rows.append(
            {
                "用例编号": f"{prefix}-{i:03d}",
                "主模块": main,
                "子模块": sub,
                "测试说明": _test_statement(c),
                "前置条件": _numbered(c.get("preconditions")),
                "复现路径": _numbered(c.get("steps")),
                # 执行期字段留空，供测试执行时填写
                "入口截图 / 测试截图": "",
                "本地化检查项": _localization_checks(c.get("category")),
                "预期结果": _expected_text(c),
                "实际结果": "",
                "测试人": "",
                "不通过原因": "",
                "测试环境": "",
                "备注": str(c.get("notes") or ""),
            }
        )
    return pd.DataFrame(rows, columns=LOC_COLUMNS)


def to_xlsx_bytes(
    cases: list[dict], sheet_name: str = "本地化测试用例", id_prefix: str = "LOC"
) -> bytes:
    df = cases_to_dataframe(cases, id_prefix=id_prefix)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buf.getvalue()


def save_output(
    cases: list[dict],
    *,
    name: str,
    out_root: Path,
    reports: dict | None = None,
) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch for ch in (name or "需求") if ch not in '\\/:*?"<>|')[:40]
    folder = out_root / f"{ts}_{safe}"
    folder.mkdir(parents=True, exist_ok=True)
    xlsx_path = folder / f"本地化测试用例_{safe}.xlsx"
    xlsx_path.write_bytes(to_xlsx_bytes(cases))
    meta = folder / "generation_meta.json"
    import json

    meta.write_text(
        json.dumps({"name": name, "count": len(cases), "cases": cases}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 质量层报告：覆盖率 / 需求缺口审查 / 质量门禁（有则落盘，不影响主流程）
    if reports:
        _write_if(reports.get("coverage_markdown"), folder / "覆盖率报告.md")
        _write_if(reports.get("gap_review_summary"), folder / "需求缺口审查.md")
        _write_if(reports.get("quality_markdown"), folder / "质量门禁.md")
    return folder


def _write_if(content: object, path: Path) -> None:
    if isinstance(content, str) and content.strip():
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            pass
