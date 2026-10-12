# -*- coding: utf-8 -*-
"""生成 SLG 本地化需求规格 xlsx（openpyxl，含公式/样式/冻结窗格）。"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, NamedStyle, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

OUT = Path(r"C:\Users\zhang\Desktop\SLG本地化需求规格_v1.xlsx")

# --- palette ---
INK = "1F1F1F"
HEADER_BG = "F2F2F2"
ACCENT_BG = "1F4E79"
ACCENT_FG = "FFFFFF"
INPUT_FG = "0033CC"
WARN_BG = "FFF2CC"
P0_BG = "FFC7CE"
P0_FG = "9C0006"
BORDER = "BFBFBF"

thin = Side(style="thin", color=BORDER)
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)


def register_styles(wb: Workbook) -> None:
    styles = {
        "hdr": NamedStyle(
            name="hdr",
            font=Font(name="微软雅黑", size=11, bold=True, color=INK),
            fill=PatternFill("solid", fgColor=HEADER_BG),
            alignment=Alignment(horizontal="center", vertical="center", wrap_text=True),
            border=BOX,
        ),
        "title": NamedStyle(
            name="title",
            font=Font(name="微软雅黑", size=14, bold=True, color=ACCENT_FG),
            fill=PatternFill("solid", fgColor=ACCENT_BG),
            alignment=Alignment(horizontal="left", vertical="center"),
        ),
        "body": NamedStyle(
            name="body",
            font=Font(name="微软雅黑", size=10, color=INK),
            alignment=Alignment(vertical="center", wrap_text=True),
            border=BOX,
        ),
        "body_c": NamedStyle(
            name="body_c",
            font=Font(name="微软雅黑", size=10, color=INK),
            alignment=Alignment(horizontal="center", vertical="center", wrap_text=True),
            border=BOX,
        ),
        "input": NamedStyle(
            name="input",
            font=Font(name="微软雅黑", size=10, color=INPUT_FG),
            alignment=Alignment(vertical="center", wrap_text=True),
            border=BOX,
            fill=PatternFill("solid", fgColor="E8F0FE"),
        ),
        "p0": NamedStyle(
            name="p0",
            font=Font(name="微软雅黑", size=10, bold=True, color=P0_FG),
            fill=PatternFill("solid", fgColor=P0_BG),
            alignment=Alignment(horizontal="center", vertical="center"),
            border=BOX,
        ),
        "warn": NamedStyle(
            name="warn",
            font=Font(name="微软雅黑", size=10, color=INK),
            fill=PatternFill("solid", fgColor=WARN_BG),
            alignment=Alignment(vertical="center", wrap_text=True),
            border=BOX,
        ),
    }
    for st in styles.values():
        wb.add_named_style(st)


def set_widths(ws, widths: dict[str, float]) -> None:
    for col, w in widths.items():
        ws.column_dimensions[col].width = w


def write_title(ws, text: str, last_col: str, row: int = 1) -> None:
    ws.merge_cells(f"A{row}:{last_col}{row}")
    cell = ws[f"A{row}"]
    cell.value = text
    cell.style = "title"
    ws.row_dimensions[row].height = 28


def write_headers(ws, headers: list[str], row: int = 2) -> None:
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.style = "hdr"
    ws.row_dimensions[row].height = 32
    ws.freeze_panes = f"A{row + 1}"


def write_row(ws, values: list, row: int, styles: list[str] | None = None) -> None:
    for i, v in enumerate(values, 1):
        c = ws.cell(row=row, column=i, value=v)
        c.style = (styles[i - 1] if styles and i - 1 < len(styles) else "body")
        c.border = BOX


def build_overview(wb: Workbook) -> None:
    ws = wb.active
    ws.title = "项目概览"
    write_title(ws, "SLG 手游本地化需求规格 · 项目概览", "D")
    write_headers(ws, ["字段", "内容", "责任方", "备注"])

    rows = [
        ["项目代号", "Eternal Kingdoms", "发行", "国服 SLG 出海首包"],
        ["项目名称", "永恒王国·海外版", "PM", "源语言 en-US"],
        ["游戏类型", "SLG / 策略手游", "制作", "含联盟、战役、商城、活动"],
        ["源语言", "en-US", "本地化", "文案库基线"],
        ["目标语言", "de-DE, ja-JP, ko-KR, pt-BR, ar-SA", "本地化", "首批 5 语"],
        ["包体阶段", "CBT → OBT", "发行", "CBT 完成首轮 LQA"],
        ["文案总量(词)", "='本地化范围'!D23", "本地化", "链接范围表合计"],
        ["UI 字符串条数", "='本地化范围'!G23", "本地化", "加权词数（是否本地化）"],
        ["交付格式", "CSV + XLIFF 2.1", "本地化", "与 LQA 平台 CSV 模板兼容"],
        ["术语库", "En-Kingdoms-v3.tbx", "LQA", "跨语言强制一致"],
        ["风格指南", "正式、简洁、军事指令感", "本地化", "禁口语与网络用语"],
        ["LQA 平台", "lqa-platform :8788", "QA", "纯模型生成 + 人工审"],
        ["需求文档版本", "v1.0", "QA", "2026-09-18"],
        ["状态", "草案待评审", "PM", "评审通过后锁范围"],
    ]
    for i, r in enumerate(rows, start=3):
        styles = ["body", "input" if i in (9, 10) else "body", "body_c", "body"]
        write_row(ws, r, i, styles)
        ws.row_dimensions[i].height = 22

    # 数字格式
    ws["B9"].number_format = "#,##0"
    ws["B10"].number_format = "#,##0"

    set_widths(ws, {"A": 16, "B": 42, "C": 12, "D": 28})
    ws.auto_filter.ref = "A2:D16"
    ws.print_title_rows = "1:2"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


def build_scope(wb: Workbook) -> None:
    ws = wb.create_sheet("本地化范围")
    write_title(
        ws,
        "本地化范围与工作量（词数估算；合计行使用公式）",
        "G",
    )
    write_headers(
        ws,
        ["模块", "功能点", "优先级", "词条数(估)", "是否本地化", "备注", "加权词数"],
    )

    modules = [
        ["主城", "建筑升级/队列", "P0", 4200, "是", "含进度条与时间"],
        ["主城", "资源面板", "P0", 2800, "是", "数字千分位"],
        ["战斗", "行军/集结", "P0", 5600, "是", "指令短语"],
        ["战斗", "战报详情", "P0", 3800, "是", "日期/胜负"],
        ["联盟", "联盟信息/职位", "P0", 3100, "是", "职位术语"],
        ["联盟", "联盟礼物/邮件", "P1", 2900, "是", "按钮与时间"],
        ["商城", "礼包/限时活动", "P0", 4500, "是", "标题易截断"],
        ["商城", "内购说明", "P0", 1800, "是", "合规文案"],
        ["邮件", "系统邮件模板", "P1", 2200, "是", "占位符"],
        ["邮件", "补偿/公告", "P1", 1600, "是", "长文本换行"],
        ["任务", "主线/日常", "P1", 5200, "是", "断句"],
        ["任务", "成就系统", "P2", 2400, "是", "解锁文案"],
        ["剧情", "章节对话", "P1", 18000, "是", "口语可轻度放宽"],
        ["剧情", "角色档案", "P2", 3600, "是", "专有名词"],
        ["设置", "账号/画质/通知", "P1", 1900, "是", "系统权限"],
        ["引导", "新手教程", "P0", 2800, "是", "步骤可点"],
        ["活动", "赛季/限时玩法", "P0", 6200, "是", "倒计时"],
        ["支付", "商店合规区", "P0", 900, "是", "年龄/退款"],
        ["图内", "活动 Banner 硬编码", "P1", 0, "是", "走图内文字 LQA"],
        ["其他", "预留缓冲 8%", "P2", 0, "是", "需求变更"],
    ]
    for i, r in enumerate(modules, start=3):
        write_row(ws, r, i, ["body", "body", "body_c", "body_c", "body_c", "body", "body"])
        # 加权词数：是否本地化=是 则取词条数，否则 0
        ws.cell(row=i, column=7, value=f'=IF(E{i}="是",D{i},0)')
        ws.cell(row=i, column=7).style = "body_c"
        ws.cell(row=i, column=7).border = BOX
        ws.cell(row=i, column=4).number_format = "#,##0"
        ws.cell(row=i, column=7).number_format = "#,##0"
        if r[2] == "P0":
            ws.cell(row=i, column=3).style = "p0"

    last = 2 + len(modules)
    total_row = last + 1
    ws.cell(row=total_row, column=1, value="合计")
    ws.cell(row=total_row, column=1).style = "hdr"
    ws.cell(row=total_row, column=3, value="—")
    ws.cell(row=total_row, column=3).style = "body_c"
    ws.cell(row=total_row, column=4, value=f"=SUM(D3:D{last})")
    ws.cell(row=total_row, column=4).style = "warn"
    ws.cell(row=total_row, column=4).number_format = "#,##0"
    ws.cell(row=total_row, column=5, value="—")
    ws.cell(row=total_row, column=5).style = "body_c"
    ws.cell(row=total_row, column=7, value=f"=SUM(G3:G{last})")
    ws.cell(row=total_row, column=7).style = "warn"
    ws.cell(row=total_row, column=7).number_format = "#,##0"
    for col in range(1, 8):
        ws.cell(row=total_row, column=col).border = BOX

    # 缓冲说明
    note_row = total_row + 2
    ws.merge_cells(f"A{note_row}:G{note_row}")
    ws[f"A{note_row}"] = "备注：图内文字不计词条但计入 LQA；缓冲按合计 8% 在排期中预留，不在本表硬编码。"
    ws[f"A{note_row}"].style = "warn"

    # DataValidation
    dv_pri = DataValidation(type="list", formula1='"P0,P1,P2,P3"', allow_blank=False)
    dv_yn = DataValidation(type="list", formula1='"是,否"', allow_blank=False)
    ws.add_data_validation(dv_pri)
    ws.add_data_validation(dv_yn)
    dv_pri.add(f"C3:C{last}")
    dv_yn.add(f"E3:E{last}")

    set_widths(ws, {"A": 12, "B": 22, "C": 10, "D": 12, "E": 12, "F": 22, "G": 12})
    ws.auto_filter.ref = f"A2:G{last}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


def build_locales(wb: Workbook) -> None:
    ws = wb.create_sheet("语言包规范")
    write_title(ws, "目标语言包规范（格式/字体/扩展率）", "H")
    write_headers(
        ws,
        [
            "Locale",
            "语言",
            "文字方向",
            "日期格式示例",
            "数字示例",
            "文本扩展率",
            "字体要求",
            "特殊说明",
        ],
    )
    rows = [
        ["de-DE", "德语", "LTR", "18.09.2026", "1.234.567", 1.35, "Noto Sans / DIN", "长词复合，按钮加宽"],
        ["ja-JP", "日语", "LTR", "2026/09/18", "1,234,567", 1.10, "Noto Sans JP", "禁则处理、半角全角"],
        ["ko-KR", "韩语", "LTR", "2026.09.18", "1,234,567", 1.15, "Noto Sans KR", "敬语层级统一"],
        ["pt-BR", "巴西葡语", "LTR", "18/09/2026", "1.234.567", 1.25, "Noto Sans", "避免欧葡用语"],
        ["ar-SA", "阿拉伯语", "RTL", "١٨/٠٩/٢٠٢٦", "١٬٢٣٤٬٥٦٧", 1.30, "Noto Naskh Arabic", "镜像 UI、图标方向"],
    ]
    for i, r in enumerate(rows, start=3):
        write_row(ws, r, i)
        ws.cell(row=i, column=6).number_format = '0.00"x"'
        ws.row_dimensions[i].height = 24
        if r[0] == "ar-SA":
            for col in range(1, 9):
                ws.cell(row=i, column=col).style = "warn"
            ws.cell(row=i, column=6).number_format = '0.00"x"'

    # 扩展率平均（公式）
    ws.cell(row=9, column=1, value="平均扩展率")
    ws.cell(row=9, column=1).style = "hdr"
    ws.cell(row=9, column=6, value="=AVERAGE(F3:F7)")
    ws.cell(row=9, column=6).style = "warn"
    ws.cell(row=9, column=6).number_format = '0.00"x"'
    ws.cell(row=9, column=7, value="用于按钮宽度设计基准")
    ws.cell(row=9, column=7).style = "body"

    set_widths(
        ws,
        {"A": 10, "B": 12, "C": 10, "D": 14, "E": 14, "F": 12, "G": 20, "H": 28},
    )
    ws.auto_filter.ref = "A2:H7"
    ws.page_setup.orientation = "landscape"


def build_glossary(wb: Workbook) -> None:
    ws = wb.create_sheet("术语表")
    write_title(ws, "核心术语表（跨语言强制一致；冲突以本表为准）", "F")
    write_headers(
        ws,
        ["术语ID", "源术语(en-US)", "锁定译法示例(de)", "词性", "上下文", "禁用译法"],
    )
    terms = [
        ["T-001", "Alliance", "Allianz", "名词", "联盟系统", "Bündnis(场景外)"],
        ["T-002", "Rally", "Sammelpunkt", "名词", "集结进攻", "Kundgebung"],
        ["T-003", "Power", "Macht", "名词", "战力/排行", "Energie(魔法语境)"],
        ["T-004", "VIP", "VIP", "缩写", "商城特权", "不翻译"],
        ["T-005", "Claim", "Einfordern", "动词", "邮件/奖励领取", "Behaupten"],
        ["T-006", "Reset", "Zurücksetzen", "动词", "日常重置", "Neustart"],
        ["T-007", "Season", "Saison", "名词", "赛季活动", "Jahreszeit"],
        ["T-008", "Scout", "Aufklärer", "名词", "侦察", "Pfadfinder(童军)"],
        ["T-009", "Garrison", "Besatzung", "名词", "驻防", "Garnison(历史义)"],
        ["T-010", "Store", "Shop", "名词", "商城入口", "Lager"],
    ]
    for i, r in enumerate(terms, start=3):
        write_row(ws, r, i)
        ws.row_dimensions[i].height = 22

    note = 3 + len(terms) + 1
    ws.merge_cells(f"A{note}:F{note}")
    ws[f"A{note}"] = "变更流程：新增术语需 LQA + 本地化双签；游戏内已上线文案若与本表冲突，开 P0 缺陷。"
    ws[f"A{note}"].style = "warn"

    set_widths(ws, {"A": 10, "B": 18, "C": 22, "D": 10, "E": 16, "F": 22})
    ws.auto_filter.ref = "A2:F12"


def build_acceptance(wb: Workbook) -> None:
    ws = wb.create_sheet("LQA验收标准")
    write_title(ws, "LQA 验收标准（对齐 lqa-platform 15 类）", "G")
    write_headers(
        ws,
        ["类别代码", "中文名", "验收标准", "严重级别", "检查方法", "阻塞发布", "覆盖模块"],
    )
    rows = [
        ["TEXT_OVERFLOW", "文本溢出/截断", "所有按钮/标题完整可见，无省略号截断关键信息", "Critical", "真机 + 模拟器逐界面", "是", "商城/邮件/主城"],
        ["LAYOUT", "UI 布局适配", "控件无重叠、无越界，间距符合设计规范", "Critical", "多分辨率对比", "是", "全界面"],
        ["FONT", "字体字形异常", "无 tofu(□)、缺字、错误字形", "Critical", "特殊字符表扫描", "是", "全界面"],
        ["ENCODING", "编码/乱码", "无 mojibake / ??? / 转义残留", "Critical", "全量文案扫库", "是", "全界面"],
        ["TERMINOLOGY", "术语一致性", "核心术语与术语表 100% 一致", "Major", "术语库 diff", "否", "全模块"],
        ["PUNCTUATION", "标点空格规范", "符合目标语言标点与空格习惯", "Minor", "规则检查 + 抽样", "否", "全模块"],
        ["DATE_FORMAT", "日期数字格式", "日期/数字/货币符合 locale", "Major", "格式正则", "否", "邮件/战报/商城"],
        ["CULTURAL", "文化合规", "无宗教/政治/敏感符号冲突", "Critical", "合规清单", "是", "剧情/活动/图内"],
        ["PLACEHOLDER", "占位符/变量", "{xxx} 全部被替换，无原始占位符", "Critical", "运行时动态文案", "是", "邮件/任务"],
        ["IMAGE_TEXT", "图内文字/硬编码", "图内文案已本地化或提供多语言图", "Major", "资源包 diff", "否", "Banner/图标"],
        ["VOICE_SUB", "语音字幕对齐", "字幕与语音内容/时长匹配", "Major", "抽样播放", "否", "剧情/过场"],
        ["RTL", "RTL 语言布局", "ar 镜像正确，图标与文本方向一致", "Critical", "RTL 专项用例", "是", "全界面"],
        ["FONT_MISSING", "字体缺失回退", "缺字体时回退可读，不白屏", "Major", "卸字体包测试", "否", "全界面"],
        ["LINE_BREAK", "换行断句", "断行自然，日文禁则正确", "Major", "长文案压力", "否", "剧情/公告"],
        ["OTHER", "其他", "按模块补充场景用例", "Minor", "探索式测试", "否", "按需"],
    ]
    for i, r in enumerate(rows, start=3):
        styles = ["body_c", "body_c", "body", "body_c", "body", "body_c", "body"]
        write_row(ws, r, i, styles)
        if r[3] == "Critical":
            ws.cell(row=i, column=4).style = "p0"
        ws.row_dimensions[i].height = 36

    set_widths(ws, {"A": 16, "B": 14, "C": 40, "D": 12, "E": 16, "F": 10, "G": 18})
    ws.auto_filter.ref = "A2:G17"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


def build_deliverables(wb: Workbook) -> None:
    ws = wb.create_sheet("交付清单")
    write_title(ws, "交付物与验收清单", "F")
    write_headers(ws, ["交付物", "格式", "责任方", "计划日期", "验收标准", "状态"])
    rows = [
        ["术语表 v3", "TBX + CSV", "本地化", "2026-09-25", "LQA 抽检 0 冲突", "未开始"],
        ["UI 字符串包", "CSV/XLIFF", "本地化", "2026-10-08", "占位符完整、编码 UTF-8", "未开始"],
        ["剧情文本包", "XLIFF", "本地化", "2026-10-12", "分段对齐、无硬编码", "未开始"],
        ["多语言字体包", "OTF/TTF", "客户端", "2026-10-10", "覆盖目标语全部字形", "未开始"],
        ["图内多语言图", "PNG/PSD", "美术", "2026-10-15", "无硬编码源语言", "未开始"],
        ["LQA 用例集", "平台库", "QA", "2026-10-18", "15 类全覆盖、P0 优先", "未开始"],
        ["首轮 LQA 报告", "XLSX", "QA", "2026-10-28", "Critical=0 才可 OBT", "未开始"],
        ["回归修复包", "增量包", "各端", "2026-11-04", "P0/P1 关闭率 100%", "未开始"],
    ]
    for i, r in enumerate(rows, start=3):
        write_row(ws, r, i)
        ws.row_dimensions[i].height = 22

    last = 2 + len(rows)
    dv = DataValidation(type="list", formula1='"未开始,进行中,已完成,阻塞"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"F3:F{last}")

    # 完成率公式
    ws.cell(row=last + 2, column=1, value="完成率")
    ws.cell(row=last + 2, column=1).style = "hdr"
    ws.cell(row=last + 2, column=2, value=f'=IF(COUNTA(F3:F{last})=0,0,COUNTIF(F3:F{last},"已完成")/COUNTA(F3:F{last}))')
    ws.cell(row=last + 2, column=2).style = "warn"
    ws.cell(row=last + 2, column=2).number_format = "0.0%"
    ws.cell(row=last + 2, column=3, value=f'=COUNTIF(F3:F{last},"已完成")&"/"&COUNTA(F3:F{last})')
    ws.cell(row=last + 2, column=3).style = "body_c"

    set_widths(ws, {"A": 16, "B": 14, "C": 12, "D": 14, "E": 28, "F": 12})
    ws.auto_filter.ref = f"A2:F{last}"
    ws.page_setup.orientation = "landscape"


def main() -> None:
    wb = Workbook()
    register_styles(wb)
    build_overview(wb)
    build_scope(wb)
    build_locales(wb)
    build_glossary(wb)
    build_acceptance(wb)
    build_deliverables(wb)

    # 文档属性
    wb.properties.title = "SLG本地化需求规格"
    wb.properties.creator = "LQA Platform / MiMo"
    wb.properties.subject = "游戏本地化需求"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"OK {OUT}")


if __name__ == "__main__":
    main()
