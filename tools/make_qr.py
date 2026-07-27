#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成包装盒背面用的说明书二维码。

用法:
    pip install segno
    python make_qr.py https://YOURDOMAIN.com/b03
    python make_qr.py https://YOURDOMAIN.com/b03 --name b03 --upper

输出到 ./out/ :
    <name>_qr.svg   -> 矢量，给印厂的正式文件（必须用这个）
    <name>_qr.eps   -> 矢量，部分印厂只收 EPS/AI
    <name>_qr.png   -> 高分位图，仅供你自己贴到设计稿里预览/测试扫码

三条硬规矩:
  1. 只做静态码 —— 内容就是 URL 本身。绝不使用第三方"动态二维码"服务，
     那些服务到期或收费后，已印出的包装会全部作废。
  2. 交付给印厂的是 SVG/EPS 矢量。给 PNG 会被缩放糊掉。
  3. 单色纯黑印刷，不要四色套印、不要反白、不要渐变。
"""

import argparse
import os
import sys

try:
    import segno
except ImportError:
    sys.exit("缺少依赖，请先运行:  pip install segno")

# Windows 控制台默认 GBK，非 GBK 字符会抛 UnicodeEncodeError
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# 印刷用的模块尺寸(mm)。0.5mm 是彩盒胶印的稳妥下限；
# 材质粗糙(瓦楞纸/牛皮纸)或有覆膜时用 0.6。
MODULE_MM_SAFE = 0.5
MODULE_MM_ROUGH = 0.6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="二维码内容，例如 https://YOURDOMAIN.com/b03")
    ap.add_argument("--name", default="qr", help="输出文件名前缀，默认 qr")
    ap.add_argument("--upper", action="store_true",
                    help="URL 转全大写以启用 alphanumeric 编码，模块数更少。"
                         "用了必须在 _redirects 里加大写路径规则")
    ap.add_argument("--error", default="q", choices=["l", "m", "q", "h"],
                    help="纠错等级，包装用 q(25%%)，默认 q")
    ap.add_argument("--outdir", default="out")
    args = ap.parse_args()

    url = args.url.upper() if args.upper else args.url

    qr = segno.make(url, error=args.error, micro=False)
    os.makedirs(args.outdir, exist_ok=True)
    base = os.path.join(args.outdir, args.name + "_qr")

    # border=4 是标准静空白区，标准要求最少 4 个模块，不能省。
    qr.save(base + ".svg", scale=10, border=4, dark="#000000", light="#FFFFFF")
    qr.save(base + ".eps", scale=10, border=4, dark="#000000", light="#FFFFFF")
    # PNG 仅供自测。scale 不要超过 20：部分解码器(含 OpenCV)在
    # 超大位图上会检测失败，容易误判成二维码本身有问题。
    qr.save(base + ".png", scale=20, border=4, dark="#000000", light="#FFFFFF")

    modules = qr.symbol_size(scale=1, border=4)[0]   # 含空白区的边长(模块数)

    print()
    print("  内容        : " + url)
    print("  编码模式    : " + ("alphanumeric (已启用大写压缩)" if args.upper else "byte"))
    print("  版本 / 纠错 : version %s / level %s" % (qr.version, args.error.upper()))
    print("  边长        : %d 模块 (含 4 模块静空白区)" % modules)
    print()
    print("  最小印刷尺寸 (光面彩盒) : %.1f x %.1f mm"
          % (modules * MODULE_MM_SAFE, modules * MODULE_MM_SAFE))
    print("  最小印刷尺寸 (粗糙材质) : %.1f x %.1f mm"
          % (modules * MODULE_MM_ROUGH, modules * MODULE_MM_ROUGH))
    print("  建议实际排版尺寸        : 25 x 25 mm")
    print()
    print("  交给印厂: " + base + ".svg  (或 .eps)")
    print("  自测用  : " + base + ".png")
    print()
    print("  [!] 开印前必须拿实际材质、实际尺寸的打样件，")
    print("    用 3-5 部不同手机(含 Redmi 等印度主力低端机)在弱光下实测扫码。")
    print("    电脑屏幕上扫图片不算数。")
    print()


if __name__ == "__main__":
    main()
