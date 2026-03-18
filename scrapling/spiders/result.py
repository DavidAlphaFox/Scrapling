"""
================================================================================
Scrapling 爬取结果模块 (Crawl Result Module)
================================================================================

【模块功能】
定义爬取结果和统计信息的容器类。

【核心类】
- ItemList: 爬取数据项列表，支持导出功能
- CrawlStats: 爬取统计信息
- CrawlResult: 完整的爬取结果

【主要特性】
1. 数据导出：支持 JSON 和 JSONL 格式
2. 统计收集：记录请求数、响应字节、状态码等
3. 结果封装：统一封装爬取的数据和统计
================================================================================
"""

from pathlib import Path
from dataclasses import dataclass, field

import orjson

from scrapling.core.utils import log
from scrapling.core._types import Any, Iterator, Dict, List, Tuple, Union


class ItemList(list):
    """爬取数据项列表 - 支持导出功能

    【功能说明】
    继承自 Python 内置 list，添加了导出功能。
    用于存储爬取到的数据项（通常是字典）。

    【导出格式】
    - JSON: 标准 JSON 数组格式
    - JSONL: JSON Lines 格式（每行一个 JSON 对象）
    """

    def to_json(self, path: Union[str, Path], *, indent: bool = False):
        """导出为 JSON 文件

        :param path: 输出文件路径
        :param indent: 是否美化输出（2 空格缩进）
        """
        options = orjson.OPT_SERIALIZE_NUMPY
        if indent:
            options |= orjson.OPT_INDENT_2

        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(orjson.dumps(list(self), option=options))
        log.info("Saved %d items to %s", len(self), path)

    def to_jsonl(self, path: Union[str, Path]):
        """导出为 JSON Lines 文件

        【格式说明】
        每行一个 JSON 对象，适合流式处理和大数据场景。

        :param path: 输出文件路径
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            for item in self:
                f.write(orjson.dumps(item, option=orjson.OPT_SERIALIZE_NUMPY))
                f.write(b"\n")
        log.info("Saved %d items to %s", len(self), path)


@dataclass
class CrawlStats:
    """爬取统计信息 - 记录爬取过程中的各项指标

    【主要统计项】
    - 请求统计：请求数、失败数、封锁数
    - 响应统计：响应字节数、状态码分布
    - 数据统计：爬取项数、丢弃项数
    - 时间统计：开始/结束时间、每秒请求数
    - 会话统计：各会话的请求数
    """

    requests_count: int = 0
    concurrent_requests: int = 0
    concurrent_requests_per_domain: int = 0
    failed_requests_count: int = 0
    offsite_requests_count: int = 0
    response_bytes: int = 0
    items_scraped: int = 0
    items_dropped: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    download_delay: float = 0.0
    blocked_requests_count: int = 0
    custom_stats: Dict = field(default_factory=dict)
    response_status_count: Dict = field(default_factory=dict)
    domains_response_bytes: Dict = field(default_factory=dict)
    sessions_requests_count: Dict = field(default_factory=dict)
    proxies: List[str | Dict | Tuple] = field(default_factory=list)
    log_levels_counter: Dict = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        """爬取耗时（秒）"""
        return self.end_time - self.start_time

    @property
    def requests_per_second(self) -> float:
        """每秒请求数"""
        if self.elapsed_seconds == 0:
            return 0.0
        return self.requests_count / self.elapsed_seconds

    def increment_status(self, status: int) -> None:
        """增加状态码计数"""
        self.response_status_count[f"status_{status}"] = self.response_status_count.get(f"status_{status}", 0) + 1

    def increment_response_bytes(self, domain: str, count: int) -> None:
        """增加响应字节数"""
        self.response_bytes += count
        self.domains_response_bytes[domain] = self.domains_response_bytes.get(domain, 0) + count

    def increment_requests_count(self, sid: str) -> None:
        """增加请求计数"""
        self.requests_count += 1
        self.sessions_requests_count[sid] = self.sessions_requests_count.get(sid, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "items_scraped": self.items_scraped,
            "items_dropped": self.items_dropped,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "download_delay": round(self.download_delay, 2),
            "concurrent_requests": self.concurrent_requests,
            "concurrent_requests_per_domain": self.concurrent_requests_per_domain,
            "requests_count": self.requests_count,
            "requests_per_second": round(self.requests_per_second, 2),
            "sessions_requests_count": self.sessions_requests_count,
            "failed_requests_count": self.failed_requests_count,
            "offsite_requests_count": self.offsite_requests_count,
            "blocked_requests_count": self.blocked_requests_count,
            "response_status_count": self.response_status_count,
            "response_bytes": self.response_bytes,
            "domains_response_bytes": self.domains_response_bytes,
            "proxies": self.proxies,
            "custom_stats": self.custom_stats,
            "log_count": self.log_levels_counter,
        }


@dataclass
class CrawlResult:
    """完整爬取结果 - 包含统计信息和数据项

    【功能说明】
    封装爬虫运行的完整结果，包括爬取的数据项和统计信息。
    支持判断爬取是否正常完成。

    【属性】
    - stats: 爬取统计信息
    - items: 爬取的数据项列表
    - paused: 是否被暂停（而非正常完成）
    """

    stats: CrawlStats
    items: ItemList
    paused: bool = False

    @property
    def completed(self) -> bool:
        """是否正常完成（未被暂停）"""
        return not self.paused

    def __len__(self) -> int:
        """数据项数量"""
        return len(self.items)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """迭代数据项"""
        return iter(self.items)
