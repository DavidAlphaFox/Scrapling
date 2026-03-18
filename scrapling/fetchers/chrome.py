"""
================================================================================
Scrapling 动态浏览器获取器模块 (Dynamic Browser Fetcher Module)
================================================================================

【模块功能】
提供基于 Chromium 浏览器的动态网页获取功能。
使用 Playwright 驱动浏览器，可以执行 JavaScript 并获取完全渲染的页面。

【核心类】
- DynamicFetcher: 动态浏览器获取器（一次性请求）
- DynamicSession: 动态浏览器会话（同步）
- AsyncDynamicSession: 动态浏览器会话（异步）

【主要特性】
1. JavaScript 执行：完全渲染动态内容
2. 页面自动化：支持自定义页面操作
3. 资源控制：可禁用图片/CSS 等资源加载
4. 域名封锁：阻止特定域名的请求
5. 代理支持：完整的代理配置
6. 网络等待：等待网络空闲后再获取

【使用场景】
- 需要 JavaScript 渲染的 SPA 应用
- 需要执行页面操作（点击、滚动等）的场景
- 反爬虫较弱的动态页面

【使用示例】
>>> from scrapling.fetchers import DynamicFetcher, DynamicSession
>>>
>>> # 一次性请求
>>> page = DynamicFetcher.fetch('https://example.com', headless=True)
>>> data = page.css('.item::text').getall()
>>>
>>> # 会话模式（保持浏览器打开）
>>> with DynamicSession(headless=True, network_idle=True) as session:
...     page = session.fetch('https://example.com')
...     data = page.css('.item::text').getall()

【依赖】
- playwright: 浏览器自动化框架
- patchright: 隐身浏览器补丁
================================================================================
"""

from scrapling.core._types import Unpack
from scrapling.engines._browsers._types import PlaywrightSession
from scrapling.engines.toolbelt.custom import BaseFetcher, Response
from scrapling.engines._browsers._controllers import DynamicSession, AsyncDynamicSession


class DynamicFetcher(BaseFetcher):
    """动态浏览器获取器 - 使用 Chromium 浏览器获取动态网页

    【功能说明】
    打开真实的浏览器实例，执行 JavaScript，获取完全渲染后的页面内容。
    基于 Playwright 实现，支持丰富的浏览器控制选项。

    【与 Fetcher 的区别】
    - Fetcher: 纯 HTTP 请求，不执行 JavaScript
    - DynamicFetcher: 完整浏览器渲染，执行所有 JavaScript

    【性能考虑】
    - 比纯 HTTP 请求慢，但能获取动态内容
    - 可通过 disable_resources 禁用资源加载提升速度

    【重要参数说明】
    - headless: 无头模式（默认 True），设为 False 可查看浏览器操作
    - network_idle: 等待网络空闲（推荐用于 AJAX 页面）
    - wait_selector: 等待特定元素出现
    - page_action: 自定义页面操作函数
    """

    @classmethod
    def fetch(cls, url: str, **kwargs: Unpack[PlaywrightSession]) -> Response:
        """打开浏览器并获取网页内容（同步版本）

        【功能说明】
        创建临时浏览器实例，访问指定 URL，返回渲染后的页面。
        请求完成后自动关闭浏览器。

        【参数说明】
        :param url: 目标 URL
        :param headless: 无头模式（默认 True），False 为有头模式
        :param disable_resources: 禁用资源加载（图片、CSS等），提升速度
        :param blocked_domains: 封锁的域名列表（支持子域名匹配）
        :param useragent: 自定义 User-Agent
        :param cookies: 预设 cookies
        :param network_idle: 等待网络空闲（至少 500ms 无请求）
        :param load_dom: 等待 DOM 完全加载（默认启用）
        :param timeout: 操作超时时间（毫秒，默认 30000）
        :param wait: 额外等待时间（毫秒）
        :param page_action: 页面操作函数，接收 page 对象
        :param wait_selector: 等待的 CSS 选择器
        :param wait_selector_state: 选择器状态（attached/visible/hidden）
        :param real_chrome: 使用本地安装的 Chrome 浏览器
        :param cdp_url: 连接到现有浏览器的 CDP URL
        :param google_search: 添加 Google Referer 头（默认启用）
        :param extra_headers: 额外的请求头
        :param proxy: 代理设置（字符串或字典）
        :param extra_flags: 额外的浏览器启动参数
        :param selector_config: Selector 类的配置参数
        :param additional_args: 传递给 Playwright context 的额外参数

        :return: Response 对象，包含页面内容和选择器
        """
        selector_config = kwargs.get("selector_config", {}) or kwargs.get("custom_config", {})  # 兼容旧参数名
        if not isinstance(selector_config, dict):
            raise TypeError("Argument `selector_config` must be a dictionary.")

        kwargs["selector_config"] = {**cls._generate_parser_arguments(), **selector_config}

        with DynamicSession(**kwargs) as session:
            return session.fetch(url)

    @classmethod
    async def async_fetch(cls, url: str, **kwargs: Unpack[PlaywrightSession]) -> Response:
        """打开浏览器并获取网页内容（异步版本）

        【功能说明】
        异步版本的 fetch 方法，功能完全相同。
        适用于异步爬虫框架或高并发场景。

        【参数说明】
        与 fetch() 方法参数完全相同，详见 fetch() 文档。

        :return: Response 对象
        """
        selector_config = kwargs.get("selector_config", {}) or kwargs.get("custom_config", {})
        if not isinstance(selector_config, dict):
            raise TypeError("Argument `selector_config` must be a dictionary.")

        kwargs["selector_config"] = {**cls._generate_parser_arguments(), **selector_config}

        async with AsyncDynamicSession(**kwargs) as session:
            return await session.fetch(url)


PlayWrightFetcher = DynamicFetcher  # For backward-compatibility
