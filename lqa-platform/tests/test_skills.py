# -*- coding: utf-8 -*-
"""Skill 领域测试知识包契约测试。

覆盖 src/lqa/skills.py（数据层）与 api_server.py（HTTP 契约）两处行为：
- 技能的 CRUD、文件持久化、名称规范化与路径安全
- 选中技能如何注入 AI 生成提示词
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lqa import skills as skills_mod
from lqa.generate import build_user_prompt
from lqa.analysis import split_requirements
from lqa.llm import build_system_prompt


# ---------- 数据层 ----------

def test_slug_strips_non_ascii_and_keeps_readable_part():
    """中英混合名保留可读的英文部分；中文部分被丢弃（不产生乱码文件名）。"""
    assert skills_mod.skill_id("Season Pass 测试要点") == "season-pass"
    assert skills_mod.skill_id("RTL 专项") == "rtl"
    # 路径分隔符绝不能进入 id
    assert "/" not in skills_mod.skill_id("/api 技能")


def test_skill_id_normalization_is_safe():
    """技能 id 必须强制 slug 化，杜绝 ../ 穿越与路径分隔符。"""
    # 中英混合 → 非 ASCII 剥离后得到可读 slug
    assert skills_mod.skill_id("RTL 专项 / v2") == "rtl-v2"
    assert skills_mod.skill_id("Season Pass") == "season-pass"
    # 纯中文无法音译，必须退化为空（由 create_skill 回退为哈希 id）
    assert skills_mod.skill_id("赛季通行证") == ""
    # 危险字符必须被剥离而不是保留
    assert "/" not in skills_mod.skill_id("../../etc/passwd")
    assert ".." not in skills_mod.skill_id("../../etc/passwd")
    assert skills_mod.skill_id("") == ""
    assert skills_mod.skill_id("///") == ""


def test_skill_id_ensure_rejects_traversal():
    """_ensure_safe_id 必须 fail-closed：slug 化为空的输入一律拒绝。"""
    # 危险字符在 slug 化阶段即被剥离/替换，产物本身是安全 slug
    assert skills_mod._ensure_safe_id("../../etc/passwd") == "etc-passwd"
    assert skills_mod._ensure_safe_id("a/b") == "a-b"
    # 真正必须拒绝的：slug 化后为空（无法形成合法文件名）
    for bad in ("..", "/", "///", "   ", "???", "赛季通行证"):
        try:
            skills_mod._ensure_safe_id(bad)
        except ValueError:
            continue
        raise AssertionError(f"未拒绝无法 slug 化的 id: {bad!r}")


def test_path_resolution_cannot_escape_skills_dir():
    """落盘路径必须锁在 skills/ 内，二次确认防逃逸。"""
    root = ROOT / "skills"
    p = skills_mod._path_for("safe-name", root=root)
    assert p.parent == root.resolve()
    # 危险 id 无法通过 _ensure_safe_id，因此也无法构造出越界路径
    try:
        skills_mod._path_for("../../escape", root=root)
    except ValueError:
        pass
    else:
        raise AssertionError("越界路径未被拦截")


def test_pure_chinese_name_falls_back_to_hash_id():
    """纯中文名无法 slug 化时，必须生成稳定可用的回退 id，而不是落盘失败。"""
    root = ROOT / "skills"
    a = skills_mod.create_skill("赛季通行证", "正文一", root=root)
    try:
        assert a["id"].startswith("skill-")
        assert a["name"] == "赛季通行证"
        # 同名同正文 → 同 id（稳定性），不同正文 → 不同 id
        b = skills_mod.create_skill("赛季通行证二", "正文二", root=root)
        assert b["id"] != a["id"]
        skills_mod.delete_skill(a["id"], root=root)
        skills_mod.delete_skill(b["id"], root=root)
    finally:
        for s in skills_mod.list_skills(root=root):
            if s["id"].startswith("skill-"):
                skills_mod.delete_skill(s["id"], root=root)


def test_skill_roundtrip_create_read_update_delete():
    """完整生命周期：新建 → 读 → 改 → 删，磁盘状态一致。"""
    root = ROOT / "skills"
    sid = "tmp-contract-roundtrip"
    try:
        created = skills_mod.create_skill(
            name="测试技能",
            description="契约测试用",
            body="重点检查 RTL 布局与占位符。",
            tags=["rtl"],
            skill_key=sid,
            root=root,
        )
        assert created["id"] == sid
        assert created["name"] == "测试技能"
        assert created["body"] == "重点检查 RTL 布局与占位符。"
        assert created["tags"] == ["rtl"]

        fetched = skills_mod.get_skill(sid, root=root)
        assert fetched["name"] == "测试技能"

        listed = skills_mod.list_skills(root=root)
        assert any(s["id"] == sid for s in listed)

        updated = skills_mod.update_skill(
            sid, name="改名了", body="新的知识正文", root=root
        )
        assert updated["name"] == "改名了"
        assert updated["body"] == "新的知识正文"
        # 未传的字段应保留，而不是被清空
        assert updated["tags"] == ["rtl"]

        skills_mod.delete_skill(sid, root=root)
        assert not (root / f"{sid}.json").exists()
        assert not any(s["id"] == sid for s in skills_mod.list_skills(root=root))
    finally:
        f = root / f"{sid}.json"
        if f.exists():
            f.unlink()


def test_list_skills_survives_corrupt_file():
    """单个损坏文件不能让整个技能库读取失败（fail-soft）。"""
    root = ROOT / "skills"
    sid = "tmp-contract-corrupt"
    try:
        skills_mod.create_skill(
            name="好文件", body="x", skill_key=sid, root=root
        )
        (root / "tmp-contract-broken.json").write_text("{ 坏掉的 json", encoding="utf-8")
        listed = skills_mod.list_skills(root=root)
        assert any(s["id"] == sid for s in listed), "损坏文件不应影响其他技能读出"
    finally:
        for name in ("tmp-contract-corrupt.json", "tmp-contract-broken.json"):
            f = root / name
            if f.exists():
                f.unlink()


# ---------- AI 注入 ----------

def test_selected_skills_inject_into_prompt():
    """选中的技能必须真正进入生成提示词（这是 skill 功能的核心价值）。"""
    root = ROOT / "skills"
    sid = "tmp-contract-inject"
    try:
        skills_mod.create_skill(
            name="赛季通行证专项",
            description="赛季体系检查要点",
            body="必须覆盖：赛季结算边界、奖励领取时效、跨赛季叠加规则。",
            skill_key=sid,
            root=root,
        )
        sk = skills_mod.get_skill(sid, root=root)
        analysis = split_requirements("【商城系统】\n1. 赛季通行证礼包展示\n")
        user = build_user_prompt(
            analysis,
            count=8,
            modules=[],
            categories=["TEXT_OVERFLOW"],
            source_lang="en-US",
            target_lang="de-DE",
            extra="",
            skeleton=[],
            selected_skills=[sk],
        )
        assert "赛季结算边界" in user, "技能正文必须注入 user prompt"
        assert "赛季通行证专项" in user, "技能名必须可见，便于模型对齐语境"

        system = build_system_prompt(None, selected_skills=[sk])
        assert "赛季结算边界" in system, "技能正文也必须注入 system prompt"
    finally:
        f = root / f"{sid}.json"
        if f.exists():
            f.unlink()


def test_no_skills_selected_keeps_prompt_clean():
    """未选技能时不得留下空占位段，避免污染模型输入。"""
    analysis = split_requirements("【商城系统】\n1. 商店展示\n")
    user = build_user_prompt(
        analysis,
        count=5,
        modules=[],
        categories=["TEXT_OVERFLOW"],
        source_lang="en-US",
        target_lang="de-DE",
        extra="",
        skeleton=[],
        selected_skills=[],
    )
    assert "## 领域测试知识包" not in user
    system = build_system_prompt(None, selected_skills=[])
    assert "## 领域测试知识包" not in system


# ---------- HTTP 契约 ----------

def test_http_skill_crud_roundtrip():
    """HTTP 层 CRUD 契约：建/列/读/改/删 + 非法输入拒绝。"""
    from fastapi.testclient import TestClient

    import api_server
    from lqa import skills as sm

    client = TestClient(api_server.app)
    key = "tmp-http-contract"
    # 用显式 key 避免 slug 化碰撞，结束时确保清理
    sm.delete_skill(key)

    # 建
    r = client.post(
        "/api/skills",
        json={
            "name": "HTTP 契约技能",
            "body": "正文要点",
            "description": "d",
            "tags": ["x"],
            "skill_key": key,
        },
    )
    assert r.status_code in (200, 201), r.text
    created = r.json()
    assert created["name"] == "HTTP 契约技能"
    assert created["id"] == key

    # 列表（前端首屏依赖）
    r = client.get("/api/skills")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["skills"], list)
    assert any(s["id"] == key for s in body["skills"])

    # 读
    r = client.get(f"/api/skills/{key}")
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "正文要点"

    # 改（PATCH 语义：未传字段保留）
    r = client.put(f"/api/skills/{key}", json={"name": "改名后"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "改名后"
    assert r.json()["body"] == "正文要点", "未传的 body 必须保留"
    assert r.json()["tags"] == ["x"], "未传的 tags 必须保留"

    # 删
    r = client.delete(f"/api/skills/{key}")
    assert r.status_code == 200, r.text
    assert r.json()["removed"] is True

    # 幂等：重复删除不应 500
    r = client.delete(f"/api/skills/{key}")
    assert r.status_code in (200, 404), r.text

    # 读已删除 → 404 而非 500
    r = client.get(f"/api/skills/{key}")
    assert r.status_code == 404, r.text


def test_http_rejects_illegal_skill_payload():
    from fastapi.testclient import TestClient

    import api_server

    client = TestClient(api_server.app)
    # 空技能名必须被拒，而不是静默落盘
    r = client.post("/api/skills", json={"name": "   ", "body": "b"})
    assert r.status_code == 422, r.text
    # 空正文没有注入价值，应被拒
    r = client.post("/api/skills", json={"name": "n", "body": ""})
    assert r.status_code == 422, r.text
    # 超长正文应被拒（skill 会完整进 prompt，必须有上限）
    r = client.post("/api/skills", json={"name": "n", "body": "x" * 5000})
    assert r.status_code == 422, r.text
    # 更新不存在的技能 → 404
    r = client.put("/api/skills/tmp-not-exist", json={"name": "x"})
    assert r.status_code == 404, r.text


def test_http_generation_accepts_skill_ids():
    """生成链路必须能接收 skill_ids；未知 id 向前兼容（忽略而非报错）。"""
    from fastapi.testclient import TestClient

    import api_server

    client = TestClient(api_server.app)
    r = client.post(
        "/api/generate",
        json={
            "text": "【商城系统】\n1. 商店展示\n",
            "count": 5,
            "use_ai": False,
            "skill_ids": ["tmp-does-not-exist"],
        },
    )
    assert r.status_code == 200, r.text


if __name__ == "__main__":
    test_skill_id_normalization_is_safe()
    test_slug_strips_non_ascii_and_keeps_readable_part()
    test_skill_id_ensure_rejects_traversal()
    test_path_resolution_cannot_escape_skills_dir()
    test_pure_chinese_name_falls_back_to_hash_id()
    test_skill_roundtrip_create_read_update_delete()
    test_list_skills_survives_corrupt_file()
    test_selected_skills_inject_into_prompt()
    test_no_skills_selected_keeps_prompt_clean()
    test_http_skill_crud_roundtrip()
    test_http_rejects_illegal_skill_payload()
    test_http_generation_accepts_skill_ids()
    print("ALL PASS")