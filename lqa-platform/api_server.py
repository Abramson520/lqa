# -*- coding: utf-8 -*-
"""LQA Web 工作台后端。

职责边界：仅做 HTTP 协议转换，**不复制任何业务逻辑**。
所有能力复用 src/lqa/（解析 / 拆解 / 规则 / LLM / 质量 / 导出），因此与早期
共享同一套结果，二者可长期并存、互为对照。

安全边界（本工具定位为本地单人使用，未引入鉴权）：
- 上传文件做扩展名白名单 + 体积上限，防止超大文件吃内存
- API Key 仅存在于请求体 / .env，响应一律返回脱敏值
- 写 .env 为「显式确认」行为，默认不落盘（详见 persist 参数）
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from lqa.analysis import split_requirements
from lqa.categories import (
    BILINGUAL_REQUIRED,
    CATEGORIES,
    CATEGORY_FOCUS,
    CORE_CATEGORIES,
    PRIORITIES,
)
from lqa.config import ENV_PATH, VALID_PROVIDERS, load_settings
from lqa.exporters import save_output, to_xlsx_bytes
from lqa.generate import generate
from lqa.llm import LLMError
from lqa.parsers import parse_upload
from lqa.quality import gate_report
from lqa import skills as skills_mod

WEB_DIR = ROOT / "web"
OUT_ROOT = ROOT / "outputs"
LIB_ROOT = ROOT / "case_library"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 超大 docx/xlsx 会整份读进内存，必须设上限
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

LANGUAGES: list[dict[str, str]] = [
    {"code": "en-US", "label": "英语（美国）"},
    {"code": "zh-CN", "label": "简体中文"},
    {"code": "zh-TW", "label": "繁体中文"},
    {"code": "ja-JP", "label": "日语"},
    {"code": "ko-KR", "label": "韩语"},
    {"code": "de-DE", "label": "德语"},
    {"code": "fr-FR", "label": "法语"},
    {"code": "es-ES", "label": "西班牙语"},
    {"code": "pt-BR", "label": "葡萄牙语（巴西）"},
    {"code": "ru-RU", "label": "俄语"},
    {"code": "ar-SA", "label": "阿拉伯语（RTL）"},
    {"code": "th-TH", "label": "泰语"},
    {"code": "tr-TR", "label": "土耳其语"},
    {"code": "id-ID", "label": "印尼语"},
]

LIB_SUFFIXES = {".xlsx", ".xls", ".md", ".txt", ".docx"}

app = FastAPI(title="LQA 工作台", version="1.0.0")

# 优雅退出：由 __main__ 在启动时注入当前 uvicorn.Server 实例；
# 测试 / `uvicorn api_server:app` 命令行启动时保持 None，此时 /api/shutdown 会拒绝并返回指引。
_uvicorn_server = None


# ---------------- 请求模型 ----------------
class AnalyzeIn(BaseModel):
    text: str


class ModelOverrides(BaseModel):
    """模型参数覆盖；留空则回落到 .env / 默认值。"""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


class GenerateIn(ModelOverrides):
    text: str
    task_name: str = "本地化需求"
    source_lang: str = "en-US"
    target_lang: str = "de-DE"
    count: int = Field(default=0, ge=0, description="目标条数；0 或不填表示不限制")
    categories: list[str] = Field(default_factory=list)
    extra: str = ""
    use_ai: bool = False
    skill_ids: list[str] = Field(default_factory=list)


class ExportIn(BaseModel):
    cases: list[dict]
    task_name: str = "需求"
    reports: dict | None = None


class SettingsTestIn(ModelOverrides):
    pass


class SettingsSaveIn(ModelOverrides):
    persist: bool = False


# ---------------- 内部工具 ----------------
def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "已配置"
    return f"{key[:4]}…{key[-4:]}"


def _settings_from(src: ModelOverrides):
    """用请求里的覆盖值构造 Settings；未提供的字段回落到 .env / 默认。"""
    return load_settings(
        provider=src.provider or None,
        base_url=src.base_url or None,
        api_key=src.api_key or None,
        model=src.model or None,
    )


def _public_dict(s) -> dict:
    """对外只暴露脱敏后的模型信息，绝不回传完整 Key。"""
    return {
        "provider": s.provider,
        "base_url": s.base_url,
        "model": s.model,
        "has_api_key": s.has_key,
        "api_key_masked": _mask(s.api_key),
        "temperature": s.temperature,
    }


def _read_env() -> dict[str, str]:
    """读取现有 .env 为 dict（忽略注释与空行）。"""
    if not ENV_PATH.is_file():
        return {}
    out: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _write_env(updates: dict[str, str]) -> None:
    """按键更新 .env，保留注释与其它变量，避免覆盖用户已有配置。"""
    lines = (
        ENV_PATH.read_text(encoding="utf-8").splitlines()
        if ENV_PATH.is_file()
        else []
    )
    handled: set[str] = set()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            out.append(line)
            continue
        k, _, _v = s.partition("=")
        k = k.strip()
        if k in updates:
            out.append(f"{k}={updates[k]}")
            handled.add(k)
        else:
            out.append(line)
    for k, v in updates.items():
        if k not in handled:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


# ---------------- 元信息 ----------------
@app.get("/api/meta")
def api_meta() -> dict:
    """首屏一次性拿到全部静态选项，避免多轮往返。"""
    s = load_settings()
    return {
        "categories": CATEGORIES,
        "category_focus": CATEGORY_FOCUS,
        "languages": LANGUAGES,
        "priorities": list(PRIORITIES),
        "core_categories": CORE_CATEGORIES,
        "bilingual_required": sorted(BILINGUAL_REQUIRED),
        "providers": list(VALID_PROVIDERS),
        "limits": {"max_upload_bytes": MAX_UPLOAD_BYTES, "max_count": 2000},
        "defaults": {
            "provider": s.provider,
            "base_url": s.base_url,
            "model": s.model,
            "count": 0,
            "source_lang": "en-US",
            "target_lang": "de-DE",
            "has_api_key": s.has_key,
            "api_key_masked": _mask(s.api_key),
        },
        "env_path": str(ENV_PATH),
    }


# ---------------- 上传解析 ----------------
@app.post("/api/parse")
async def api_parse(file: UploadFile = File(...)) -> dict:
    """上传需求文档 → 纯文本。不支持的类型直接 400，不静默吞异常。"""
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(data) / 1048576:.1f}MB），上限 {MAX_UPLOAD_BYTES // 1048576}MB",
        )
    try:
        text = parse_upload(file.filename or "", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": file.filename, "text": text, "chars": len(text)}


# ---------------- 需求拆解 ----------------
@app.post("/api/analyze")
def api_analyze(payload: AnalyzeIn) -> dict:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请先提供需求内容")
    analysis = split_requirements(text)
    if not analysis.points:
        raise HTTPException(
            status_code=400,
            detail="未能拆解出需求点，请检查内容是否为有效文本",
        )
    return {
        "summary": analysis.summary(),
        "modules": analysis.modules,
        "points": [
            {"index": p.index, "module": p.module, "text": p.text}
            for p in analysis.points
        ],
        "chars": len(text),
    }


# ---------------- 生成 ----------------
@app.post("/api/generate")
def api_generate(payload: GenerateIn) -> dict:
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请先上传需求文档或粘贴需求文本")

    settings = _settings_from(payload)
    if payload.use_ai and not settings.has_key:
        raise HTTPException(
            status_code=400,
            detail="未配置 API Key，无法启用 AI 补强（可取消勾选走规则生成）",
        )

    analysis = split_requirements(text)
    if not analysis.points:
        raise HTTPException(
            status_code=400,
            detail="未能拆解出需求点，无法生成用例，请检查文档内容",
        )

    try:
        result = generate(
            settings,
            analysis,
            source_lang=payload.source_lang,
            target_lang=payload.target_lang,
            modules=analysis.modules,
            categories=payload.categories,
            extra=payload.extra,
            use_ai=payload.use_ai,
            count=payload.count,
            case_library=LIB_ROOT,
            selected_skills=skills_mod.resolve_skills(payload.skill_ids),
        )
    except LLMError as e:
        # AI 失败不应中断：返回规则骨架 + 明确提示
        raise HTTPException(status_code=400, detail=f"AI 生成失败：{e}")
    except Exception as e:  # aqg: top-level boundary
        raise HTTPException(
            status_code=500, detail=f"生成失败：{type(e).__name__}: {e}"
        )

    cases = result["cases"]
    gate = result.get("gate") or gate_report(cases)
    return {
        "cases": cases,
        "generator": result.get("generator", ""),
        "ai_error": result.get("ai_error", ""),
        "model": result.get("model", ""),
        "analysis_summary": result.get("analysis_summary", analysis.summary()),
        "gate": gate,
        "avg_score": gate.get("avg_score", 0),
        "gap_review": result.get("gap_review", []),
        "gap_review_summary": result.get("gap_review_summary", ""),
        "quality_issues": result.get("quality_issues", []),
        "quality_markdown": result.get("quality_markdown", ""),
        "coverage": result.get("coverage"),
        "coverage_markdown": result.get("coverage_markdown", ""),
    }


# ---------------- 导出 / 保存 ----------------
@app.post("/api/export")
def api_export(payload: ExportIn) -> Response:
    if not payload.cases:
        raise HTTPException(status_code=400, detail="没有可导出的用例")
    try:
        data = to_xlsx_bytes(payload.cases)
    except Exception as e:  # aqg: top-level boundary
        raise HTTPException(
            status_code=500, detail=f"导出失败：{type(e).__name__}: {e}"
        )
    # HTTP 头仅支持 latin-1，中文文件名必须走 RFC 6266 编码：
    # ASCII 回退名 + filename*=UTF-8''<百分号编码>，否则直接 UnicodeEncodeError。
    cleaned = "".join(ch for ch in payload.task_name if ch not in '\\/:*?"<>|')[:40] or "LQA"
    ascii_name = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "-_") else "-" for ch in cleaned).strip("-")
    fallback = f"LQA_{ascii_name}" if ascii_name else "LQA_cases"
    quoted = quote(f"{cleaned}.xlsx")
    return Response(
        content=data,
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="{fallback}.xlsx"; filename*=UTF-8\'\'{quoted}',
            "Cache-Control": "no-store",
        },
    )


@app.post("/api/save")
def api_save(payload: ExportIn) -> dict:
    if not payload.cases:
        raise HTTPException(status_code=400, detail="没有可保存的用例")
    try:
        folder = save_output(
            payload.cases,
            name=payload.task_name,
            out_root=OUT_ROOT,
            reports=payload.reports,
        )
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"保存失败：{e}")
    return {"folder": str(folder), "count": len(payload.cases)}


# ---------------- 模型配置 ----------------
@app.post("/api/settings/test")
def api_settings_test(payload: SettingsTestIn) -> dict:
    """连通性探测：失败返回 ok=False + 原因，不抛 500（前端要稳定展示）。"""
    s = _settings_from(payload)
    if not s.has_key:
        return {"ok": False, "message": "未配置 API Key", "settings": _public_dict(s)}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=s.api_key, base_url=s.base_url, timeout=20)
        client.chat.completions.create(
            model=s.model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=4,
        )
        return {"ok": True, "message": "连通成功", "settings": _public_dict(s)}
    except Exception as e:
        return {
            "ok": False,
            "message": f"连通失败：{type(e).__name__}: {str(e)[:200]}",
            "settings": _public_dict(s),
        }


@app.post("/api/settings/save")
def api_settings_save(payload: SettingsSaveIn) -> dict:
    """可选持久化到 .env。

    仅在 persist=True 且提供了 Key 时写盘；写盘为**明文**，前端需显式告知用户。
    空值不覆盖已有配置，避免误清空。
    """
    s = _settings_from(payload)
    if not payload.persist:
        return {"persisted": False, "settings": _public_dict(s)}
    if not s.api_key:
        raise HTTPException(status_code=400, detail="未提供 API Key，拒绝写入 .env")

    updates = dict(_read_env())
    if s.provider:
        updates["LQA_PROVIDER"] = s.provider
    if s.model:
        updates["LQA_MODEL"] = s.model
    if s.base_url:
        updates["LQA_BASE_URL"] = s.base_url
    updates["LQA_API_KEY"] = s.api_key
    try:
        _write_env(updates)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"写入 .env 失败：{e}")
    return {
        "persisted": True,
        "path": str(ENV_PATH),
        "settings": {
            "provider": s.provider,
            "base_url": s.base_url,
            "model": s.model,
            "has_api_key": True,
            "api_key_masked": _mask(s.api_key),
        },
    }


# ---------------- 案例库 ----------------
@app.get("/api/case-library")
def api_case_library() -> dict:
    LIB_ROOT.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(LIB_ROOT.rglob("*")):
        if p.is_file() and p.suffix.lower() in LIB_SUFFIXES:
            st = p.stat()
            files.append(
                {
                    "name": str(p.relative_to(LIB_ROOT)),
                    "size": st.st_size,
                    "modified": datetime.fromtimestamp(st.st_mtime).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                }
            )
    return {"files": files, "count": len(files), "root": str(LIB_ROOT)}


# ---------------- 领域测试知识包（Skill） ----------------
class SkillIn(BaseModel):
    name: str
    body: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    skill_key: str = ""
    fmt: str = "json"  # 落盘格式：json（默认）/ md / yaml（需已安装 PyYAML）


class SkillUpdateIn(BaseModel):
    name: str | None = None
    body: str | None = None
    description: str | None = None
    tags: list[str] | None = None


@app.get("/api/skills")
def api_skills_list() -> dict:
    items = skills_mod.list_skills()
    return {
        "skills": items,
        "count": len(items),
        "formats": skills_mod.available_formats(),
        "root": str(skills_mod.SKILLS_DIR),
    }


@app.get("/api/skills/{sid}")
def api_skill_get(sid: str) -> dict:
    try:
        return skills_mod.get_skill(sid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"技能不存在: {sid}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/skills")
def api_skill_create(payload: SkillIn) -> dict:
    try:
        return skills_mod.create_skill(
            payload.name,
            payload.body,
            description=payload.description,
            tags=payload.tags,
            skill_key=payload.skill_key,
            fmt=payload.fmt,
        )
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.put("/api/skills/{sid}")
def api_skill_update(sid: str, payload: SkillUpdateIn) -> dict:
    try:
        return skills_mod.update_skill(
            sid,
            name=payload.name,
            body=payload.body,
            description=payload.description,
            tags=payload.tags,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"技能不存在: {sid}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/api/skills/{sid}")
def api_skill_delete(sid: str) -> dict:
    try:
        removed = skills_mod.delete_skill(sid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "removed": removed}


@app.get("/api/health")
def api_health() -> dict:
    return {"ok": True, "frontend": (WEB_DIR / "index.html").is_file()}


@app.post("/api/shutdown")
def api_shutdown() -> dict:
    """优雅停止本服务并释放端口。

    仅在通过 `python api_server.py` 启动（即 __main__ 持有 uvicorn.Server 实例）时有效；
    若以 `uvicorn api_server:app` 命令行启动，Server 实例不可达，请改用 stop_web.bat 停止。
    """
    if _uvicorn_server is None:
        raise HTTPException(
            status_code=400,
            detail="当前启动方式不支持接口关机，请用 stop_web.bat 停止服务",
        )
    _uvicorn_server.should_exit = True
    return {"ok": True, "message": "服务正在停止，端口即将释放"}


# 静态前端挂载必须放最后：API 路由先注册，优先命中，剩下的落到 SPA。
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


def _serve() -> None:
    """以 uvicorn.Server 实例方式运行，使 /api/shutdown 能优雅退出并释放端口。

    与 `uvicorn api_server:app` 的区别：这里持有 Server 实例，可响应关机请求。
    """
    global _uvicorn_server
    config = uvicorn.Config(app, host="127.0.0.1", port=8788, log_level="info")
    _uvicorn_server = uvicorn.Server(config)
    _uvicorn_server.run()


if __name__ == "__main__":
    _serve()
