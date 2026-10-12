# -*- coding: utf-8 -*-
"""Skill 多格式支持契约测试（JSON / Markdown / YAML 探测启用）。

覆盖 src/lqa/skills.py 的格式注册表机制：
- Markdown front-matter 技能的读 / 列举 / prompt 注入
- 同 id 多格式优先级（json > md > yaml）与去重
- 写侧格式语义：create 指定格式、update 不迁移格式、delete 全覆盖
- 跨格式同名冲突拒绝、未知格式拒绝
- 坏文件 fail-soft（front-matter 未闭合不影响其他技能）
- YAML 注册与 PyYAML 可用性一致（探测启用，无硬依赖）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from lqa import skills as skills_mod


def _cleanup(root: Path, *names: str) -> None:
    """清理测试技能的所有候选格式文件，保证用例之间无残留。"""
    for n in names:
        for ext in (".json", ".md", ".yaml", ".yml"):
            f = root / f"{n}{ext}"
            if f.exists():
                f.unlink()


def _yaml_available() -> bool:
    """探测 PyYAML 是否可用（返回 True 时保证 safe_load/safe_dump 可调用）。"""
    try:
        import yaml

        return callable(yaml.safe_load) and callable(yaml.safe_dump)
    except ImportError:
        return False


# ---------- Markdown 读取 ----------

def test_md_skill_is_readable():
    """手写的 .md 技能（front-matter + 正文）必须被完整读出为同构 dict。"""
    root = ROOT / "skills"
    sid = "tmp-md-readable"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.md").write_text(
            "---\n"
            "id: tmp-md-readable\n"
            "name: RTL 布局要点\n"
            "description: 从右至左布局检查\n"
            "tags: rtl, layout\n"
            "---\n"
            "\n"
            "- 检查 RTL 下图标镜像\n"
            "- 检查占位符方向\n",
            encoding="utf-8",
        )
        item = skills_mod.get_skill(sid, root=root)
        assert item["id"] == sid
        assert item["name"] == "RTL 布局要点"
        assert item["description"] == "从右至左布局检查"
        assert item["tags"] == ["rtl", "layout"]
        assert "图标镜像" in item["body"]
        # 列表页也必须收录
        assert any(s["id"] == sid for s in skills_mod.list_skills(root=root))
    finally:
        _cleanup(root, sid)


def test_md_skill_injects_into_prompt():
    """md 技能与 json 技能一样必须能注入提示词（端到端可用）。"""
    from lqa.generate import build_user_prompt
    from lqa.analysis import split_requirements

    root = ROOT / "skills"
    sid = "tmp-md-inject"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-md-inject\nname: 支付边界\n---\n\n必须覆盖：退款窗口、重复扣款。\n",
            encoding="utf-8",
        )
        sk = skills_mod.get_skill(sid, root=root)
        analysis = split_requirements("【支付】\n1. 退款功能\n")
        user = build_user_prompt(
            analysis,
            count=5,
            modules=[],
            categories=["TEXT_OVERFLOW"],
            source_lang="en-US",
            target_lang="de-DE",
            extra="",
            skeleton=[],
            selected_skills=[sk],
        )
        assert "重复扣款" in user, "md 技能正文必须注入 user prompt"
        assert "支付边界" in user, "md 技能名必须可见"
    finally:
        _cleanup(root, sid)


# ---------- 同 id 唯一性与优先级 ----------

def test_json_wins_over_md_for_same_id():
    """同 id 多格式共存时读/列按注册优先级取 json，且列表去重为一条。"""
    root = ROOT / "skills"
    sid = "tmp-multi-priority"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.json").write_text(
            '{"id": "tmp-multi-priority", "name": "来自JSON", "body": "json正文"}',
            encoding="utf-8",
        )
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-multi-priority\nname: 来自MD\n---\n\nmd正文\n",
            encoding="utf-8",
        )
        assert skills_mod.get_skill(sid, root=root)["name"] == "来自JSON"
        listed = [s for s in skills_mod.list_skills(root=root) if s["id"] == sid]
        assert len(listed) == 1, "同 id 在列表中只能出现一次"
        assert listed[0]["name"] == "来自JSON"
    finally:
        _cleanup(root, sid)


# ---------- 写侧格式语义 ----------

def test_create_with_md_format():
    """create_skill(fmt='md') 必须落盘 .md 且读回一致。"""
    root = ROOT / "skills"
    sid = "tmp-create-md"
    _cleanup(root, sid)
    try:
        created = skills_mod.create_skill(
            name="md创建技能",
            body="- 检查点一\n- 检查点二",
            description="d",
            tags=["a"],
            skill_key=sid,
            fmt="md",
            root=root,
        )
        assert created["id"] == sid
        assert (root / f"{sid}.md").exists(), "必须落盘为 .md"
        assert not (root / f"{sid}.json").exists(), "不得顺带生成 .json"
        fetched = skills_mod.get_skill(sid, root=root)
        assert fetched["name"] == "md创建技能"
        assert fetched["body"] == "- 检查点一\n- 检查点二"
        assert fetched["tags"] == ["a"]
    finally:
        _cleanup(root, sid)


def test_update_preserves_original_format():
    """更新必须写回原文件格式，不迁移为 json。"""
    root = ROOT / "skills"
    sid = "tmp-update-md"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-update-md\nname: 原名\n---\n\n原正文\n", encoding="utf-8"
        )
        updated = skills_mod.update_skill(sid, name="新名", root=root)
        assert updated["name"] == "新名"
        assert (root / f"{sid}.md").exists(), "更新后仍应是 .md"
        assert not (root / f"{sid}.json").exists(), "不得生成 .json"
        assert skills_mod.get_skill(sid, root=root)["name"] == "新名"
    finally:
        _cleanup(root, sid)


def test_delete_removes_all_formats():
    """删除必须清掉该 id 的所有格式文件，且幂等。"""
    root = ROOT / "skills"
    sid = "tmp-delete-multi"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.json").write_text(
            '{"id":"tmp-delete-multi","name":"n","body":"b"}', encoding="utf-8"
        )
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-delete-multi\nname: n\n---\n\nb\n", encoding="utf-8"
        )
        assert skills_mod.delete_skill(sid, root=root) is True
        assert not (root / f"{sid}.json").exists()
        assert not (root / f"{sid}.md").exists()
        assert skills_mod.delete_skill(sid, root=root) is False, "重复删除应幂等"
    finally:
        _cleanup(root, sid)


def test_create_conflict_across_formats():
    """已有任一格式的同 id 文件时，创建必须报 FileExistsError（409 语义）。"""
    root = ROOT / "skills"
    sid = "tmp-conflict"
    _cleanup(root, sid)
    try:
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-conflict\nname: n\n---\n\nb\n", encoding="utf-8"
        )
        try:
            skills_mod.create_skill(
                name="n2", body="b2", skill_key=sid, fmt="md", root=root
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("跨格式同名冲突未被拦截")
    finally:
        _cleanup(root, sid)


def test_unsupported_format_rejected():
    """未注册的格式名必须 fail-closed 拒绝（ValueError → API 422）。"""
    root = ROOT / "skills"
    try:
        skills_mod.create_skill(name="n", body="b", fmt="toml", root=root)
    except ValueError:
        pass
    else:
        raise AssertionError("未知格式未被拒绝")


# ---------- fail-soft ----------

def test_broken_md_frontmatter_skipped():
    """front-matter 未闭合的 .md 必须被跳过，且不影响其他技能。"""
    root = ROOT / "skills"
    sid = "tmp-md-broken"
    good = "tmp-md-good"
    _cleanup(root, sid, good)
    try:
        (root / f"{sid}.md").write_text(
            "---\nid: tmp-md-broken\nname: 没闭合\n", encoding="utf-8"
        )
        (root / f"{good}.json").write_text(
            '{"id":"tmp-md-good","name":"好技能","body":"b"}', encoding="utf-8"
        )
        listed = skills_mod.list_skills(root=root)
        assert not any(s["id"] == sid for s in listed), "坏 md 应被跳过"
        assert any(s["id"] == good for s in listed), "好技能必须不受影响"
    finally:
        _cleanup(root, sid, good)


# ---------- YAML（运行时探测） ----------

def test_yaml_registration_matches_availability():
    """YAML 注册与否必须与 PyYAML 可用性一致；json/md 必须始终注册。"""
    fmts = skills_mod.available_formats()
    assert ("yaml" in fmts) == _yaml_available(), "注册状态必须与 PyYAML 可用性一致"
    assert "json" in fmts and "md" in fmts, "json/md 必须始终注册"


def test_yaml_roundtrip_when_available():
    """装有 PyYAML 时 .yaml 技能必须可创建/读回，且落盘内容是合法 YAML。"""
    if not _yaml_available():
        return
    import yaml

    root = ROOT / "skills"
    sid = "tmp-yaml-rt"
    _cleanup(root, sid)
    try:
        created = skills_mod.create_skill(
            name="yaml技能", body="- 检查点", skill_key=sid, fmt="yaml", root=root
        )
        assert created["id"] == sid
        assert (root / f"{sid}.yaml").exists(), "必须落盘为 .yaml"
        assert not (root / f"{sid}.json").exists()
        # 落盘内容必须是可被 YAML 解析器读回的合法 YAML（而非伪装格式）
        raw = yaml.safe_load((root / f"{sid}.yaml").read_text(encoding="utf-8"))
        assert raw["name"] == "yaml技能"
        assert raw["body"] == "- 检查点"
        fetched = skills_mod.get_skill(sid, root=root)
        assert fetched["name"] == "yaml技能"
        assert fetched["body"] == "- 检查点"
    finally:
        _cleanup(root, sid)


def test_list_skills_reports_source_format():
    """list_skills 每项须带 fmt 字段（该技能文件的落盘格式），供前端展示。"""
    root = ROOT / "skills"
    sid = "tmp-fmt-meta"
    _cleanup(root, sid)
    try:
        skills_mod.create_skill(name="元数据", body="- 检查点", skill_key=sid, fmt="md", root=root)
        item = next(i for i in skills_mod.list_skills(root=root) if i["id"] == sid)
        assert item["fmt"] == "md", "落盘为 md 的技能须上报 fmt=md"
    finally:
        _cleanup(root, sid)


def test_api_skills_list_reports_available_formats():
    """/api/skills 须携带 formats（当前注册的格式名），前端据此启用/禁用格式选项。"""
    import api_server
    from fastapi.testclient import TestClient

    cl = TestClient(api_server.app)
    fmts = cl.get("/api/skills").json()["formats"]
    assert "json" in fmts and "md" in fmts, "json/md 必须始终注册"
    assert ("yaml" in fmts) == ("yaml" in skills_mod.available_formats()), \
        "API 上报的 formats 必须与注册表一致"


if __name__ == "__main__":
    test_md_skill_is_readable()
    test_md_skill_injects_into_prompt()
    test_json_wins_over_md_for_same_id()
    test_create_with_md_format()
    test_update_preserves_original_format()
    test_delete_removes_all_formats()
    test_create_conflict_across_formats()
    test_unsupported_format_rejected()
    test_broken_md_frontmatter_skipped()
    test_yaml_registration_matches_availability()
    test_yaml_roundtrip_when_available()
    test_list_skills_reports_source_format()
    test_api_skills_list_reports_available_formats()
    print("ALL PASS")
