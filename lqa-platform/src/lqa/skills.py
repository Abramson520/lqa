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

多格式持久化
------------
技能可按注册格式落盘：``json``（默认，便于 git diff）/ ``md``（front-matter，
人工最易写）/ ``yaml``（运行时探测 PyYAML，**未安装则不注册**，不引入硬依赖）。
所有格式读入后归一化为同一内部 dict（id/name/description/body/tags/updated_at），
上层（prompt 注入 / API / 前端）不感知格式差异。

同一 id 视为一个逻辑实体：读与列举按注册顺序取第一个（json > md > yaml）并去重；
更新写回原文件所在格式（不迁移）；删除清掉该 id 的全部格式文件。
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


# --------------------------------------------------------------------------
# 格式注册表：新增一种格式只需在这里加一个「parse / dump / exts / errors」
# 四元组类，读写主逻辑（_read_one/_write/list/get/create/update/delete）不变。
# dict 插入序即优先级：同 id 多格式并存时，排前者赢。
# --------------------------------------------------------------------------


class _JsonFormat:
    """JSON：标准库序列化，默认落盘格式（git diff 友好）。"""

    exts = (".json",)
    errors: tuple[type[BaseException], ...] = (ValueError,)

    @staticmethod
    def parse(text: str) -> dict[str, Any] | None:
        data = json.loads(text)
        return data if isinstance(data, dict) else None

    @staticmethod
    def dump(payload: dict[str, Any]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


class _MarkdownFormat:
    """Markdown + 极简 front-matter：``---`` 包裹的 ``key: value`` 行 + 正文。

    解析契约（fail-soft，与坏 JSON 同语义）：
    - 首行必须为 ``---``，且存在第二个 ``---`` 闭合行，否则整个文件判坏；
    - front-matter 行按**首个冒号**切分（值含冒号不会破坏解析）；
    - ``tags`` 值为逗号分隔字符串，归一化为 list；
    - 正文取第二个 ``---`` 之后的全部内容（首尾空行剥离）。
    """

    exts = (".md",)
    errors: tuple[type[BaseException], ...] = (ValueError,)

    @staticmethod
    def parse(text: str) -> dict[str, Any] | None:
        lines = (text or "").splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is None:
            return None  # front-matter 未闭合 → 判坏文件
        data: dict[str, Any] = {}
        for line in lines[1:end]:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
        raw_tags = data.get("tags")
        if isinstance(raw_tags, str):
            data["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
        data["body"] = "\n".join(lines[end + 1 :]).strip("\n")
        return data

    @staticmethod
    def dump(payload: dict[str, Any]) -> str:
        lines = ["---"]
        for key in ("id", "name", "description"):
            lines.append(f"{key}: {payload.get(key) or ''}")
        tags = payload.get("tags") or []
        lines.append("tags: " + ", ".join(str(t) for t in tags))
        lines.append(f"updated_at: {payload.get('updated_at') or ''}")
        lines.append("---")
        lines.append("")
        lines.append(str(payload.get("body") or "").strip())
        lines.append("")
        return "\n".join(lines)


def _yaml_format() -> type | None:
    """探测 PyYAML 是否可用；可用才返回 YAML 格式类（不引入硬依赖）。"""
    try:
        import yaml
    except ImportError:
        return None

    class _YamlFormat:
        exts = (".yaml", ".yml")
        errors: tuple[type[BaseException], ...] = (ValueError, yaml.YAMLError)

        @staticmethod
        def parse(text: str) -> dict[str, Any] | None:
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else None

        @staticmethod
        def dump(payload: dict[str, Any]) -> str:
            return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)

    return _YamlFormat


def _build_formats() -> dict[str, type]:
    """构建格式注册表。dict 插入序即同 id 优先级（先注册先赢）。"""
    fmts: dict[str, type] = {"json": _JsonFormat, "md": _MarkdownFormat}
    yf = _yaml_format()
    if yf is not None:
        fmts["yaml"] = yf
    return fmts


#: 模块级注册表（import 时探测一次）。测试可通过直接改写本表验证探测行为。
_FORMATS: dict[str, type] = _build_formats()


def available_formats() -> list[str]:
    """返回当前已注册的格式名（按优先级排序）。供测试 / 前端 / 诊断使用。"""
    return list(_FORMATS.keys())


def _ext_to_fmt() -> dict[str, str]:
    """扩展名（小写）→ 格式名 的反查表。"""
    table: dict[str, str] = {}
    for fmt, cls in _FORMATS.items():
        for ext in cls.exts:
            table[ext] = fmt
    return table


def _fmt_for_path(path: Path) -> type | None:
    """按扩展名解析格式类；未注册扩展名返回 None（列举时跳过）。"""
    return _FORMATS.get(_ext_to_fmt().get(path.suffix.lower(), ""))


def _candidate_paths(sid: str, root: Path | None = None) -> list[Path]:
    """按注册优先级返回该 sid 的全部候选路径（越界即抛错，fail-closed）。"""
    base = skills_root(root).resolve()
    out: list[Path] = []
    for cls in _FORMATS.values():
        for ext in cls.exts:
            target = (base / f"{sid}{ext}").resolve()
            if target.parent != base:
                raise ValueError(f"技能路径越界: {sid!r}")
            out.append(target)
    return out


def _path_for(sid: str, root: Path | None = None, fmt: str = "json") -> Path:
    """由已规范化的 id 解析落盘路径（默认 json 语义），并二次确认未逃逸。"""
    cls = _FORMATS.get(fmt)
    if cls is None:
        raise ValueError(f"不支持的技能格式: {fmt}（可用: {', '.join(_FORMATS)}）")
    base = skills_root(root).resolve()
    target = (base / f"{sid}{cls.exts[0]}").resolve()
    if target.parent != base:
        raise ValueError(f"技能路径越界: {sid!r}")
    return target


def _locate(sid: str, root: Path | None = None) -> tuple[Path, type] | None:
    """按注册优先级定位该 sid 的现存文件；不存在返回 None。"""
    for p in _candidate_paths(sid, root):
        if p.exists():
            return p, _fmt_for_path(p)
    return None


def _read_one(path: Path) -> dict[str, Any] | None:
    """读取单个技能文件；坏文件 / 未注册扩展名返回 None（fail-soft，不抛异常）。

    坏文件包含：解析失败（JSON 损坏 / front-matter 未闭合 / YAML 错误）、
    结构非 dict、id 非法（如含路径分隔符或 ".."）——
    单个坏文件不得影响 list_skills 对其余文件的列举。
    """
    fmt_cls = _fmt_for_path(path)
    if fmt_cls is None:
        return None
    try:
        data = fmt_cls.parse(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        sid = _ensure_safe_id(str(data.get("id") or path.stem))
    except (OSError, ValueError, *fmt_cls.errors):
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


def _write(path: Path, payload: dict[str, Any], fmt: str) -> dict[str, Any]:
    """按指定格式落盘；updated_at 统一在写前刷新（各格式字段同构）。"""
    cls = _FORMATS.get(fmt)
    if cls is None:
        raise ValueError(f"不支持的技能格式: {fmt}（可用: {', '.join(_FORMATS)}）")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    path.write_text(cls.dump(payload), encoding="utf-8")
    return payload


def list_skills(root: Path | None = None) -> list[dict[str, Any]]:
    """列出全部技能（按注册格式优先级扫描，同 id 去重）；损坏文件被跳过。"""
    base = skills_root(root)
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cls in _FORMATS.values():
        for ext in cls.exts:
            for p in sorted(base.glob(f"*{ext}")):
                item = _read_one(p)
                if item and item["id"] not in seen:
                    seen.add(item["id"])
                    out.append(item)
    return out


def get_skill(sid: str, root: Path | None = None) -> dict[str, Any]:
    """按 id 读取技能；按注册优先级探测，全部不存在/损坏抛 KeyError（转 404）。"""
    safe = _ensure_safe_id(sid)
    for p in _candidate_paths(safe, root):
        if not p.exists():
            continue
        item = _read_one(p)
        if item is not None:
            return item
    raise KeyError(safe)


def create_skill(
    name: str,
    body: str,
    *,
    description: str = "",
    tags: list[str] | None = None,
    skill_key: str = "",
    fmt: str = "json",
    root: Path | None = None,
) -> dict[str, Any]:
    """新建技能。skill_key 可显式指定 id；否则由名称 slug 化，空则回退哈希。

    fmt 指定落盘格式（默认 json，向后兼容）；该 id 在**任一**已注册格式下
    已存在时抛 FileExistsError（跨格式同名同样视为冲突）。
    """
    fmt_key = (fmt or "json").lower().lstrip(".")
    if fmt_key not in _FORMATS:
        raise ValueError(f"不支持的技能格式: {fmt}（可用: {', '.join(_FORMATS)}）")
    clean_name, clean_body = _validate(name, body)
    base = skill_key.strip() or clean_name
    sid = skill_id(base) or _fallback_id(clean_body)
    safe = _ensure_safe_id(sid)
    if _locate(safe, root) is not None:
        raise FileExistsError(f"技能已存在: {safe}")
    payload = {
        "id": safe,
        "name": clean_name,
        "description": (description or "").strip(),
        "body": clean_body,
        "tags": [str(t).strip() for t in (tags or []) if str(t).strip()][:MAX_TAGS],
    }
    return _write(_path_for(safe, root, fmt_key), payload, fmt_key)


def update_skill(
    sid: str,
    *,
    name: str | None = None,
    body: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """更新技能；未传的字段保留原值（避免 PATCH 语义下的意外清空）。

    定位到的现存文件用什么格式，就写回什么格式（不迁移格式）。
    """
    safe = _ensure_safe_id(sid)
    located = _locate(safe, root)
    if located is None:
        raise KeyError(safe)
    path, _fmt_cls = located
    fmt_key = _ext_to_fmt().get(path.suffix.lower(), "")
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
    return _write(path, merged, fmt_key)


def delete_skill(sid: str, root: Path | None = None) -> bool:
    """删除技能（清掉该 id 的全部格式文件）；返回是否实际删除（幂等）。"""
    safe = _ensure_safe_id(sid)
    removed = False
    for p in _candidate_paths(safe, root):
        if p.exists():
            p.unlink()
            removed = True
    return removed


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
