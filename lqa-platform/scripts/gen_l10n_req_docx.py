# -*- coding: utf-8 -*-
"""生成「策划提测」风格的本地化需求 Word 文档。"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(r"C:\Users\zhang\Desktop\XX王国_本地化需求_策划提测_v1.0.docx")

INK = RGBColor(0x1F, 0x1F, 0x1F)
NAVY = RGBColor(0x1F, 0x3A, 0x5F)
MUTED = RGBColor(0x59, 0x59, 0x59)
FONT_CJK = "微软雅黑"
FONT_LATIN = "Calibri"


def set_run_font(run, size: float = 11, bold: bool = False, color: RGBColor = INK, name: str = FONT_LATIN):
    run.font.name = name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    r = run._element
    rPr = r.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), FONT_CJK)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)


def setup_page(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.top_margin = section.bottom_margin = Cm(2.2)
    section.left_margin = section.right_margin = Cm(2.5)


def tune_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = FONT_LATIN
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
    pf = normal.paragraph_format
    pf.line_spacing = 1.25
    pf.space_after = Pt(6)

    for n, size in [(1, 16), (2, 13), (3, 12)]:
        s = doc.styles[f"Heading {n}"]
        s.font.name = FONT_LATIN
        s.font.size = Pt(size)
        s.font.bold = True
        s.font.color.rgb = NAVY
        s._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
        s.paragraph_format.space_before = Pt(12 if n == 1 else 8)
        s.paragraph_format.space_after = Pt(4)

    title = doc.styles["Title"]
    title.font.name = FONT_LATIN
    title.font.size = Pt(22)
    title.font.bold = True
    title.font.color.rgb = NAVY
    title._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)

    for name in ("List Bullet", "List Number"):
        s = doc.styles[name]
        s.font.name = FONT_LATIN
        s.font.size = Pt(11)
        s._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)


def add_page_number(paragraph) -> None:
    run = paragraph.add_run()
    fld1 = OxmlElement("w:fldChar")
    fld1.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld2 = OxmlElement("w:fldChar")
    fld2.set(qn("w:fldCharType"), "end")
    run._r.append(fld1)
    run._r.append(instr)
    run._r.append(fld2)
    set_run_font(run, size=9, color=MUTED)


def setup_header_footer(doc: Document) -> None:
    section = doc.sections[0]
    header = section.header.paragraphs[0]
    header.text = ""
    r = header.add_run("XX王国 · 本地化需求（策划提测） · 内部资料")
    set_run_font(r, size=9, color=MUTED)
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = footer.add_run("第 ")
    set_run_font(r2, size=9, color=MUTED)
    add_page_number(footer)
    r3 = footer.add_run(" 页")
    set_run_font(r3, size=9, color=MUTED)


def add_para(doc, text: str, *, style: str = "Normal", bold_prefix: str | None = None):
    p = doc.add_paragraph(style=style)
    if bold_prefix:
        r = p.add_run(bold_prefix)
        set_run_font(r, bold=True)
        r2 = p.add_run(text)
        set_run_font(r2)
    else:
        r = p.add_run(text)
        set_run_font(r)
    return p


def add_bullets(doc, items: list[str]) -> None:
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(it)
        set_run_font(r)


def add_table(doc, header: list[str], rows: list[list[str]], col_widths: list[float] | None = None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for i, name in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(name)
        set_run_font(r, size=10, bold=True)

    for r_idx, row in enumerate(rows, start=1):
        for c_idx, value in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            r = p.add_run(str(value) if value != "" else " ")
            set_run_font(r, size=9)

    if col_widths:
        for row in table.rows:
            for idx, w in enumerate(col_widths):
                row.cells[idx].width = Cm(w)
    return table


def build() -> None:
    doc = Document()
    setup_page(doc)
    tune_styles(doc)
    setup_header_footer(doc)

    # ---- 封面信息 ----
    t = doc.add_paragraph("XX王国（海外版）", style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = st.add_run("本地化需求文档 · 策划提测版")
    set_run_font(r, size=14, bold=True, color=MUTED)

    doc.add_paragraph()

    add_table(
        doc,
        ["字段", "内容"],
        [
            ["文档编号", "LOC-REQ-2026-009"],
            ["版本", "v1.0（提测）"],
            ["提出方", "系统策划组 / 张策"],
            ["接收方", "本地化组、LQA 测试组"],
            ["日期", "2026-09-18"],
            ["优先级", "P0 — 阻塞 CBT 出海包"],
            ["关联项目", "Eternal Kingdoms · SLG 手游"],
        ],
        col_widths=[3.5, 12],
    )

    doc.add_paragraph()
    add_para(doc, "说明：本文档由系统策划根据 0.9 版功能范围编写，用于向本地化与 LQA 同步「翻什么、怎么翻、什么算过」。文案终稿以本地化交付包为准；功能范围变更会另行升版。", style="Normal")

    doc.add_page_break()

    # ---- 1 背景 ----
    doc.add_paragraph("1. 背景与目标", style="Heading 1")
    add_para(
        doc,
        "《XX王国》国服已稳定运营，现启动海外版。CBT 首包需覆盖 5 个目标语言（德/日/韩/葡/阿），确保核心 SLG 循环——主城建设、行军集结、联盟协作、商城付费——在目标语言下可正常游玩且无阻断级本地化问题。",
    )
    add_para(doc, "本文档不是翻译风格手册全文，只约束策划侧必须对齐的功能范围、术语锁死项与验收红线。完整风格指南见附件 A。")

    doc.add_paragraph("1.1 术语约定", style="Heading 2")
    add_bullets(
        doc,
        [
            "本地化需求：策划要求「哪些内容必须进入翻译范围」的功能性说明。",
            "LQA：对已翻译文案在客户端真实界面的表现进行质量验收。",
            "阻塞项（Blocker）：不修复不得提测/发布的本地化问题。",
            "词条：客户端中一条独立的可翻译字符串（含占位符）。",
        ],
    )

    # ---- 2 项目信息 ----
    doc.add_paragraph("2. 项目信息", style="Heading 1")
    add_table(
        doc,
        ["项", "说明"],
        [
            ["游戏类型", "SLG 策略手游（大地图 + 联盟战）"],
            ["源语言", "en-US（英文文案库为唯一基线）"],
            ["目标语言", "de-DE / ja-JP / ko-KR / pt-BR / ar-SA"],
            ["包体阶段", "CBT → OBT；本文档对应 CBT 首包"],
            ["预计词条", "约 1.8 万条 UI + 4.5 万词剧情（详见第 3 章）"],
            ["交付格式", "UTF-8 CSV（与 LQA 平台模板兼容）或 XLIFF 2.1"],
            ["参考客户端", "海外测试包 build 0.9.3（安装包见内网盘）"],
        ],
        col_widths=[3.5, 12],
    )

    # ---- 3 范围 ----
    doc.add_paragraph("3. 本地化范围", style="Heading 1")
    add_para(doc, "按功能系统划分。策划侧确认：下表「是」的模块必须进入首包翻译范围；「否」的模块 CBT 可保留英文，OBT 前补齐。")

    doc.add_paragraph("3.1 模块范围表", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "是否首包", "优先级", "备注"],
        [
            ["主城", "建筑升级、队列、资源面板", "是", "P0", "新手必经"],
            ["战斗", "行军、集结、战报", "是", "P0", "指令短语需统一"],
            ["联盟", "联盟信息、职位、礼物", "是", "P0", "社交核心"],
            ["商城", "礼包、限时活动、价格说明", "是", "P0", "付费相关，合规敏感"],
            ["邮件", "系统邮件、补偿模板", "是", "P1", "含 {player} 等占位符"],
            ["任务", "主线、日常、成就", "是", "P1", "长文本注意换行"],
            ["剧情", "章节对话、角色档案", "是", "P1", "可轻度口语"],
            ["设置", "账号、画质、通知", "是", "P1", "系统权限文案"],
            ["引导", "新手教程步骤", "是", "P0", "步骤必须可点可跟"],
            ["活动", "赛季 / 限时玩法", "是", "P0", "倒计时与规则说明"],
            ["支付", "年龄提示、退款说明", "是", "P0", "目标市场合规"],
            ["图内", "Banner / 活动硬编码图", "是", "P1", "需多语言图资源"],
            ["聊天", "联盟频道快捷短语", "否", "P2", "CBT 暂用英文"],
            ["回放", "战报回放 UI", "否", "P2", "OBT 前补齐"],
        ],
        col_widths=[2.2, 4.5, 2.2, 1.8, 4.8],
    )

    doc.add_paragraph("3.2 工作量预估（策划侧粗算）", style="Heading 2")
    add_table(
        doc,
        ["类型", "预估量", "说明"],
        [
            ["UI 词条", "约 12,400 条", "含按钮、标签、弹窗"],
            ["系统邮件模板", "约 180 条", "必须保留占位符"],
            ["剧情文本", "约 45,000 词", "按词计费/排期参考"],
            ["图内文字", "约 60 张图", "需出 5 语版本"],
            ["活动文案", "随赛季更新", "每赛季约 +800 条"],
        ],
        col_widths=[3.5, 3.5, 8.5],
    )
    add_para(doc, "注：预估供排期，不作为合同词数；以本地化实际导出为准。缓冲按 8% 预留。")

    # ---- 4 语言与格式 ----
    doc.add_paragraph("4. 目标语言特殊要求", style="Heading 1")
    add_para(doc, "客户端需按 locale 正确处理日期、数字与文字方向。策划确认以下格式为验收基准：")

    add_table(
        doc,
        ["语言", "方向", "日期示例", "数字示例", "策划侧特别说明"],
        [
            ["德语 de-DE", "LTR", "18.09.2026", "1.234.567", "按钮预留 +35% 宽度，避免复合词截断"],
            ["日语 ja-JP", "LTR", "2026/09/18", "1,234,567", "禁止错误断行；半角/全角统一"],
            ["韩语 ko-KR", "LTR", "2026.09.18", "1,234,567", "敬语层级：系统用해요体"],
            ["葡语 pt-BR", "LTR", "18/09/2026", "1.234.567", "用巴西用语，禁欧葡"],
            ["阿语 ar-SA", "RTL", "地区习惯", "阿拉伯数字", "整界面镜像；图标方向同步检查"],
        ],
        col_widths=[3.0, 1.5, 2.8, 2.8, 5.5],
    )

    # ---- 5 术语 ----
    doc.add_paragraph("5. 核心术语锁死表", style="Heading 1")
    add_para(doc, "下列术语已在策划会上定稿，翻译与游戏内文案必须一致。若与通用译法冲突，以本表为准；变更需策划 + 本地化双签。")

    add_table(
        doc,
        ["英文", "德语锁定译法", "适用场景", "禁止"],
        [
            ["Alliance", "Allianz", "联盟系统全量", "Bündnis（非本场景）"],
            ["Rally", "Sammelpunkt", "集结进攻", "Kundgebung"],
            ["Power", "Macht", "战力/排行榜", "Energie（魔法语境）"],
            ["Scout", "Aufklärer", "侦察", "Pfadfinder"],
            ["Claim", "Einfordern", "奖励领取", "Behaupten"],
            ["Season", "Saison", "赛季", "Jahreszeit"],
            ["VIP", "VIP", "商城特权", "不翻译"],
            ["Store", "Shop", "商城入口", "Lager"],
        ],
        col_widths=[3.0, 3.5, 4.0, 5.0],
    )
    add_para(doc, "日/韩/葡/阿完整术语表见附件 B（本地化组维护），冲突时回本文档仲裁。")

    # ---- 6 风格 ----
    doc.add_paragraph("6. 文案风格要求", style="Heading 1")
    add_bullets(
        doc,
        [
            "整体语气：正式、简洁、指令感；像军事简报，不像聊天。",
            "按钮文案：尽量 ≤ 12 个英文字符等效长度；超长必须改写，不允许截断显示。",
            "系统提示：完整句；错误提示必须说明「发生了什么 + 玩家可做什么」。",
            "剧情对白：可口语，但禁网络用语、梗、目标市场敏感俚语。",
            "禁止：未翻译英文残留、机翻痕迹（语序明显错误）、同一概念多译。",
        ],
    )

    # ---- 7 验收 ----
    doc.add_paragraph("7. LQA 验收红线（策划确认）", style="Heading 1")
    add_para(doc, "下列问题在 CBT 提测时视为阻塞项，LQA 必须开 P0/Critical：")

    add_table(
        doc,
        ["检查项", "合格标准", "不通过示例"],
        [
            ["文本溢出", "按钮/标题完整可见", "“Claim Reward” 被截成 “Claim Rew…”"],
            ["编码乱码", "无 ??? / 方框字 / 转义符", "显示 &amp; 或 ▯▯▯"],
            ["占位符", "运行时全部被替换", "邮件里出现字面量 {player_name}"],
            ["术语一致", "与锁死表 100% 一致", "同一界面出现 Allianz / Bündnis 混用"],
            ["日期数字", "符合第 4 章 locale 格式", "德语区显示 09/18/2026"],
            ["RTL 布局", "阿语镜像正确，无重叠", "返回键跑到错误一侧"],
            ["文化合规", "无宗教/政治敏感符号", "活动图出现目标市场禁忌符号"],
        ],
        col_widths=[2.8, 5.5, 7.2],
    )

    add_para(
        doc,
        "非阻塞但需记录：标点空格、轻度术语漂移、图内未本地化（已有替代图可先过）。详见 LQA 平台类别定义。",
    )

    # ---- 8 交付与排期 ----
    doc.add_paragraph("8. 交付物与排期", style="Heading 1")
    add_table(
        doc,
        ["交付物", "负责", "计划日期", "接收方"],
        [
            ["功能范围确认（本文档 v1.0 签字）", "策划", "2026-09-20", "本地化 / QA"],
            ["UI 字符串包（5 语）", "本地化", "2026-10-08", "客户端 / QA"],
            ["剧情文本包", "本地化", "2026-10-12", "客户端 / QA"],
            ["多语言字体与图资源", "客户端 / 美术", "2026-10-15", "QA"],
            ["首轮 LQA 报告", "QA", "2026-10-28", "策划 / 发行"],
            ["阻塞项修复包", "各端", "2026-11-04", "QA 回归"],
        ],
        col_widths=[5.5, 3.0, 3.0, 4.0],
    )

    # ---- 9 未决 ----
    doc.add_paragraph("9. 未决事项（需回复）", style="Heading 1")
    add_para(doc, "以下问题策划暂无定论，请本地化/发行在 2026-09-22 前书面回复：")
    add_bullets(
        doc,
        [
            "阿拉伯语是否使用西方数字（1,234）还是阿拉伯-印度数字（١٬٢٣٤）？目前客户端配置为阿拉伯-印度数字，发行未最终确认。",
            "聊天快捷短语 CBT 是否允许英文残留？若允许，LQA 该项降为 P2。",
            "活动 Banner 是否必须 5 语全出，还是可先 3 语（德/日/韩）？",
            "剧情语音若后置，字幕 LQA 是否可与 UI LQA 拆期？",
        ],
    )

    # ---- 10 联系 ----
    doc.add_paragraph("10. 联系人", style="Heading 1")
    add_table(
        doc,
        ["角色", "姓名", "职责"],
        [
            ["系统策划", "张策", "范围、术语、验收红线"],
            ["本地化负责人", "李译", "译文质量、术语表维护"],
            ["LQA 负责人", "王测", "用例、执行、缺陷分级"],
            ["客户端", "陈端", "UI 适配、字体、RTL"],
            ["发行", "赵发", "目标市场合规、未决项拍板"],
        ],
        col_widths=[3.5, 3.0, 9.0],
    )

    # ---- 附件 ----
    doc.add_page_break()
    doc.add_paragraph("附件 A：风格指南摘要", style="Heading 1")
    add_bullets(
        doc,
        [
            "标题：Title Case（英）；目标语言按各自惯例，不强行模仿英文大小写。",
            "按钮：动词优先（Claim / Upgrade / Join），避免完整长句。",
            "通知：首句写结果，次句写原因或下一步。",
            "数字缩写：资源可用 K/M，但价格与战力必须完整数字。",
            "占位符：{xxx} 命名不得翻译、不得删改花括号。",
        ],
    )

    doc.add_paragraph("附件 B：占位符清单（节选）", style="Heading 1")
    add_table(
        doc,
        ["占位符", "含义", "示例替换"],
        [
            ["{player_name}", "玩家昵称", "CommanderAlex"],
            ["{alliance_name}", "联盟名", "IronLegion"],
            ["{item_name}", "道具名", "Speed-Up Ticket"],
            ["{amount}", "数量", "2,400"],
            ["{time}", "剩余时间", "02:15:30"],
            ["{server_id}", "服务器编号", "S-107"],
        ],
        col_widths=[4.0, 4.0, 7.5],
    )

    doc.add_paragraph("附件 C：变更记录", style="Heading 1")
    add_table(
        doc,
        ["版本", "日期", "作者", "说明"],
        [
            ["v0.9", "2026-09-10", "张策", "内部草稿，范围未锁"],
            ["v1.0", "2026-09-18", "张策", "提测版：锁范围、术语、验收红线；提交本地化/LQA"],
        ],
        col_widths=[2.5, 3.0, 3.0, 7.0],
    )

    doc.add_paragraph()
    add_para(doc, "—— 以下无正文 ——", style="Normal")

    # 文档属性
    doc.core_properties.title = "XX王国本地化需求（策划提测）"
    doc.core_properties.author = "系统策划组 / 张策"
    doc.core_properties.subject = "SLG 出海本地化需求"
    doc.core_properties.comments = "模拟策划提测文档，供 LQA 需求评审使用"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        # 若被占用则另存
        alt = OUT.with_name(OUT.stem + "_alt.docx")
        doc.save(alt)
        print(f"OK (alt) {alt}")
    else:
        doc.save(OUT)
        print(f"OK {OUT}")


if __name__ == "__main__":
    build()
