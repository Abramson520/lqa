# -*- coding: utf-8 -*-
"""领域测试知识包（Skill）：可命名、可复用、可持久化的 QA 领域知识。

设计要点
--------
- **通用能力，不硬编码业务**：本模块只提供「知识条目的存取与渲染」机制，
  领域内容全部由用户在技能库中自行创建，代码里不预置任何业务知识。
- **fail-closed 的落盘边界**：技能 id 一律强制 slug 化，杜绝 ``../`` 穿越与
  路径分隔符落盘；文件名由 id 决定而非用户输入，用户输入的 name 只作为内容字段。
- **fail-soft 的读取边界**：单个损坏文件不应让整个技能库不可用，
  读取时跳过坏文件并保留其余技能（列表页仍可渲染）。

持久化格式：``skills/<id>.json``，便于团队共享（git 跟踪）与人工审阅。
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parents[2]
SKILLS_DIR = BASE / "skills"

#: 技能正文长度上限。skill 会被完整注入 prompt，过长会挤压 token 预算并稀释指令。
MAX_BODY_CHARS = 4000
MAX_NAME_CHARS = 60
MAX_TAGS = 12

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def skills_root(root: Path | None = None) -> Path:
    """返回技能根目录；未显式指定时用项目内 skills/。"""
    return Path(root) if root is not None else SKILLS_DIR


def skill_id(name: str) -> str:
    """把任意名称规范化为安全 slug（ASCII、小写、连字符分隔）。

    非 ASCII（如中文）会被音译或直接剥离，因此中文名可能退化为空串——
    此时调用方需自行提供 id（见 create_skill 的 fallback）。
    """
    text = unicodedata.normalize("NFKD", name or "")
    ascii_text = text.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_text).strip("-")
    return slug


def _fallback_id(body_or_name: str) -> str:
    """当名称无法 slug 化（如纯中文）时，用内容哈希生成稳定 id。"""
    import hashlib

    seed = (body_or_name or "").strip() or "skill"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"skill-{digest}"


def _ensure_safe_id(raw: str) -> str:
    """校验并返回一个安全的技能 id，非法输入直接抛错（fail-closed）。"""
    s = skill_id(raw)
    if not s or ".." in s or "/" in s or "\\" in s:
        raise ValueError(f"非法技能 id: {raw!r}")
    return s


def _path_for(sid: str, root: Path | None = None) -> Path:
    """由已规范化的 id 解析落盘路径，并二次确认结果未逃逸出技能目录。"""
    base = skills_root(root).resolve()
    target = (base / f"{sid}.json").resolve()
    if target.parent != base:
        raise ValueError(f"技能路径越界: {sid!r}")
    return target


def _read_one(path: Path) -> dict[str, Any] | None:
    """读取单个技能文件；坏文件返回 None（fail-soft，不抛异常）。

    坏文件包含：JSON 损坏、结构非 dict、id 非法（如含路径分隔符或 ".."）——
    单个坏文件不得影响 list_skills 对其余文件的列举。
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        sid = _ensure_safe_id(str(data.get("id") or path.stem))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return {
        "id": sid,
        "name": str(data.get("name") or sid),
        "description": str(data.get("description") or ""),
        "body": str(data.get("body") or ""),
        "tags": [str(t) for t in (data.get("tags") or []) if str(t).strip()][:MAX_TAGS],
        "updated_at": str(data.get("updated_at") or ""),
    }


def _validate(name: str, body: str) -> tuple[str, str]:
    """校验名称与正文；非法输入 fail-closed 抛 ValueError。"""
    clean_name = (name or "").strip()
    clean_body = (body or "").strip()
    if not clean_name:
        raise ValueError("技能名称不能为空")
    if not clean_body:
        raise ValueError("技能正文不能为空（该内容会注入 AI 提示词）")
    if len(clean_name) > MAX_NAME_CHARS:
        raise ValueError(f"技能名称过长（上限 {MAX_NAME_CHARS} 字）")
    if len(clean_body) > MAX_BODY_CHARS:
        raise ValueError(f"技能正文过长（上限 {MAX_BODY_CHARS} 字）")
    return clean_name, clean_body


def _write(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def list_skills(root: Path | None = None) -> list[dict[str, Any]]:
    """列出全部技能；损坏文件被跳过，不影响其余技能。"""
    base = skills_root(root)
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(base.glob("*.json")):
        item = _read_one(p)
        if item:
            out.append(item)
    return out


def get_skill(sid: str, root: Path | None = None) -> dict[str, Any]:
    """按 id 读取技能；不存在抛 KeyError（调用方转 404）。"""
    safe = _ensure_safe_id(sid)
    item = _read_one(_path_for(safe, root))
    if item is None:
        raise KeyError(safe)
    return item


def create_skill(
    name: str,
    body: str,
    *,
    description: str = "",
    tags: list[str] | None = None,
    skill_key: str = "",
    root: Path | None = None,
) -> dict[str, Any]:
    """新建技能。skill_key 可显式指定 id；否则由名称 slug 化，空则回退哈希。"""
    clean_name, clean_body = _validate(name, body)
    base = skill_key.strip() or clean_name
    sid = skill_id(base) or _fallback_id(clean_body)
    safe = _ensure_safe_id(sid)
    path = _path_for(safe, root)
    if path.exists():
        raise FileExistsError(f"技能已存在: {safe}")
    payload = {
        "id": safe,
        "name": clean_name,
        "description": (description or "").strip(),
        "body": clean_body,
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()][:MAX_TAGS],
    }
    return _write(path, payload)


def update_skill(
    sid: str,
    *,
    name: str | None = None,
    body: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """更新技能；未传的字段保留原值（避免 PATCH 语义下的意外清空）。"""
    safe = _ensure_safe_id(sid)
    path = _path_for(safe, root)
    current = _read_one(path)
    if current is None:
        raise KeyError(safe)
    merged = dict(current)
    if name is not None or body is not None:
        merged["name"], merged["body"] = _validate(
            name if name is not None else current["name"],
            body if body is not None else current["body"],
        )
    if description is not None:
        merged["description"] = description.strip()
    if tags is not None:
        merged["tags"] = [str(t).strip() for t in tags if str(t).strip()][:MAX_TAGS]
    merged["id"] = safe
    return _write(path, merged)


def delete_skill(sid: str, root: Path | None = None) -> bool:
    """删除技能；返回是否实际删除（幂等）。"""
    safe = _ensure_safe_id(sid)
    path = _path_for(safe, root)
    if not path.exists():
        return False
    path.unlink()
    return True


def resolve_skills(
    skill_ids: list[str] | None, root: Path | None = None
) -> list[dict[str, Any]]:
    """把 id 列表解析为技能对象；未知/非法 id 被静默忽略（向前兼容）。

    前端可能因缓存持有已删除技能的 id，此处不应因此让整个生成请求失败。
    """
    if not skill_ids:
        return []
    out: list[dict[str, Any]] = []
    for raw in skill_ids:
        try:
            out.append(get_skill(raw, root=root))
        except (ValueError, KeyError):
            continue
    return out


def render_skills_block(skills: list[dict[str, Any]]) -> str:
    """把选中技能渲染为可注入 prompt 的文本块；无技能返回空串。"""
    if not skills:
        return ""
    lines = ["## 领域测试知识包（由用户选定，必须遵守）"]
    for s in skills:
        head = f"### {s['name']}"
        if s.get("description"):
            head += f" —— {s['description']}"
        lines.append(head)
        lines.append(s["body"].strip())
    return "\n\n".join(lines)