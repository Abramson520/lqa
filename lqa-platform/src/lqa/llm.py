# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 调用 + 高质量 LQA System Prompt。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .categories import BUILTIN_FEW_SHOT, CATEGORIES, CATEGORY_FOCUS
from .config import Settings
from .skills import render_skills_block


class LLMError(RuntimeError):
    pass


SYSTEM_PROMPT_TEMPLATE = """你是资深游戏本地化 QA（LQA）专家，输出可直接进入用例评审的测试用例。

## 输出契约
1. 只输出 JSON，不要 Markdown、不要解释。
2. 顶层结构必须是 {"cases":[...]}。
3. 每条用例字段：module, feature, category, priority, source_lang, target_lang, source_text, target_text, preconditions, steps, expected, notes。
4. category 使用关注类别列表中的值：内置类别（__CATS__）或用户自定义文本均可；单次生成内同一概念保持类别一致。
5. priority 只能 P0/P1/P2/P3。

## 质量硬标准（不合格会被系统打回）
- feature：具体功能点，格式建议「场景对象·检查类型」，禁止“测试文案”“检查UI”这类空话。
- preconditions：写清语言、入口、数据状态（活动开启/有邮件/已登录等）。
- steps：3-7 条编号步骤；必须包含：切换目标语言 → 进入具体模块/控件 → 观察/对照点 → 截图或记录。禁止只写“检查是否正常”。
- expected：可判定。必须写出：正确表现 + 失败特征（截断/乱码/混用/{var} 未替换/重叠等）。禁止“正常显示”。
- source_text / target_text：
  - 类别属于 TEXT_OVERFLOW/TERMINOLOGY/ENCODING/PUNCTUATION/DATE_FORMAT/PLACEHOLDER/FONT/CULTURAL/LINE_BREAK 时，必须给出真实游戏语境双语文案。
  - source_text 跟随 source_lang，target_text 跟随 target_lang。
  - PLACEHOLDER 必须保留变量占位形态。
  - 目标语言文案要符合该语言长度/书写习惯（如 de 长、ja 紧凑、ar RTL）。
- 同批禁止重复「模块+功能点+类别」；覆盖不同模块，不要全部堆在通用。
- category_focus 指明了该类别的观察点，expected 必须对齐。

## category 与观察点
__FOCUS__

## 金标准示例（风格必须对齐，内容按本次需求重写，禁止照抄示例文案）
__SHOTS__

## 骨架用例处理
若用户给了 skeleton_cases：
- 在骨架基础上补强：具体化 steps、补齐双语文案、改写 expected 为可判定描述。
- 保持 module/category 与骨架对齐或合理优化。
- 可新增缺失的高风险类别用例，覆盖尽可能多的需求点（不限制总数）。
- 优先覆盖需求点里明确提到的界面/模块/文案。

## 额外要求
若 generate.extra_requirements 非空，必须遵守。
禁止输出 notes 为空；notes 可写风险原因/对照术语表/建议工具。
"""

SYSTEM_PROMPT = (
    SYSTEM_PROMPT_TEMPLATE
    .replace("__CATS__", ", ".join(CATEGORIES.keys()))
    .replace("__FOCUS__", "\n".join(f"- {k}: {v}" for k, v in CATEGORY_FOCUS.items()))
    .replace("__SHOTS__", "")
)


def _format_shot(c: dict) -> str:
    return json.dumps(
        {
            "module": c.get("module"),
            "feature": c.get("feature"),
            "category": c.get("category"),
            "priority": c.get("priority"),
            "source_text": c.get("source_text"),
            "target_text": c.get("target_text"),
            "preconditions": c.get("preconditions"),
            "steps": c.get("steps"),
            "expected": c.get("expected"),
            "notes": c.get("notes"),
        },
        ensure_ascii=False,
    )


def load_few_shots(case_library: Path | None, limit: int = 3) -> list[dict]:
    shots: list[dict] = list(BUILTIN_FEW_SHOT)
    if case_library and case_library.exists():
        try:
            import pandas as pd

            for p in sorted(case_library.rglob("*.xlsx"))[:5]:
                df = pd.read_excel(p)
                cols = {str(c).strip(): c for c in df.columns}
                alias = {
                    "module": ["主模块", "模块", "module"],
                    "submodule": ["子模块", "sub_module", "submodule"],
                    "feature": ["测试说明", "功能点", "功能", "feature"],
                    "category": ["类别", "category"],
                    "priority": ["优先级", "priority"],
                    "source_text": ["源文案", "source_text", "source"],
                    "target_text": ["目标文案", "target_text", "target"],
                    "preconditions": ["前置条件", "preconditions"],
                    "steps": ["复现路径", "步骤", "steps"],
                    "expected": ["预期结果", "预期", "expected"],
                    "notes": ["备注", "notes"],
                }

                def pick(keys: list[str]) -> Any:
                    for k in keys:
                        if k in cols:
                            return cols[k]
                    return None

                m = pick(alias["module"])
                sub = pick(alias["submodule"])
                f = pick(alias["feature"])
                s = pick(alias["steps"])
                e = pick(alias["expected"])
                if not (m and f and s and e):
                    continue
                for _, row in df.head(8).iterrows():
                    module_val = str(row[m] or "").strip()
                    if sub is not None:
                        sv = str(row[sub] or "").strip()
                        if sv:
                            module_val = f"{module_val}/{sv}" if module_val else sv
                    case = {
                        "module": module_val,
                        "feature": str(row[f] or "").strip(),
                        "category": str(row[pick(alias["category"])] or "").strip() if pick(alias["category"]) else "OTHER",
                        "priority": str(row[pick(alias["priority"])] or "").strip() if pick(alias["priority"]) else "P1",
                        "source_text": str(row[pick(alias["source_text"])] or "").strip() if pick(alias["source_text"]) else "",
                        "target_text": str(row[pick(alias["target_text"])] or "").strip() if pick(alias["target_text"]) else "",
                        "preconditions": str(row[pick(alias["preconditions"])] or "").strip() if pick(alias["preconditions"]) else "",
                        "steps": str(row[s] or "").strip(),
                        "expected": str(row[e] or "").strip(),
                        "notes": str(row[pick(alias["notes"])] or "").strip() if pick(alias["notes"]) else "",
                    }
                    if case["module"] and case["feature"] and len(case["steps"]) >= 20:
                        shots.append(case)
        except Exception:
            pass
    # 内置优先，再补充案例库，截断
    return shots[: max(3, limit)]


def build_system_prompt(
    case_library: Path | None = None,
    *,
    selected_skills: list[dict] | None = None,
) -> str:
    shots = load_few_shots(case_library, limit=4)
    prompt = (
        SYSTEM_PROMPT_TEMPLATE
        .replace("__CATS__", ", ".join(CATEGORIES.keys()))
        .replace("__FOCUS__", "\n".join(f"- {k}: {v}" for k, v in CATEGORY_FOCUS.items()))
        .replace("__SHOTS__", "\n".join(_format_shot(s) for s in shots))
    )
    # 用户选定的领域知识包放在最后：靠近生成指令位置，模型更易遵守
    block = render_skills_block(selected_skills or [])
    if block:
        prompt = f"{prompt}\n\n{block}"
    return prompt


def _client(settings: Settings):
    try:
        from openai import OpenAI
    except ImportError as e:
        raise LLMError("缺少 openai 依赖，请 pip install -r requirements.txt") from e
    return OpenAI(
        api_key=settings.api_key or "sk-placeholder",
        base_url=settings.base_url,
        timeout=settings.timeout_s,
    )


def extract_json_payload(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"cases": data}
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return json.loads(raw[start : end + 1])
    raise LLMError("LLM 输出不是 JSON")


def chat_json(
    settings: Settings,
    user_prompt: str,
    *,
    system: str | None = None,
) -> dict[str, Any]:
    if not settings.has_key:
        raise LLMError("未配置 API Key：请在「模型配置」或 .env 填写")
    client = _client(settings)
    sys_prompt = system or build_system_prompt()
    last_err: Exception | None = None
    for use_json in (True, False):
        try:
            kwargs: dict[str, Any] = {
                "model": settings.model,
                "temperature": settings.temperature,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            }
            if use_json:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            if not content:
                raise LLMError("LLM 返回空 content")
            return extract_json_payload(content)
        except LLMError:
            raise
        except Exception as e:
            last_err = e
            msg = str(e)
            if use_json and any(x in msg for x in ("400", "404", "422", "response_format")):
                continue
            raise LLMError(f"LLM 调用失败: {e}") from e
    raise LLMError(f"LLM 调用失败: {last_err}")
