# -*- coding: utf-8 -*-
"""生成《三角洲行动》策划提测风格本地化需求 Word（模块全覆盖样例）。"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(r"C:\Users\zhang\Desktop\三角洲行动_本地化需求_策划提测_v1.0.docx")

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
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), FONT_CJK)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)


def setup_page(doc: Document) -> None:
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21.0), Cm(29.7)
    s.top_margin = s.bottom_margin = Cm(2.2)
    s.left_margin = s.right_margin = Cm(2.5)


def tune_styles(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = FONT_LATIN
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
    normal.paragraph_format.line_spacing = 1.25
    normal.paragraph_format.space_after = Pt(6)

    for n, size in [(1, 16), (2, 13), (3, 12)]:
        st = doc.styles[f"Heading {n}"]
        st.font.name = FONT_LATIN
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = NAVY
        st._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)
        st.paragraph_format.space_before = Pt(12 if n == 1 else 8)
        st.paragraph_format.space_after = Pt(4)

    title = doc.styles["Title"]
    title.font.name = FONT_LATIN
    title.font.size = Pt(22)
    title.font.bold = True
    title.font.color.rgb = NAVY
    title._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)

    for name in ("List Bullet", "List Number"):
        st = doc.styles[name]
        st.font.name = FONT_LATIN
        st.font.size = Pt(11)
        st._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_CJK)


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
    s = doc.sections[0]
    header = s.header.paragraphs[0]
    header.text = ""
    r = header.add_run("三角洲行动 · 本地化需求（策划提测） · 内部资料")
    set_run_font(r, size=9, color=MUTED)
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    footer = s.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = footer.add_run("第 ")
    set_run_font(r2, size=9, color=MUTED)
    add_page_number(footer)
    r3 = footer.add_run(" 页")
    set_run_font(r3, size=9, color=MUTED)


def add_para(doc, text: str, *, style: str = "Normal"):
    p = doc.add_paragraph(style=style)
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

    # 封面
    t = doc.add_paragraph("三角洲行动（Delta Force）", style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st = doc.add_paragraph()
    st.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = st.add_run("海外版本地化需求文档 · 策划提测版")
    set_run_font(r, size=14, bold=True, color=MUTED)
    doc.add_paragraph()

    add_table(
        doc,
        ["字段", "内容"],
        [
            ["文档编号", "DF-LOC-REQ-2026-012"],
            ["版本", "v1.0（提测）"],
            ["提出方", "系统策划组 / 张策"],
            ["接收方", "本地化组、LQA 测试组、客户端"],
            ["日期", "2026-09-18"],
            ["优先级", "P0 — 阻塞海外 CBT 首包"],
            ["关联产品", "三角洲行动 · 战术射击 / 提取射击"],
            ["源语言", "zh-CN（国服文案库为基线）→ 以 en-US 为二次源的模块见备注"],
        ],
        col_widths=[3.5, 12],
    )
    doc.add_paragraph()
    add_para(
        doc,
        "说明：本文档由系统策划根据 1.2 版功能范围编写，覆盖全面战场、烽火地带、干员、武器、社交、商业化等全部客户端可见模块。翻译范围以「是否首包」列为准；验收红线见第 7 章。功能变更会升版并邮件同步。",
    )

    doc.add_page_break()

    # 1 背景
    doc.add_paragraph("1. 背景与目标", style="Heading 1")
    add_para(
        doc,
        "《三角洲行动》国服已上线，海外版需在 CBT 前完成核心玩法全链路本地化：从登录、匹配、对局 HUD、结算，到烽火地带的撤离与仓库经济，以及商城/通行证/干员养成。首包目标语言 6 个：英语、德语、日语、韩语、巴西葡语、阿拉伯语。",
    )
    add_para(doc, "本文档约束：①必须进首包的模块清单；②枪械/干员/模式等专有术语锁死表；③LQA 阻塞级验收标准。风格细则见附件 A。")

    doc.add_paragraph("1.1 术语约定", style="Heading 2")
    add_bullets(
        doc,
        [
            "全面战场：大地图载具协同的征服式模式（Warfare）。",
            "烽火地带：小队潜入、搜刮、撤离的提取射击模式（Operations）。",
            "干员：可选用的战术角色（Operator），含技能与背景故事。",
            "主武器 / 副武器 / 战术装备：配装栏位固定译名，不得随语境漂移。",
            "LQA：在真实客户端界面对译文表现做质量验收。",
            "阻塞项：不修复不得提测或发布的本地化问题。",
        ],
    )

    # 2 项目信息
    doc.add_paragraph("2. 项目信息", style="Heading 1")
    add_table(
        doc,
        ["项", "说明"],
        [
            ["产品类型", "战术 FPS / 提取射击（多模式共存）"],
            ["源语言", "zh-CN；部分枪械与军事术语以 en-US 为权威对照"],
            ["目标语言", "en-US / de-DE / ja-JP / ko-KR / pt-BR / ar-SA"],
            ["包体阶段", "海外 CBT → OBT；本文档对应 CBT 首包"],
            ["预计词条", "约 2.6 万条 UI + 8 万词剧情/干员传记 + 3.2 万词枪械与配件说明"],
            ["交付格式", "UTF-8 CSV（对齐 LQA 平台模板）或 XLIFF 2.1"],
            ["参考客户端", "海外测试包 build 1.2.0-rc3"],
            ["特殊场景", "击杀播报、语音字幕、战令文案、图内活动 Banner"],
        ],
        col_widths=[3.5, 12],
    )

    # 3 模块范围 — 重点
    doc.add_paragraph("3. 本地化模块范围（不限模块，全量列示）", style="Heading 1")
    add_para(doc, "策划按「玩家路径」拆模块。下表为完整清单；「首包」= CBT 必须完成本地化，「可延后」= OBT 前补齐。LQA 用例需按模块覆盖。")

    doc.add_paragraph("3.1 账号与外壳", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["登录/启动", "登录方式、用户协议、隐私政策、健康游戏提示", "是", "P0", "合规文案，目标市场版本不同"],
            ["更新与公告", "热更提示、登录公告、维护通知", "是", "P0", "支持富文本与倒计时"],
            ["主界面 HUD", "活动入口、红点、货币栏、赛季倒计时", "是", "P0", "高频截断风险区"],
            ["设置", "音画、键位、灵敏度、辅助功能、语言切换", "是", "P0", "语言切换即时生效需验证"],
            ["新手引导", "首次进入、模式教学、射击校准", "是", "P0", "步骤可点，禁止只写「点击这里」"],
            ["账号绑定", "平台账号、找回、封禁提示", "是", "P0", "法务审过的目标市场版本"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.2 全面战场（Warfare）", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["模式选择", "征服、突袭、团队死斗等入口说明", "是", "P0", "模式一句话卖点需本地化"],
            ["地图与部署", "地图名、据点名、部署点、重生倒计时", "是", "P0", "据点名与战术地图一致"],
            ["对局 HUD", "比分、占点提示、小队状态、击杀播报", "是", "P0", "击杀播报短促，字符数受限"],
            ["载具", "坦克/直升机/装甲车名称、座位、维修提示", "是", "P1", "军事装备译名统一"],
            ["指挥与标记", "进攻/防守/请求支援快捷指令", "是", "P0", "语音+字幕需对齐"],
            ["结算", "胜负、经验、勋章、举报入口", "是", "P0", "数字格式 locale 化"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.3 烽火地带（Operations）", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["进入与配装", "地图选择、带入装备价值、保险提示", "是", "P0", "经济文案，付费敏感"],
            ["局内搜刮", "容器名、物品稀有度、拾取提示", "是", "P0", "稀有度颜色+文字双通道"],
            ["任务与合约", "局内目标、完成条件、失败惩罚", "是", "P0", "条件必须可判定"],
            ["撤离", "撤离点开关、倒计时、成功/失败结算", "是", "P0", "倒计时与状态机文案"],
            ["仓库与市场", "物品栏、上架、出售、价值显示", "是", "P0", "数字千分位+货币符号"],
            ["保险箱/找回", "遗失找回规则说明", "是", "P1", "规则长文本，注意换行"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.4 干员与技能", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["干员列表", "代号、定位标签、解锁条件", "是", "P0", "代号不意译，保留呼号感"],
            ["技能说明", "主动/被动技能名与描述", "是", "P0", "冷却/范围数值用占位符"],
            ["干员档案", "背景故事、语音台词字幕", "是", "P1", "可口语；军事黑话需一致"],
            ["熟练度与解锁", "等级、里程碑奖励文案", "是", "P1", "—"],
            ["局内语音", "战术喊话、受击、击杀语音字幕", "是", "P1", "与语音时长对齐，抽样 LQA"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.5 武器与配装", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["枪械列表", "主/副武器名、类别标签", "是", "P0", "真实枪械名按授权译名表"],
            ["配件与改装", "瞄具、枪口、弹匣、握把名称与属性", "是", "P0", "属性条名称统一"],
            ["属性面板", "伤害、射速、后坐力、射程等", "是", "P0", "缩写需在图例中解释"],
            ["皮肤与蓝图", "皮肤名、获取途径说明", "是", "P1", "活动限定文案"],
            ["近战与投掷物", "刀、雷、烟雾弹等战术装备", "是", "P1", "—"],
            ["训练场", "打靶提示、伤害数字说明", "是", "P2", "可延后至 OBT 前"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.6 社交与组队", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["好友与组队", "邀请、队伍状态、准备/取消", "是", "P0", "状态短语"],
            ["聊天", "世界/队伍/私聊、快捷短语、屏蔽", "是", "P1", "快捷短语可英文残留见未决项"],
            ["战队/集团", "创建、职位、公告、贡献", "是", "P1", "职位术语锁死"],
            ["名片与成就", "称号、徽章、个人展示", "是", "P2", "可延后"],
            ["观战与回放", "观战 HUD、回放控制条", "可延后", "P2", "OBT 前补齐"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.7 商业化与成长", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["商城", "礼包、直购、限时折扣、价格与说明", "是", "P0", "付费合规；折扣表述需法务模板"],
            ["战斗通行证", "等级、任务、奖励轨道、购买引导", "是", "P0", "任务条件可判定"],
            ["充值与支付", "档位、货币、失败重试、发票说明", "是", "P0", "目标商店政策文案"],
            ["活动中心", "签到、赛季活动、联动规则", "是", "P0", "规则长文+倒计时"],
            ["邮件", "系统、补偿、奖励、封禁通知", "是", "P0", "大量占位符"],
            ["商店合规区", "年龄提示、退款、概率公示（如适用）", "是", "P0", "按目标市场法规"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.8 排位、赛事与内容", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["排位", "段位名、晋级/掉段、赛季重置说明", "是", "P1", "段位名统一意译策略"],
            ["赛事中心", "赛程、观赛、竞猜（如有）", "可延后", "P2", "视海外赛事节奏"],
            ["剧情/档案馆", "世界观文档、战役碎片叙事", "是", "P1", "长文本，分段交付"],
            ["图内与视频", "活动 Banner、过场字幕、宣传图内文字", "是", "P1", "需多语言图/字幕文件"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.9 客户端与系统", style="Heading 2")
    add_table(
        doc,
        ["模块", "功能点", "首包", "优先级", "备注"],
        [
            ["错误与断线", "网络断开、重连、反作弊提示、崩溃上报文案", "是", "P0", "玩家可见的失败路径"],
            ["下载与资源", "分包下载、资源校验失败提示", "是", "P1", "—"],
            ["性能与兼容", "低配提示、驱动过旧提示", "是", "P2", "可延后"],
            ["无障碍", "色盲模式说明、字幕开关", "是", "P1", "部分市场强制"],
            ["系统通知", "推送、邮件摘要（如开启）", "可延后", "P2", "OBT 前"],
        ],
        col_widths=[2.8, 5.2, 1.5, 1.5, 4.5],
    )

    doc.add_paragraph("3.10 工作量粗算", style="Heading 2")
    add_table(
        doc,
        ["类型", "预估", "说明"],
        [
            ["UI 词条（全模块）", "≈ 26,000 条", "含 HUD/设置/商城/活动"],
            ["武器与配件说明", "≈ 32,000 词", "按词计排期参考"],
            ["干员档案与语音字幕", "≈ 18,000 词", "字幕需与音频对齐抽样"],
            ["剧情/世界观", "≈ 62,000 词", "可分批交付"],
            ["系统邮件模板", "≈ 220 条", "占位符完整"],
            ["图内文字资源", "≈ 90 张图 × 6 语", "Banner/活动图"],
            ["变更缓冲", "8%", "赛季更新另计"],
        ],
        col_widths=[4.5, 3.5, 7.5],
    )
    add_para(doc, "注：预估供排期，不作为合同词数；以导出文案库为准。")

    # 4 语言格式
    doc.add_paragraph("4. 目标语言特殊要求", style="Heading 1")
    add_table(
        doc,
        ["语言", "方向", "日期", "数字", "策划侧特别说明"],
        [
            ["英语 en-US", "LTR", "09/18/2026", "1,234,567", "军事缩写保持大写（HUD、M4 等）"],
            ["德语 de-DE", "LTR", "18.09.2026", "1.234.567", "按钮 +35% 宽；复合枪械名防截断"],
            ["日语 ja-JP", "LTR", "2026/09/18", "1,234,567", "片假名枪械名统一表；禁则处理"],
            ["韩语 ko-KR", "LTR", "2026.09.18", "1,234,567", "对局指令用简洁体"],
            ["葡语 pt-BR", "LTR", "18/09/2026", "1.234.567", "巴西用语，禁欧葡军事术语"],
            ["阿语 ar-SA", "RTL", "地区习惯", "阿拉伯数字或西方数字（见未决）", "HUD 全镜像；击杀播报 RTL"],
        ],
        col_widths=[2.8, 1.5, 2.6, 3.2, 5.4],
    )

    # 5 术语
    doc.add_paragraph("5. 核心术语锁死表（节选）", style="Heading 1")
    add_para(doc, "下列为跨模块必须一致的锁定译法示例（以 en 显示名为国际对照）。完整表由本地化维护，冲突回本文档仲裁。")

    add_table(
        doc,
        ["中文", "en（对照）", "de 锁定示例", "场景", "禁止"],
        [
            ["全面战场", "Warfare", "Kriegsführung", "模式入口", "Schlachtfeld（泛化）"],
            ["烽火地带", "Operations", "Operationen", "模式入口", "Betrieb"],
            ["干员", "Operator", "Operativkraft", "干员系统", "Agent（非本作）"],
            ["撤离", "Exfiltration", "Exfiltration", "局内结算", "Flucht（语气不符）"],
            ["主武器", "Primary Weapon", "Primärwaffe", "配装", "Hauptgewehr（可场景用）"],
            ["战术装备", "Tactical Gear", "Taktische Ausrüstung", "配装栏", "道具（泛称）"],
            ["战斗通行证", "Battle Pass", "Battle Pass", "商业化", "Gefechtspass（生造）"],
            ["据点", "Objective", "Zielpunkt", "全面战场 HUD", "Stützpunkt（视图义）"],
            ["击杀播报", "Killfeed", "Killfeed", "HUD", "Todesmeldung（过长）"],
            ["保险箱找回", "Secure Case", "Sicherer Koffer", "烽火地带", "Tresor（银行义）"],
        ],
        col_widths=[2.5, 3.0, 3.5, 2.8, 3.7],
    )

    # 6 风格
    doc.add_paragraph("6. 文案风格要求", style="Heading 1")
    add_bullets(
        doc,
        [
            "整体：军事简报语气，短句、指令感；避免营销腔长难句。",
            "HUD 与击杀播报：≤ 屏显安全区；英文基线尽量 ≤ 18 字符等效。",
            "技能与配件：先写效果，再写数值；数值用 {value} 类占位符。",
            "失败/错误：说明原因 + 玩家下一步（重连、重试、联系客服）。",
            "剧情与档案：可文学化，但专有名词与术语表一致。",
            "禁止：未翻译残留、机翻语序、同一枪械/干员多译、目标市场禁忌用语。",
        ],
    )

    # 7 验收
    doc.add_paragraph("7. LQA 验收红线（阻塞项）", style="Heading 1")
    add_para(doc, "CBT 提测时下列问题为 Critical/P0，必须清零或达成书面豁免：")

    add_table(
        doc,
        ["检查项", "合格标准", "不通过示例"],
        [
            ["文本溢出/截断", "按钮、干员名、枪械名完整", "「Exfiltration」按钮显示 “Exfiltra…”"],
            ["编码/字体", "无乱码、无 tofu（□）", "阿语显示方框字"],
            ["占位符", "{player} 等运行时替换", "邮件字面量 {item_name}"],
            ["术语一致", "与锁死表一致", "同界面 Warfare / Battlefield 混用"],
            ["日期数字", "符合第 4 章 locale", "德语区 09/18/2026"],
            ["RTL 布局", "阿语 HUD 镜像正确", "小地图与击杀播报方向错误"],
            ["字幕对齐", "字幕与语音内容/时长匹配", "干员语音与字幕错行"],
            ["文化合规", "无敏感符号/表述", "活动图违反目标市场法规"],
            ["付费文案", "价格、折扣、退款表述合规", "虚构原价被监管认定误导"],
        ],
        col_widths=[2.8, 5.5, 7.2],
    )

    # 8 交付
    doc.add_paragraph("8. 交付物与排期", style="Heading 1")
    add_table(
        doc,
        ["交付物", "负责", "计划日期", "接收"],
        [
            ["本文档 v1.0 会签", "策划", "2026-09-20", "本地化 / QA / 客户端"],
            ["术语表 v2（全模块）", "本地化", "2026-09-30", "QA / 客户端"],
            ["UI 字符串包（6 语）", "本地化", "2026-10-10", "客户端 / QA"],
            ["武器配件说明包", "本地化", "2026-10-14", "客户端 / QA"],
            ["干员档案与字幕", "本地化", "2026-10-18", "客户端 / QA"],
            ["多语言图与字体", "美术 / 客户端", "2026-10-20", "QA"],
            ["首轮 LQA 报告", "QA", "2026-10-30", "策划 / 发行"],
            ["阻塞修复与回归包", "各端", "2026-11-06", "QA"],
        ],
        col_widths=[5.0, 3.0, 3.0, 4.5],
    )

    # 9 未决
    doc.add_paragraph("9. 未决事项（请 2026-09-22 前书面回复）", style="Heading 1")
    add_bullets(
        doc,
        [
            "阿语数字：阿拉伯-印度数字还是西方数字？HUD 与仓库需统一，现客户端配置未最终拍板。",
            "真实枪械商标名：目标市场是否需使用虚构名/授权名差异？以法务清单为准，策划已预留映射表。",
            "聊天快捷短语：CBT 是否允许英文残留？若允许，该项 LQA 降为 P2。",
            "过场视频字幕：是否与 UI 同包提交，还是独立字幕文件流式加载？",
            "图内 Banner：是否必须 6 语全出，或可先英/德/日？",
            "击杀播报字符上限：各语言是否统一按英文 18 字符裁剪，还是按容器自适应？需客户端确认。",
        ],
    )

    # 10 联系人
    doc.add_paragraph("10. 联系人", style="Heading 1")
    add_table(
        doc,
        ["角色", "姓名", "职责"],
        [
            ["系统策划", "张策", "模块范围、术语、验收红线"],
            ["战斗策划", "李枪", "武器/干员/模式文案准确性"],
            ["商业化策划", "王商", "商城、通行证、合规表述"],
            ["本地化负责人", "赵译", "译文质量、术语表"],
            ["LQA 负责人", "钱测", "用例、执行、缺陷分级"],
            ["客户端", "孙端", "UI 适配、RTL、字体、字幕"],
            ["发行/法务", "周发", "目标市场合规、未决项拍板"],
        ],
        col_widths=[3.5, 3.0, 9.0],
    )

    # 附件
    doc.add_page_break()
    doc.add_paragraph("附件 A：风格指南摘要", style="Heading 1")
    add_bullets(
        doc,
        [
            "HUD：全大写缩写可保留（HUD、UI、FPS）；完整句则不用全大写。",
            "枪械名：官方授权名优先；无授权时用中性描述名，禁生造商标感词。",
            "干员代号：呼号保留不意译（如「红狼」可音译+注释），技能名可意译。",
            "按钮：动词优先（部署、撤离、改装、购买）。",
            "错误：原因 + 下一步；禁止只显示错误码。",
            "占位符：{xxx} 不翻译、不改花括号。",
        ],
    )

    doc.add_paragraph("附件 B：占位符清单（节选）", style="Heading 1")
    add_table(
        doc,
        ["占位符", "含义", "示例"],
        [
            ["{player_name}", "玩家昵称", "Ghost-07"],
            ["{operator_name}", "干员代号", "Stinger"],
            ["{weapon_name}", "武器名", "M4A1"],
            ["{map_name}", "地图名", "Ascension"],
            ["{objective}", "据点名", "Bravo"],
            ["{count}", "数量", "3"],
            ["{time}", "时间/倒计时", "00:45"],
            ["{value}", "属性数值", "72"],
            ["{currency}", "货币", "2,400"],
            ["{season}", "赛季名", "Season 3"],
        ],
        col_widths=[3.5, 3.5, 8.5],
    )

    doc.add_paragraph("附件 C：LQA 平台对接", style="Heading 1")
    add_para(doc, "用例建议在 lqa-platform 按下表类别生成；模块名使用第 3 章中文模块名，便于筛选。")
    add_table(
        doc,
        ["重点模块", "优先 LQA 类别"],
        [
            ["主界面 HUD / 击杀播报", "TEXT_OVERFLOW, LAYOUT, LINE_BREAK"],
            ["干员与枪械列表", "TERMINOLOGY, FONT, TEXT_OVERFLOW"],
            ["烽火地带仓库/市场", "DATE_FORMAT, PLACEHOLDER, TERMINOLOGY"],
            ["商城与通行证", "CULTURAL, DATE_FORMAT, TEXT_OVERFLOW"],
            ["阿语全界面", "RTL, FONT_MISSING, LAYOUT"],
            ["语音字幕", "VOICE_SUB, LINE_BREAK"],
            ["图内 Banner", "IMAGE_TEXT, CULTURAL"],
        ],
        col_widths=[5.0, 10.5],
    )

    doc.add_paragraph("附件 D：变更记录", style="Heading 1")
    add_table(
        doc,
        ["版本", "日期", "作者", "说明"],
        [
            ["v0.8", "2026-09-05", "张策", "草稿，仅战斗与烽火地带"],
            ["v0.9", "2026-09-12", "张策", "补社交、商业化、系统模块"],
            ["v1.0", "2026-09-18", "张策", "提测：全模块范围 + 术语 + 验收红线；提交本地化/LQA"],
        ],
        col_widths=[2.5, 3.0, 3.0, 7.0],
    )

    doc.add_paragraph()
    add_para(doc, "—— 以下无正文 ——")

    doc.core_properties.title = "三角洲行动本地化需求（策划提测）"
    doc.core_properties.author = "系统策划组 / 张策"
    doc.core_properties.subject = "战术射击海外本地化需求"
    doc.core_properties.comments = "模拟策划提测文档：全模块范围样例，供 LQA 需求评审"

    if OUT.exists():
        alt = OUT.with_name(OUT.stem + "_alt.docx")
        doc.save(alt)
        print(f"OK (alt) {alt}")
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        doc.save(OUT)
        print(f"OK {OUT}")


if __name__ == "__main__":
    build()
