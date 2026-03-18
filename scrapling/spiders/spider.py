"""
================================================================================
Scrapling Spider 爬虫基类模块 (Spider Base Class Module)
================================================================================

【模块功能】
提供类似 Scrapy 的爬虫框架基类，支持并发爬取、多会话、暂停/恢复等功能。

【核心类】
- Spider: 爬虫抽象基类，用户继承此类定义自己的爬虫
- SessionConfigurationError: 会话配置错误异常
- LogCounterHandler: 日志计数处理器

【主要特性】
1. Scrapy-like API: 熟悉的 start_urls + parse 模式
2. 并发控制: 可配置的并发请求数和每域名并发限制
3. 多会话支持: 在同一爬虫中使用不同类型的获取器
4. 断点续爬: 通过 crawldir 启用检查点，支持暂停/恢复
5. 流式输出: 通过 stream() 方法实时获取爬取结果

【使用示例】
>>> from scrapling.spiders import Spider, Request, Response
>>>
>>> class MySpider(Spider):
...     name = "my_spider"
...     start_urls = ["https://example.com/"]
...     concurrent_requests = 10
...
...     async def parse(self, response: Response):
...         for item in response.css('.product'):
...             yield {"title": item.css('h2::text').get()}
...
...         next_page = response.css('.next a::attr(href)').get()
...         if next_page:
...             yield response.follow(next_page)
>>>
>>> result = MySpider().start()
>>> print(f"Scraped {len(result.items)} items")

【生命周期方法】
- start_requests(): 生成初始请求
- parse(response): 处理响应（必须实现）
- on_start(resuming): 爬取开始前调用
- on_close(): 爬取结束后调用
- on_error(request, error): 请求出错时调用
- on_scraped_item(item): 处理爬取的数据项
- is_blocked(response): 判断是否被封锁
================================================================================
"""

import signal
import logging
from pathlib import Path
from abc import ABC, abstractmethod

import anyio
from anyio import Path as AsyncPath

from scrapling.spiders.request import Request
from scrapling.spiders.engine import CrawlerEngine
from scrapling.spiders.session import SessionManager
from scrapling.core.utils import set_logger, reset_logger
from scrapling.spiders.result import CrawlResult, CrawlStats
from scrapling.core._types import Set, Any, Dict, Optional, Union, TYPE_CHECKING, AsyncGenerator

BLOCKED_CODES = {401, 403, 407, 429, 444, 500, 502, 503, 504}
if TYPE_CHECKING:
    from scrapling.engines.toolbelt.custom import Response


class LogCounterHandler(logging.Handler):
    """日志计数处理器 - 统计各级别日志消息数量

    【功能说明】
    继承自 logging.Handler，用于统计爬虫运行过程中
    产生的各级别日志消息数量，最终汇入爬取统计。

    【统计的日志级别】
    - DEBUG: 调试信息
    - INFO: 一般信息
    - WARNING: 警告信息
    - ERROR: 错误信息
    - CRITICAL: 严重错误
    """

    def __init__(self):
        super().__init__()
        self.counts = {
            logging.DEBUG: 0,
            logging.INFO: 0,
            logging.WARNING: 0,
            logging.ERROR: 0,
            logging.CRITICAL: 0,
        }

    def emit(self, record: logging.LogRecord) -> None:
        """处理日志记录，增加对应级别的计数"""
        level = record.levelno
        if level >= logging.CRITICAL:
            self.counts[logging.CRITICAL] += 1
        elif level >= logging.ERROR:
            self.counts[logging.ERROR] += 1
        elif level >= logging.WARNING:
            self.counts[logging.WARNING] += 1
        elif level >= logging.INFO:
            self.counts[logging.INFO] += 1
        else:
            self.counts[logging.DEBUG] += 1

    def get_counts(self) -> Dict[str, int]:
        """返回字符串键的计数字典"""
        return {
            "debug": self.counts[logging.DEBUG],
            "info": self.counts[logging.INFO],
            "warning": self.counts[logging.WARNING],
            "error": self.counts[logging.ERROR],
            "critical": self.counts[logging.CRITICAL],
        }


class SessionConfigurationError(Exception):
    """会话配置错误异常

    当 configure_sessions() 方法配置失败时抛出。
    """

    pass


class Spider(ABC):
    """爬虫抽象基类 - 所有爬虫必须继承此类

    【功能说明】
    提供完整的爬虫框架，包括请求调度、并发控制、
    会话管理、断点续爬等功能。

    【必须实现】
    - name: 爬虫名称
    - parse(response): 响应处理方法

    【可选重写】
    - start_requests(): 自定义初始请求
    - configure_sessions(): 配置多个会话
    - on_start(): 爬取开始钩子
    - on_close(): 爬取结束钩子
    - on_error(): 错误处理钩子
    - is_blocked(): 封锁检测
    - retry_blocked_request(): 重试准备

    【类属性】
    - name: 爬虫名称（必须设置）
    - start_urls: 起始 URL 列表
    - allowed_domains: 允许的域名集合
    - concurrent_requests: 全局并发请求数
    - concurrent_requests_per_domain: 每域名并发数
    - download_delay: 下载延迟（秒）
    - max_blocked_retries: 被封锁后的最大重试次数
    """

    name: Optional[str] = None
    start_urls: list[str] = []
    allowed_domains: Set[str] = set()

    concurrent_requests: int = 4
    concurrent_requests_per_domain: int = 0
    download_delay: float = 0.0
    max_blocked_retries: int = 3

    fp_include_kwargs: bool = False
    fp_keep_fragments: bool = False
    fp_include_headers: bool = False

    logging_level: int = logging.DEBUG
    logging_format: str = "[%(asctime)s]:({spider_name}) %(levelname)s: %(message)s"
    logging_date_format: str = "%Y-%m-%d %H:%M:%S"
    log_file: Optional[str] = None

    def __init__(self, crawldir: Optional[Union[str, Path, AsyncPath]] = None, interval: float = 300.0):
        """初始化爬虫

        :param crawldir: 检查点目录路径，设置后启用断点续爬功能
        :param interval: 定期保存检查点的时间间隔（秒），默认 5 分钟
        """
        if self.name is None:
            raise ValueError(f"{self.__class__.__name__} must have a name.")

        self.logger = logging.getLogger(f"scrapling.spiders.{self.name}")
        self.logger.setLevel(self.logging_level)
        self.logger.handlers.clear()
        self.logger.propagate = False

        formatter = logging.Formatter(
            fmt=self.logging_format.format(spider_name=self.name), datefmt=self.logging_date_format
        )

        self._log_counter = LogCounterHandler()
        self.logger.addHandler(self._log_counter)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        if self.log_file:
            Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        self.crawldir: Optional[Path] = Path(crawldir) if crawldir else None
        self._interval = interval
        self._engine: Optional[CrawlerEngine] = None
        self._original_sigint_handler: Any = None

        self._session_manager = SessionManager()

        try:
            self.configure_sessions(self._session_manager)
        except Exception as e:
            raise SessionConfigurationError(f"Error in {self.__class__.__name__}.configure_sessions(): {e}") from e

        if len(self._session_manager) == 0:
            raise SessionConfigurationError(f"{self.__class__.__name__}.configure_sessions() did not add any sessions")

        self.logger.info("Spider initialized")

    async def start_requests(self) -> AsyncGenerator[Request, None]:
        """生成初始请求

        【功能说明】
        默认为 start_urls 中的每个 URL 创建一个 Request 对象，
        使用默认会话和 parse() 作为回调。

        【重写场景】
        - 需要添加自定义请求头
        - 需要使用不同的回调函数
        - 需要动态生成起始 URL
        """
        if not self.start_urls:
            raise RuntimeError(
                "Spider has no starting point, either set `start_urls` or override `start_requests` function."
            )

        for url in self.start_urls:
            yield Request(url, sid=self._session_manager.default_session_id)

    @abstractmethod
    async def parse(self, response: "Response") -> AsyncGenerator[Dict[str, Any] | Request | None, None]:
        """处理响应的回调方法（必须实现）

        【功能说明】
        处理每个响应，可以 yield：
        - dict: 爬取的数据项
        - Request: 新的请求
        - None: 不产生任何结果

        :param response: 响应对象，包含页面内容和选择器
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement parse() method")
        yield

    async def on_start(self, resuming: bool = False) -> None:
        """爬取开始前的钩子方法

        :param resuming: True 表示从检查点恢复，False 表示全新开始
        """
        if resuming:
            self.logger.debug("Resuming spider from checkpoint")
        else:
            self.logger.debug("Starting spider")

    async def on_close(self) -> None:
        """爬取结束后的钩子方法，用于清理资源"""
        self.logger.debug("Spider closed")

    async def on_error(self, request: Request, error: Exception) -> None:
        """请求出错时的钩子方法

        :param request: 出错的请求对象
        :param error: 捕获的异常
        """
        pass

    async def on_scraped_item(self, item: Dict[str, Any]) -> Dict[str, Any] | None:
        """处理爬取数据项的钩子方法

        【功能说明】
        对每个爬取的数据项进行后处理。
        返回 None 可以静默丢弃该数据项。

        :param item: 爬取的数据字典
        :return: 处理后的数据字典，或 None 丢弃
        """
        return item

    async def is_blocked(self, response: "Response") -> bool:
        """判断响应是否被封锁

        【功能说明】
        默认通过 HTTP 状态码判断（401, 403, 407, 429, 444, 500, 502, 503, 504）。
        可重写以实现自定义检测逻辑。

        :param response: 响应对象
        :return: True 表示被封锁
        """
        if response.status in BLOCKED_CODES:
            return True
        return False

    async def retry_blocked_request(self, request: Request, response: "Response") -> Request:
        """准备被封锁请求的重试

        【功能说明】
        在请求被判定为封锁后、重新入队前调用。
        可重写以修改请求（如切换代理）。

        :param request: 原请求对象
        :param response: 被封锁的响应
        :return: 修改后的请求对象
        """
        return request

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} '{self.name}'>"

    def configure_sessions(self, manager: SessionManager) -> None:
        """配置会话管理器

        【功能说明】
        默认创建一个 FetcherSession 会话。
        可重写以添加多个不同类型的会话。

        【使用示例】
        >>> def configure_sessions(self, manager):
        ...     manager.add("fast", FetcherSession(impersonate="chrome"))
        ...     manager.add("stealth", StealthySession(headless=True), lazy=True)

        :param manager: 会话管理器实例
        """
        from scrapling.fetchers import FetcherSession

        manager.add("default", FetcherSession())

    def pause(self):
        """请求暂停爬取"""
        if self._engine:
            self._engine.request_pause()
        else:
            raise RuntimeError("No active crawl to stop")

    def _setup_signal_handler(self) -> None:
        """设置 SIGINT 信号处理器，支持 Ctrl+C 优雅暂停"""

        def handler(_signum: int, _frame: Any) -> None:
            if self._engine:
                self._engine.request_pause()
            else:
                raise KeyboardInterrupt

        try:
            self._original_sigint_handler = signal.signal(signal.SIGINT, handler)
        except ValueError:
            self._original_sigint_handler = None

    def _restore_signal_handler(self) -> None:
        """恢复原始 SIGINT 信号处理器"""
        if self._original_sigint_handler is not None:
            try:
                signal.signal(signal.SIGINT, self._original_sigint_handler)
            except ValueError:
                pass

    async def __run(self) -> CrawlResult:
        """内部运行方法"""
        token = set_logger(self.logger)
        try:
            self._engine = CrawlerEngine(self, self._session_manager, self.crawldir, self._interval)
            stats = await self._engine.crawl()
            paused = self._engine.paused
            return CrawlResult(stats=stats, items=self._engine.items, paused=paused)
        finally:
            self._engine = None
            reset_logger(token)
            if self.log_file:
                for handler in self.logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.close()

    def start(self, use_uvloop: bool = False, **backend_options: Any) -> CrawlResult:
        """启动爬虫（主入口方法）

        【功能说明】
        运行爬虫并返回结果。内部处理异步执行。

        【交互控制】
        - 第一次 Ctrl+C: 优雅暂停（等待活动任务完成）
        - 第二次 Ctrl+C: 强制停止

        【断点续爬】
        如果设置了 crawldir，优雅暂停时会保存检查点，
        再次运行时自动从断点恢复。

        :param use_uvloop: 是否使用更快的 uvloop 事件循环
        :param backend_options: 传递给 anyio.run 的后端选项
        :return: CrawlResult 对象，包含爬取结果和统计信息
        """
        backend_options = backend_options or {}
        if use_uvloop:
            backend_options.update({"use_uvloop": True})

        self._setup_signal_handler()
        try:
            return anyio.run(self.__run, backend="asyncio", backend_options=backend_options)
        finally:
            self._restore_signal_handler()

    async def stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """流式获取爬取结果

        【功能说明】
        以异步生成器形式实时返回爬取的数据项。
        适用于长时间运行的爬虫或构建上层应用。

        【使用示例】
        >>> async for item in spider.stream():
        ...     print(item)
        ...     print(spider.stats)  # 实时统计

        【注意】
        流式模式下不支持 SIGINT 暂停/恢复。
        """
        token = set_logger(self.logger)
        try:
            self._engine = CrawlerEngine(self, self._session_manager, self.crawldir, self._interval)
            async for item in self._engine:
                yield item
        finally:
            self._engine = None
            reset_logger(token)
            if self.log_file:
                for handler in self.logger.handlers:
                    if isinstance(handler, logging.FileHandler):
                        handler.close()

    @property
    def stats(self) -> CrawlStats:
        """访问当前爬取统计（在 stream() 循环中使用）"""
        if self._engine:
            return self._engine.stats
        raise RuntimeError("No active crawl. Use this property inside `async for item in spider.stream():`")
