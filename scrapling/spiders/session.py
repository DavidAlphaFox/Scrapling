"""
================================================================================
Scrapling 会话管理器模块 (Session Manager Module)
================================================================================

【模块功能】
管理爬虫使用的多种获取器会话，支持在同一个爬虫中使用不同类型的获取器。

【核心类】
- SessionManager: 会话管理器

【主要特性】
1. 多会话支持：注册多个不同类型的会话（HTTP、动态浏览器、隐身浏览器）
2. 延迟启动：支持 lazy 模式，只在首次使用时启动会话
3. 默认会话：自动指定第一个会话为默认会话
4. 生命周期管理：统一管理所有会话的启动和关闭

【使用示例】
>>> from scrapling.spiders import Spider
>>> from scrapling.fetchers import FetcherSession, AsyncStealthySession
>>>
>>> class MySpider(Spider):
...     def configure_sessions(self, manager):
...         manager.add("fast", FetcherSession(impersonate="chrome"))
...         manager.add("stealth", AsyncStealthySession(headless=True), lazy=True)
>>>
>>> # 在请求中指定会话
>>> yield Request(url, sid="stealth")
================================================================================
"""

from asyncio import Lock

from scrapling.spiders.request import Request
from scrapling.engines.static import _ASyncSessionLogic
from scrapling.engines.toolbelt.convertor import Response
from scrapling.core._types import Set, cast, SUPPORTED_HTTP_METHODS
from scrapling.fetchers import AsyncDynamicSession, AsyncStealthySession, FetcherSession

Session = FetcherSession | AsyncDynamicSession | AsyncStealthySession


class SessionManager:
    """会话管理器 - 管理预配置的会话实例

    【功能说明】
    集中管理爬虫使用的各种获取器会话。
    支持在同一爬虫中混合使用 HTTP 请求、动态浏览器和隐身浏览器。

    【会话类型】
    - FetcherSession: HTTP 请求会话（快速）
    - AsyncDynamicSession: 动态浏览器会话（支持 JS）
    - AsyncStealthySession: 隐身浏览器会话（反爬虫）

    【延迟启动】
    通过 lazy=True 注册的会话不会在爬虫启动时立即初始化，
    而是等到首次有请求使用该会话 ID 时才启动。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._default_session_id: str | None = None
        self._started: bool = False
        self._lazy_sessions: Set[str] = set()
        self._lazy_lock = Lock()

    def add(self, session_id: str, session: Session, *, default: bool = False, lazy: bool = False) -> "SessionManager":
        """注册会话实例

        :param session_id: 会话标识符，在请求中通过 sid 引用
        :param session: 预配置的会话实例
        :param default: 设为默认会话（不指定时自动使用第一个）
        :param lazy: 延迟启动，首次使用时才初始化
        :return: 返回自身，支持链式调用
        """
        if session_id in self._sessions:
            raise ValueError(f"Session '{session_id}' already registered")

        self._sessions[session_id] = session

        if default or self._default_session_id is None:
            self._default_session_id = session_id

        if lazy:
            self._lazy_sessions.add(session_id)

        return self

    def remove(self, session_id: str) -> None:
        """移除会话

        :param session_id: 要移除的会话 ID
        """
        _ = self.pop(session_id)

    def pop(self, session_id: str) -> Session:
        """移除并返回会话

        :param session_id: 要移除的会话 ID
        :return: 被移除的会话实例
        """
        if session_id not in self._sessions:
            raise KeyError(f"Session '{session_id}' not found")

        session = self._sessions.pop(session_id)
        if session_id in self._lazy_sessions:
            self._lazy_sessions.remove(session_id)

        if session and self._default_session_id == session_id:
            self._default_session_id = next(iter(self._sessions), None)

        return session

    @property
    def default_session_id(self) -> str:
        """默认会话 ID"""
        if self._default_session_id is None:
            raise RuntimeError("No sessions registered")
        return self._default_session_id

    @property
    def session_ids(self) -> list[str]:
        """所有已注册的会话 ID"""
        return list(self._sessions.keys())

    def get(self, session_id: str) -> Session:
        """获取指定会话

        :param session_id: 会话 ID
        :return: 会话实例
        """
        if session_id not in self._sessions:
            available = ", ".join(self._sessions.keys())
            raise KeyError(f"Session '{session_id}' not found. Available: {available}")
        return self._sessions[session_id]

    async def start(self) -> None:
        """启动所有非延迟会话"""
        if self._started:
            return

        for sid, session in self._sessions.items():
            if sid not in self._lazy_sessions and not session._is_alive:
                await session.__aenter__()

        self._started = True

    async def close(self) -> None:
        """关闭所有已注册的会话"""
        for session in self._sessions.values():
            _ = await session.__aexit__(None, None, None)

        self._started = False

    async def fetch(self, request: Request) -> Response:
        """使用指定会话获取请求

        【功能说明】
        根据 request.sid 选择对应的会话，发送请求并返回响应。
        如果是延迟会话且未启动，会先启动再使用。

        :param request: 请求对象
        :return: 响应对象
        """
        sid = request.sid if request.sid else self.default_session_id
        session = self.get(sid)

        if session:
            if sid in self._lazy_sessions and not session._is_alive:
                async with self._lazy_lock:
                    if not session._is_alive:
                        await session.__aenter__()

            if isinstance(session, FetcherSession):
                client = session._client

                if isinstance(client, _ASyncSessionLogic):
                    response = await client._make_request(
                        method=cast(SUPPORTED_HTTP_METHODS, request._session_kwargs.pop("method", "GET")),
                        url=request.url,
                        **request._session_kwargs,
                    )
                else:
                    raise TypeError(f"Session type {type(client)} not supported for async fetch")
            else:
                response = await session.fetch(url=request.url, **request._session_kwargs)

            response.request = request
            response.meta = {**request.meta, **response.meta}
            return response
        raise RuntimeError("No session found with the request session id")

    async def __aenter__(self) -> "SessionManager":
        """异步上下文管理器入口"""
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        """异步上下文管理器出口"""
        await self.close()

    def __contains__(self, session_id: str) -> bool:
        """检查会话 ID 是否已注册"""
        return session_id in self._sessions

    def __len__(self) -> int:
        """已注册的会话数量"""
        return len(self._sessions)
