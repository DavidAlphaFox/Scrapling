# Scrapling 架构文档

本文档描述了 Scrapling 项目的整体架构设计、模块组织和数据流。

## 项目概述

Scrapling 是一个自适应的 Python Web 爬虫框架，能够处理从单个请求到大规模爬取的各种场景。其核心特性包括：

- **自适应解析器**：当网站结构变化时自动重新定位元素
- **反爬虫绕过**：内置绕过 Cloudflare Turnstile 等反爬系统的能力
- **Spider 框架**：支持并发、多会话、暂停/恢复的大规模爬取

## 模块结构

```
scrapling/
├── __init__.py          # 主入口，懒加载导出
├── parser.py            # HTML 解析器核心
├── cli.py               # 命令行接口
├── fetchers/            # 网页获取模块
│   ├── __init__.py
│   ├── requests.py      # HTTP 请求获取器
│   ├── chrome.py        # 动态浏览器获取器
│   └── stealth_chrome.py # 隐身浏览器获取器
├── spiders/             # 爬虫框架模块
│   ├── __init__.py
│   ├── spider.py        # Spider 基类
│   ├── engine.py        # 爬虫引擎
│   ├── scheduler.py     # 请求调度器
│   ├── request.py       # 请求对象
│   ├── result.py        # 爬取结果
│   ├── session.py       # 会话管理器
│   └── checkpoint.py    # 断点续爬
├── engines/             # 底层引擎模块
│   ├── __init__.py
│   ├── static.py        # 静态解析引擎
│   ├── constants.py     # 常量定义
│   ├── toolbelt/        # 工具集
│   │   ├── proxy_rotation.py  # 代理轮换
│   │   ├── navigation.py      # 导航工具
│   │   ├── fingerprints.py    # 指纹生成
│   │   ├── custom.py          # 自定义类型
│   │   └── convertor.py       # 转换器
│   └── _browsers/       # 浏览器相关
│       ├── _base.py     # 基础浏览器类
│       ├── _stealth.py  # 隐身浏览器
│       ├── _page.py     # 页面控制
│       ├── _config_tools.py # 配置工具
│       ├── _controllers.py # 控制器
│       ├── _types.py    # 类型定义
│       └── _validators.py # 验证器
├── core/                # 核心工具模块
│   ├── __init__.py
│   ├── translator.py    # CSS/XPath 转换器
│   ├── storage.py       # 存储系统
│   ├── mixins.py        # 混入类
│   ├── custom_types.py  # 自定义类型
│   ├── ai.py            # AI 集成
│   ├── shell.py         # 交互式 Shell
│   └── utils/           # 工具函数
│       ├── _utils.py
│       └── _shell.py
└── tests/               # 测试套件
    ├── fetchers/
    ├── spiders/
    ├── parser/
    ├── core/
    ├── cli/
    └── ai/
```

## 核心架构

### 1. 解析层 (Parser Layer)

**入口类**: `Selector` / `Selectors`

解析层是 Scrapling 的核心，提供高性能的 HTML 解析和元素选择能力。

```
┌─────────────────────────────────────────────────────────┐
│                      Selector                           │
├─────────────────────────────────────────────────────────┤
│ - css(selector)      → CSS3 选择器                      │
│ - xpath(selector)    → XPath 选择器                     │
│ - find_all(...)      → 过滤器查找                       │
│ - find_by_text(...)  → 文本查找                         │
│ - find_by_regex(...) → 正则查找                         │
│ - find_similar(...)  → 相似元素查找                     │
│ - relocate(...)      → 自适应重定位                     │
└─────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│                   Selectors (List子类)                  │
├─────────────────────────────────────────────────────────┤
│ - 链式调用支持                                           │
│ - 批量操作                                              │
│ - filter/get/getall 等方法                              │
└─────────────────────────────────────────────────────────┘
```

**关键特性**:
- 基于 `lxml` 的高性能解析
- 自适应元素追踪（当网站结构变化时自动重新定位）
- 懒加载属性优化性能
- 支持序列化到 SQLite 存储

### 2. 获取层 (Fetcher Layer)

**入口类**: `Fetcher`, `DynamicFetcher`, `StealthyFetcher`

获取层提供多种网页获取方式，从简单的 HTTP 请求到复杂的浏览器自动化。

```
┌────────────────────────────────────────────────────────────────┐
│                        Fetcher Types                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐ │
│  │   Fetcher    │   │  DynamicFetcher  │   │ StealthyFetcher│ │
│  │   (HTTP)     │   │   (Browser)      │   │   (Stealth)    │ │
│  └──────┬───────┘   └────────┬─────────┘   └───────┬────────┘ │
│         │                    │                     │          │
│         ▼                    ▼                     ▼          │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐ │
│  │FetcherSession│   │  DynamicSession  │   │ StealthySession│ │
│  └──────────────┘   └──────────────────┘   └────────────────┘ │
│                                                                │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐ │
│  │ AsyncFetcher │   │AsyncDynamicSess  │   │AsyncStealthy   │ │
│  └──────────────┘   └──────────────────┘   └────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Fetcher 类型对比**:

| 类型 | 底层技术 | 用途 | 特点 |
|------|----------|------|------|
| `Fetcher` | curl_cffi | 快速 HTTP 请求 | TLS 指纹伪装、HTTP/3 支持 |
| `DynamicFetcher` | Playwright | 动态页面 | 完整浏览器自动化 |
| `StealthyFetcher` | Patchright | 反爬绕过 | 指纹欺骗、Cloudflare 绕过 |

**会话管理**:
- 所有 Fetcher 都有对应的 Session 类
- 支持同步/异步两种模式
- 支持代理轮换 (`ProxyRotator`)

### 3. 爬虫框架层 (Spider Framework)

**入口类**: `Spider`

爬虫框架提供类似 Scrapy 的 API，支持大规模并发爬取。

```
┌────────────────────────────────────────────────────────────────┐
│                         Spider                                 │
├────────────────────────────────────────────────────────────────┤
│ - name: str              # 爬虫名称                           │
│ - start_urls: List[str]  # 起始 URL                           │
│ - concurrent_requests    # 并发数                              │
│ - parse(response)        # 解析回调                            │
│ - configure_sessions()   # 配置多会话                          │
└────────────────────────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────┐
│                     CrawlerEngine                              │
├────────────────────────────────────────────────────────────────┤
│ - 管理爬取生命周期                                             │
│ - 协调调度器和会话管理器                                       │
│ - 处理请求/响应流程                                            │
└────────────────────────────────────────────────────────────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐ ┌──────────────┐
│Scheduler│ │SessionManager│
├─────────┤ ├──────────────┤
│请求队列 │ │多会话支持    │
│去重     │ │FetcherSession│
│优先级   │ │StealthySess  │
│         │ │DynamicSess   │
└─────────┘ └──────────────┘
```

**数据流**:

```
start_urls
    │
    ▼
┌─────────┐     ┌─────────┐     ┌─────────┐
│ Request │ ──▶ │ Engine  │ ──▶ │Scheduler│
└─────────┘     └────┬────┘     └─────────┘
                     │
                     ▼
              ┌─────────────┐
              │SessionManager│
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ HTTP    │ │ Stealth │ │ Dynamic │
    │ Session │ │ Session │ │ Session │
    └────┬────┘ └────┬────┘ └────┬────┘
         │           │           │
         └───────────┼───────────┘
                     ▼
              ┌─────────────┐
              │  Response   │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │   parse()   │
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │  Items  │ │ Request │ │  None   │
    │ (数据)  │ │(新请求) │ │ (结束)  │
    └────┬────┘ └────┬────┘ └─────────┘
         │           │
         ▼           ▼
    ┌─────────────────────┐
    │    CrawlResult      │
    │  - items            │
    │  - stats            │
    │  - to_json()        │
    └─────────────────────┘
```

### 4. 引擎层 (Engine Layer)

引擎层提供底层支持，包括浏览器控制和工具集。

**浏览器控制** (`engines/_browsers/`):
- `_base.py`: 基础浏览器抽象
- `_stealth.py`: 隐身浏览器实现
- `_page.py`: 页面操作封装
- `_controllers.py`: 浏览器控制器

**工具集** (`engines/toolbelt/`):
- `proxy_rotation.py`: 代理轮换策略
- `fingerprints.py`: 浏览器指纹生成
- `navigation.py`: 页面导航工具
- `convertor.py`: 数据转换器

### 5. 核心工具层 (Core Layer)

**主要组件**:

| 模块 | 功能 |
|------|------|
| `translator.py` | CSS 到 XPath 转换（基于 Parsel） |
| `storage.py` | SQLite 存储系统，用于自适应元素追踪 |
| `custom_types.py` | `TextHandler`, `AttributesHandler` 等自定义类型 |
| `mixins.py` | 选择器生成混入类 |
| `ai.py` | MCP 服务器集成 |
| `shell.py` | 交互式 IPython Shell |

## 设计模式

### 1. 懒加载 (Lazy Loading)

主模块使用懒加载模式，只有在实际使用时才导入模块：

```python
# scrapling/__init__.py
_LAZY_IMPORTS = {
    "Fetcher": ("scrapling.fetchers", "Fetcher"),
    "Selector": ("scrapling.parser", "Selector"),
    ...
}

def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        module_path, class_name = _LAZY_IMPORTS[name]
        module = __import__(module_path, fromlist=[class_name])
        return getattr(module, class_name)
```

### 2. 上下文管理器 (Context Manager)

所有 Session 类都支持上下文管理器模式：

```python
with FetcherSession(impersonate='chrome') as session:
    page = session.get('https://example.com')
    # 自动管理资源
```

### 3. 生成器模式 (Generator Pattern)

Spider 的 `parse` 方法使用生成器返回数据：

```python
async def parse(self, response: Response):
    for item in response.css('.item'):
        yield {"title": item.css('::text').get()}
```

### 4. 混入模式 (Mixin)

`SelectorsGeneration` 混入类为 `Selector` 提供选择器生成功能。

## 性能优化

### 1. 懒加载属性

`Selector` 类的 `text`, `attrib`, `tag` 等属性使用懒加载：

```python
@property
def text(self) -> TextHandler:
    if self.__text is None:
        self.__text = TextHandler(self._root.text or "")
    return self.__text
```

### 2. 预编译 XPath

常用 XPath 表达式预编译：

```python
_find_all_elements = XPath(".//*")
_find_all_text_nodes = XPath(".//text()")
```

### 3. 快速 JSON 序列化

使用 `orjson` 替代标准库 `json`，性能提升约 10 倍。

## 扩展点

### 1. 自定义存储系统

继承 `StorageSystemMixin` 实现自定义存储：

```python
class CustomStorage(StorageSystemMixin):
    def save(self, element, identifier): ...
    def retrieve(self, identifier): ...
```

### 2. 自定义代理轮换策略

通过 `ProxyRotator` 自定义轮换逻辑：

```python
rotator = ProxyRotator(proxies, strategy='custom')
```

### 3. Spider 钩子

Spider 支持多种钩子方法：

```python
class MySpider(Spider):
    def configure_sessions(self, manager): ...
    async def start_requests(self): ...
```

## 测试覆盖

项目拥有 92% 的测试覆盖率，测试分布在：

- `tests/fetchers/`: 获取器测试
- `tests/spiders/`: 爬虫框架测试
- `tests/parser/`: 解析器测试
- `tests/core/`: 核心工具测试
- `tests/cli/`: 命令行测试
- `tests/ai/`: AI 集成测试
