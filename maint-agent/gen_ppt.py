# -*- coding: utf-8 -*-
"""生成《Maint-Agent 答辩 PPT》。运行：python gen_ppt.py"""
import math
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Cm, Pt

OUT_DIR = Path(__file__).parent
PRIMARY = RGBColor(0x1A, 0x36, 0x5D)
ACCENT = RGBColor(0x2B, 0x6C, 0xB0)
LIGHT = RGBColor(0xEA, 0xF1, 0xF9)
GRAY = RGBColor(0x44, 0x44, 0x44)
MUTED = RGBColor(0x77, 0x77, 0x77)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
WARN = RGBColor(0xC0, 0x54, 0x1E)

SLIDE_W = Cm(33.87)   # 16:9
SLIDE_H = Cm(19.05)

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


def set_cjk(run, font="微软雅黑"):
    run.font.name = font
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", font)


def add_box(slide, x, y, w, h, fill=None, line=None, shadow=False, round_=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if round_ else MSO_SHAPE.RECTANGLE
    sp = slide.shapes.add_shape(shape_type, x, y, w, h)
    if round_:
        try:
            sp.adjustments[0] = 0.08
        except Exception:
            pass
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp


def add_text(slide, x, y, w, h, runs, size=16, color=GRAY, bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.15,
             space_after=4):
    """runs: str 或 [(text, {size,color,bold}), ...]（每项为一段）"""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [(runs, {})]
    for i, (text, opt) in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = opt.get("align", align)
        p.line_spacing = opt.get("line_spacing", line_spacing)
        p.space_after = Pt(opt.get("space_after", space_after))
        r = p.add_run()
        r.text = text
        r.font.size = Pt(opt.get("size", size))
        r.font.bold = opt.get("bold", bold)
        r.font.color.rgb = opt.get("color", color)
        set_cjk(r)
    return tb


def slide_header(slide, title, subtitle=None, page=None):
    add_box(slide, 0, 0, SLIDE_W, Cm(0.18), fill=PRIMARY)
    add_text(slide, Cm(1.2), Cm(0.7), Cm(28), Cm(1.6),
             [(title, {"size": 28, "color": PRIMARY, "bold": True})])
    if subtitle:
        add_text(slide, Cm(1.2), Cm(2.0), Cm(31), Cm(1.0),
                 [(subtitle, {"size": 14, "color": MUTED})])
    add_box(slide, Cm(1.25), Cm(1.85), Cm(2.2), Cm(0.07), fill=ACCENT)
    if page:
        add_text(slide, SLIDE_W - Cm(3), SLIDE_H - Cm(1.3), Cm(2), Cm(0.8),
                 [(str(page), {"size": 12, "color": MUTED, "align": PP_ALIGN.RIGHT})])


def bullet_list(slide, x, y, w, h, items, size=16, gap=10):
    runs = []
    for it in items:
        if isinstance(it, tuple):
            head, rest = it
            runs.append((f"▎{head}", {"size": size, "color": ACCENT, "bold": True, "space_after": 2}))
            runs.append((rest, {"size": size, "color": GRAY, "space_after": gap}))
        else:
            runs.append((f"▎{it}", {"size": size, "color": GRAY, "space_after": gap}))
    add_text(slide, x, y, w, h, runs)


def card(slide, x, y, w, h, head, body, head_size=15, body_size=12.5,
         fill=LIGHT, head_color=PRIMARY, bar=ACCENT):
    add_box(slide, x, y, w, h, fill=fill, round_=True)
    add_box(slide, x, y, Cm(0.14), h, fill=bar)
    add_text(slide, x + Cm(0.45), y + Cm(0.3), w - Cm(0.8), Cm(1.1),
             [(head, {"size": head_size, "bold": True, "color": head_color})])
    add_text(slide, x + Cm(0.45), y + Cm(1.45), w - Cm(0.8), h - Cm(1.7),
             [(body, {"size": body_size, "color": GRAY, "line_spacing": 1.15})])


def arrow(slide, x, y, w, h, fill=ACCENT):
    sp = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x, y, w, h)
    sp.fill.solid()
    sp.fill.fore_color.rgb = fill
    sp.line.fill.background()
    sp.shadow.inherit = False
    return sp


# ================= P1 封面 =================
s = prs.slides.add_slide(BLANK)
add_box(s, 0, 0, SLIDE_W, SLIDE_H, fill=PRIMARY)
add_box(s, 0, SLIDE_H - Cm(1.1), SLIDE_W, Cm(1.1), fill=ACCENT)
add_text(s, Cm(2), Cm(4.2), Cm(30), Cm(1.4),
         [("第二届全国人工智能应用创新大赛 · 校内选拔", {"size": 18, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(6.2), Cm(30), Cm(3.6),
         [("Maint-Agent", {"size": 54, "color": WHITE, "bold": True, "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(9.6), Cm(30), Cm(2.2),
         [("面向中小型机加工场景的设备维保智能体", {"size": 26, "color": WHITE, "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(12.4), Cm(30), Cm(1.2),
         [("让 AI Agent 赋能千行百业 · 制造方向", {"size": 16, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(15.2), Cm(30), Cm(2.2),
         [("参赛团队：【队长姓名】 【队员姓名】　指导教师：【教师姓名】", {"size": 14, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER, "space_after": 2}),
          ("太原科技大学 · 2026 年 11 月", {"size": 14, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER})])

# ================= P2 行业痛点 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "行业痛点：中小机加工厂的设备维保困局", "设备停机 = 产值损失，而维保体系却停留在“纸质本子 + 微信群”时代", 2)
pts = [
    ("经验流失", "说明书、图纸、维修记录散落各处，老师傅一离职，多年经验随之清零"),
    ("排查低效", "师傅看不懂复杂报警码，冷门故障无人指导，每次从头试错"),
    ("记录零散", "点检、报修、备件申领靠微信和纸本，无沉淀、无提醒、无统计"),
    ("平台太重", "大型工业互联网平台价格高、部署重，中小工厂“买不起、用不动”"),
]
for i, (h, b) in enumerate(pts):
    x = Cm(1.6) + Cm(7.8) * (i % 2)
    y = Cm(3.6) + Cm(4.6) * (i // 2)
    card(s, x, y, Cm(7.4), Cm(4.1), h, b, head_size=17, body_size=13)
add_box(s, Cm(17.6), Cm(3.6), Cm(14.8), Cm(8.7), fill=PRIMARY, round_=True)
add_text(s, Cm(18.4), Cm(4.3), Cm(13.2), Cm(1.2),
         [("我们的目标", {"size": 18, "color": WHITE, "bold": True})])
add_text(s, Cm(18.4), Cm(5.8), Cm(13.2), Cm(6.2),
         [("用“轻软件 + 大模型 + 知识自沉淀”替代重资产平台，", {"size": 15, "color": WHITE, "line_spacing": 1.35}),
          ("让每一家中小机加工厂都用得起一位 7×24 小时在线、", {"size": 15, "color": WHITE, "line_spacing": 1.35}),
          ("越用越懂本厂设备的维保老师傅。", {"size": 15, "color": WHITE, "line_spacing": 1.35})])

# ================= P3 系统架构 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "系统架构：四层架构 + 双知识引擎", "大模型只负责调度与表达，核心推理全部落在确定性代码上", 3)
layers = [
    ("大模型调度层", "DeepSeek 意图理解 · 任务拆解 · 工具决策 · 回复生成", PRIMARY, WHITE),
    ("Agent 任务规划层", "Function Calling 多轮编排：识码 → 查图谱 → 调案例 → 核备件 → 开工单 → 跟闭环", ACCENT, WHITE),
    ("领域知识库层", "故障树知识图谱（结构化因果链推理） ＋ RAG 文档库（手册 · 保养规范 · 历史案例，BM25 检索）", LIGHT, PRIMARY),
    ("外部工具层", "工单生成 · 备件库存查询 · 维修入库（知识回流） · 维保月度统计", LIGHT, PRIMARY),
]
y = Cm(3.8)
for i, (h, b, fill, fc) in enumerate(layers):
    add_box(s, Cm(2.2), y, Cm(19.5), Cm(2.9), fill=fill, round_=True)
    add_text(s, Cm(3.0), y + Cm(0.35), Cm(18), Cm(1.0),
             [(h, {"size": 17, "bold": True, "color": fc})])
    add_text(s, Cm(3.0), y + Cm(1.4), Cm(18), Cm(1.3),
             [(b, {"size": 12.5, "color": fc})])
    if i < 3:
        arrow(s, Cm(11.4), y + Cm(2.95), Cm(1.1), Cm(0.75))
    y += Cm(3.7)
add_box(s, Cm(23.2), Cm(3.8), Cm(9.2), Cm(13.9), fill=LIGHT, round_=True)
add_text(s, Cm(23.9), Cm(4.2), Cm(7.8), Cm(1.1),
         [("关键工程决策", {"size": 16, "bold": True, "color": PRIMARY})])
add_text(s, Cm(23.9), Cm(5.5), Cm(7.8), Cm(11.8),
         [("纯 RAG 擅长“查资料”，不擅长链式推理；", {"size": 13, "color": GRAY, "line_spacing": 1.3, "space_after": 8}),
          ("故障排查是典型的因果链推理任务。", {"size": 13, "color": GRAY, "line_spacing": 1.3, "space_after": 8}),
          ("因此采用：", {"size": 13, "color": GRAY, "line_spacing": 1.3, "space_after": 4}),
          ("图谱推理 ＋ RAG 补充", {"size": 15, "color": ACCENT, "bold": True, "space_after": 8}),
          ("双引擎互补：图谱压住幻觉，RAG 补齐覆盖面。", {"size": 13, "color": GRAY, "line_spacing": 1.3})])

# ================= P4 演示链路工作流程 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "一次完整的故障处置：从一句报修到知识沉淀", "示例：师傅输入“VMC850 开机报伺服过载 X03”", 4)
steps = [
    ("1 识别", "match_fault\n报警码 X03 命中\n“伺服过载”故障节点"),
    ("2 推理", "get_causes\n9 类诱因\n按“由简到繁”排序"),
    ("3 检索", "search_docs\nFANUC 手册 +\n本厂历史维修案例"),
    ("4 处置", "query_parts\n核备件库存\ncreate_workorder"),
    ("5 闭环", "log_repair\n修复确认入库\n进入图谱待审核队列"),
]
w = Cm(5.6)
gap = (Cm(32.2) - Cm(1.4) - w * 5) / 4
x = Cm(1.6)
for i, (h, b) in enumerate(steps):
    fill = PRIMARY if i in (0, 4) else ACCENT
    add_box(s, x, Cm(4.0), w, Cm(1.6), fill=fill, round_=True)
    add_text(s, x, Cm(4.15), w, Cm(1.3),
             [(h, {"size": 16, "bold": True, "color": WHITE, "align": PP_ALIGN.CENTER})])
    add_box(s, x, Cm(5.8), w, Cm(4.6), fill=LIGHT, round_=True)
    add_text(s, x + Cm(0.3), Cm(6.1), w - Cm(0.6), Cm(4.1),
             [(b, {"size": 12.5, "color": GRAY, "align": PP_ALIGN.CENTER, "line_spacing": 1.25})])
    if i < 4:
        arrow(s, x + w + Cm(0.05), Cm(4.5), gap - Cm(0.1), Cm(0.7))
    x += w + gap
add_box(s, Cm(1.6), Cm(11.4), Cm(30.6), Cm(6.2), fill=LIGHT, round_=True)
add_text(s, Cm(2.3), Cm(11.8), Cm(29.5), Cm(5.5),
         [("智能体的实际回复（端到端实测摘录）", {"size": 15, "bold": True, "color": PRIMARY, "space_after": 8}),
          ("① 先断电、挂“禁止合闸”警示牌 —— 高危操作强制提醒；", {"size": 13.5, "color": GRAY, "space_after": 5}),
          ("② 第 1 步（最简单）：检查伺服电机线缆接头是否松动、有无明显磨损 —— 通俗语言、逐步引导；", {"size": 13.5, "color": GRAY, "space_after": 5}),
          ("③ 本厂 8 月 12 日同型号机床出现过同类报警，最终确认是 X 轴编码器线缆破损，更换后恢复 —— 主动引用历史案例；", {"size": 13.5, "color": GRAY, "space_after": 5}),
          ("④ 师傅反馈“修好了”后，自动抽取结构化字段写入台账，并进入图谱待审核队列。", {"size": 13.5, "color": GRAY})])

# ================= P5 创新点 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "创新点：双引擎推理 + 知识自回流闭环", "回应工业大模型落地最难的两个问题——幻觉与知识更新", 5)
card(s, Cm(1.6), Cm(3.8), Cm(15.2), Cm(6.6),
     "★ 双知识引擎融合",
     "知识图谱负责确定性因果推理（设备-报警码-故障-诱因-动作-备件的结构化链路），\n"
     "RAG 负责海量非结构化细节（手册原文、历史案例）。\n"
     "图谱压住大模型幻觉，RAG 补齐知识覆盖面——二者互补，直击工业 AI 落地关键难题。",
     head_size=17, body_size=13.5)
card(s, Cm(17.2), Cm(3.8), Cm(15.2), Cm(6.6),
     "★ 知识自回流闭环",
     "每一次真实维修确认后，维修路径自动进入“待人工审核队列”；\n"
     "管理员用审核工具一键并入图谱，图谱版本自动升级。\n"
     "系统越用越懂本厂设备，维保经验从“老师傅脑子里的隐性知识”变成“企业账上的显性资产”。",
     head_size=17, body_size=13.5)
card(s, Cm(1.6), Cm(10.9), Cm(15.2), Cm(6.6),
     "★ 工业风控设计",
     "“由简到繁”排查排序（成本低、风险低的诱因优先）；\n"
     "结论置信度标注，无可靠依据明确说“不确定”；\n"
     "带电操作、参数修改等高危动作强制风险提醒。\n"
     "直面工业 AI 最受关注的安全性质疑。",
     head_size=17, body_size=13.5, bar=WARN)
card(s, Cm(17.2), Cm(10.9), Cm(15.2), Cm(6.6),
     "★ 车间场景适配",
     "通俗语言交互，说人话不堆术语；\n"
     "逐步引导式排查：一次只让师傅做一步，等反馈再继续，\n"
     "而非一次性甩出长文——贴合一线师傅真实使用习惯。",
     head_size=17, body_size=13.5)

# ================= P6 端到端实测 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "实施验证：可运行原型 + 真实大模型端到端实测",
             "同一故障：人工翻 3 份文档约 1420 字 ≈ 6 分钟（估算）vs Agent 一句话 5 秒级给出 6 诱因 · 17 步排查链", 6)
rows = [
    ("故障树知识图谱", "2 个设备型号（VMC850 / VMC650）· 4 类故障 · 14 类诱因 · 6 类备件；跨型号平移验证通过——新增型号只增补数据、架构零改动"),
    ("RAG + Agent", "纯 Python BM25 首条命中历史案例；DeepSeek Function Calling 多轮调度 7 个工具，API 超时自动重试"),
    ("语音与日志接入", "语音报修实测（Edge/Chrome 转写自动填充）；日志适配层实测：20 秒内 2 次报警全部自动命中图谱并自动建单，全程无人操作"),
    ("端到端实测", "真实调用 DeepSeek：报修 → 图谱推理 → RAG 案例 → 通俗排查指引；修复后自动入库进回流队列；系统自测 7 项全部通过"),
    ("量化对比（benchmark 实测）", "人工：4 个查找动作 × 3 份文档 × 通读约 1420 字 ≈ 6 分钟（估算）；Agent：1 句话输入 5.3s 返回 6 诱因 17 步骤 + 历史案例，修复回流 4.6s"),
    ("回流审核与演示保障", "Web 一键审核：案例并入图谱、版本自动升级（实测）；一键启动 + 状态一键重置，支撑现场反复演示"),
]
y = Cm(3.7)
for h, b in rows:
    add_box(s, Cm(1.6), y, Cm(6.4), Cm(2.15), fill=PRIMARY, round_=True)
    add_text(s, Cm(1.9), y, Cm(5.8), Cm(2.15),
             [(h, {"size": 14.5, "bold": True, "color": WHITE, "align": PP_ALIGN.CENTER})],
             anchor=MSO_ANCHOR.MIDDLE)
    add_box(s, Cm(8.2), y, Cm(24.2), Cm(2.15), fill=LIGHT, round_=True)
    add_text(s, Cm(8.7), y + Cm(0.2), Cm(23.2), Cm(1.8),
             [(b, {"size": 12.5, "color": GRAY, "line_spacing": 1.15})],
             anchor=MSO_ANCHOR.MIDDLE)
    y += Cm(2.45)

# ================= P7 安全风控 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "安全风控：把“不确定”和“危险”说在前面", "工业场景下，宁可承认不会，绝不能编造", 7)
risks = [
    ("诊断错误风险", "故障树由简到繁排序 · 不确定结论强制标注 · 高危操作建议联系厂家工程师"),
    ("知识盲区风险", "图谱未覆盖的新型故障自动切换 RAG 检索并标记待补充，管理员审核后入谱"),
    ("数据真实风险", "手册整理自 FANUC 公开报警资料、故障树基于行业通用方法、台账为明确标注的仿真数据；不虚构企业合作，真实数据随试点接入"),
    ("模型依赖风险", "图谱排序、检索、工具均为确定性代码，大模型仅承担调度与表达，更换底层模型不影响系统骨架"),
]
y = Cm(3.8)
for h, b in risks:
    add_box(s, Cm(1.6), y, Cm(30.8), Cm(3.0), fill=LIGHT, round_=True)
    add_box(s, Cm(1.6), y, Cm(0.14), Cm(3.0), fill=WARN)
    add_text(s, Cm(2.2), y + Cm(0.35), Cm(6.5), Cm(2.3),
             [(h, {"size": 15.5, "bold": True, "color": WARN})],
             anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Cm(9.2), y + Cm(0.35), Cm(22.6), Cm(2.3),
             [("对策：", {"size": 13.5, "bold": True, "color": PRIMARY}),
              (b, {"size": 13.5, "color": GRAY, "line_spacing": 1.2})],
             anchor=MSO_ANCHOR.MIDDLE)
    y += Cm(3.4)

# ================= P8 应用前景 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "应用前景：从一台机床到一个行业", "方案的核心资产是知识组织方式，可低成本横向复制", 8)
fwd = [
    ("直接价值", "降低中小机加工厂故障排查时间与停机损失，把老师傅经验沉淀为企业知识资产"),
    ("横向拓展", "跨型号平移已验证（VMC850 → VMC650 仅增补故障树数据）；向注塑、纺织等场景扩展只需替换语料"),
    ("技术演进", "采集卡升级为真实硬件协议接入；YOLO 视觉部件识别与多模态维保助手（区域赛规划）"),
    ("模式创新", "“轻软件 + 大模型 + 知识自沉淀”替代重资产工业平台，为量大面广的中小企业提供买得起的 AI 维保方案"),
]
y = Cm(3.9)
for i, (h, b) in enumerate(fwd):
    num = add_box(s, Cm(1.8), y, Cm(1.7), Cm(1.7), fill=PRIMARY, round_=True)
    add_text(s, Cm(1.8), y + Cm(0.18), Cm(1.7), Cm(1.4),
             [(str(i + 1), {"size": 20, "bold": True, "color": WHITE, "align": PP_ALIGN.CENTER})])
    add_text(s, Cm(4.3), y, Cm(8), Cm(1.7),
             [(h, {"size": 17, "bold": True, "color": PRIMARY})],
             anchor=MSO_ANCHOR.MIDDLE)
    add_text(s, Cm(12.5), y, Cm(19.8), Cm(1.7),
             [(b, {"size": 14, "color": GRAY, "line_spacing": 1.2})],
             anchor=MSO_ANCHOR.MIDDLE)
    y += Cm(3.3)

# ================= P9 进度安排 =================
s = prs.slides.add_slide(BLANK)
slide_header(s, "项目进度安排（2026 年）", "当前已完成可运行原型与端到端实测，按赛程稳步推进", 9)
phases = [
    ("10 月下旬", "需求调研与方案设计", "确定“图谱推理 + RAG 补充”双引擎架构", True),
    ("11 月上旬", "系统开发与实测", "知识图谱 / RAG / 工具层 / Agent 主循环完成，Web 演示上线，端到端实测通过", True),
    ("11 月中旬", "校级评审", "根据发题要求适配指定智能体平台", False),
    ("11 下旬–12 月", "区域赛", "故障树扩充至 10 类以上故障，开展真实工况试用与效果量化", False),
    ("12 月下旬", "总决赛", "完善多模态能力演示与推广方案", False),
]
x0, w, gap = Cm(1.6), Cm(5.9), Cm(0.55)
add_box(s, x0 + Cm(0.3), Cm(5.2), w * 5 + gap * 4 - Cm(0.6), Cm(0.12), fill=RGBColor(0xC9, 0xD6, 0xE6))
for i, (t, h, b, done) in enumerate(phases):
    x = x0 + (w + gap) * i
    dot_fill = ACCENT if done else RGBColor(0xC9, 0xD6, 0xE6)
    dot = slide_dot = s.shapes.add_shape(MSO_SHAPE.OVAL, x + w / 2 - Cm(0.45), Cm(4.85), Cm(0.9), Cm(0.9))
    dot.fill.solid()
    dot.fill.fore_color.rgb = dot_fill
    dot.line.color.rgb = WHITE
    dot.line.width = Pt(2)
    dot.shadow.inherit = False
    add_text(s, x, Cm(3.9), w, Cm(0.9),
             [(t, {"size": 14, "bold": True, "color": PRIMARY, "align": PP_ALIGN.CENTER})])
    add_box(s, x, Cm(6.2), w, Cm(7.6), fill=LIGHT, round_=True)
    mark = "✓ 已完成" if done else "计划中"
    add_text(s, x + Cm(0.3), Cm(6.5), w - Cm(0.6), Cm(0.9),
             [(mark, {"size": 11.5, "bold": True, "color": ACCENT if done else MUTED, "align": PP_ALIGN.CENTER})])
    add_text(s, x + Cm(0.3), Cm(7.6), w - Cm(0.6), Cm(1.4),
             [(h, {"size": 14.5, "bold": True, "color": PRIMARY, "align": PP_ALIGN.CENTER, "line_spacing": 1.1})])
    add_text(s, x + Cm(0.35), Cm(9.3), w - Cm(0.7), Cm(4.3),
             [(b, {"size": 11.5, "color": GRAY, "align": PP_ALIGN.CENTER, "line_spacing": 1.2})])
add_text(s, Cm(1.6), Cm(14.6), Cm(30.6), Cm(2.6),
         [("注：进度安排以实际赛程文件为准，校级评审与平台适配时间随主办方通知动态调整。",
           {"size": 12, "color": MUTED})])

# ================= P10 结尾 =================
s = prs.slides.add_slide(BLANK)
add_box(s, 0, 0, SLIDE_W, SLIDE_H, fill=PRIMARY)
add_box(s, 0, 0, SLIDE_W, Cm(1.1), fill=ACCENT)
add_text(s, Cm(2), Cm(6.6), Cm(30), Cm(2.6),
         [("谢谢评委老师", {"size": 44, "color": WHITE, "bold": True, "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(10.0), Cm(30), Cm(1.4),
         [("Maint-Agent —— 让每家中小工厂都有一位越用越懂它的维保老师傅",
           {"size": 18, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER})])
add_text(s, Cm(2), Cm(13.6), Cm(30), Cm(1.2),
         [("现场演示环节：欢迎扫码/观看 Web 系统实测", {"size": 14, "color": RGBColor(0xB9, 0xCE, 0xE8), "align": PP_ALIGN.CENTER})])

out = OUT_DIR / "Maint-Agent答辩PPT.pptx"
prs.save(out)
print("已生成：", out)
