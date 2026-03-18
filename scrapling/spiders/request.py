"""
================================================================================
Scrapling 请求对象模块 (Request Object Module)
================================================================================

【模块功能】
定义爬虫框架中的请求对象，用于封装 URL、回调、优先级等信息。

【核心类】
- Request: 请求对象，封装爬取请求的所有信息

【主要特性】
1. 指纹生成：基于 URL、方法、请求体等生成唯一指纹
2. 回调支持：支持自定义回调函数处理响应
3. 优先级：支持请求优先级排序
4. 元数据：通过 meta 字典传递自定义数据
5. 序列化：支持 pickle 序列化（用于检查点）

【使用示例】
>>> from scrapling.spiders import Request
>>>
>>> # 基本请求
>>> request = Request('https://example.com')
>>>
>>> # 带回调和优先级
>>> request = Request(
...     'https://example.com/product',
...     callback=self.parse_product,
...     priority=10,
...     meta={'category': 'electronics'}
... )
================================================================================
"""

import hashlib
from io import BytesIO
from functools import cached_property
from urllib.parse import urlparse, urlencode

import orjson
from w3lib.url import canonicalize_url

from scrapling.engines.toolbelt.custom import Response
from scrapling.core._types import Any, AsyncGenerator, Callable, Dict, Optional, Union, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from scrapling.spiders.spider import Spider


def _convert_to_bytes(value: str | bytes) -> bytes:
    """将字符串或字节转换为字节"""
    if isinstance(value, bytes):
        return value
    if not isinstance(value, str):
        raise TypeError(f"Can't convert {type(value).__name__} to bytes")

    return value.encode(encoding="utf-8", errors="ignore")


class Request:
    """请求对象 - 封装爬取请求的所有信息

    【功能说明】
    表示一个待处理的爬取请求，包含 URL、会话 ID、回调函数、
    优先级、元数据和会话参数等信息。

    【主要属性】
    - url: 请求的 URL
    - sid: 会话 ID（指定使用哪个获取器）
    - callback: 响应处理回调函数
    - priority: 优先级（越高越先处理）
    - dont_filter: 是否跳过去重
    - meta: 自定义元数据字典

    【指纹机制】
    通过 update_fingerprint() 方法生成请求的唯一标识，
    用于去重。指纹基于 URL、方法、请求体等计算。
    """

    def __init__(
        self,
        url: str,
        sid: str = "",
        callback: Callable[[Response], AsyncGenerator[Union[Dict[str, Any], "Request", None], None]] | None = None,
        priority: int = 0,
        dont_filter: bool = False,
        meta: dict[str, Any] | None = None,
        _retry_count: int = 0,
        **kwargs: Any,
    ) -> None:
        """初始化请求对象

        :param url: 请求的 URL
        :param sid: 会话 ID，指定使用哪个获取器会话
        :param callback: 响应处理回调函数，接收 Response，返回生成器
        :param priority: 优先级，数值越高越先处理
        :param dont_filter: True 表示跳过 URL 去重
        :param meta: 自定义元数据，会传递给 Response
        :param _retry_count: 内部使用，重试计数
        :param kwargs: 额外的会话参数（如 headers、proxy、data 等）
        """
        self.url: str = url
        self.sid: str = sid
        self.callback = callback
        self.priority: int = priority
        self.dont_filter: bool = dont_filter
        self.meta: dict[str, Any] = meta if meta else {}
        self._retry_count: int = _retry_count
        self._session_kwargs = kwargs if kwargs else {}
        self._fp: Optional[bytes] = None

    def copy(self) -> "Request":
        """创建请求的副本"""
        return Request(
            url=self.url,
            sid=self.sid,
            callback=self.callback,
            priority=self.priority,
            dont_filter=self.dont_filter,
            meta=self.meta.copy(),
            _retry_count=self._retry_count,
            **self._session_kwargs,
        )

    @cached_property
    def domain(self) -> str:
        """请求的域名"""
        return urlparse(self.url).netloc

    def update_fingerprint(
        self,
        include_kwargs: bool = False,
        include_headers: bool = False,
        keep_fragments: bool = False,
    ) -> bytes:
        """生成请求指纹用于去重

        【功能说明】
        基于 URL、方法、请求体等信息计算 SHA1 哈希作为唯一标识。
        结果会被缓存，后续调用直接返回缓存值。

        :param include_kwargs: 是否包含会话参数
        :param include_headers: 是否包含请求头
        :param keep_fragments: URL 是否保留片段
        :return: 20 字节的指纹
        """
        if self._fp is not None:
            return self._fp

        post_data = self._session_kwargs.get("data", {})
        body = b""
        if post_data:
            if isinstance(post_data, dict | list | tuple):
                body = urlencode(post_data).encode()
            elif isinstance(post_data, str):
                body = post_data.encode()
            elif isinstance(post_data, BytesIO):
                body = post_data.getvalue()
            elif isinstance(post_data, bytes):
                body = post_data
        else:
            post_data = self._session_kwargs.get("json", {})
            body = orjson.dumps(post_data) if post_data else b""

        data: Dict[str, str | Tuple] = {
            "sid": self.sid,
            "body": body.hex(),
            "method": self._session_kwargs.get("method", "GET"),
            "url": canonicalize_url(self.url, keep_fragments=keep_fragments),
        }

        if include_kwargs:
            kwargs = (key.lower() for key in self._session_kwargs.keys() if key.lower() not in ("data", "json"))
            data["kwargs"] = "".join(set(_convert_to_bytes(key).hex() for key in kwargs))

        if include_headers:
            headers = self._session_kwargs.get("headers") or self._session_kwargs.get("extra_headers") or {}
            processed_headers = {}
            for key, value in headers.items():
                processed_headers[_convert_to_bytes(key.lower()).hex()] = _convert_to_bytes(value.lower()).hex()
            data["headers"] = tuple(processed_headers.items())

        fp = hashlib.sha1(orjson.dumps(data, option=orjson.OPT_SORT_KEYS), usedforsecurity=False).digest()
        self._fp = fp
        return fp

    def __repr__(self) -> str:
        callback_name = getattr(self.callback, "__name__", None) or "None"
        return f"<Request({self.url}) priority={self.priority} callback={callback_name}>"

    def __str__(self) -> str:
        return self.url

    def __lt__(self, other: object) -> bool:
        """比较运算符 - 按优先级比较"""
        if not isinstance(other, Request):
            return NotImplemented
        return self.priority < other.priority

    def __gt__(self, other: object) -> bool:
        """比较运算符 - 按优先级比较"""
        if not isinstance(other, Request):
            return NotImplemented
        return self.priority > other.priority

    def __eq__(self, other: object) -> bool:
        """相等比较 - 基于指纹"""
        if not isinstance(other, Request):
            return NotImplemented
        if self._fp is None or other._fp is None:
            raise RuntimeError("Cannot compare requests before generating their fingerprints!")
        return self._fp == other._fp

    def __getstate__(self) -> dict[str, Any]:
        """准备 pickle 状态 - 回调函数转为名称字符串"""
        state = self.__dict__.copy()
        state["_callback_name"] = getattr(self.callback, "__name__", None) if self.callback is not None else None
        state["callback"] = None
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """从 pickle 恢复状态"""
        self._callback_name: str | None = state.pop("_callback_name", None)
        self.__dict__.update(state)

    def _restore_callback(self, spider: "Spider") -> None:
        """从 Spider 恢复回调函数（pickle 后）

        :param spider: Spider 实例，用于查找回调方法
        """
        if hasattr(self, "_callback_name") and self._callback_name:
            self.callback = getattr(spider, self._callback_name, None) or spider.parse
            del self._callback_name
        elif hasattr(self, "_callback_name"):
            del self._callback_name
