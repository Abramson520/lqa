"""参考案例 few-shot 列名识别契约测试（新「测试执行表」格式）。

锁定：load_few_shots 必须能识别 主模块/子模块/测试说明/复现路径/预期结果
这类执行表列名（而不仅限旧的 模块/功能点/步骤/预期结果），并把
主模块+子模块 自动拼成 module 路径。
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from lqa.llm import load_few_shots  # noqa: E402


def _make_new_format_xlsx(path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "用例编号": "LOC-001",
                "主模块": "娱乐板块-咱俩练练",
                "子模块": "大厅入口",
                "测试说明": "校验未选中态文案本地化显示",
                "前置条件": "1.已登录",
                "复现路径": "1.进入战略板\n2.确认未选中\n3.检查入口文案完整性",
                "本地化检查项": "术语一致",
                "预期结果": "1.翻译准确\n2.无截断",
                "实际结果": "",
                "测试人": "",
                "不通过原因": "",
                "测试环境": "",
                "备注": "重点看溢出",
            },
            {
                "用例编号": "LOC-002",
                "主模块": "娱乐板块-咱俩练练",
                "子模块": "创建房间",
                "测试说明": "短步骤不会入选",
                "前置条件": "1.已进入大厅",
                "复现路径": "点创建房间",
                "预期结果": "显示占位符",
            },
        ]
    )
    df.to_excel(path, index=False)


def test_new_format_columns_recognized():
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / "case_library"
        lib.mkdir()
        _make_new_format_xlsx(lib / "ref.xlsx")
        shots = load_few_shots(lib, limit=8)
    # 至少一条来自参考表，且 module 由 主模块/子模块 拼成
    matched = [c for c in shots if c.get("module") == "娱乐板块-咱俩练练/大厅入口"]
    assert matched, "新格式参考表未被识别为 few-shot"
    c = matched[0]
    assert c["feature"] == "校验未选中态文案本地化显示"
    assert "复现路径" not in c["steps"]  # 列名不应泄漏进值
    assert "进入战略板" in c["steps"]
    assert "翻译准确" in c["expected"]


def test_short_steps_filtered_out():
    with tempfile.TemporaryDirectory() as td:
        lib = Path(td) / "case_library"
        lib.mkdir()
        _make_new_format_xlsx(lib / "ref.xlsx")
        shots = load_few_shots(lib, limit=8)
    # LOC-002 步骤过短，不应入选
    assert not any(
        c.get("module") == "娱乐板块-咱俩练练/创建房间" for c in shots
    ), "步骤过短的用例不应作为 few-shot"


if __name__ == "__main__":
    test_new_format_columns_recognized()
    test_short_steps_filtered_out()
    print("test_fewshot_columns: PASS")
