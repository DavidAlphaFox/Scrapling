"""
================================================================================
Scrapling CSS 到 XPath 转换器模块 (CSS to XPath Translator Module)
================================================================================

【模块功能】
将 CSS 选择器转换为 XPath 表达式，支持 Parsel/Scrapy 风格的伪元素。

【核心类】
- XPathExpr: 扩展的 XPath 表达式类
- TranslatorMixin: 转换器混入类，添加伪元素支持
- HTMLTranslator: HTML 转换器，集成混入功能

【支持的伪元素】
- ::text: 选择文本节点
- ::attr(NAME): 选择属性值

【使用示例】
>>> from scrapling.core.translator import css_to_xpath
>>>
>>> css_to_xpath('div.item')
>>> # "descendant-or-self::div[@class and contains(concat(' ', normalize-space(@class), ' '), ' item')]"
>>>
>>> css_to_xpath('div::text')
>>> # "descendant-or-self::div/text()"
>>>
>>> css_to_xpath('a::attr(href)')
>>> # "descendant-or-self::a/@href"

【来源说明】
大部分代码改编自 Parsel 库，添加了伪元素支持以兼容 Scrapy/Parsel 选择器格式。

【参考文档】
https://cssselect.readthedocs.io/en/latest/#cssselect.FunctionalPseudoElement
================================================================================
"""

from functools import lru_cache

from cssselect import HTMLTranslator as OriginalHTMLTranslator
from cssselect.xpath import ExpressionError, XPathExpr as OriginalXPathExpr
from cssselect.parser import Element, FunctionalPseudoElement, PseudoElement

from scrapling.core._types import Any, Protocol, Self


class XPathExpr(OriginalXPathExpr):
    """扩展的 XPath 表达式类

    【功能说明】
    继承自 cssselect 的 XPathExpr，添加：
    - textnode: 是否选择文本节点
    - attribute: 是否选择属性

    【伪元素支持】
    - ::text → textnode=True
    - ::attr(name) → attribute=name
    """

    textnode: bool = False
    attribute: str | None = None

    @classmethod
    def from_xpath(
        cls,
        xpath: OriginalXPathExpr,
        textnode: bool = False,
        attribute: str | None = None,
    ) -> Self:
        """从现有 XPath 表达式创建扩展实例"""
        x = cls(path=xpath.path, element=xpath.element, condition=xpath.condition)
        x.textnode = textnode
        x.attribute = attribute
        return x

    def __str__(self) -> str:
        """转换为 XPath 字符串，附加伪元素处理"""
        path = super().__str__()
        if self.textnode:
            if path == "*":
                path = "text()"
            elif path.endswith("::*/*"):
                path = path[:-3] + "text()"
            else:
                path += "/text()"

        if self.attribute is not None:
            if path.endswith("::*/*"):
                path = path[:-2]
            path += f"/@{self.attribute}"

        return path

    def join(
        self: Self,
        combiner: str,
        other: OriginalXPathExpr,
        *args: Any,
        **kwargs: Any,
    ) -> Self:
        """连接两个 XPath 表达式，继承伪元素属性"""
        if not isinstance(other, XPathExpr):
            raise ValueError(
                f"Expressions of type {__name__}.XPathExpr can ony join expressions"
                f" of the same type (or its descendants), got {type(other)}"
            )
        super().join(combiner, other, *args, **kwargs)
        self.textnode = other.textnode
        self.attribute = other.attribute
        return self


class TranslatorProtocol(Protocol):
    """转换器协议，定义接口"""

    def xpath_element(self, selector: Element) -> OriginalXPathExpr:
        pass

    def css_to_xpath(self, css: str, prefix: str = ...) -> str:
        pass


class TranslatorMixin:
    """转换器混入类 - 添加 CSS 伪元素支持

    【功能说明】
    为 CSS 到 XPath 转换器添加伪元素支持：
    - ::text: 选择元素的文本内容
    - ::attr(ATTR_NAME): 选择元素的属性值

    【设计模式】
    使用混入模式，可以与任何 cssselect 转换器组合使用。
    """

    def xpath_element(self: TranslatorProtocol, selector: Element) -> XPathExpr:
        """处理元素选择器，返回扩展的 XPathExpr"""
        xpath = super().xpath_element(selector)
        return XPathExpr.from_xpath(xpath)

    def xpath_pseudo_element(self, xpath: OriginalXPathExpr, pseudo_element: PseudoElement) -> OriginalXPathExpr:
        """处理伪元素，分发到具体方法"""
        if isinstance(pseudo_element, FunctionalPseudoElement):
            method_name = f"xpath_{pseudo_element.name.replace('-', '_')}_functional_pseudo_element"
            method = getattr(self, method_name, None)
            if not method:
                raise ExpressionError(f"The functional pseudo-element ::{pseudo_element.name}() is unknown")
            xpath = method(xpath, pseudo_element)
        else:
            method_name = f"xpath_{pseudo_element.replace('-', '_')}_simple_pseudo_element"
            method = getattr(self, method_name, None)
            if not method:
                raise ExpressionError(f"The pseudo-element ::{pseudo_element} is unknown")
            xpath = method(xpath)
        return xpath

    @staticmethod
    def xpath_attr_functional_pseudo_element(xpath: OriginalXPathExpr, function: FunctionalPseudoElement) -> XPathExpr:
        """处理 ::attr(NAME) 伪元素 - 选择属性值"""
        if function.argument_types() not in (["STRING"], ["IDENT"]):
            raise ExpressionError(f"Expected a single string or ident for ::attr(), got {function.arguments!r}")
        return XPathExpr.from_xpath(xpath, attribute=function.arguments[0].value)

    @staticmethod
    def xpath_text_simple_pseudo_element(xpath: OriginalXPathExpr) -> XPathExpr:
        """处理 ::text 伪元素 - 选择文本节点"""
        return XPathExpr.from_xpath(xpath, textnode=True)


class HTMLTranslator(TranslatorMixin, OriginalHTMLTranslator):
    """HTML 转换器 - 集成混入功能的完整转换器

    【功能说明】
    继承 TranslatorMixin 和 OriginalHTMLTranslator，
    提供完整的 CSS 到 XPath 转换功能。
    """

    def css_to_xpath(self, css: str, prefix: str = "descendant-or-self::") -> str:
        return super().css_to_xpath(css, prefix)


translator = HTMLTranslator()


@lru_cache(maxsize=256)
def css_to_xpath(query: str) -> str:
    """将 CSS 选择器转换为 XPath 表达式

    【功能说明】
    高性能的 CSS 到 XPath 转换函数，使用 LRU 缓存优化。

    【使用示例】
    >>> css_to_xpath('div.item::text')
    >>> # "descendant-or-self::div[@class and contains(concat(' ', normalize-space(@class), ' '), ' item')]/text()"

    :param query: CSS 选择器字符串
    :return: XPath 表达式字符串
    """
    return translator.css_to_xpath(query)
