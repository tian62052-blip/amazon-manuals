# 电子说明书站点 (amazon-manuals)

包装盒二维码指向的站点。由 Cloudflare Pages 自动部署，**当前使用免费的 `*.pages.dev` 域名**。

**核心约定：二维码只编码 `https://windin.pages.dev/b03` 这一个地址，永远不变。**
背后指向什么、内容是什么，全部可以随时改。

> 当前批次：2000 个包装（试产）。第二批放量时再买自有域名，届时本项目**必须保留不删**——
> 已售出的 2000 个盒子仍然依赖这个地址。

---

## 目录结构

```
/
├── B03-user-manual.pdf     当前生效的说明书（文件名不要改）
├── index.html              根目录的型号索引页
├── b03/index.html          B03 落地页 = 二维码扫出来的页面
├── _redirects              路径跳转规则（/b03/pdf -> 实际 PDF 文件）
├── _headers                缓存与 Content-Disposition 设置
├── archive/                历史版本存档，供售后/法律追溯
├── tools/
│   └── make_print_artwork.py   二维码印刷稿生成脚本
└── B03包装二维码_给印厂/    给印厂的交付件（脚本直接输出到这里）
    ├── B03_二维码_印刷稿_25mm.pdf   正式印刷文件
    ├── B03_二维码_印刷稿_25mm.svg   备用（AI / CorelDRAW）
    └── 印厂须知_B03二维码.pdf       尺寸/颜色/工艺红线/打样要求
```

`tools/` 、`archive/` 、`B03包装二维码_给印厂/` 均已在 `.assetsignore` 中排除，
不会被当作网站资源对外提供。

---

## 一次性搭建

### 1. 确定 Pages 项目名 ⚠️ 不可更改

`*.pages.dev` 子域名在**项目创建时分配，之后无法修改**（重命名项目也没用，
只能删除重建）。因为它要印在包装上，必须一次定对。

命名要求：

- **绝对不能含 `amazon`** —— 印在自己包装上等于使用他人商标
- 越短越好（直接决定二维码模块数）
- 不含连字符和数字，避开 `l/I/1`、`0/O` 易混字符
- 纯小写英文，可拼读

### 2. 建 Cloudflare Pages 项目

Cloudflare 控制台 → Workers & Pages → Create → Pages → Connect to Git

- 授权并选择仓库 `tian62052-blip/amazon-manuals`
- Project name: **你第 1 步定好的名字**（这就是最终域名）
- Production branch: `main`
- Framework preset: **None**
- Build command: **留空**
- Build output directory: **`/`**

点 Save and Deploy，约 1 分钟完成。

### 3. 验证（开印前必做）

```bash
curl -sI https://windin.pages.dev/b03/pdf
```

必须看到 `302`，跟随后的最终响应包含：

- `content-type: application/pdf`
- `content-disposition: inline`
- `cache-control: public, max-age=3600, must-revalidate`

再用**手机实际访问**一遍，确认 PDF 是直接打开而不是弹下载框。

### 4. 生成二维码

```bash
pip install segno reportlab fonttools
cd tools
python make_print_artwork.py
```

产出直接覆盖 `B03包装二维码_给印厂/`，详见下方「印刷规范速查」。

### 5. 账号加固（免费方案的全部保障都在账号上）

- Cloudflare 账号开启 **2FA**
- 账号邮箱换成**常用邮箱**，不要用僵尸邮箱
- 把账号邮箱、项目名、部署方式写进交接文档

---

## 日常更新说明书（3 步）

1. 把旧版备份进 `archive/`，例如 `archive/B03-user-manual-v1.pdf`
2. 用新 PDF 覆盖根目录的 `B03-user-manual.pdf`（**文件名保持不变**）
3. `git add -A && git commit -m "update B03 manual" && git push`

Cloudflare Pages 自动重新部署，约 1 分钟后全球生效。**二维码不动。**

验证：`curl -sI https://windin.pages.dev/b03/pdf | grep -i etag`

### ⚠️ 第 4 步：同步更新 Listing 上的 PDF

说明书有两个投放点，**必须同时更新**：

| 位置 | 更新方式 |
|---|---|
| 包装二维码 → `windin.pages.dev/b03` | 上面 1–3 步 |
| Amazon Listing 商品文档 | Seller Central → 编辑商品 → 重新上传 PDF |

只更新一处会导致「扫码看到的」和「Listing 上显示的」内容不一致，
是 A-to-Z 索赔和差评的把柄。

Listing 重新上传后 Amazon 会生成新的 `m.media-amazon.com` 地址，
**不用理会**——包装二维码不指向 Amazon，不受影响。

历史比对记录：截至 2026-07-27，两份内容差异仅第 3 页
`Adapter not included` 一句（新版有，旧 Listing 版无），其余 7 页逐字一致。

---

## PDF 处理规矩（换新说明书时必看）

> **一句话：不要压缩说明书。** 源稿直接用，只做无损结构整理。
> 2026-07-28 因为压缩连续出了两个问题，教训写在下面。

### 第一条：绝对不要重采样图片

2026-07-28 买家反馈第 6 页插图背景出现一片脏斑、整体发糊。原因是当时用
Ghostscript 压缩时带了 `-dColorImageResolution=150`，把图片降到 150dpi 并重新
JPEG 编码。降的幅度非常离谱：

| 页 | 原图 | 压缩后 |
|---|---|---|
| p3 | 3938×1056 | 787×211 |
| p5 | 2048×2048 | **58×58** |
| p6 | 2048×2048 | **60×60** |
| p6 | 1920×1870 | 640×623 |

背景那片脏斑就是 JPEG 块效应，原图那里是纯白。

**这份说明书全是线条插图（line art），最忌讳有损重编码。**
禁止使用的参数：`-dPDFSETTINGS`、`-dColorImageResolution`、
`-dGrayImageResolution`、`-dDownsampleColorImages` 及任何同类重采样开关。

源稿 1.4MB，无损处理后约 1.17MB，对手机完全没有压力，没有任何压缩的必要。

### 第二条：绝对不要用 `-dFastWebView`

同一次压缩还带了 `-dFastWebView=true`（线性化）。它会在文件里写一张 hint 表，
告诉阅读器"第 N 页在第几字节"，供边下边看。**Ghostscript 生成的这张表不合法**
（`pikepdf.Pdf.check_linearization()` 返回 False）。

Safari / iOS PDFKit 会读这张表，PyMuPDF、Chrome 不读——所以本地怎么查都是好的。
当时有买家反馈 iPhone 上第 3 页重复出现两次，怀疑与此有关，但**未能确证**：
Listing 上那份（Amazon 托管）同样 `check_linearization()` 为 False 却显示正常，
说明表不合法并不必然导致错页。

不管是不是它，**这个站点都不需要线性化**：服务端（Cloudflare Workers 静态资源）
根本不支持 Range 分段请求（无 `Accept-Ranges`，请求分段返回的是 200 + 整个文件），
线性化在这里毫无作用，纯粹是白背一个可能出错的包袱。

### 换说明书时的标准动作

```bash
pip install pikepdf pymupdf numpy

python - <<'PY'
import pikepdf, fitz, numpy as np, hashlib
SRC, DST = "B03新说明书.pdf", "B03-user-manual.pdf"

# 只做无损处理：去线性化 + 内容流 flate + 对象流合并。
# 没有任何重采样/重编码参数 —— 图片数据原封不动搬过去。
p = pikepdf.open(SRC)
p.save(DST, linearize=False, compress_streams=True,
       object_stream_mode=pikepdf.ObjectStreamMode.generate)
p.close()

assert not pikepdf.open(DST).is_linearized, "还带着线性化"

a, b = fitz.open(SRC), fitz.open(DST)
assert a.page_count == b.page_count

# 图片必须逐字节一致 —— 这条能挡住所有"手滑压糊了"
for i in range(a.page_count):
    def sig(d):
        return sorted(
            "%dx%d/%s" % (x["width"], x["height"],
                          hashlib.md5(x["image"]).hexdigest()[:8])
            for im in d[i].get_images(full=True)
            for x in [d.extract_image(im[0])])
    assert sig(a) == sig(b), "第 %d 页图片被改动了" % (i + 1)
    assert a[i].get_text() == b[i].get_text(), "第 %d 页文字变了" % (i + 1)

# 300dpi 渲染必须像素级一致
for i in range(a.page_count):
    def px(d):
        m = d[i].get_pixmap(dpi=300, colorspace=fitz.csGRAY)
        return np.frombuffer(m.samples, np.uint8).reshape(m.height, m.width).astype(np.int16)
    assert np.abs(px(a) - px(b)).max() == 0, "第 %d 页渲染有差异" % (i + 1)

print("OK  %d 页，图片/文字/渲染与源稿完全一致" % b.page_count)
PY
```

改完必须**用真 iPhone 扫码实测翻完 8 页**，重点看有插图的 p3 / p5 / p6。
电脑上用 Chrome 或 PyMuPDF 看不出线性化类问题，缩略图也看不出插图糊没糊。

---

## 将来升级到自有域名（第二批包装时）

**零返工，且不影响已售出的 2000 个盒子：**

1. 注册域名（Cloudflare Registrar，成本价，建议一次买满 10 年）
2. 本项目 → Custom domains → 添加域名
3. 用新域名重新生成二维码，用于**新一批包装**

`*.pages.dev` 地址会**继续正常工作**，两个地址并存。

> ⚠️ 升级之后也**不要删除本项目、不要解绑 pages.dev**。
> 第一批 2000 个盒子上印的是 pages.dev 地址，删掉即失效，
> 且该子域名会重新变为可注册状态，存在被他人接管的风险。

---

## 印刷规范速查

| 项 | 要求 |
|---|---|
| 二维码类型 | **静态码**。绝不使用第三方"动态二维码"服务 |
| 纠错等级 | **Q (25%)** |
| 交付格式 | **SVG 或 EPS 矢量** |
| 最小尺寸 | 20×20 mm，**建议排版 25×25 mm** |
| 静空白区 | 四周至少 4 个模块，不能被边框/图案压到 |
| 颜色 | 单色纯黑 + 白底。不反白、不渐变、不四色套印 |
| Logo | 中心遮挡 ≤15%，建议不放 |
| 配套文字 | 码下方印 `Scan for User Manual` |

**开印前必须**：拿实际材质、实际尺寸的打样件，用 3–5 部不同手机（含 Redmi
等印度主力低端机）在弱光下实测扫码。电脑屏幕上扫图片不作数。

### 生成给印厂的正式文件

```bash
pip install segno reportlab fonttools
python tools/make_print_artwork.py
```

出的是可以直接落到包装设计稿上的整块图（码 + 引导文字 + 白色底板）。

**产出直接覆盖 `B03包装二维码_给印厂/`，全项目只此一份。**
不要另存副本——两份文件迟早会不一致，而发错版本给印厂的代价是 2000 个盒子。

| 文件 | 用途 |
|---|---|
| `B03_二维码_印刷稿_25mm.pdf` | 交印厂的正式文件 |
| `B03_二维码_印刷稿_25mm.svg` | 备用，给用 AI / CorelDRAW 的设计师 |
| `印厂须知_B03二维码.pdf` | 一并发给印厂。一次性文档，无生成脚本 |

规格：整块 25.00 × 29.21 mm（码区 25×25 mm，单模块 0.610 mm），
100% 单黑 CMYK 0/0/0/100，无嵌入字体（已转曲）、无位图、无透明。

改文案或改尺寸：`--text "..."` / `--qr-mm 28`。文字会自动按宽度缩放，
缩到 5.5pt 以下会直接报错而不是硬印上去——那个尺寸货架上看不清。

配套的《印厂须知》（尺寸、颜色红线、印后工艺禁忌、打样要求）在
`桌面/B03包装二维码_给印厂/`，和印刷稿一起发给印厂。

---

## 两条红线

**Amazon 政策**：包装二维码及落地页只能承载说明书和售后内容。
不得出现索取评价（"leave a review"、好评返现），不得放独立站或店铺购买链接。
域名/项目名不得含 `amazon` 字样。违反的是账号层面的风险。

**印度 Legal Metrology**：进口商信息、原产国、净含量、MRP、客服联系方式等
法定标注必须**实体印在包装上**，二维码不能替代。

---

## 已废弃的地址（不要印）

| 地址 | 原因 |
|---|---|
| `m.media-amazon.com/images/I/A1poUVm7dwL.pdf` | Amazon 内容寻址不可变资源，`Expires: 2046`。重新上传说明书会生成**新文件名**，旧链接永远返回旧版本 |
| `cdn.jsdelivr.net/gh/...@main/B03-user-manual.pdf` | 浏览器缓存 7 天、CDN 缓存 12 小时，改了不能及时生效；且是不受你控制的第三方免费 CDN |
| `raw.githubusercontent.com/...` | 返回 `application/octet-stream` + sandbox CSP，手机上会变成下载文件 |
| `*.github.io` | 不支持 `_headers` / `_redirects`，本项目的跳转和缓存设计全部失效 |
