"""
================================================================================
Scrapling 隐身浏览器获取器模块 (Stealth Browser Fetcher Module)
================================================================================

【模块功能】
提供高级反检测能力的浏览器获取功能。
使用 patchright（Playwright 的隐身补丁版本）绕过各种反爬虫系统。

【核心类】
- StealthyFetcher: 隐身浏览器获取器（一次性请求）
- StealthySession: 隐身浏览器会话（同步）
- AsyncStealthySession: 隐身浏览器会话（异步）

【主要特性】
1. Cloudflare 绕过：自动解决 Cloudflare Turnstile 验证
2. 指纹欺骗：模拟真实浏览器的各种指纹特征
3. 自动化检测规避：隐藏 webdriver 等自动化特征
4. 完整的浏览器功能：继承 DynamicFetcher 的所有能力

【使用场景】
- 有 Cloudflare 保护的网站
- 检测自动化工具的网站
- 需要高级反爬虫绑过的场景

【使用示例】
>>> from scrapling.fetchers import StealthyFetcher, StealthySession
>>>
>>> # 一次性请求（自动解决 Cloudflare）
>>> page = StealthyFetcher.fetch(
...     'https://nopecha.com/demo/cloudflare',
...     headless=True,
...     solve_cloudflare=True
... )
>>>
>>> # 会话模式
>>> with StealthySession(headless=True, solve_cloudflare=True) as session:
...     page = session.fetch('https://protected-site.com')
...     data = page.css('.content').getall()

【与 DynamicFetcher 的区别】
- DynamicFetcher: 标准浏览器，可能被检测
- StealthyFetcher: 隐身浏览器，绑过大多数检测

【依赖】
- patchright: Playwright 的隐身补丁版本
- browserforge: 浏览器指纹生成
================================================================================
"""

from scrapling.core._types import Unpack
from scrapling.engines._browsers._types import StealthSession
from scrapling.engines.toolbelt.custom import BaseFetcher, Response
from scrapling.engines._browsers._stealth import StealthySession, AsyncStealthySession


class StealthyFetcher(BaseFetcher):
    """隐身浏览器获取器 - 绑过反爬虫检测的高级浏览器获取器

    【功能说明】
    基于 patchright（Playwright 的隐身版本）实现的浏览器获取器。
    能够绑过 Cloudflare Turnstile、DataDome 等反爬虫系统。

    【与 DynamicFetcher 的区别】
    - 使用 patchright 而非 playwright
    - 内置指纹欺骗和自动化检测规避
    - 支持自动解决 Cloudflare 验证码

    【性能考虑】
    - 比 DynamicFetcher 略慢（因为额外的隐身处理）
    - 建议仅在需要绑过反爬虫时使用

    【重要参数说明】
    - solve_cloudflare: 自动解决 Cloudflare（默认 False）
    - google_search: 添加 Google Referer（默认启用）
    - 其余参数与 DynamicFetcher 相同
    """

    @classmethod
    def fetch(cls, url: str, **kwargs: Unpack[StealthSession]) -> Response:
        """打开隐身浏览器并获取网页内容（同步版本）

        【功能说明】
        创建临时隐身浏览器实例，访问指定 URL，自动绑过检测并返回页面。
        请求完成后自动关闭浏览器。

        【特有参数】
        :param url: 目标 URL
        :param solve_cloudflare: 自动解决 Cloudflare Turnstile 验证（默认 False）
        :param hide_canvas: 添加随机噪声防止 Canvas 指纹（默认 False）
        :param block_webrtc: 强制 WebRTC 使用代理防止 IP 泄露（默认 False）
        :param allow_webgl: 启用 WebGL（默认 True，禁用可能导致被检测）
        :param timezone_id: 设置浏览器时区
        :param user_data_dir: 用户数据目录，存储 cookies 和本地存储

        【继承参数】
        继承 DynamicFetcher 的所有参数：
        :param headless: 无头模式（默认 True）
        :param disable_resources: 禁用资源加载提升速度
        :param blocked_domains: 封锁的域名列表
        :param useragent: 自定义 User-Agent
        :param cookies: 预设 cookies
        :param network_idle: 等待网络空闲
        :param timeout: 操作超时时间（毫秒）
        :param wait: 额外等待时间（毫秒）
        :param page_action: 页面操作函数
        :param wait_selector: 等待的 CSS 选择器
        :param init_script: 页面创建时执行的 JS 文件路径
        :param locale: 用户区域设置
        :param wait_selector_state: 选择器状态（attached/visible/hidden）
        :param real_chrome: 使用本地 Chrome 浏览器
        :param cdp_url: 连接到现有浏览器的 CDP URL
        :param google_search: 添加 Google Referer 头（默认启用）
        :param extra_headers: 额外的请求头
        :param proxy: 代理设置
        :param extra_flags: 额外的浏览器启动参数
        :param selector_config: Selector 类的配置参数
        :param additional_args: 传递给 Playwright context 的额外参数

        :return: Response 对象，包含页面内容和选择器
        """
        selector_config = kwargs.get("selector_config", {}) or kwargs.get("custom_config", {})
        if not isinstance(selector_config, dict):
            raise TypeError("Argument `selector_config` must be a dictionary.")

        kwargs["selector_config"] = {**cls._generate_parser_arguments(), **selector_config}

        with StealthySession(**kwargs) as engine:
            return engine.fetch(url)

    @classmethod
    async def async_fetch(cls, url: str, **kwargs: Unpack[StealthSession]) -> Response:
        """打开隐身浏览器并获取网页内容（异步版本）

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

        async with AsyncStealthySession(**kwargs) as engine:
            return await engine.fetch(url)
