"""
================================================================================
Scrapling 存储系统模块 (Storage System Module)
================================================================================

【模块功能】
提供元素特征存储功能，用于自适应元素追踪。
当网站结构变化时，通过存储的元素特征重新定位元素。

【核心类】
- StorageSystemMixin: 存储系统抽象基类
- SQLiteStorageSystem: 基于 SQLite 的存储实现（推荐）
- _StorageTools: 存储工具类

【主要特性】
1. 元素特征存储：保存元素的标签、属性、文本、路径等特征
2. 线程安全：使用锁保护并发访问
3. URL 隔离：不同 URL 的数据相互隔离
4. 标识符哈希：安全的标识符处理

【使用场景】
与 Selector 类的 adaptive 功能配合使用：
1. 首次爬取时保存元素特征 (auto_save=True)
2. 网站改版后使用 adaptive=True 重新定位

【使用示例】
>>> from scrapling.parser import Selector
>>>
>>> page = Selector(html, url='https://example.com', adaptive=True)
>>>
>>> # 首次保存元素
>>> items = page.css('.product', auto_save=True)
>>>
>>> # 之后网站改版，使用 adaptive 重定位
>>> items = page.css('.product', adaptive=True)
================================================================================
"""

from hashlib import sha256
from threading import RLock
from functools import lru_cache
from abc import ABC, abstractmethod
from sqlite3 import connect as db_connect

from orjson import dumps, loads
from lxml.html import HtmlElement

from scrapling.core.utils import _StorageTools, log
from scrapling.core._types import Dict, Optional, Any, cast


class StorageSystemMixin(ABC):
    """存储系统抽象基类

    【功能说明】
    定义存储系统的接口，用户可继承此类实现自定义存储。

    【必须实现的方法】
    - save(element, identifier): 保存元素特征
    - retrieve(identifier): 检索元素特征

    【注意】
    存储类必须使用 @lru_cache 装饰器包装。
    """

    @lru_cache(64, typed=True)
    def _get_base_url(self, default_value: str = "default") -> str:
        """获取基础 URL，用于数据隔离"""
        if not self.url:
            return default_value

        try:
            from tld import get_tld, Result

            extracted: Result | None = cast(Result, get_tld(self.url, as_object=True, fix_protocol=True))
            return extracted.fld if extracted else default_value
        except Exception:
            return default_value

    @staticmethod
    def hash_identifier(identifier: str) -> str:
        """安全地哈希标识符

        【功能说明】
        对标识符进行 SHA256 哈希，减少冲突概率。

        :param identifier: 原始标识符
        :return: 哈希后的标识符（格式：hash_length）
        """
        _identifier = identifier.lower().strip()
        _identifier_bytes = _identifier.encode("utf-8")

        hash_value = sha256(_identifier_bytes).hexdigest()
        return f"{hash_value}_{len(_identifier_bytes)}"


@lru_cache(1, typed=True)
class SQLiteStorageSystem(StorageSystemMixin):
    """SQLite 存储系统 - 推荐的存储实现

    【功能说明】
    基于 SQLite 的元素特征存储，线程安全，支持并发。
    使用 WAL 模式提升并发性能。

    【数据库结构】
    - storage 表：
      - id: 主键
      - url: 基础 URL（用于数据隔离）
      - identifier: 元素标识符
      - element_data: 元素特征 JSON

    【线程安全】
    使用 RLock 保护所有数据库操作，可在多线程环境使用。
    """

    def __init__(self, storage_file: str, url: Optional[str] = None):
        """初始化 SQLite 存储系统

        :param storage_file: SQLite 数据库文件路径
        :param url: 关联的 URL（用于数据隔离）
        """
        self.url = url
        self.storage_file = storage_file
        self.lock = RLock()
        self.connection = db_connect(self.storage_file, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.cursor = self.connection.cursor()
        self._setup_database()
        log.debug(f'Storage system loaded with arguments (storage_file="{storage_file}", url="{url}")')

    def _setup_database(self) -> None:
        """创建数据库表结构"""
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS storage (
                id INTEGER PRIMARY KEY,
                url TEXT,
                identifier TEXT,
                element_data BLOB,
                UNIQUE(url, identifier)
            )
        """)
        self.connection.commit()

    def save(self, element: HtmlElement, identifier: str) -> None:
        """保存元素特征到存储

        【功能说明】
        提取元素的特征（标签、属性、文本、路径等）并保存。
        如果相同 URL 和标识符已存在，则更新。

        :param element: 要保存的 lxml 元素
        :param identifier: 元素标识符（通常为选择器字符串）
        """
        url = self._get_base_url()
        element_data = _StorageTools.element_to_dict(element)
        with self.lock:
            self.cursor.execute(
                """
                INSERT OR REPLACE INTO storage (url, identifier, element_data)
                VALUES (?, ?, ?)
                """,
                (url, identifier, dumps(element_data)),
            )
            self.connection.commit()

    def retrieve(self, identifier: str) -> Optional[Dict[str, Any]]:
        """从存储检索元素特征

        【功能说明】
        根据标识符检索之前保存的元素特征。

        :param identifier: 元素标识符
        :return: 元素特征字典，不存在则返回 None
        """
        url = self._get_base_url()
        with self.lock:
            self.cursor.execute(
                "SELECT element_data FROM storage WHERE url = ? AND identifier = ?",
                (url, identifier),
            )
            result = self.cursor.fetchone()
            if result:
                return loads(result[0])
            return None

    def close(self):
        """关闭所有数据库连接"""
        with self.lock:
            self.connection.commit()
            self.cursor.close()
            self.connection.close()

    def __del__(self):
        """对象销毁时确保连接关闭"""
        self.close()
