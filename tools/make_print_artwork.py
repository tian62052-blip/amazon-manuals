#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成交给印刷厂的二维码印刷稿（矢量 PDF + SVG）。

和 make_qr.py 的区别：
    make_qr.py            只出一个光秃秃的二维码图形
    make_print_artwork.py 出的是"可以直接落到包装设计稿上的整块图"——
                          二维码 + 下方引导文字 + 白色底板，尺寸已经定死

为什么要有白色底板：
    彩盒背面未必是白的。二维码的浅色模块必须真的浅，黑字也必须印在浅底上，
    否则扫不出来。给一块白底，印厂无论把它放在什么颜色的区域上都不会出错。
    如果那块区域本来就是白的，白底板是隐形的，不影响观感。

为什么文字要转曲：
    印厂的 RIP 上不一定装了 Arial。转成曲线后就不再依赖字体，
    不存在"字跑了/替换成别的字体"的可能。

用法:
    pip install segno reportlab fonttools
    python make_print_artwork.py
    python make_print_artwork.py --qr-mm 28 --text "Scan for User Manual"
"""

import argparse
import os
import sys

try:
    import segno
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from fontTools.ttLib import TTFont
    from fontTools.pens.recordingPen import RecordingPen
    from fontTools.pens.qu2cuPen import Qu2CuPen
except ImportError as e:
    sys.exit("缺少依赖: %s\n请运行:  pip install segno reportlab fonttools" % e)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


URL = "https://windin.tian62052.workers.dev/b03"
FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"      # Arial Bold

# --- 版面参数 (mm) ---------------------------------------------------
QR_MM = 25.0          # 二维码图形边长，含 4 模块静空白区
GAP_MM = 1.3          # 二维码下沿到文字顶部
PAD_BOTTOM_MM = 1.3   # 文字底部到白底板下沿
TEXT_SIDE_PAD = 1.0   # 文字两侧各留多少，用来算自动缩放
FONT_PT_MAX = 8.5     # 文字上限，再大就比二维码抢眼了
FONT_PT_MIN = 5.5     # 文字下限，再小印度买家在货架上看不清

PT_PER_MM = 72.0 / 25.4


# ---------------------------------------------------------------------
# 字体转曲
# ---------------------------------------------------------------------
class GlyphOutliner:
    """把 TrueType 字形取出来，转成三次贝塞尔曲线（PDF 只认三次）。"""

    def __init__(self, font_path):
        self.tt = TTFont(font_path)
        self.glyphset = self.tt.getGlyphSet()
        self.cmap = self.tt.getBestCmap()
        self.upem = self.tt['head'].unitsPerEm
        self.hmtx = self.tt['hmtx']
        os2 = self.tt['OS/2']
        # sCapHeight 在老字体里可能缺失，用 'H' 的实际高度兜底
        self.cap_height = getattr(os2, 'sCapHeight', 0) or self._measure_cap()

    def _measure_cap(self):
        gn = self.cmap.get(ord('H'))
        if not gn:
            return int(self.upem * 0.7)
        pen = RecordingPen()
        self.glyphset[gn].draw(pen)
        ys = [p[1] for _, pts in pen.value for p in (pts or ())]
        return max(ys) if ys else int(self.upem * 0.7)

    def text_width(self, text):
        """单位: em (1.0 = 一个字号)。不做 kerning，这个尺寸下看不出差别。"""
        total = 0
        for ch in text:
            gn = self.cmap.get(ord(ch))
            if gn is None:
                raise ValueError("字体里没有这个字符: %r" % ch)
            total += self.hmtx[gn][0]
        return total / self.upem

    # PDF 和 SVG 都只认三次贝塞尔，而 TrueType 存的是二次曲线。
    # Qu2CuPen 负责转换，但 all_cubic 默认是 False —— 那样它会把二次段
    # 原样以 qCurveTo 吐出来。漏掉这个参数的后果是所有弧线被静默丢弃，
    # 字只剩下直线笔画的碎片，而且 PDF 照样能打开、看不出报错。
    ALLOWED_OPS = {'moveTo': 1, 'lineTo': 1, 'curveTo': 3, 'closePath': 0}

    def outline(self, ch):
        """取单个字符的轮廓，只返回已知算子；出现意外算子直接报错。"""
        gn = self.cmap.get(ord(ch))
        if gn is None:
            raise ValueError("字体里没有这个字符: %r" % ch)
        rec = RecordingPen()
        # max_err 用字体单位，upem/1000 ≈ 2 单位，远小于印刷精度
        self.glyphset[gn].draw(
            Qu2CuPen(rec, max_err=self.upem / 1000.0, all_cubic=True))
        for op, pts in rec.value:
            want = self.ALLOWED_OPS.get(op)
            if want is None:
                raise ValueError("未处理的轮廓算子 %r（字符 %r）" % (op, ch))
            if len(pts or ()) != want:
                raise ValueError("算子 %r 点数为 %d，预期 %d（字符 %r）"
                                 % (op, len(pts or ()), want, ch))
        return rec.value

    def draw(self, c, text, size_pt, x_pt, y_pt):
        """在 reportlab canvas 上按曲线画出文字。x/y 为左下角基线起点。"""
        scale = size_pt / self.upem
        cursor = x_pt
        for ch in text:
            gn = self.cmap[ord(ch)]
            rec = self.outline(ch)
            if rec:
                p = c.beginPath()
                for op, pts in rec:
                    q = [(cursor + px * scale, y_pt + py * scale) for px, py in (pts or ())]
                    if op == 'moveTo':
                        p.moveTo(*q[0])
                    elif op == 'lineTo':
                        p.lineTo(*q[0])
                    elif op == 'curveTo':
                        p.curveTo(q[0][0], q[0][1], q[1][0], q[1][1], q[2][0], q[2][1])
                    elif op == 'closePath':
                        p.close()
                c.drawPath(p, stroke=0, fill=1)   # 非零环绕，TrueType 的标准填充规则
            cursor += self.hmtx[gn][0] * scale


# ---------------------------------------------------------------------
def build(url, text, qr_mm, outdir, name, title="B03 Auto Clicker - Packaging QR Artwork"):
    qr = segno.make(url, error='q', micro=False)
    matrix = list(qr.matrix_iter(scale=1, border=4))
    n = len(matrix)                       # 含静空白区的模块数
    module_mm = qr_mm / n

    out = GlyphOutliner(FONT_PATH)

    # --- 文字自动适配宽度 -------------------------------------------
    avail_mm = qr_mm - 2 * TEXT_SIDE_PAD
    w_em = out.text_width(text)
    size_pt = min(FONT_PT_MAX, (avail_mm * PT_PER_MM) / w_em)
    if size_pt < FONT_PT_MIN:
        raise SystemExit(
            "[X] 文字 %r 在 %.1fmm 宽度内只能缩到 %.1fpt，低于 %.1fpt 下限。\n"
            "    请换更短的文案，或用 --qr-mm 把整块加宽。"
            % (text, qr_mm, size_pt, FONT_PT_MIN))

    text_w_pt = w_em * size_pt
    cap_mm = (out.cap_height / out.upem) * size_pt / PT_PER_MM

    block_w_mm = qr_mm
    block_h_mm = qr_mm + GAP_MM + cap_mm + PAD_BOTTOM_MM

    os.makedirs(outdir, exist_ok=True)
    pdf_path = os.path.join(outdir, name + ".pdf")

    # --- 画 PDF ------------------------------------------------------
    W, H = block_w_mm * mm, block_h_mm * mm
    c = rl_canvas.Canvas(pdf_path, pagesize=(W, H))
    c.setTitle(title)
    c.setSubject(url)                     # 印厂在文件属性里能核对内容
    c.setCreator("WINDIN")

    # 白底板。用 CMYK 全 0 = 不上任何墨，等于"露出纸白/底色白"，
    # 不会因为叠印设置不同而变脏。
    c.setFillColorCMYK(0, 0, 0, 0)
    c.rect(0, 0, W, H, stroke=0, fill=1)

    # 二维码和文字统一 100% 单黑。绝不能用 RGB 黑或四色黑：
    # 四色黑一旦套印不准，二维码边缘会出现彩边，识别率直接掉下去。
    c.setFillColorCMYK(0, 0, 0, 1)

    step = module_mm * mm
    top = H                               # PDF 坐标系原点在左下角
    for r, row in enumerate(matrix):
        cs = 0
        while cs < n:
            if row[cs]:
                ce = cs
                while ce + 1 < n and row[ce + 1]:
                    ce += 1               # 把连续的黑模块并成一个矩形，减少路径数
                c.rect(cs * step, top - (r + 1) * step,
                       (ce - cs + 1) * step, step, stroke=0, fill=1)
                cs = ce + 1
            else:
                cs += 1

    baseline_y = (PAD_BOTTOM_MM) * mm
    out.draw(c, text, size_pt, (W - text_w_pt) / 2.0, baseline_y)

    c.showPage()
    c.save()
    _strip_unused_font(pdf_path)

    # --- 同步出一份 SVG，给用 Illustrator/CorelDRAW 的设计师 ----------
    svg_path = os.path.join(outdir, name + ".svg")
    _write_svg(svg_path, matrix, n, module_mm, block_w_mm, block_h_mm,
               out, text, size_pt, text_w_pt)

    return dict(pdf=pdf_path, svg=svg_path, n=n, module_mm=module_mm,
                version=qr.version, size_pt=size_pt, cap_mm=cap_mm,
                block_w=block_w_mm, block_h=block_h_mm)


def _strip_unused_font(path):
    """去掉 reportlab 自动塞进来的 Helvetica 空引用。

    reportlab 每页开头都会写一段 'BT /F1 12 Tf 14.4 TL ET'——设了字体但一个
    字符也没画（Tj/TJ 为 0）。我们的文字全部转曲，页面上根本没有文字对象。
    留着不影响印刷，但印厂 preflight 会报"Helvetica 未嵌入"，平白引来一通
    电话确认。清掉，让文件过检时干干净净。
    """
    import re
    try:
        import fitz
    except ImportError:
        print("[!] 未装 PyMuPDF，跳过清理空字体引用（不影响印刷）")
        return

    doc = fitz.open(path)
    page = doc[0]
    xref = page.get_contents()[0]
    data = doc.xref_stream(xref)
    cleaned = re.sub(rb'BT\s+/\w+\s+[\d.]+\s+Tf\s+[\d.]+\s+TL\s+ET\s*', b'', data)
    if cleaned != data:
        doc.update_stream(xref, cleaned)
    doc.xref_set_key(page.xref, "Resources/Font", "null")
    # PyMuPDF 不允许非增量方式存回原路径，先写临时文件再替换
    tmp = path + ".tmp"
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    os.replace(tmp, path)


def _write_svg(path, matrix, n, module_mm, bw, bh, out, text, size_pt, text_w_pt):
    """SVG 用 mm 作单位，导入 AI/CDR 后尺寸就是实际印刷尺寸。"""
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%.4fmm" height="%.4fmm" viewBox="0 0 %.4f %.4f">' % (bw, bh, bw, bh),
        '<rect x="0" y="0" width="%.4f" height="%.4f" fill="#FFFFFF"/>' % (bw, bh),
        '<g fill="#000000" shape-rendering="crispEdges">',
    ]
    for r, row in enumerate(matrix):
        cs = 0
        while cs < n:
            if row[cs]:
                ce = cs
                while ce + 1 < n and row[ce + 1]:
                    ce += 1
                parts.append('<rect x="%.4f" y="%.4f" width="%.4f" height="%.4f"/>'
                             % (cs * module_mm, r * module_mm,
                                (ce - cs + 1) * module_mm, module_mm))
                cs = ce + 1
            else:
                cs += 1
    parts.append('</g>')

    # 文字同样转曲。SVG 的 y 轴朝下，字形坐标朝上，所以 scale 取负。
    size_mm = size_pt / PT_PER_MM
    scale = size_mm / out.upem
    baseline_y = bh - PAD_BOTTOM_MM
    cursor = (bw - text_w_pt / PT_PER_MM) / 2.0
    d = []
    for ch in text:
        gn = out.cmap[ord(ch)]
        for op, pts in out.outline(ch):
            q = [(cursor + px * scale, baseline_y - py * scale) for px, py in (pts or ())]
            if op == 'moveTo':
                d.append('M%.4f %.4f' % q[0])
            elif op == 'lineTo':
                d.append('L%.4f %.4f' % q[0])
            elif op == 'curveTo':
                d.append('C%.4f %.4f %.4f %.4f %.4f %.4f'
                         % (q[0][0], q[0][1], q[1][0], q[1][1], q[2][0], q[2][1]))
            elif op == 'closePath':
                d.append('Z')
        cursor += out.hmtx[gn][0] * scale
    parts.append('<path fill="#000000" fill-rule="nonzero" d="%s"/>' % ' '.join(d))
    parts.append('</svg>')

    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--text", default="Scan for User Manual")
    ap.add_argument("--qr-mm", type=float, default=QR_MM)
    ap.add_argument("--name", default="B03_二维码_印刷稿_25mm")
    # 只影响 PDF 文件属性里的标题，印厂靠它核对拿到的是哪个型号的稿。
    ap.add_argument("--title", default="B03 Auto Clicker - Packaging QR Artwork")
    # 直接写进交付文件夹，不再单独留一份产物 —— 两份文件迟早会不一致，
    # 而发错版本给印厂的代价是 2000 个盒子。
    ap.add_argument("--outdir",
                    default=os.path.join(os.path.dirname(os.path.dirname(
                        os.path.abspath(__file__))), "B03包装二维码_给印厂"))
    a = ap.parse_args()

    r = build(a.url, a.text, a.qr_mm, a.outdir, a.name, a.title)

    print()
    print("  内容            : " + a.url)
    print("  版本 / 纠错     : version %s / level Q (25%%)" % r['version'])
    print("  模块数          : %d x %d (含 4 模块静空白区)" % (r['n'], r['n']))
    print("  单模块尺寸      : %.3f mm   %s"
          % (r['module_mm'],
             "OK" if r['module_mm'] >= 0.5 else "[X] 低于 0.5mm 胶印下限"))
    print()
    print("  文字            : %r" % a.text)
    print("  字号 / 字高     : %.2f pt / 字高 %.2f mm   %s"
          % (r['size_pt'], r['cap_mm'],
             "OK" if r['cap_mm'] >= 1.4 else "[!] 偏小"))
    print()
    print("  整块尺寸        : %.2f x %.2f mm" % (r['block_w'], r['block_h']))
    print("  颜色            : 100%% 单黑 (CMYK 0/0/0/100)，白底为不上墨区域")
    print("  文字            : 已转曲，不依赖任何字体")
    print()
    print("  交印厂: " + r['pdf'])
    print("  备用  : " + r['svg'])
    print()


if __name__ == "__main__":
    main()
