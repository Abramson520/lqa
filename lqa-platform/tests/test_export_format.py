# -*- coding: utf-8 -*-
r"""导出格式契约测试：锁定「执行表」列结构与字段映射规则。

参考格式：C:\Users\zhang\Desktop\三角洲咱俩练练本地化测试用例.xlsx
（测试执行表，14 列，LOC- 编号，两级模块，多行文本用「1. 2. 3.」编号换行）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lqa.exporters import (
    LOC_COLUMNS,
    cases_to_dataframe,
    to_xlsx_bytes,
    _numbered,
    _split_module,
    _localization_checks,
)

# 项目内部用例样例（字段名为 src/lqa 的既有 schema）
SAMPLE_CASE = {
    "module": "娱乐板块-咱俩练练/大厅入口",
    "feature": "校验【咱俩练练】未选中态，左侧列表及入口区域全部UI文案本地化显示",
    "category": "TEXT_OVERFLOW",
    "priority": "P1",
    "source_lang": "en-US",
    "target_lang": "zh-CN",
    "source_text": "Join Room",
    "target_text": "加入房间",
    "preconditions": "1.账号正常登录游戏客户端\n2.可正常进入战略板大厅",
    "steps": "1.进入【战略板】\n2.确认【咱俩练练】处于未选中状态\n3.检查入口区域全部可见文案",
    "expected": "1.目标语言下文案翻译准确\n2.文本完整显示，无截断",
    "notes": "",
}


def test_columns_match_reference_exactly():
    """导出列必须与参考执行表一致（14 列，顺序不可变）。"""
    assert list(LOC_COLUMNS) == [
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
    ], f"列结构不符：{list(LOC_COLUMNS)}"


def test_case_id_uses_loc_prefix():
    """用例编号用 LOC-001 递增（前缀可配置但默认 LOC）。"""
    df = cases_to_dataframe([SAMPLE_CASE, SAMPLE_CASE], id_prefix="LOC")
    assert list(df["用例编号"]) == ["LOC-001", "LOC-002"]


def test_module_splits_into_two_levels():
    """「娱乐板块-咱俩练练/大厅入口」须拆为主模块 + 子模块。"""
    assert _split_module("娱乐板块-咱俩练练/大厅入口") == ("娱乐板块-咱俩练练", "大厅入口")
    # 无斜杠时，主模块保持原值，子模块留空而非编造
    assert _split_module("商城系统") == ("商城系统", "")
    # 多级斜杠：取第一段作主模块，其余并入子模块
    assert _split_module("A/B/C") == ("A", "B/C")
    # 空值安全
    assert _split_module("") == ("", "")
    assert _split_module(None) == ("", "")


def test_numbered_normalizes_to_numbered_lines():
    """多行文本必须规范成「1. 2. 3.」编号格式（点后无空格，对齐参考表）。"""
    # 已带编号的原样保留（重新编号，去掉旧编号避免「1. 1. xxx」）
    assert _numbered("1. 第一\n2. 第二") == "1.第一\n2.第二"
    # 无编号的按行补编号
    assert _numbered("检查A\n检查B") == "1.检查A\n2.检查B"
    # 顿号/分号分隔的单行拆成多行
    assert _numbered("文案准确；无硬编码；不截断") == "1.文案准确\n2.无硬编码\n3.不截断"
    # 空值返回空串
    assert _numbered("") == ""
    assert _numbered(None) == ""


def test_preconditions_and_steps_keep_numbering():
    """前置条件与复现路径必须保留编号换行格式。"""
    df = cases_to_dataframe([SAMPLE_CASE])
    row = df.iloc[0]
    assert row["前置条件"] == SAMPLE_CASE["preconditions"]
    assert row["复现路径"] == SAMPLE_CASE["steps"]


def test_localization_checks_contain_category_specific_item():
    """本地化检查项须含通用 4 条 + 类别特有项（来自 LQA 类别体系）。"""
    checks = _localization_checks("TEXT_OVERFLOW")
    assert "文案翻译准确" in checks
    assert "硬编码" in checks
    assert "截断" in checks or "溢出" in checks
    # 类别特有项必须体现
    assert "截断" in checks or "溢出" in checks
    # 必须是编号多行格式
    assert checks.splitlines()[0].startswith("1.")


def test_unknown_category_falls_back_gracefully():
    """未知类别不得抛异常，退化为通用检查项。"""
    checks = _localization_checks("SOME_UNKNOWN_CATEGORY")
    assert checks
    assert checks.splitlines()[0].startswith("1.")


def test_execution_columns_blank_for_tester():
    """执行期字段（实际结果/测试人/不通过原因/测试环境/截图）必须留空。"""
    df = cases_to_dataframe([SAMPLE_CASE])
    row = df.iloc[0]
    for col in ("入口截图 / 测试截图", "实际结果", "测试人", "不通过原因", "测试环境"):
        assert (row[col] == "" or row[col] is None), f"{col} 应留空，实际={row[col]!r}"


def test_xlsx_export_uses_reference_columns():
    """导出 xlsx 的列必须与参考表一致（前端下载的表能被直接使用）。"""
    import io

    import pandas as pd

    data = to_xlsx_bytes([SAMPLE_CASE], id_prefix="LOC")
    df = pd.read_excel(io.BytesIO(data))
    assert list(df.columns) == list(LOC_COLUMNS), f"导出列不符：{list(df.columns)}"
    assert len(df) == 1
    assert df.iloc[0]["用例编号"] == "LOC-001"


if __name__ == "__main__":
    test_columns_match_reference_exactly()
    test_case_id_uses_loc_prefix()
    test_module_splits_into_two_levels()
    test_numbered_normalizes_to_numbered_lines()
    test_preconditions_and_steps_keep_numbering()
    test_localization_checks_contain_category_specific_item()
    test_unknown_category_falls_back_gracefully()
    test_execution_columns_blank_for_tester()
    test_xlsx_export_uses_reference_columns()
    print("ALL PASS")