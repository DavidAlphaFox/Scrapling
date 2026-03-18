"""
================================================================================
Scrapling 爬虫引擎模块 (Crawler Engine Module)
================================================================================

【模块功能】
爬虫的核心执行引擎，协调调度器、会话管理器和检查点系统，
实现并发爬取、请求处理、断点续爬等功能。

【核心类】
- CrawlerEngine: 爬虫引擎，协调整个爬取过程

【主要职责】
1. 并发控制：管理全局和每域名的并发限制
2. 请求处理：下载页面、执行回调、处理结果
3. 调度协调：与调度器配合管理请求队列
4. 统计收集：记录爬取过程中的各项统计
5. 断点续爬：保存和恢复爬取状态
6. 流式输出：支持实时返回爬取结果

【工作流程】
1. 初始化调度器、会话管理器、统计对象
2. 从检查点恢复或从 start_urls 开始
3. 循环处理调度器中的请求
4. 对每个请求：下载 -> 检测封锁 -> 执行回调
5. 处理回调返回的 Request 或数据项
6. 定期保存检查点
7. 完成后返回统计信息
================================================================================
"""

import json
import pprint
from pathlib import Path

import anyio
from anyio import Path as AsyncPath
from anyio import create_task_group, CapacityLimiter, create_memory_object_stream, EndOfStream

from scrapling.core.utils import log
from scrapling.spiders.request import Request
from scrapling.spiders.scheduler import Scheduler
from scrapling.spiders.session import SessionManager
from scrapling.spiders.result import CrawlStats, ItemList
from scrapling.spiders.checkpoint import CheckpointManager, CheckpointData
from scrapling.core._types import Dict, Union, Optional, TYPE_CHECKING, Any, AsyncGenerator

if TYPE_CHECKING:
    from scrapling.spiders.spider import Spider


def _dump(obj: Dict) -> str:
    """格式化字典为 JSON 字符串"""
    return json.dumps(obj, indent=4)


class CrawlerEngine:
    """爬虫引擎 - 协调整个爬取过程

    【功能说明】
    爬虫的核心执行引擎，负责：
    - 管理请求的下载和处理
    - 协调并发控制
    - 处理封锁检测和重试
    - 管理检查点的保存和恢复
    - 收集爬取统计

    【生命周期】
    1. __init__(): 初始化组件
    2. crawl(): 执行爬取（主入口）
    3. _process_request(): 处理单个请求
    4. _save_checkpoint(): 保存断点
    """

    def __init__(
        self,
        spider: "Spider",
        session_manager: SessionManager,
        crawldir: Optional[Union[str, Path, AsyncPath]] = None,
        interval: float = 300.0,
    ):
        """初始化爬虫引擎

        :param spider: Spider 实例
        :param session_manager: 会话管理器
        :param crawldir: 检查点目录（启用断点续爬）
        :param interval: 定期保存检查点的时间间隔（秒）
        """
        self.spider = spider
        self.session_manager = session_manager
        self.scheduler = Scheduler(
            include_kwargs=spider.fp_include_kwargs,
            include_headers=spider.fp_include_headers,
            keep_fragments=spider.fp_keep_fragments,
        )
        self.stats = CrawlStats()

        self._global_limiter = CapacityLimiter(spider.concurrent_requests)
        self._domain_limiters: dict[str, CapacityLimiter] = {}
        self._allowed_domains: set[str] = spider.allowed_domains or set()

        self._active_tasks: int = 0
        self._running: bool = False
        self._items: ItemList = ItemList()
        self._item_stream: Any = None

        self._checkpoint_system_enabled = bool(crawldir)
        self._checkpoint_manager = CheckpointManager(crawldir or "", interval)
        self._last_checkpoint_time: float = 0.0
        self._pause_requested: bool = False
        self._force_stop: bool = False
        self.paused: bool = False

    def _is_domain_allowed(self, request: Request) -> bool:
        """检查请求的域名是否在允许列表中"""
        if not self._allowed_domains:
            return True

        domain = request.domain
        for allowed in self._allowed_domains:
            if domain == allowed or domain.endswith("." + allowed):
                return True
        return False

    def _rate_limiter(self, domain: str) -> CapacityLimiter:
        """获取或创建域名级别的并发限制器"""
        if self.spider.concurrent_requests_per_domain:
            if domain not in self._domain_limiters:
                self._domain_limiters[domain] = CapacityLimiter(self.spider.concurrent_requests_per_domain)
            return self._domain_limiters[domain]
        return self._global_limiter

    def _normalize_request(self, request: Request) -> None:
        """规范化请求字段，确保会话 ID 一致"""
        if not request.sid:
            request.sid = self.session_manager.default_session_id

    async def _process_request(self, request: Request) -> None:
        """下载并处理单个请求

        【处理流程】
        1. 应用并发限制和下载延迟
        2. 记录代理使用
        3. 发起请求获取响应
        4. 检测是否被封锁
        5. 执行回调处理响应
        6. 处理回调返回的结果
        """
        async with self._rate_limiter(request.domain):
            if self.spider.download_delay:
                await anyio.sleep(self.spider.download_delay)

            if request._session_kwargs.get("proxy"):
                self.stats.proxies.append(request._session_kwargs["proxy"])
            if request._session_kwargs.get("proxies"):
                self.stats.proxies.append(dict(request._session_kwargs["proxies"]))
            try:
                response = await self.session_manager.fetch(request)
                self.stats.increment_requests_count(request.sid or self.session_manager.default_session_id)
                self.stats.increment_response_bytes(request.domain, len(response.body))
                self.stats.increment_status(response.status)

            except Exception as e:
                self.stats.failed_requests_count += 1
                await self.spider.on_error(request, e)
                return

        if await self.spider.is_blocked(response):
            self.stats.blocked_requests_count += 1
            if request._retry_count < self.spider.max_blocked_retries:
                retry_request = request.copy()
                retry_request._retry_count += 1
                retry_request.priority -= 1
                retry_request.dont_filter = True
                retry_request._session_kwargs.pop("proxy", None)
                retry_request._session_kwargs.pop("proxies", None)

                new_request = await self.spider.retry_blocked_request(retry_request, response)
                self._normalize_request(new_request)
                await self.scheduler.enqueue(new_request)
                log.info(
                    f"Scheduled blocked request for retry ({retry_request._retry_count}/{self.spider.max_blocked_retries}): {request.url}"
                )
            else:
                log.warning(f"Max retries exceeded for blocked request: {request.url}")
            return

        callback = request.callback if request.callback else self.spider.parse
        try:
            async for result in callback(response):
                if isinstance(result, Request):
                    if self._is_domain_allowed(result):
                        self._normalize_request(result)
                        await self.scheduler.enqueue(result)
                    else:
                        self.stats.offsite_requests_count += 1
                        log.debug(f"Filtered offsite request to: {result.url}")
                elif isinstance(result, dict):
                    processed_result = await self.spider.on_scraped_item(result)
                    if processed_result:
                        self.stats.items_scraped += 1
                        log.debug(f"Scraped from {str(response)}\n{pprint.pformat(processed_result)}")
                        if self._item_stream:
                            await self._item_stream.send(processed_result)
                        else:
                            self._items.append(processed_result)
                    else:
                        self.stats.items_dropped += 1
                        log.warning(f"Dropped from {str(response)}\n{processed_result}")
                elif result is not None:
                    log.error(f"Spider must return Request, dict or None, got '{type(result)}' in {request}")
        except Exception as e:
            msg = f"Spider error processing {request}:\n {e}"
            log.error(msg, exc_info=e)
            await self.spider.on_error(request, e)

    async def _task_wrapper(self, request: Request) -> None:
        """任务包装器，跟踪活动任务数量"""
        try:
            await self._process_request(request)
        finally:
            self._active_tasks -= 1

    def request_pause(self) -> None:
        """请求优雅暂停

        第一次调用：请求优雅暂停（等待活动任务完成）
        第二次调用：强制立即停止
        """
        if self._force_stop:
            return

        if self._pause_requested:
            self._force_stop = True
            log.warning("Force stop requested, cancelling immediately...")
        else:
            self._pause_requested = True
            log.info(
                "Pause requested, waiting for in-flight requests to complete (press Ctrl+C again to force stop)..."
            )

    async def _save_checkpoint(self) -> None:
        """保存当前状态到检查点文件"""
        requests, seen = self.scheduler.snapshot()
        data = CheckpointData(requests=requests, seen=seen)
        await self._checkpoint_manager.save(data)
        self._last_checkpoint_time = anyio.current_time()

    def _is_checkpoint_time(self) -> bool:
        """检查是否到了定期保存检查点的时间"""
        if not self._checkpoint_system_enabled:
            return False

        if self._checkpoint_manager.interval == 0:
            return False

        current_time = anyio.current_time()
        return (current_time - self._last_checkpoint_time) >= self._checkpoint_manager.interval

    async def _restore_from_checkpoint(self) -> bool:
        """尝试从检查点恢复状态

        :return: 成功恢复返回 True，否则返回 False
        """
        if not self._checkpoint_system_enabled:
            raise

        data = await self._checkpoint_manager.load()
        if data is None:
            return False

        self.scheduler.restore(data)

        for request in data.requests:
            request._restore_callback(self.spider)

        return True

    async def crawl(self) -> CrawlStats:
        """运行爬虫并返回统计信息（主入口方法）

        【执行流程】
        1. 初始化状态和统计
        2. 尝试从检查点恢复（如果启用）
        3. 初始化会话
        4. 处理请求队列直到完成
        5. 清理并返回统计
        """
        self._running = True
        self._items.clear()
        self.paused = False
        self._pause_requested = False
        self._force_stop = False
        self.stats = CrawlStats(start_time=anyio.current_time())

        resuming = (await self._restore_from_checkpoint()) if self._checkpoint_system_enabled else False
        self._last_checkpoint_time = anyio.current_time()

        async with self.session_manager:
            self.stats.concurrent_requests = self.spider.concurrent_requests
            self.stats.concurrent_requests_per_domain = self.spider.concurrent_requests_per_domain
            self.stats.download_delay = self.spider.download_delay
            await self.spider.on_start(resuming=resuming)

            try:
                if not resuming:
                    async for request in self.spider.start_requests():
                        self._normalize_request(request)
                        await self.scheduler.enqueue(request)
                else:
                    log.info("Resuming from checkpoint, skipping start_requests()")

                async with create_task_group() as tg:
                    while self._running:
                        if self._pause_requested:
                            if self._active_tasks == 0 or self._force_stop:
                                if self._force_stop:
                                    log.warning(f"Force stopping with {self._active_tasks} active tasks")
                                    tg.cancel_scope.cancel()

                                if self._checkpoint_system_enabled:
                                    await self._save_checkpoint()
                                    self.paused = True
                                    log.info("Spider paused, checkpoint saved")
                                else:
                                    log.info("Spider stopped gracefully")

                                self._running = False
                                break

                            await anyio.sleep(0.05)
                            continue

                        if self._checkpoint_system_enabled and self._is_checkpoint_time():
                            await self._save_checkpoint()

                        if self.scheduler.is_empty:
                            if self._active_tasks == 0:
                                self._running = False
                                log.debug("Spider idle")
                                break

                            await anyio.sleep(0.05)
                            continue

                        if self._active_tasks >= self.spider.concurrent_requests:
                            await anyio.sleep(0.01)
                            continue

                        request = await self.scheduler.dequeue()
                        self._active_tasks += 1
                        tg.start_soon(self._task_wrapper, request)

            finally:
                await self.spider.on_close()
                if not self.paused and self._checkpoint_system_enabled:
                    await self._checkpoint_manager.cleanup()

        self.stats.log_levels_counter = self.spider._log_counter.get_counts()
        self.stats.end_time = anyio.current_time()
        log.info(_dump(self.stats.to_dict()))
        return self.stats

    @property
    def items(self) -> ItemList:
        """访问已爬取的数据项"""
        return self._items

    def __aiter__(self) -> AsyncGenerator[dict, None]:
        return self._stream()

    async def _stream(self) -> AsyncGenerator[dict, None]:
        """异步生成器，运行爬取并实时返回数据项"""
        send, recv = create_memory_object_stream[dict](100)
        self._item_stream = send

        async def run():
            try:
                await self.crawl()
            finally:
                await send.aclose()

        async with create_task_group() as tg:
            tg.start_soon(run)
            try:
                async for item in recv:
                    yield item
            except EndOfStream:
                pass
