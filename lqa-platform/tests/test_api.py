# -*- coding: utf-8 -*-
"""Web API 契约测试：锁定前端依赖的接口形状（形状变更即失败）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import api_server
from lqa.categories import CATEGORIES, CORE_CATEGORIES, PRIORITIES
from lqa.generate import _balanced_top

client = TestClient(api_server.app)

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

# 导出/预览都依赖这些字段，缺一即前端渲染破窗
REQUIRED_CASE_FIELDS = (
    "module",
    "feature",
    "category",
    "priority",
    "source_lang",
    "target_lang",
    "source_text",
    "target_text",
    "preconditions",
    "steps",
    "expected",
    "quality_score",
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_meta_exposes_full_category_system():
    """前端首屏要一次性拿到类别/语言/优先级，避免多轮往返。"""
    r = client.get("/api/meta")
    assert r.status_code == 200, r.text
    data = r.json()

    assert set(data["categories"].keys()) == set(CATEGORIES.keys())
    assert data["priorities"] == list(PRIORITIES)
    assert "core_categories" in data
    assert set(data["core_categories"]) == set(CORE_CATEGORIES)
    # 语言列表供给前端下拉框，需带中文标签而非裸 code
    codes = [lang["code"] for lang in data["languages"]]
    assert "en-US" in codes
    assert "de-DE" in codes
    assert all("label" in lang for lang in data["languages"])
    assert isinstance(data["defaults"], dict)
    assert {"provider", "count", "source_lang", "target_lang"} <= set(data["defaults"])


def test_analyze_returns_points_and_modules():
    r = client.post("/api/analyze", json={"text": SAMPLE})
    assert r.status_code == 200, r.text
    data = r.json()

    assert len(data["points"]) >= 4
    assert any("商城" in m or "邮件" in m for m in data["modules"])
    # 每个需求点必须是 {index, module, text} 形状，前端直接渲染表格
    for p in data["points"]:
        assert {"index", "module", "text"} <= set(p.keys())
    assert data["points"][0]["index"] == 1


def test_generate_rules_mode_returns_normalized_cases():
    r = client.post(
        "/api/generate",
        json={
            "text": SAMPLE,
            "source_lang": "en-US",
            "target_lang": "de-DE",
            "count": 8,
            "categories": ["TEXT_OVERFLOW", "PLACEHOLDER", "LAYOUT", "TERMINOLOGY"],
            "use_ai": False,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["generator"] == "rules"
    assert len(data["cases"]) > 0
    for c in data["cases"]:
        assert all(f in c for f in REQUIRED_CASE_FIELDS), f"缺字段: {c.keys()}"
        # 自定义类别（非内置 code）同样合法，不再强制 OTHER
        assert isinstance(c["category"], str) and c["category"]
        assert isinstance(c["quality_score"], int)

    gate = data["gate"]
    assert {"count", "issue_count", "issues", "avg_score", "pass"} <= set(gate.keys())
    assert gate["count"] == len(data["cases"])


def test_generate_rejects_empty_input():
    r = client.post("/api/generate", json={"text": "   ", "use_ai": False})
    assert r.status_code == 400, r.text
    assert "需求" in r.json()["detail"]


def test_generate_ai_without_key_is_refused_not_crash():
    """勾选 AI 但无 Key 时必须是清晰报错，不能 500。"""
    r = client.post(
        "/api/generate",
        json={"text": SAMPLE, "use_ai": True, "api_key": ""},
    )
    assert r.status_code == 400, r.text
    assert "Key" in r.json()["detail"]


def test_generate_respects_count_cap():
    """count 作为目标规模硬约束：输出条数不超过 count，且字段完整（覆盖均衡不影响接口形状）。"""
    r = client.post(
        "/api/generate",
        json={
            "text": SAMPLE,
            "source_lang": "en-US",
            "target_lang": "de-DE",
            "count": 4,
            "categories": ["TEXT_OVERFLOW", "PLACEHOLDER", "LAYOUT", "TERMINOLOGY", "FONT", "RTL", "GRAPHICS"],
            "use_ai": False,
        },
    )
    assert r.status_code == 200, r.text
    cases = r.json()["cases"]
    assert len(cases) <= 4, f"超出目标规模: {len(cases)}"
    for c in cases:
        assert all(f in c for f in REQUIRED_CASE_FIELDS), f"缺字段: {c.keys()}"


def test_balanced_top_keeps_low_quality_module_when_room():
    """覆盖均衡：即便某模块质量最低，只要有名额就保留（对比纯质量截断会丢它）。"""
    cases = [
        {"module": "A", "category": "x", "quality_score": 90},
        {"module": "B", "category": "y", "quality_score": 80},
        {"module": "C", "category": "z", "quality_score": 10},
        {"module": "D", "category": "w", "quality_score": 70},
    ]
    out = _balanced_top(cases, 4)
    assert {c["module"] for c in out} == {"A", "B", "C", "D"}
    assert len(out) == 4


def test_balanced_top_respects_count_when_modules_exceed():
    """覆盖优先但规模硬约束：模块数超过 count 时，取质量最高的 count 个模块。"""
    cases = [{"module": f"M{i}", "category": "c", "quality_score": i} for i in range(10)]
    out = _balanced_top(cases, 3)
    assert len(out) == 3
    assert {c["module"] for c in out} == {"M9", "M8", "M7"}


def test_export_returns_real_xlsx():
    gen = client.post(
        "/api/generate",
        json={"text": SAMPLE, "count": 4, "use_ai": False},
    )
    cases = gen.json()["cases"]

    r = client.post("/api/export", json={"cases": cases, "task_name": "冒烟"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(XLSX_MIME)
    # xlsx 本质是 zip，魔数必须是 PK
    assert r.content[:2] == b"PK"


def test_export_rejects_empty_cases():
    r = client.post("/api/export", json={"cases": [], "task_name": "空"})
    assert r.status_code == 400, r.text


def test_parse_upload_md_and_reject_unsupported():
    ok = client.post(
        "/api/parse",
        files={"file": ("需求.md", SAMPLE.encode("utf-8"), "text/markdown")},
    )
    assert ok.status_code == 200, ok.text
    assert "限时礼包" in ok.json()["text"]

    bad = client.post(
        "/api/parse",
        files={"file": ("恶意.exe", b"MZ\x90\x00", "application/octet-stream")},
    )
    assert bad.status_code == 400, bad.text
    assert "不支持" in bad.json()["detail"]


def test_case_library_lists_files():
    data = client.get("/api/case-library").json()
    assert "files" in data
    assert isinstance(data["files"], list)


def test_root_serves_frontend():
    r = client.get("/")
    assert r.status_code == 200, r.text
    assert "LQA" in r.text


def test_shutdown_rejected_without_server_instance():
    """TestClient 模式下 _uvicorn_server 为 None：接口应拒绝并指引用 stop_web.bat，绝不裸退出。"""
    r = client.post("/api/shutdown")
    assert r.status_code == 400, r.text
    assert "stop_web.bat" in r.json()["detail"]


if __name__ == "__main__":
    test_meta_exposes_full_category_system()
    test_analyze_returns_points_and_modules()
    test_generate_rules_mode_returns_normalized_cases()
    test_generate_rejects_empty_input()
    test_generate_ai_without_key_is_refused_not_crash()
    test_generate_respects_count_cap()
    test_balanced_top_keeps_low_quality_module_when_room()
    test_balanced_top_respects_count_when_modules_exceed()
    test_export_returns_real_xlsx()
    test_export_rejects_empty_cases()
    test_parse_upload_md_and_reject_unsupported()
    test_case_library_lists_files()
    test_root_serves_frontend()
    test_shutdown_rejected_without_server_instance()
    print("ALL PASS")
