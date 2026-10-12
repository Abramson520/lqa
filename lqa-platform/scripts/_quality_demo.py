# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(r"E:\智谱\本地化测试平台\lqa-platform")
sys.path.insert(0, str(ROOT / "src"))

from lqa.analysis import split_requirements
from lqa.parsers import parse_txt
from lqa.generate import generate
from lqa.config import load_settings
from lqa.exporters import save_output
from lqa.llm import build_system_prompt

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

a = split_requirements(parse_txt(SAMPLE))
settings = load_settings(provider="deepseek", api_key="")
result = generate(
    settings,
    a,
    source_lang="en-US",
    target_lang="de-DE",
    modules=a.modules,
    categories=["TEXT_OVERFLOW", "PLACEHOLDER", "TERMINOLOGY", "LAYOUT"],
    extra="优先商店与邮件",
    use_ai=False,
    count=12,
    case_library=ROOT / "case_library",
)
gate = result["gate"]
print("=== RULE PATH QUALITY ===")
print(
    f"generator={result['generator']} count={len(result['cases'])} "
    f"avg={gate['avg_score']} min={gate['min_score']} max={gate['max_score']} "
    f"issues={gate['issue_count']}"
)
print("issues:", gate["issues"][:8])
print("points:", [(p.module, p.text[:24]) for p in a.points])
from collections import Counter
print("category_dist:", dict(Counter(c["category"] for c in result["cases"])))
print()
print("=== SAMPLE CASES (top3) ===")
for i, c in enumerate(result["cases"][:3], 1):
    print(f"[{i}] score={c.get('quality_score')} {c['module']}/{c['category']}/{c['priority']}")
    print(f"  feature: {c['feature']}")
    print(f"  source: {c.get('source_text') or '(empty)'}")
    print(f"  steps: {c['steps'][:140].replace(chr(10), ' | ')}...")
    print(f"  expected: {c['expected'][:140]}")
    print()

folder = save_output(result["cases"], name="质量样例_商城邮件设置", out_root=ROOT / "outputs")
print(f"Excel saved: {folder}")
sys_prompt = build_system_prompt(ROOT / "case_library")
print(f"SystemPrompt len={len(sys_prompt)} fewshot={'Limited Offer' in sys_prompt}")
