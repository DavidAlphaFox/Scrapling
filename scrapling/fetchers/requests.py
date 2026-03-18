"""
================================================================================
Scrapling HTTP 请求获取器模块 (Requests Fetcher Module)
================================================================================

【模块功能】
提供基于 HTTP 协议的网页获取功能，是 Scrapling 最基础的获取器。
使用 curl_cffi 库实现，支持 TLS 指纹伪装和 HTTP/3。

【核心类】
- Fetcher: 同步 HTTP 请求获取器，支持 GET/POST/PUT/DELETE 方法
- AsyncFetcher: 异步 HTTP 请求获取器，支持 GET/POST/PUT/DELETE 方法

【特点】
1. TLS 指纹伪装：可模拟 Chrome、Firefox 等浏览器的 TLS 指纹
2. HTTP/3 支持：更快的连接速度
3. 隐身请求头：可选添加反检测请求头

【使用示例】
>>> from scrapling.fetchers import Fetcher, FetcherSession
>>>
>>> # 一次性请求
>>> page = Fetcher.get('https://example.com')
>>> quotes = page.css('.quote .text::text').getall()
>>>
>>> # 会话模式（保持 cookies 和连接）
>>> with FetcherSession(impersonate='chrome') as session:
...     page = session.get('https://example.com', stealthy_headers=True)
...     data = page.css('.item::text').getall()

【依赖】
- curl_cffi: HTTP 客户端，支持 TLS 指纹伪装
- scrapling.engines.static: 底层静态引擎实现
================================================================================
"""

from scrapling.engines.static import (
    FetcherSession,
    FetcherClient as _FetcherClient,
    AsyncFetcherClient as _AsyncFetcherClient,
)
from scrapling.engines.toolbelt.custom import BaseFetcher


__FetcherClientInstance__ = _FetcherClient()
__AsyncFetcherClientInstance__ = _AsyncFetcherClient()


class Fetcher(BaseFetcher):
    """HTTP 请求获取器（同步版本）

    【功能说明】
    提供基本的 GET、POST、PUT、DELETE HTTP 请求功能。
    基于 curl_cffi 实现，支持 TLS 指纹伪装。

    【使用场景】
    - 简单的网页抓取
    - API 请求
    - 不需要浏览器渲染的页面

    【注意】
    这是一个"一次性"获取器，每次请求都是独立的。
    如需保持会话状态（cookies、连接复用），请使用 FetcherSession。

    【示例】
    >>> page = Fetcher.get('https://example.com')
    >>> page = Fetcher.post('https://api.example.com', data={'key': 'value'})
    """

    get = __FetcherClientInstance__.get  # GET 请求方法
    post = __FetcherClientInstance__.post  # POST 请求方法
    put = __FetcherClientInstance__.put  # PUT 请求方法
    delete = __FetcherClientInstance__.delete  # DELETE 请求方法


class AsyncFetcher(BaseFetcher):
    """HTTP 请求获取器（异步版本）

    【功能说明】
    提供异步的 GET、POST、PUT、DELETE HTTP 请求功能。
    与 Fetcher 功能相同，但支持异步调用。

    【使用场景】
    - 异步爬虫框架中
    - 需要高并发的场景
    - 与 asyncio 配合使用

    【示例】
    >>> import asyncio
    >>>
    >>> async def main():
    ...     page = await AsyncFetcher.get('https://example.com')
    ...     return page.css('.item::text').getall()
    >>>
    >>> asyncio.run(main())
    """

    get = __AsyncFetcherClientInstance__.get  # 异步 GET 请求方法
    post = __AsyncFetcherClientInstance__.post  # 异步 POST 请求方法
    put = __AsyncFetcherClientInstance__.put  # 异步 PUT 请求方法
    delete = __AsyncFetcherClientInstance__.delete  # 异步 DELETE 请求方法
