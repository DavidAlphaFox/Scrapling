"""
================================================================================
Scrapling 调度器模块 (Scheduler Module)
================================================================================

【模块功能】
提供带优先级和 URL 去重的请求队列。
使用 heapq 实现优先级队列，确保高优先级请求先被处理。

【核心类】
- Scheduler: 请求调度器

【主要特性】
1. 优先级队列：高优先级请求先处理
2. URL 去重：自动过滤重复请求
3. 检查点支持：支持保存和恢复状态

【使用场景】
由 CrawlerEngine 内部使用，管理待处理的请求队列。
================================================================================
"""

import asyncio
from itertools import count

from scrapling.core.utils import log
from scrapling.spiders.request import Request
from scrapling.core._types import List, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from scrapling.spiders.checkpoint import CheckpointData


class Scheduler:
    """请求调度器 - 带优先级和去重的请求队列

    【功能说明】
    管理待处理请求的优先级队列，自动过滤重复请求。
    使用 asyncio.PriorityQueue 实现线程安全的优先级队列。

    【去重机制】
    基于请求指纹（fingerprint）去重，相同指纹的请求只保留一个。
    可通过 dont_filter=True 跳过去重。

    【优先级】
    priority 越高越先处理。内部使用负数实现，因为 PriorityQueue 是最小堆。
    """

    def __init__(self, include_kwargs: bool = False, include_headers: bool = False, keep_fragments: bool = False):
        """初始化调度器

        :param include_kwargs: 指纹是否包含会话参数
        :param include_headers: 指纹是否包含请求头
        :param keep_fragments: URL 规范化时是否保留片段
        """
        self._queue: asyncio.PriorityQueue[tuple[int, int, Request]] = asyncio.PriorityQueue()
        self._seen: set[bytes] = set()
        self._counter = count()
        self._pending: dict[int, tuple[int, int, Request]] = {}
        self._include_kwargs = include_kwargs
        self._include_headers = include_headers
        self._keep_fragments = keep_fragments

    async def enqueue(self, request: Request) -> bool:
        """将请求加入队列

        【功能说明】
        计算请求指纹，检查是否重复，然后加入优先级队列。

        :param request: 要加入的请求
        :return: True 表示成功加入，False 表示重复被过滤
        """
        fingerprint = request.update_fingerprint(self._include_kwargs, self._include_headers, self._keep_fragments)

        if not request.dont_filter and fingerprint in self._seen:
            log.debug("Dropped duplicate request: %s", request)
            return False

        self._seen.add(fingerprint)

        counter = next(self._counter)
        item = (-request.priority, counter, request)
        self._pending[counter] = item
        await self._queue.put(item)
        return True

    async def dequeue(self) -> Request:
        """从队列取出下一个请求"""
        _, counter, request = await self._queue.get()
        self._pending.pop(counter, None)
        return request

    def __len__(self) -> int:
        """队列中待处理的请求数量"""
        return self._queue.qsize()

    @property
    def is_empty(self) -> bool:
        """队列是否为空"""
        return self._queue.empty()

    def snapshot(self) -> Tuple[List[Request], Set[bytes]]:
        """创建当前状态的快照（用于检查点）

        :return: (请求列表, 已见指纹集合)
        """
        sorted_items = sorted(self._pending.values(), key=lambda x: (x[0], x[1]))
        requests = [item[2] for item in sorted_items]
        return requests, self._seen.copy()

    def restore(self, data: "CheckpointData") -> None:
        """从检查点数据恢复调度器状态

        :param data: 包含请求和已见集合的检查点数据
        """
        self._seen = data.seen.copy()

        for request in data.requests:
            counter = next(self._counter)
            item = (-request.priority, counter, request)
            self._pending[counter] = item
            self._queue.put_nowait(item)

        log.info(f"Scheduler restored: {len(data.requests)} requests, {len(data.seen)} seen")
