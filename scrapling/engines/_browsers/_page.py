"""
【模块功能】
页面池管理，用于管理浏览器标签页的状态和并发。

【核心类】
- PageInfo: 页面信息数据类，跟踪页面状态和URL
- PagePool: 页面池管理类，管理多个浏览器标签页

【主要特性】
- 状态跟踪：跟踪页面的ready/busy/error状态
- 线程安全：使用RLock保证多线程环境下的安全性
- 容量限制：限制最大页面数量，防止资源耗尽
- 自动清理：支持清理错误状态的页面

【类型定义】
- PageState: 页面状态类型（"ready" | "busy" | "error"）
- PageType: 页面类型变量（SyncPage | AsyncPage）
"""

from threading import RLock
from dataclasses import dataclass

from playwright.sync_api._generated import Page as SyncPage
from playwright.async_api._generated import Page as AsyncPage

from scrapling.core._types import Optional, List, Literal, overload, TypeVar, Generic, cast

PageState = Literal["ready", "busy", "error"]  # States that a page can be in
PageType = TypeVar("PageType", SyncPage, AsyncPage)


@dataclass
class PageInfo(Generic[PageType]):
    """Information about the page and its current state"""

    __slots__ = ("page", "state", "url")
    page: PageType
    state: PageState
    url: Optional[str]

    def mark_busy(self, url: str = ""):
        """Mark the page as busy"""
        self.state = "busy"
        self.url = url

    def mark_error(self):
        """Mark the page as having an error"""
        self.state = "error"

    def __repr__(self):
        return f'Page(URL="{self.url!r}", state={self.state!r})'

    def __eq__(self, other_page):
        """Comparing this page to another page object."""
        if other_page.__class__ is not self.__class__:
            return NotImplemented
        return self.page == other_page.page


class PagePool:
    """Manages a pool of browser pages/tabs with state tracking"""

    __slots__ = ("max_pages", "pages", "_lock")

    def __init__(self, max_pages: int = 5):
        self.max_pages = max_pages
        self.pages: List[PageInfo[SyncPage] | PageInfo[AsyncPage]] = []
        self._lock = RLock()

    @overload
    def add_page(self, page: SyncPage) -> PageInfo[SyncPage]: ...

    @overload
    def add_page(self, page: AsyncPage) -> PageInfo[AsyncPage]: ...

    def add_page(self, page: SyncPage | AsyncPage) -> PageInfo[SyncPage] | PageInfo[AsyncPage]:
        """Add a new page to the pool"""
        with self._lock:
            if len(self.pages) >= self.max_pages:
                raise RuntimeError(f"Maximum page limit ({self.max_pages}) reached")

            if isinstance(page, AsyncPage):
                page_info: PageInfo[SyncPage] | PageInfo[AsyncPage] = cast(
                    PageInfo[AsyncPage], PageInfo(page, "ready", "")
                )
            else:
                page_info = cast(PageInfo[SyncPage], PageInfo(page, "ready", ""))

            self.pages.append(page_info)
            return page_info

    @property
    def pages_count(self) -> int:
        """Get the total number of pages"""
        return len(self.pages)

    @property
    def busy_count(self) -> int:
        """Get the number of busy pages"""
        with self._lock:
            return sum(1 for p in self.pages if p.state == "busy")

    def cleanup_error_pages(self):
        """Remove pages in error state"""
        with self._lock:
            self.pages = [p for p in self.pages if p.state != "error"]
