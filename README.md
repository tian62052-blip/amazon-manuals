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
├── tools/make_qr.py        二维码生成脚本
└── .gitignore
```

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
pip install segno
cd tools
python make_qr.py https://windin.pages.dev/b03 --name b03
```

把 `tools/out/b03_qr.svg` 交给印厂。**不要给 PNG。**

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
| 配套文字 | 码下方印可读地址 + `Scan for User Manual` |

**开印前必须**：拿实际材质、实际尺寸的打样件，用 3–5 部不同手机（含 Redmi
等印度主力低端机）在弱光下实测扫码。电脑屏幕上扫图片不作数。

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
