# Scrapling 依赖包文档

本文档详细描述了 Scrapling 项目使用的所有依赖包及其用途。

## 依赖概述

Scrapling 采用模块化依赖设计，核心解析功能只需要少量依赖，额外功能通过可选依赖组安装。

## 核心依赖 (Core Dependencies)

这些依赖是 Scrapling 运行的最低要求，安装 `pip install scrapling` 即可获得。

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `lxml` | >=6.0.2 | 高性能 HTML/XML 解析器，是整个解析层的基础 |
| `cssselect` | >=1.4.0 | CSS 选择器到 XPath 的转换 |
| `orjson` | >=3.11.7 | 快速 JSON 序列化库，比标准库快约 10 倍 |
| `tld` | >=0.13.2 | 顶级域名提取，用于 URL 处理 |
| `w3lib` | >=2.4.0 | URL 处理和编码工具 |
| `typing_extensions` | - | Python 类型扩展支持 |

### 核心依赖详解

#### lxml
- **用途**: HTML/XML 解析的核心引擎
- **为什么选择 lxml**:
  - 性能优异，基于 C 库 libxml2 和 libxslt
  - 支持 XPath 1.0
  - 支持宽松的 HTML 解析
  - 内存效率高
- **在 Scrapling 中的使用**:
  - `Selector` 类使用 `lxml.html.HtmlElement` 作为底层元素表示
  - 所有 CSS 选择器最终转换为 XPath 执行
  - 支持 `huge_tree` 模式处理大型文档

#### cssselect
- **用途**: 将 CSS3 选择器转换为 XPath 表达式
- **为什么重要**: 让用户可以使用熟悉的 CSS 语法而非 XPath
- **在 Scrapling 中的使用**:
  - `css()` 方法通过此库转换选择器
  - 支持大部分 CSS3 选择器语法

#### orjson
- **用途**: 高性能 JSON 序列化
- **性能对比**: 比标准 `json` 库快约 10 倍
- **在 Scrapling 中的使用**:
  - `TextHandler.json()` 方法
  - `CrawlResult.items.to_json()` 导出
  - 内部数据序列化

## 可选依赖组 (Optional Dependencies)

### fetchers 组

用于网页获取、浏览器自动化和反爬虫绕过功能。

```bash
pip install "scrapling[fetchers]"
```

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `click` | >=8.3.0 | 命令行接口框架 |
| `curl_cffi` | >=0.14.0 | HTTP 客户端，模拟浏览器 TLS 指纹 |
| `playwright` | ==1.58.0 | 浏览器自动化框架 |
| `patchright` | ==1.58.2 | Playwright 的隐身补丁版本 |
| `browserforge` | >=1.2.4 | 浏览器指纹生成 |
| `apify-fingerprint-datapoints` | >=0.11.0 | 高级指纹数据 |
| `msgspec` | >=0.20.0 | 快速消息序列化 |
| `anyio` | >=4.12.1 | 异步 IO 抽象层 |

#### fetchers 依赖详解

##### curl_cffi
- **用途**: 高性能 HTTP 客户端，支持 TLS 指纹伪装
- **特点**:
  - 可以模拟 Chrome、Firefox 等浏览器的 TLS 指纹
  - 支持 HTTP/2 和 HTTP/3
  - 比原生 requests 更难被检测
- **在 Scrapling 中的使用**:
  - `Fetcher` 和 `FetcherSession` 的底层实现
  - `impersonate` 参数支持多种浏览器指纹

##### playwright
- **用途**: 跨浏览器自动化框架
- **特点**:
  - 支持 Chromium、Firefox、WebKit
  - 自动等待、网络拦截
  - 强大的选择器引擎
- **在 Scrapling 中的使用**:
  - `DynamicFetcher` 的基础
  - 处理 JavaScript 渲染的页面

##### patchright
- **用途**: Playwright 的隐身版本
- **特点**:
  - 移除了自动化检测特征
  - 可以绑过 Cloudflare Turnstile
  - 指纹欺骗功能
- **在 Scrapling 中的使用**:
  - `StealthyFetcher` 的底层实现
  - 反爬虫绕过场景

##### browserforge
- **用途**: 生成逼真的浏览器指纹
- **生成内容**:
  - User-Agent
  - Accept headers
  - Sec-CH-UA headers
  - 导航器属性

### ai 组

用于 MCP 服务器集成，支持 AI 辅助爬取。

```bash
pip install "scrapling[ai]"
```

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `mcp` | >=1.26.0 | Model Context Protocol 服务器 |
| `markdownify` | >=1.2.0 | HTML 转 Markdown |
| `scrapling[fetchers]` | - | 包含 fetchers 组 |

#### ai 依赖详解

##### mcp
- **用途**: 实现 Model Context Protocol 服务器
- **应用场景**:
  - 与 Claude、Cursor 等 AI 工具集成
  - AI 辅助数据提取
  - 减少传递给 AI 的 token 数量

##### markdownify
- **用途**: 将 HTML 转换为 Markdown
- **在 Scrapling 中的使用**:
  - MCP 服务器中预处理网页内容
  - 提取主要内容供 AI 分析

### shell 组

用于交互式 Web Scraping Shell。

```bash
pip install "scrapling[shell]"
```

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `IPython` | >=8.37 | 增强的交互式 Python Shell |
| `markdownify` | >=1.2.0 | HTML 转 Markdown |
| `scrapling[fetchers]` | - | 包含 fetchers 组 |

#### shell 依赖详解

##### IPython
- **用途**: 提供增强的交互式开发环境
- **特点**:
  - 语法高亮
  - 自动补全
  - 魔术命令
  - 丰富的对象显示
- **在 Scrapling 中的使用**:
  - `scrapling shell` 命令
  - 快速原型开发和调试

### all 组

安装所有可选功能。

```bash
pip install "scrapling[all]"
```

包含: `ai` + `shell` 组的所有依赖。

## 开发依赖 (Development Dependencies)

### 文档构建 (docs/requirements.txt)

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| `zensical` | >=0.0.27 | 文档主题/工具 |
| `mkdocstrings` | >=1.0.3 | MkDocs 代码文档字符串插件 |
| `mkdocstrings-python` | >=2.0.3 | Python 代码文档支持 |
| `griffe-inherited-docstrings` | >=1.1.3 | 继承文档字符串支持 |
| `griffe-runtime-objects` | >=0.3.1 | 运行时对象检查 |
| `griffe-sphinx` | >=0.2.1 | Sphinx 风格文档支持 |
| `black` | >=26.1.0 | 代码格式化 |
| `pngquant` | - | PNG 图片压缩 |

### 测试和代码质量

从 `pytest.ini`, `ruff.toml`, `tox.ini` 等配置文件可见：

| 工具 | 用途 |
|------|------|
| `pytest` | 测试框架 |
| `ruff` | 快速 Linter 和格式化 |
| `tox` | 多环境测试 |
| `pre-commit` | Git 钩子管理 |
| `bandit` | 安全检查 |
| `mypy` | 静态类型检查 |
| `pyright` | 类型检查 |

## 依赖关系图

```
scrapling (核心)
├── lxml >=6.0.2
├── cssselect >=1.4.0
├── orjson >=3.11.7
├── tld >=0.13.2
├── w3lib >=2.4.0
└── typing_extensions

scrapling[fetchers]
├── (核心依赖)
├── click >=8.3.0
├── curl_cffi >=0.14.0
├── playwright ==1.58.0
├── patchright ==1.58.2
├── browserforge >=1.2.4
├── apify-fingerprint-datapoints >=0.11.0
├── msgspec >=0.20.0
└── anyio >=4.12.1

scrapling[ai]
├── (fetchers 依赖)
├── mcp >=1.26.0
└── markdownify >=1.2.0

scrapling[shell]
├── (fetchers 依赖)
├── IPython >=8.37
└── markdownify >=1.2.0

scrapling[all]
├── (ai 依赖)
└── (shell 依赖)
```

## 版本兼容性

### Python 版本

- **最低要求**: Python 3.10
- **支持版本**: 3.10, 3.11, 3.12, 3.13
- **实现**: CPython

### 操作系统

- **支持**: 跨平台 (Linux, macOS, Windows)
- **注意**: 某些浏览器自动化功能在无头服务器上需要额外配置

## 安装后配置

### 浏览器安装

安装 `fetchers` 组后，需要下载浏览器：

```bash
scrapling install           # 正常安装
scrapling install --force   # 强制重新安装
```

或通过代码安装：

```python
from scrapling.cli import install
install([], standalone_mode=False)
```

### Docker 镜像

预配置的 Docker 镜像包含所有依赖和浏览器：

```bash
docker pull pyd4vinci/scrapling
# 或
docker pull ghcr.io/d4vinci/scrapling:latest
```

## 常见问题

### 1. 为什么 playwright 和 patchright 版本固定？

这两个包版本需要严格匹配以确保兼容性。`patchright` 是 `playwright` 的补丁版本，必须同步更新。

### 2. curl_cffi 安装失败？

`curl_cffi` 需要编译 C 扩展，确保系统有：
- C 编译器 (gcc/clang)
- libcurl 开发头文件
- Python 开发头文件

### 3. 如何减少依赖？

如果只需要解析功能：
```bash
pip install scrapling  # 只安装核心依赖
```

然后在代码中直接使用 `Selector`：
```python
from scrapling.parser import Selector
page = Selector("<html>...</html>")
```

### 4. IPython 版本限制

IPython >=8.37 是最后一个支持 Python 3.10 的版本。如果使用 Python 3.11+，可以使用更新的 IPython 版本。
