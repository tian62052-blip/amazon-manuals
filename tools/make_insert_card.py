#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成包装盒内的售后卡片印刷稿（正反双面，矢量 PDF + 预览 PNG）。

和 make_print_artwork.py 的关系：
    make_print_artwork.py  出的是印在彩盒外面的那一小块二维码
    make_insert_card.py    出的是塞在盒子里的整张卡片（85x54mm 名片规格）

两者编码同一个地址，绝不能不一致——盒外扫到 A 页、盒内扫到 B 页，
售后会当场变成两套说法。地址常量统一从 make_print_artwork 引入。

版面要点：
    正面 = 品牌 + 抽象产品线描图 + "SCAN FOR USER MANUAL" + 右下角二维码
    背面 = 精简版常见问题（取自 B03 说明书第 7 页）+ 售后电话/邮箱
    橙色只做点缀（品牌条、标题重音、底部色块），主色是白底+炭黑字，
    这样 300g 白卡上四色印刷成本最低，也不会和亚马逊的橙抢眼。

用法:
    pip install segno reportlab fonttools pillow pymupdf
    python make_insert_card.py
    python make_insert_card.py --no-preview
"""

import argparse
import os
import sys

try:
    import segno
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from PIL import Image
except ImportError as e:
    sys.exit("缺少依赖: %s\n请运行:  pip install segno reportlab fonttools pillow pymupdf" % e)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_print_artwork import GlyphOutliner, PT_PER_MM, URL   # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# --- 版面参数 (mm) ---------------------------------------------------
TRIM_W, TRIM_H = 85.0, 54.0   # 成品尺寸，标准名片
BLEED = 3.0                   # 出血
MARK = 3.0                    # 出血外再留一圈给裁切线
PAGE_W = TRIM_W + 2 * (BLEED + MARK)
PAGE_H = TRIM_H + 2 * (BLEED + MARK)
ORIGIN = BLEED + MARK         # 成品框左下角在页面里的位置

SAFE = 5.0                    # 安全边距：重要内容不进这一圈

QR_MM = 23.0                  # 卡片上的二维码边长（含 4 模块静空白区）
LOGO_RATIO = 0.28             # 中心挖空边长占二维码边长的比例

# --- 正面版面 (mm) ---------------------------------------------------
# 左边标题的左边距 = 右边白面板的右边距，两侧对称。早先左 7mm、右 2.2mm，
# 整个正面看着往右偏。
FRONT_MARGIN = 6.5
PLATE_PAD = 2.8               # 白面板四周比二维码宽出多少
PLATE_TOP = 34.6              # 面板上沿，压在空心字下方
PLATE_BOTTOM = 3.6            # 面板下沿
QR_X = TRIM_W - FRONT_MARGIN - PLATE_PAD - QR_MM
QR_Y = PLATE_TOP - PLATE_PAD - QR_MM
# 标题分两级：SCAN FOR 细体小字带出 USER MANUAL 粗体大字。
# 两行同字重同字号时只是两行字，拉开层级后才有"一句标题"的读法。
TITLE_SMALL_PT = 11.0
TITLE_BIG_PT = 15.5
TITLE_LEAD = 7.5              # 两行基线间距
# 标注图也用 QR_X / QR_Y，两处各写一份的话，标注图迟早会写错位置

FONT_BOLD = r"C:\Windows\Fonts\arialbd.ttf"
FONT_REG = r"C:\Windows\Fonts\arial.ttf"
FONT_ITALIC = r"C:\Windows\Fonts\ariali.ttf"

# 正面背景：大号 WINDIN，空心描边，横向铺满整页。
# 早先做过高斯虚化版，那个只能走光栅；改描边后整个正面回到纯矢量，
# 文件里一张位图都没有，印厂 preflight 更干净，放大也不糊。
WORDMARK = "WINDIN"
WORDMARK_W_MM = 91.0      # = 出血宽度。两端正好抵住出血边，裁切后微微出血
# 字压在上半部当横幅，把下半部整个让给标题和二维码。
# 试过居中铺满：二维码的白底板会从 DIN 三个字母上啃掉一个方口子，
# 底板做宽做圆也盖不住，那就是印坏了的样子。错开比遮挡干净。
WORDMARK_CY_MM = 45.5     # 大写字高的中线位置（成品坐标系）
WORDMARK_STROKE_MM = 0.6  # 描边粗细。再细胶印会断线，再粗就压过标题了

QR_CENTER_LOGO = False    # 中心是否放产品标记。极简版关掉

# --- 颜色 (CMYK) -----------------------------------------------------
# 文字一律单黑：四色黑在小字号下套印不准会发虚。
INK = (0, 0, 0, 0.88)          # 正文炭黑
INK_SOFT = (0, 0, 0, 0.55)     # 次要说明文字
ORANGE = (0, 0.62, 0.88, 0)    # 品牌橙
ORANGE_TINT = (0, 0.07, 0.11, 0)   # 底部色块，很淡
WHITE = (0, 0, 0, 0)

# 正面满铺底色。比 ORANGE 稍压一点，浅字压上去才够对比；
# 再深就发红发褐，不像橙了。
ORANGE_FLOOD = (0, 0.66, 0.94, 0.03)
# 正面所有文字和空心字都用这个米黄，不用纯白：橙底上纯白偏冷、偏硬，
# 米黄和底色是同一支暖色，整个正面才是一套颜色。
CREAM = (0, 0.09, 0.27, 0)


# ---------------------------------------------------------------------
# 文字
# ---------------------------------------------------------------------
class Text:
    """把 GlyphOutliner 包一层，补上字距、对齐和自动换行。"""

    def __init__(self, path):
        self.out = GlyphOutliner(path)

    def width(self, text, size_pt, tracking_pt=0.0):
        if not text:
            return 0.0
        w = self.out.text_width(text) * size_pt
        return w + tracking_pt * (len(text) - 1)

    def draw(self, c, text, size_pt, x_pt, y_pt, tracking_pt=0.0, align="left"):
        """x/y 单位为 pt，y 是基线。align: left / center / right。"""
        if not text:
            return
        w = self.width(text, size_pt, tracking_pt)
        if align == "center":
            x_pt -= w / 2.0
        elif align == "right":
            x_pt -= w
        cursor = x_pt
        for ch in text:
            self.out.draw(c, ch, size_pt, cursor, y_pt)
            gn = self.out.cmap[ord(ch)]
            cursor += self.out.hmtx[gn][0] * size_pt / self.out.upem + tracking_pt

    def wrap(self, text, size_pt, max_w_pt, tracking_pt=0.0):
        """按空格断行。字号这么小，不做连字符断词。"""
        words, lines, cur = text.split(), [], ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if self.width(trial, size_pt, tracking_pt) <= max_w_pt or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines


def set_ink(c, cmyk):
    c.setFillColorCMYK(*cmyk)


def rect_mm(c, x, y, w, h, cmyk):
    set_ink(c, cmyk)
    c.rect(x * mm, y * mm, w * mm, h * mm, stroke=0, fill=1)


# ---------------------------------------------------------------------
# 裁切线
# ---------------------------------------------------------------------
def crop_marks(c):
    """画在出血框之外，成品框的四条边延长线上。100% 单黑细线。"""
    c.setStrokeColorCMYK(0, 0, 0, 1)
    c.setLineWidth(0.25)
    x0, y0 = ORIGIN, ORIGIN
    x1, y1 = ORIGIN + TRIM_W, ORIGIN + TRIM_H
    for x in (x0, x1):
        c.line(x * mm, 0, x * mm, MARK * mm)
        c.line(x * mm, PAGE_H * mm, x * mm, (PAGE_H - MARK) * mm)
    for y in (y0, y1):
        c.line(0, y * mm, MARK * mm, y * mm)
        c.line(PAGE_W * mm, y * mm, (PAGE_W - MARK) * mm, y * mm)


# ---------------------------------------------------------------------
# 二维码
# ---------------------------------------------------------------------
def draw_qr(c, url, x, y, side_mm):
    """左下角 (x, y)，单位 mm。纠错 H，中心挖空放产品标记。

    中心挖空 26% 边长 = 6.8% 面积，远低于 H 级 30% 的恢复上限，
    再叠加 4 模块静空白区，扫描裕度足够。
    """
    qr = segno.make(url, error='h', micro=False)
    matrix = list(qr.matrix_iter(scale=1, border=4))
    n = len(matrix)
    module = side_mm / n

    set_ink(c, INK if False else (0, 0, 0, 1))   # 二维码必须 100% 单黑
    step = module * mm
    top = (y + side_mm) * mm
    for r, row in enumerate(matrix):
        cs = 0
        while cs < n:
            if row[cs]:
                ce = cs
                while ce + 1 < n and row[ce + 1]:
                    ce += 1
                c.rect(x * mm + cs * step, top - (r + 1) * step,
                       (ce - cs + 1) * step, step, stroke=0, fill=1)
                cs = ce + 1
            else:
                cs += 1

    # 中心挖空 + 产品标记。极简版不放，QR_CENTER_LOGO 置 True 即可恢复。
    if QR_CENTER_LOGO:
        ko = side_mm * LOGO_RATIO
        cx, cy = x + side_mm / 2.0, y + side_mm / 2.0
        set_ink(c, WHITE)
        c.roundRect((cx - ko / 2) * mm, (cy - ko / 2) * mm, ko * mm, ko * mm,
                    (ko * 0.18) * mm, stroke=0, fill=1)
        # 标记只占挖空的 76%，四周留一圈白。挤满会和周围模块糊成一片。
        # 剪影是斜向的，外接框近似正方，四角本来就留白，可以给得比横向剪影大些。
        draw_clicker_mark(c, cx, cy, ko * 0.76)
    return qr.version


def draw_clicker_mark(c, cx, cy, size_mm):
    """二维码中心的点击器剪影。

    这里不用 B03 线描图：那张图在 5mm 见方里全是发丝线，印出来是一团灰，
    还会吃掉二维码的纠错余量。改画一个能在 5mm 下看清的实心剪影。

    照实物主图的姿态画：机身是一根 45° 斜条压在右上，转臂从机身左下端
    伸出，末端一颗圆点击头落在左下角。前两版画成"横躺的机身 + 夹座"，
    朝向和实物相反，怎么调都只是一坨方块——姿态错了，细节再多也没用。

    斜向构图另有一个好处：轮廓沿对角线铺开，方形挖空的四角自然留白，
    不会像横向剪影那样两侧顶到边、上下空一片。

    三个部件必须互相咬合成连通轮廓：转臂两端分别埋进机身端头和点击头内部，
    留缝的话印出来就是断开的几块。
    """
    s = size_mm / 100.0                       # 图形在 100x100 单位内绘制
    def X(u):
        return (cx - size_mm / 2.0 + u * s) * mm
    def Y(v):
        return (cy - size_mm / 2.0 + v * s) * mm
    def L(u):
        return u * s * mm

    set_ink(c, (0, 0, 0, 1))

    # 点击头：左下角那颗圆头
    c.circle(X(17), Y(17), L(17), stroke=0, fill=1)

    # 转臂：45° 斜向连接点击头与机身，两端分别埋进头和机身内部。
    # 必须明显比机身和点击头细——三者粗细相近时会连成一根锥形棍子，
    # 看着像把勺子，读不出"点击头—颈—机身"三段。
    c.setStrokeColorCMYK(0, 0, 0, 1)
    c.setLineWidth(L(10))
    c.setLineCap(1)
    p = c.beginPath()
    p.moveTo(X(24), Y(24))
    p.lineTo(X(48), Y(48))
    c.drawPath(p, stroke=1, fill=0)

    # 机身：45° 斜条，两端全圆角。旋转后坐标系原点在机身中心，
    # 所以 roundRect 从 (-长/2, -宽/2) 起画。
    c.saveState()
    c.translate(X(68), Y(68))
    c.rotate(45)
    c.roundRect(-L(25), -L(17), L(50), L(34), L(17), stroke=0, fill=1)
    c.restoreState()


# ---------------------------------------------------------------------
# 正面背景：空心描边的 WINDIN
# ---------------------------------------------------------------------
def draw_wordmark(c, txt_obj):
    """把 WINDIN 按字形轮廓描边画出来，横向铺满整页。

    走的是 Text 里那套字形转曲的路子，只是把 drawPath 从填充改成描边，
    于是得到真正的空心字：印出来是六个线框，不是六块实心色。
    """
    out = txt_obj.out
    size_pt = (WORDMARK_W_MM * PT_PER_MM) / out.text_width(WORDMARK)
    cap_pt = (out.cap_height / out.upem) * size_pt

    # 以大写字高的中线对齐成品正中，不受 ascender/descender 影响
    x = ((TRIM_W - WORDMARK_W_MM) / 2.0) * mm
    y = (WORDMARK_CY_MM * mm) - cap_pt / 2.0

    bottom_mm = WORDMARK_CY_MM - (cap_pt / mm) / 2.0

    c.setStrokeColorCMYK(*CREAM)
    c.setLineWidth(WORDMARK_STROKE_MM * mm)
    c.setLineJoin(1)                      # 圆角接合，尖角在细线上会崩出毛刺
    scale = size_pt / out.upem
    cursor = x
    for ch in WORDMARK:
        rec = out.outline(ch)
        if rec:
            p = c.beginPath()
            for op, pts in rec:
                q = [(cursor + px * scale, y + py * scale) for px, py in (pts or ())]
                if op == 'moveTo':
                    p.moveTo(*q[0])
                elif op == 'lineTo':
                    p.lineTo(*q[0])
                elif op == 'curveTo':
                    p.curveTo(q[0][0], q[0][1], q[1][0], q[1][1], q[2][0], q[2][1])
                elif op == 'closePath':
                    p.close()
            c.drawPath(p, stroke=1, fill=0)
        cursor += out.hmtx[out.cmap[ord(ch)]][0] * scale

    return bottom_mm


# ---------------------------------------------------------------------
# 正面
# ---------------------------------------------------------------------
def draw_front(c, bold, reg, url):
    """品牌橙满铺 + 白字：大标题 SCAN FOR USER MANUAL、右下角二维码带 SCAN ME、
    上半部横向铺满的空心 WINDIN。

    刻意不放：品牌小字、型号副题、备用网址、产品线描图。
    这些信息在背面和落地页上都有，正面留白比塞满更能让人一眼看到该扫码。
    """
    # 满铺底色，铺到出血边
    rect_mm(c, -BLEED, -BLEED, TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED, ORANGE_FLOOD)

    # 背景：横向铺满的空心 WINDIN，压在上半部
    word_bottom = draw_wordmark(c, bold)

    # 白色圆角面板：兜住二维码的静空白区，顺带装下方的 SCAN ME。
    # 满铺底色下它是个明确的设计元素，不再像白底那版只是啃出来的一个方口子。
    if PLATE_TOP > word_bottom - 0.8:
        raise SystemExit(
            "[X] 二维码面板顶到 %.1fmm，已贴上空心字底部 %.1fmm。\n"
            "    静空白区里不能压任何线条，请上移 WORDMARK_CY_MM 或下移面板。"
            % (PLATE_TOP, word_bottom))
    set_ink(c, WHITE)
    c.roundRect((QR_X - PLATE_PAD) * mm, PLATE_BOTTOM * mm,
                (QR_MM + 2 * PLATE_PAD) * mm, (PLATE_TOP - PLATE_BOTTOM) * mm,
                2.6 * mm, stroke=0, fill=1)

    version = draw_qr(c, url, QR_X, QR_Y, QR_MM)

    # SCAN ME 落在面板内、二维码正下方
    set_ink(c, ORANGE)
    bold.draw(c, "SCAN ME", 6.0, (QR_X + QR_MM / 2) * mm, 5.9 * mm,
              tracking_pt=0.8, align="center")

    # 主标题：整块垂直居中对齐白面板。上沿按细体的大写字高算，
    # 下沿是粗体的基线——之前标题偏低、面板偏高，两边各走各的，就是没对齐。
    cap_small = (reg.out.cap_height / reg.out.upem) * TITLE_SMALL_PT / PT_PER_MM
    plate_cy = (PLATE_TOP + PLATE_BOTTOM) / 2.0
    base1 = plate_cy + (TITLE_LEAD + cap_small) / 2.0
    set_ink(c, CREAM)
    reg.draw(c, "SCAN FOR", TITLE_SMALL_PT, FRONT_MARGIN * mm, base1 * mm,
             tracking_pt=0.3)
    bold.draw(c, "USER MANUAL", TITLE_BIG_PT, FRONT_MARGIN * mm,
              (base1 - TITLE_LEAD) * mm, tracking_pt=0.2)

    # 标题右端不能顶到面板上
    title_right = FRONT_MARGIN + bold.width("USER MANUAL", TITLE_BIG_PT, 0.2) / PT_PER_MM
    if title_right > QR_X - PLATE_PAD - 2.0:
        raise SystemExit(
            "[X] 标题右端排到 %.1fmm，与 %.1fmm 处的二维码面板挨得太近。"
            % (title_right, QR_X - PLATE_PAD))
    return version


# ---------------------------------------------------------------------
# 图标
# ---------------------------------------------------------------------
# 全部在 100x100 单位框内画，再按 size_mm 缩放。4mm 见方是它们的工作尺寸，
# 所以一律走简笔轮廓：齿轮那种带齿的细节在这个尺寸下只会糊成一个圆点。
def _icon_frame(c, x, y, size_mm, stroke_units=7.0):
    s = size_mm / 100.0
    def X(u):
        return (x + u * s) * mm
    def Y(v):
        return (y + v * s) * mm
    def L(u):
        return u * s * mm
    c.setStrokeColorCMYK(*ORANGE)
    c.setFillColorCMYK(*ORANGE)
    c.setLineWidth(L(stroke_units))
    c.setLineCap(1)
    c.setLineJoin(1)
    return X, Y, L


def icon_battery(c, x, y, s):
    X, Y, L = _icon_frame(c, x, y, s)
    c.roundRect(X(4), Y(28), L(76), L(44), L(10), stroke=1, fill=0)
    c.roundRect(X(84), Y(42), L(11), L(16), L(4), stroke=0, fill=1)
    c.roundRect(X(15), Y(39), L(28), L(22), L(4), stroke=0, fill=1)


def icon_tap(c, x, y, s):
    """点击：一个实心触点 + 两道向外扩的涟漪。"""
    X, Y, L = _icon_frame(c, x, y, s)
    c.circle(X(34), Y(34), L(15), stroke=0, fill=1)
    for r in (34, 52):
        c.arc(X(34 - r), Y(34 - r), X(34 + r), Y(34 + r), 8, 74)


def icon_power(c, x, y, s):
    """电源：顶部留缺口的圆环 + 一根竖线。比齿轮在 4mm 下清楚得多。"""
    X, Y, L = _icon_frame(c, x, y, s)
    c.arc(X(14), Y(8), X(86), Y(80), 300, 300)
    c.line(X(50), Y(50), X(50), Y(94))


def icon_shield(c, x, y, s):
    X, Y, L = _icon_frame(c, x, y, s)
    p = c.beginPath()
    p.moveTo(X(50), Y(94))
    p.lineTo(X(12), Y(76))
    p.lineTo(X(12), Y(44))
    p.lineTo(X(50), Y(8))
    p.lineTo(X(88), Y(44))
    p.lineTo(X(88), Y(76))
    p.close()
    c.drawPath(p, stroke=1, fill=0)


def icon_phone(c, x, y, s):
    X, Y, L = _icon_frame(c, x, y, s)
    c.roundRect(X(28), Y(6), L(44), L(88), L(9), stroke=1, fill=0)
    c.line(X(42), Y(82), X(58), Y(82))
    c.circle(X(50), Y(17), L(4), stroke=0, fill=1)


def icon_mail(c, x, y, s):
    X, Y, L = _icon_frame(c, x, y, s)
    c.rect(X(6), Y(24), L(88), L(52), stroke=1, fill=0)
    p = c.beginPath()
    p.moveTo(X(6), Y(76))
    p.lineTo(X(50), Y(44))
    p.lineTo(X(94), Y(76))
    c.drawPath(p, stroke=1, fill=0)


# ---------------------------------------------------------------------
# 背面
# ---------------------------------------------------------------------
# 每条 = (图标, 标题, 正文, 补充说明或 None)
FAQ = [
    (icon_battery, "Screen shows LL and fails to power on",
     "Charge for 1-2 hours via Type-C cable.", None),
    # "Fast flashing = working" 没说是哪个灯，买家找不到。
    # 必须点名：点击头上方那颗蓝灯。
    (icon_tap, "Taps are not registering",
     "The blue light above the tapping head flashes fast = working. "
     "If not, press START.",
     "Note: We recommend 5-10 taps/sec for optimal use."),
    (icon_power, "Device stops responding",
     "Power off, re-clamp, and restart.", None),
    (icon_shield, "Warranty",
     "12-month warranty  ·  30-day replacement.", None),
]

# 背面排版参数。文案一改就可能顶到底部色块，这几个值是配合
# draw_back() 末尾那道断言用的——顶到了会直接报错，不会静默印出半截字。
FAQ_LEAD = 2.2       # 正文行距
FAQ_GAP = 1.35       # 条目之间额外留白
FAQ_ICON = 4.2       # 图标边长
FAQ_TEXT_X = 11.5    # 文字左边界，给图标让出位置
SUPPORT_H = 14.5     # 底部售后色块高度

PHONE = "+91 76785 33071"
EMAIL = "windinsupport@gmail.com"


def draw_back(c, bold, reg, ital):
    rect_mm(c, -BLEED, -BLEED, TRIM_W + 2 * BLEED, TRIM_H + 2 * BLEED, WHITE)

    # 标题
    set_ink(c, INK)
    bold.draw(c, "QUICK HELP", 8.2, SAFE * mm, (TRIM_H - 7.0) * mm, tracking_pt=1.0)
    rect_mm(c, SAFE, TRIM_H - 9.4, 9.0, 0.9, ORANGE)

    max_w = (TRIM_W - SAFE - FAQ_TEXT_X) * PT_PER_MM
    y = TRIM_H - 12.4
    for icon, title, body, note in FAQ:
        # 图标垂直居中对着「标题 + 正文」这一小块，不是对着标题基线，
        # 否则四个图标会一律偏高，看着像浮在字上面。
        icon(c, SAFE, y - 2.9, FAQ_ICON)

        set_ink(c, INK)
        bold.draw(c, title, 6.2, FAQ_TEXT_X * mm, y * mm)
        y -= 2.7
        set_ink(c, INK_SOFT)
        for line in reg.wrap(body, 5.3, max_w):
            reg.draw(c, line, 5.3, FAQ_TEXT_X * mm, y * mm)
            y -= FAQ_LEAD
        if note:
            for line in ital.wrap(note, 4.9, max_w):
                ital.draw(c, line, 4.9, FAQ_TEXT_X * mm, y * mm)
                y -= 2.0
        y -= FAQ_GAP

    # 版面是算好的，但文案一改就可能顶到色块上。这里直接拦住，
    # 免得又出一版"Amazon Order ID"被压掉一半的稿子。
    if y + FAQ_GAP < SUPPORT_H + 1.0:
        raise SystemExit(
            "[X] 背面常见问题排到 y=%.1fmm，已顶到 %.1fmm 的售后色块。\n"
            "    请精简 FAQ 文案，或调小 SUPPORT_H / 字号。"
            % (y + FAQ_GAP, SUPPORT_H))

    # 售后色块：满出血压在底部
    rect_mm(c, -BLEED, -BLEED, TRIM_W + 2 * BLEED, SUPPORT_H + BLEED, ORANGE_TINT)
    rect_mm(c, -BLEED, SUPPORT_H - 0.7, TRIM_W + 2 * BLEED, 0.7, ORANGE)

    # 电话和邮箱排一行。原先上下两行时，邮箱基线离成品下边只有 1.4mm，
    # 远在 5mm 安全区之外——裁切偏个 1mm 就把字切掉了。
    contact_y = 5.5
    icon_s = 3.6
    phone_x, mail_x = SAFE + 4.8, 41.0 + 4.8
    set_ink(c, INK)
    bold.draw(c, "NEED MORE HELP?", 6.2, SAFE * mm, (SUPPORT_H - 4.0) * mm,
              tracking_pt=0.6)
    icon_phone(c, SAFE, contact_y - 0.7, icon_s)
    icon_mail(c, 41.0, contact_y - 0.5, icon_s)
    set_ink(c, INK)
    reg.draw(c, PHONE, 6.2, phone_x * mm, contact_y * mm)
    reg.draw(c, EMAIL, 6.2, mail_x * mm, contact_y * mm)

    # 邮箱是最右边的元素，越界就是印出来被切掉。换更长的邮箱地址时
    # 这里会直接报错，而不是让它悄悄压到裁切线上。
    phone_right = phone_x + reg.width(PHONE, 6.2) / PT_PER_MM
    mail_right = mail_x + reg.width(EMAIL, 6.2) / PT_PER_MM
    if mail_right > TRIM_W - SAFE:
        raise SystemExit(
            "[X] 邮箱右端排到 %.1fmm，超出 %.1fmm 的安全区。\n"
            "    请缩短邮箱、左移 Email 栏，或把电话邮箱改回上下两行。"
            % (mail_right, TRIM_W - SAFE))
    if phone_right > 41.0 - 2.0:
        raise SystemExit(
            "[X] 电话右端排到 %.1fmm，与 41.0mm 处的 Email 栏挨得太近。"
            % phone_right)


# ---------------------------------------------------------------------
def build(url, outdir, name, preview):
    bold, reg, ital = Text(FONT_BOLD), Text(FONT_REG), Text(FONT_ITALIC)

    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, name + ".pdf")

    c = rl_canvas.Canvas(pdf_path, pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle("B03 Auto Clicker - After-Sales Insert Card")
    c.setSubject(url)
    c.setCreator("WINDIN")

    for painter in (draw_front, draw_back):
        crop_marks(c)
        c.saveState()
        c.translate(ORIGIN * mm, ORIGIN * mm)
        if painter is draw_front:
            version = painter(c, bold, reg, url)
        else:
            painter(c, bold, reg, ital)
        c.restoreState()
        c.showPage()

    c.save()
    strip_unused_font(pdf_path)

    spec_path = build_spec_sheet(os.path.join(outdir, "B03_售后卡片_尺寸标注.pdf"))

    png_path = None
    if preview:
        png_path = os.path.join(outdir, name + "_预览.png")
        render_preview(pdf_path, png_path)

    return dict(pdf=pdf_path, png=png_path, spec=spec_path, version=version,
                module_mm=QR_MM / (len(list(segno.make(url, error='h')
                                            .matrix_iter(scale=1, border=4)))))


# ---------------------------------------------------------------------
# 尺寸标注图（给印厂看的，不是印刷件）
# ---------------------------------------------------------------------
A4_W, A4_H = 210.0, 297.0
CJK_TTC = r"C:\Windows\Fonts\msyh.ttc"


def _register_cjk():
    """标注图是参考文档不是印刷件，字体直接嵌入即可，不必转曲。"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        pdfmetrics.registerFont(TTFont("CJK", CJK_TTC, subfontIndex=0))
        pdfmetrics.registerFont(TTFont("CJKB", CJK_TTC, subfontIndex=1))
        return "CJK", "CJKB"
    except Exception as e:
        print("[!] 中文字体注册失败(%s)，标注图改用 Helvetica" % e)
        return "Helvetica", "Helvetica-Bold"


def _dim_line(c, x0, y0, x1, y1, label, fnt, offset=0):
    """带箭头的标注线 + 居中标签。坐标 mm。"""
    c.setStrokeColorCMYK(0, 0.62, 0.88, 0)
    c.setLineWidth(0.3)
    c.line(x0 * mm, y0 * mm, x1 * mm, y1 * mm)
    ah = 1.4                                   # 箭头长度 mm
    if abs(y1 - y0) < 1e-6:                    # 水平
        for xa, sgn in ((x0, 1), (x1, -1)):
            p = c.beginPath()
            p.moveTo(xa * mm, y0 * mm)
            p.lineTo((xa + sgn * ah) * mm, (y0 + ah * 0.45) * mm)
            p.lineTo((xa + sgn * ah) * mm, (y0 - ah * 0.45) * mm)
            p.close()
            c.setFillColorCMYK(0, 0.62, 0.88, 0)
            c.drawPath(p, stroke=0, fill=1)
        # 文字放在标注线下方：放上方会压到出血框的虚线上
        tx, ty, rot = (x0 + x1) / 2, y0 - 4.0, 0
    else:                                      # 垂直
        for ya, sgn in ((y0, 1), (y1, -1)):
            p = c.beginPath()
            p.moveTo(x0 * mm, ya * mm)
            p.lineTo((x0 + ah * 0.45) * mm, (ya + sgn * ah) * mm)
            p.lineTo((x0 - ah * 0.45) * mm, (ya + sgn * ah) * mm)
            p.close()
            c.setFillColorCMYK(0, 0.62, 0.88, 0)
            c.drawPath(p, stroke=0, fill=1)
        tx, ty, rot = x0 + 1.2, (y0 + y1) / 2, 90
    c.saveState()
    c.setFillColorCMYK(*INK)
    c.setFont(fnt, 7)
    c.translate(tx * mm, ty * mm)
    c.rotate(rot)
    c.drawCentredString(0, 1.0 * mm, label)
    c.restoreState()


SPEC_ROWS = [
    ("成品尺寸", "85 × 54 mm（标准名片通版，印厂最便宜的规格）"),
    ("页面尺寸", "97 × 66 mm = 成品 + 四边各 3 mm 出血 + 3 mm 裁切线区"),
    ("出血", "四边各 3 mm。底色块、水印已铺到出血边，裁切偏移不会露白"),
    ("安全区", "距成品边 5 mm。所有文字均在安全区内"),
    ("页序", "P1 = 正面，P2 = 背面。双面印，同向"),
    ("二维码", "23 × 23 mm，纠错等级 H，单模块 0.511 mm（≥ 0.5 mm 胶印下限）"),
    ("二维码位置", "距成品右边 %.1f mm、下边 %.1f mm，四周静空白区已含在 23 mm 内"
                   % (TRIM_W - QR_X - QR_MM, QR_Y)),
    ("正面", "满铺品牌橙实地 + 白字，二维码坐白色圆角面板，下方 SCAN ME"),
    ("背面", "白底 + 图标式常见问题，底部淡橙色块放售后联系方式"),
    ("颜色", "二维码 100% 单黑 K100；橙色为四色；背面文字单黑"),
    ("字体", "全部转曲，文件内无嵌入字体，不存在替换字体的可能"),
    ("图像", "全矢量，无位图、无透明。正面的空心 WINDIN 是描边路径"),
    # 这张表是画进 PDF 的，不是 Markdown——写 **粗体** 会把星号原样印出来
    ("建议材质", "300 g 白卡，双面印刷。正面满版实地，必须覆哑膜，防刮花露白"),
    ("工艺禁忌", "二维码区域禁止烫金、局部 UV、压纹；禁止反白、渐变、四色黑"),
    ("开印前", "用实际材质打样，3–5 部不同手机（含低端机）弱光实测扫码"),
]


def build_spec_sheet(path):
    """A4，1:1 画出成品框/出血框/安全区，配尺寸标注和规格表。"""
    reg, bd = _register_cjk()
    c = rl_canvas.Canvas(path, pagesize=(A4_W * mm, A4_H * mm))
    c.setTitle("B03 售后卡片 - 尺寸标注")
    c.setCreator("WINDIN")

    c.setFillColorCMYK(*INK)
    c.setFont(bd, 15)
    c.drawString(18 * mm, (A4_H - 22) * mm, "B03 售后卡片 · 印刷尺寸标注")
    c.setFont(reg, 8.5)
    c.setFillColorCMYK(*INK_SOFT)
    c.drawString(18 * mm, (A4_H - 28) * mm,
                 "下图为 1:1 实际尺寸，可直接用尺量。印刷文件为 B03_售后卡片_85x54.pdf（共 2 页）。")

    # --- 1:1 图框 ---------------------------------------------------
    bx = (A4_W - (TRIM_W + 2 * BLEED)) / 2.0   # 出血框左下角
    by = A4_H - 52 - (TRIM_H + 2 * BLEED)

    c.setStrokeColorCMYK(0, 0, 0, 0.35)
    c.setLineWidth(0.4)
    c.setDash(2, 2)
    c.rect(bx * mm, by * mm, (TRIM_W + 2 * BLEED) * mm, (TRIM_H + 2 * BLEED) * mm)

    tx, ty = bx + BLEED, by + BLEED
    c.setDash()
    c.setStrokeColorCMYK(0, 0, 0, 1)
    c.setLineWidth(0.5)
    c.rect(tx * mm, ty * mm, TRIM_W * mm, TRIM_H * mm)

    c.setStrokeColorCMYK(0, 0.62, 0.88, 0)
    c.setLineWidth(0.35)
    c.setDash(1.5, 1.5)
    c.rect((tx + SAFE) * mm, (ty + SAFE) * mm,
           (TRIM_W - 2 * SAFE) * mm, (TRIM_H - 2 * SAFE) * mm)

    # 二维码占位框，让印厂一眼看到不能压什么
    c.rect((tx + QR_X) * mm, (ty + QR_Y) * mm, QR_MM * mm, QR_MM * mm)
    c.setDash()
    c.setFillColorCMYK(*INK_SOFT)
    c.setFont(reg, 6.5)
    c.drawCentredString((tx + QR_X + QR_MM / 2) * mm,
                        (ty + QR_Y + QR_MM / 2) * mm, "二维码 23×23")

    # --- 标注 -------------------------------------------------------
    _dim_line(c, tx, ty - 6, tx + TRIM_W, ty - 6, "成品 85 mm", reg)
    _dim_line(c, tx + TRIM_W + 6, ty, tx + TRIM_W + 6, ty + TRIM_H, "成品 54 mm", reg)
    _dim_line(c, bx, by - 16, bx + TRIM_W + 2 * BLEED, by - 16, "含出血 91 mm", reg)

    c.setFillColorCMYK(*INK)
    c.setFont(reg, 7.5)
    lx = bx + TRIM_W + 2 * BLEED + 4
    for i, (txt, col) in enumerate([
            ("——— 实线：成品裁切线 85 × 54 mm", INK),
            ("- - - 灰虚线：出血边 91 × 60 mm", INK_SOFT),
            ("- - - 橙虚线：安全区 75 × 44 mm", ORANGE)]):
        c.setFillColorCMYK(*col)
        c.drawString((bx) * mm, (by - 26 - i * 5) * mm, txt)

    # --- 规格表 -----------------------------------------------------
    y = by - 50
    c.setFillColorCMYK(*INK)
    c.setFont(bd, 10)
    c.drawString(18 * mm, y * mm, "规格明细")
    y -= 3
    c.setStrokeColorCMYK(0, 0.62, 0.88, 0)
    c.setLineWidth(0.9)
    c.line(18 * mm, y * mm, 27 * mm, y * mm)
    y -= 7

    for k, v in SPEC_ROWS:
        c.setFillColorCMYK(*INK)
        c.setFont(bd, 8)
        c.drawString(18 * mm, y * mm, k)
        c.setFillColorCMYK(*INK_SOFT)
        c.setFont(reg, 8)
        c.drawString(48 * mm, y * mm, v)
        y -= 6.2

    c.setFillColorCMYK(*INK_SOFT)
    c.setFont(reg, 7)
    c.drawString(18 * mm, 16 * mm,
                 "二维码内容与包装盒外那块码完全一致，两处不允许出现不同地址。")
    c.showPage()
    c.save()
    return path


def strip_unused_font(path):
    """去掉 reportlab 自动塞进来的 Helvetica 空引用。

    每页开头都会写一段 'BT /F1 12 Tf 14.4 TL ET'——设了字体但一个字符也没画。
    我们的文字全部转曲，页面上根本没有文字对象。留着不影响印刷，
    但印厂 preflight 会报"Helvetica 未嵌入"，平白引来一通电话确认。

    make_print_artwork.py 里有一份单页版。没有直接复用它、也没有把那份
    改成多页，是因为那个脚本产出的是已经印在 2000 个盒子上的稿子，
    不值得为了去重去动它。
    """
    import re
    try:
        import fitz
    except ImportError:
        print("[!] 未装 PyMuPDF，跳过清理空字体引用（不影响印刷）")
        return

    doc = fitz.open(path)
    for page in doc:
        for xref in page.get_contents():
            data = doc.xref_stream(xref)
            cleaned = re.sub(rb'BT\s+/\w+\s+[\d.]+\s+Tf\s+[\d.]+\s+TL\s+ET\s*', b'', data)
            if cleaned != data:
                doc.update_stream(xref, cleaned)
        doc.xref_set_key(page.xref, "Resources/Font", "null")
    tmp = path + ".tmp"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, path)


def render_preview(pdf_path, png_path, dpi=400):
    """把两页并排渲染成一张 PNG，纯粹用来在屏幕上看，不参与印刷。"""
    try:
        import fitz
    except ImportError:
        print("[!] 未装 PyMuPDF，跳过预览图")
        return
    doc = fitz.open(pdf_path)
    zoom = dpi / 72.0
    pix = [p.get_pixmap(matrix=fitz.Matrix(zoom, zoom)) for p in doc]
    gap = int(0.08 * pix[0].width)
    W = pix[0].width + gap + pix[1].width
    H = max(pix[0].height, pix[1].height)
    canvas = Image.new("RGB", (W, H), "white")
    canvas.paste(Image.frombytes("RGB", (pix[0].width, pix[0].height), pix[0].samples),
                 (0, 0))
    canvas.paste(Image.frombytes("RGB", (pix[1].width, pix[1].height), pix[1].samples),
                 (pix[0].width + gap, 0))
    canvas.save(png_path)
    doc.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--name", default="B03_售后卡片_85x54")
    ap.add_argument("--no-preview", dest="preview", action="store_false")
    ap.add_argument("--outdir",
                    default=os.path.join(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__))), "B03售后卡片_给印厂"))
    a = ap.parse_args()

    r = build(a.url, a.outdir, a.name, a.preview)

    print()
    print("  二维码内容      : " + a.url)
    print("  纠错等级        : H (30%%)，中心挖空 %.0f%% 边长" % (LOGO_RATIO * 100))
    print("  单模块尺寸      : %.3f mm   %s"
          % (r['module_mm'], "OK" if r['module_mm'] >= 0.5 else "[X] 低于胶印下限"))
    print()
    print("  成品尺寸        : %.0f x %.0f mm（标准名片）" % (TRIM_W, TRIM_H))
    print("  页面尺寸        : %.0f x %.0f mm（含 %.0fmm 出血 + 裁切线）"
          % (PAGE_W, PAGE_H, BLEED))
    print("  文字            : 已转曲，不依赖任何字体")
    print("  颜色            : 文字/二维码 100% 单黑，橙色为四色")
    print("  图像            : 全矢量，无位图")
    print()
    print("  交印厂: " + r['pdf'])
    print("  标注图: " + r['spec'])
    if r['png']:
        print("  预览  : " + r['png'])
    print()


if __name__ == "__main__":
    main()
