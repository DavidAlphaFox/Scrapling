"""
================================================================================
Scrapling 自定义类型模块 (Custom Types Module)
================================================================================

【模块功能】
提供增强的字符串和属性处理类型，扩展 Python 内置类型的功能。

【核心类】
- TextHandler: 增强的字符串类，支持正则、JSON、清理等操作
- TextHandlers: TextHandler 的列表容器
- AttributesHandler: 增强的属性字典，支持搜索和 JSON 序列化

【主要特性】
1. 正则支持: re(), re_first() 方法支持正则匹配
2. 文本清理: clean() 方法移除空白和连续空格
3. JSON 解析: json() 方法解析 JSON 字符串
4. 属性搜索: search_values() 方法按值搜索属性
5. 兼容 Scrapy: extract, extract_first 等别名方法

【使用示例】
>>> from scrapling.core.custom_types import TextHandler, AttributesHandler
>>>
>>> text = TextHandler("  Hello  World  ")
>>> text.clean()  # "Hello World"
>>> text.re(r'\w+')  # ['Hello', 'World']
>>>
>>> attrs = AttributesHandler({'class': 'item', 'id': 'product-1'})
>>> attrs.search_values('product')  # 搜索包含 'product' 的属性
================================================================================
"""

from collections.abc import Mapping
from types import MappingProxyType
from re import compile as re_compile, UNICODE, IGNORECASE

from orjson import dumps, loads
from w3lib.html import replace_entities as _replace_entities

from scrapling.core._types import (
    Any,
    cast,
    Dict,
    List,
    Union,
    overload,
    TypeVar,
    Literal,
    Pattern,
    Iterable,
    Generator,
    SupportsIndex,
)
from scrapling.core.utils import _is_iterable, flatten, __CONSECUTIVE_SPACES_REGEX__

_TextHandlerType = TypeVar("_TextHandlerType", bound="TextHandler")
__CLEANING_TABLE__ = str.maketrans("\t\r\n", "   ")


class TextHandler(str):
    """增强的字符串类 - 扩展 Python 内置 str 类

    【功能说明】
    继承自 str，提供额外的文本处理功能，包括：
    - 正则匹配
    - 文本清理
    - JSON 解析
    - 兼容 Scrapy/Parsel 的方法别名

    【设计考虑】
    所有字符串操作方法都返回 TextHandler 而非 str，
    支持链式调用。
    """

    __slots__ = ()

    def __getitem__(self, key: SupportsIndex | slice) -> "TextHandler":
        lst = super().__getitem__(key)
        return TextHandler(lst)

    def split(self, sep: str | None = None, maxsplit: SupportsIndex = -1) -> list[Any]:
        return TextHandlers([TextHandler(s) for s in super().split(sep, maxsplit)])

    def strip(self, chars: str | None = None) -> Union[str, "TextHandler"]:
        return TextHandler(super().strip(chars))

    def lstrip(self, chars: str | None = None) -> Union[str, "TextHandler"]:
        return TextHandler(super().lstrip(chars))

    def rstrip(self, chars: str | None = None) -> Union[str, "TextHandler"]:
        return TextHandler(super().rstrip(chars))

    def capitalize(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().capitalize())

    def casefold(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().casefold())

    def center(self, width: SupportsIndex, fillchar: str = " ") -> Union[str, "TextHandler"]:
        return TextHandler(super().center(width, fillchar))

    def expandtabs(self, tabsize: SupportsIndex = 8) -> Union[str, "TextHandler"]:
        return TextHandler(super().expandtabs(tabsize))

    def format(self, *args: object, **kwargs: object) -> Union[str, "TextHandler"]:
        return TextHandler(super().format(*args, **kwargs))

    def format_map(self, mapping) -> Union[str, "TextHandler"]:
        return TextHandler(super().format_map(mapping))

    def join(self, iterable: Iterable[str]) -> Union[str, "TextHandler"]:
        return TextHandler(super().join(iterable))

    def ljust(self, width: SupportsIndex, fillchar: str = " ") -> Union[str, "TextHandler"]:
        return TextHandler(super().ljust(width, fillchar))

    def rjust(self, width: SupportsIndex, fillchar: str = " ") -> Union[str, "TextHandler"]:
        return TextHandler(super().rjust(width, fillchar))

    def swapcase(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().swapcase())

    def title(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().title())

    def translate(self, table) -> Union[str, "TextHandler"]:
        return TextHandler(super().translate(table))

    def zfill(self, width: SupportsIndex) -> Union[str, "TextHandler"]:
        return TextHandler(super().zfill(width))

    def replace(self, old: str, new: str, count: SupportsIndex = -1) -> Union[str, "TextHandler"]:
        return TextHandler(super().replace(old, new, count))

    def upper(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().upper())

    def lower(self) -> Union[str, "TextHandler"]:
        return TextHandler(super().lower())

    def sort(self, reverse: bool = False) -> Union[str, "TextHandler"]:
        """返回排序后的字符串"""
        return self.__class__("".join(sorted(self, reverse=reverse)))

    def clean(self, remove_entities=False) -> Union[str, "TextHandler"]:
        """清理文本 - 移除空白和连续空格

        【功能说明】
        将制表符、回车、换行替换为空格，然后移除连续空格。

        :param remove_entities: 是否同时替换 HTML 实体
        :return: 清理后的 TextHandler
        """
        data = self.translate(__CLEANING_TABLE__)
        if remove_entities:
            data = _replace_entities(data)
        return self.__class__(__CONSECUTIVE_SPACES_REGEX__.sub(" ", data).strip())

    def get(self, default=None):
        """兼容 Scrapy/Parsel - 返回自身"""
        return self

    def get_all(self):
        """兼容 Scrapy/Parsel - 返回自身"""
        return self

    extract = get_all
    extract_first = get

    def json(self) -> Dict:
        """解析 JSON 字符串

        【功能说明】
        将字符串解析为 Python 字典。
        使用 orjson 提供高性能解析。

        :return: 解析后的字典
        """
        return loads(str(self))

    def re(
        self,
        regex: str | Pattern,
        replace_entities: bool = True,
        clean_match: bool = False,
        case_sensitive: bool = True,
        check_match: bool = False,
    ) -> Union["TextHandlers", bool]:
        """正则匹配

        【功能说明】
        应用正则表达式并返回匹配结果列表。

        :param regex: 正则表达式字符串或编译后的 Pattern
        :param replace_entities: 是否替换 HTML 实体
        :param clean_match: 是否先清理文本再匹配
        :param case_sensitive: 是否区分大小写
        :param check_match: True 时只返回是否匹配（布尔值）

        :return: TextHandlers 列表或布尔值
        """
        if isinstance(regex, str):
            if case_sensitive:
                regex = re_compile(regex, UNICODE)
            else:
                regex = re_compile(regex, flags=UNICODE | IGNORECASE)

        input_text = self.clean() if clean_match else self
        results = regex.findall(input_text)
        if check_match:
            return bool(results)

        if all(_is_iterable(res) for res in results):
            results = flatten(results)

        if not replace_entities:
            return TextHandlers([TextHandler(string) for string in results])

        return TextHandlers([TextHandler(_replace_entities(s)) for s in results])

    def re_first(
        self,
        regex: str | Pattern,
        default: Any = None,
        replace_entities: bool = True,
        clean_match: bool = False,
        case_sensitive: bool = True,
    ) -> "TextHandler":
        """返回正则匹配的第一个结果

        【功能说明】
        应用正则表达式，返回第一个匹配结果，无匹配则返回默认值。

        :param regex: 正则表达式
        :param default: 无匹配时的默认返回值
        :param replace_entities: 是否替换 HTML 实体
        :param clean_match: 是否先清理文本再匹配
        :param case_sensitive: 是否区分大小写

        :return: 第一个匹配结果或默认值
        """
        result = self.re(
            regex,
            replace_entities,
            clean_match=clean_match,
            case_sensitive=case_sensitive,
        )
        return result[0] if result else default


class TextHandlers(List[TextHandler]):
    """TextHandler 列表容器 - 扩展 Python 内置 List 类

    【功能说明】
    用于存储多个 TextHandler 对象的容器，支持：
    - 批量正则匹配
    - 链式操作
    - 兼容 Scrapy/Parsel 的方法
    """

    __slots__ = ()

    @overload
    def __getitem__(self, pos: SupportsIndex) -> TextHandler: ...

    @overload
    def __getitem__(self, pos: slice) -> "TextHandlers": ...

    def __getitem__(self, pos: SupportsIndex | slice) -> Union[TextHandler, "TextHandlers"]:
        lst = super().__getitem__(pos)
        if isinstance(pos, slice):
            return TextHandlers(cast(List[TextHandler], lst))
        return TextHandler(cast(TextHandler, lst))

    def re(
        self,
        regex: str | Pattern,
        replace_entities: bool = True,
        clean_match: bool = False,
        case_sensitive: bool = True,
    ) -> "TextHandlers":
        """对列表中每个元素执行正则匹配，合并结果"""
        results = [n.re(regex, replace_entities, clean_match, case_sensitive) for n in self]
        return TextHandlers(flatten(results))

    def re_first(
        self,
        regex: str | Pattern,
        default: Any = None,
        replace_entities: bool = True,
        clean_match: bool = False,
        case_sensitive: bool = True,
    ) -> TextHandler:
        """返回第一个正则匹配结果"""
        for n in self:
            for result in n.re(regex, replace_entities, clean_match, case_sensitive):
                return result
        return default

    def get(self, default=None):
        """返回第一个元素或默认值"""
        return self[0] if len(self) > 0 else default

    def extract(self):
        return self

    extract_first = get
    get_all = extract


class AttributesHandler(Mapping[str, _TextHandlerType]):
    """属性处理器 - 只读映射，增强属性字典功能

    【功能说明】
    用于处理 HTML 元素属性，提供：
    - 只读映射（基于 MappingProxyType）
    - 按值搜索属性
    - JSON 序列化

    【设计考虑】
    使用 MappingProxyType 实现只读，提升读取性能。
    所有字符串值自动转换为 TextHandler。
    """

    __slots__ = ("_data",)

    def __init__(self, mapping: Any = None, **kwargs: Any) -> None:
        """初始化属性处理器

        :param mapping: 初始属性字典
        :param kwargs: 额外的键值对
        """
        mapping = (
            {key: TextHandler(value) if isinstance(value, str) else value for key, value in mapping.items()}
            if mapping is not None
            else {}
        )

        if kwargs:
            mapping.update(
                {key: TextHandler(value) if isinstance(value, str) else value for key, value in kwargs.items()}
            )

        self._data: Mapping[str, Any] = MappingProxyType(mapping)

    def get(self, key: str, default: Any = None) -> _TextHandlerType:
        """获取属性值，不存在则返回默认值"""
        return self._data.get(key, default)

    def search_values(self, keyword: str, partial: bool = False) -> Generator["AttributesHandler", None, None]:
        """按值搜索属性

        【功能说明】
        遍历所有属性，返回值匹配的属性。

        :param keyword: 搜索关键词
        :param partial: True 为部分匹配，False 为完全匹配

        :return: 生成器，产生匹配的单属性 AttributesHandler
        """
        for key, value in self._data.items():
            if partial:
                if keyword in value:
                    yield AttributesHandler({key: value})
            else:
                if keyword == value:
                    yield AttributesHandler({key: value})

    @property
    def json_string(self) -> bytes:
        """转换为 JSON 字节"""
        return dumps(dict(self._data))

    def __getitem__(self, key: str) -> _TextHandlerType:
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._data})"

    def __str__(self):
        return str(self._data)

    def __contains__(self, key):
        return key in self._data
