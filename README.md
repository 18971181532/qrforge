# QRForge

从零手写的 QR 码编解码器 —— GF(256) Reed-Solomon、BCH 格式信息、掩码评估、损伤自愈、PNG 渲染、CLI 与 Canvas Web 工作台。**版本 1–10，零第三方依赖。**

*A QR code encoder/decoder built from scratch: GF(256) Reed-Solomon, BCH format info, mask evaluation, damage self-healing, PNG rendering, CLI and a Canvas web workbench. Versions 1–10, zero dependencies.*

```
qrforge encode "Hello, QRForge!"      # ASCII 矩阵
qrforge png "https://example.com" -o qr.png
qrforge decode --selfcheck "中文往返"
qrforge serve                          # 打开 Web 工作台 (127.0.0.1:8860)
```

## 为什么造这个轮子？

市面上的 Python QR 库（qrcode、pyzbar、segno）把编解码当黑盒。QRForge 把整条链路——有限域算术、纠错码、掩码选择、模块摆位——逐层从零实现，每一层都可以单独观察和测试，适合用来真正理解 ISO/IEC 18004 而不是调用它。

| 层 | 内容 |
|---|---|
| `galois.py` | GF(2⁸) 表驱动乘除法，本原多项式 0x11D，α = 2 |
| `tables.py` | 版本 1–10 全量块结构 / 格式信息 / 对齐中心（对照 Thonky 纠错表） |
| `encode.py` | numeric / alphanumeric / byte 三种模式位流封装 |
| `rscodec.py` | RS 编码 + 完整解码流水线：伴随式 → Berlekamp-Massey → Chien 搜索 → Forney 纠错 |
| `matrix.py` | 定位图形、时序线、对齐图形、8 种掩码、N1–N4 惩罚评估 |
| `formatinfo.py` | BCH(15,5) 格式信息与 BCH(18,6) 版本信息 |
| `qrforge.py` | 端到端 encode/decode、蛇形摆位、块交织/解交织、损伤注入 |
| `png.py` | 纯 `zlib` + `struct` 的 PNG 编码器（24-bit 真彩、4 模块静区） |
| `cli.py` / `server.py` | CLI 子命令与 ThreadingHTTPServer 工作台后端 |

## 功能

- **编码**：三种数据模式（数字 / 字母数字 / 字节），UTF-8 中文支持，自动选择最紧凑模式与最小版本（1–10），四档纠错级别 L/M/Q/H
- **解码**：完整逆向链路，支持从 ASCII 矩阵文件或 `--selfcheck` 模式解码
- **损伤自愈**：基于 Reed-Solomon 的字节级纠错（每块最多 t = ec/2 字节），实时显示纠正字节数；超容量时明确报错拒绝静默坏数据
- **掩码评估**：8 种掩码的 N1–N4 惩罚分明细，自动选最优（惩罚分最低）
- **RS 流水线观察**：逐块数据/纠错码字十六进制展示与交织结果
- **基准**：全版本×级别 40 组往返测试的编码/解码耗时
- **PNG 输出**：零依赖真彩 PNG，可调缩放与静区
- **Web 工作台**：六标签暗色界面（生成 / 损伤自愈 / 掩码评估 / RS 编解码 / 基准 / 参考）

## 环境与依赖

- Python **3.9+**（无任何第三方依赖，纯标准库）
- 平台无关（Windows / macOS / Linux）

## 安装

```bash
git clone https://github.com/18971181532/qrforge.git
cd qrforge
pip install -e .
```

## 使用

### CLI

```bash
# 生成 ASCII 矩阵（终端直接打印）
qrforge encode "Hello, QRForge!"
qrforge encode "8675309" -l L          # 数字模式，纠错级 L

# JSON 输出（含 rows 矩阵，便于程序消费）
qrforge encode "api payload" --json

# 导出 PNG（-s 每模块像素数，默认 8；-b 静区模块数，默认 4）
qrforge png "https://example.com" -o qr.png -s 6

# 解码 ASCII 矩阵文件
qrforge encode "round trip" > qr.txt
qrforge decode qr.txt

# 自检：生成→损伤注入→RS 自愈→往返校验，一条命令
qrforge decode --selfcheck "通过中文字符的往返测试" -l Q

# 版本 1–10 × L/M/Q/H 块结构速查表
qrforge info

# 启动 Web 工作台（默认 127.0.0.1:8860）
qrforge serve
```

### Python API

```python
from qrforge import qrforge as core

r = core.encode("Hello, QRForge!", level="M")
print(r["version"], r["mask"], r["size"])   # 2 5 25

d = core.decode(r["matrix"])
print(d["text"], d["corrected_bytes"])       # Hello, QRForge! 0

# 损伤自愈：随机翻转 12 个数据模块
damaged, flips = core.damage(r["matrix"], 12, seed=1)
d = core.decode(damaged)
print(d["text"], "corrected", d["corrected_bytes"], "bytes")

# 观察掩码评估 / RS 流水线
core.mask_eval("mask detail", "M")   # 8 种掩码的 N1–N4 惩罚分
core.rs_pipeline("pipeline", "M")    # 逐块 data/ec 码字 + 交织结果
```

### Web 工作台

`qrforge serve` 后浏览器打开 `http://127.0.0.1:8860/`：

- **生成** — QR canvas + 参数卡 + ASCII 矩阵
- **损伤自愈** — 滑块控制翻转模块数，红框标记损伤位置，实时显示 RS 纠错结果
- **掩码评估** — 8 种掩码惩罚分明细表，最低分行高亮
- **RS 编解码** — 块结构、生成多项式、逐块码字十六进制流水线
- **基准** — 40 组版本×级别往返基准
- **参考** — 版本 1–10 块结构表（Thonky / ISO 18004）

## 测试

```bash
python -m unittest discover tests    # 52 个测试
```

覆盖：GF(256) 域公理、生成多项式系数（对照 Thonky）、RS 编解码（含随机错码压力测试）、格式信息 BCH 码字海明距、三种模式位级打包、全版本×级别往返、损伤自愈边界（恰 t 字节必纠回 / 超容量必拒绝）、PNG 块完整性与 IHDR 字段、CLI 全子命令。

## 目录结构

```
qrforge/
├── qrforge/
│   ├── __init__.py      # 包导出
│   ├── galois.py        # GF(256) 有限域算术
│   ├── tables.py        # 版本 1–10 块结构/格式/对齐表
│   ├── encode.py        # 位流编码（numeric/alnum/byte）
│   ├── rscodec.py       # Reed-Solomon 编解码流水线
│   ├── matrix.py        # 模块矩阵、掩码、惩罚评估
│   ├── formatinfo.py    # BCH 格式/版本信息
│   ├── qrforge.py       # 端到端 encode/decode/damage
│   ├── png.py           # 零依赖 PNG 编码器
│   ├── cli.py           # CLI 子命令
│   ├── server.py        # 工作台 HTTP 后端
│   └── web/             # index.html / style.css / app.js
├── tests/               # 52 个单元/集成测试
├── examples/
│   ├── generate_demo.py # API 使用示例
│   └── damage_heal.py   # 损伤自愈演示
├── pyproject.toml
└── README.md
```

## 技术要点

**GF(256) 算术** — 乘法用对数/指数双表实现 O(1) 查表；本原多项式 x⁸+x⁴+x³+x²+1（0x11D），生成元 α=2。

**Reed-Solomon** — 编码为多项式除以生成多项式 g(x)=∏(x−αⁱ)；解码完整实现教科书流水线：伴随式计算 → Berlekamp-Massey 求错误位置多项式 σ(x) → Chien 搜索根 → Forney 公式求错误幅值。所有多项式采用低次在先约定。

**掩码选择** — ISO 18004 定义的 8 种掩码函数逐一试算 N1（连续同色）/N2（2×2 同色块）/N3（类定位图形）/N4（暗模块占比）四项惩罚，取总分最低者。

**格式信息** — 15 位 BCH(15,5) 双副本放置；解析采用暴力枚举 32 个合法码字（比 BCH 解码更简单可靠）。版本 7+ 附加 BCH(18,6) 版本信息。

## 许可

MIT
