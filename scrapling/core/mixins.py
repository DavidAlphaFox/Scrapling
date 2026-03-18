"""
【模块功能】
选择器生成混入类，用于自动生成CSS和XPath选择器。

【核心类】
- SelectorsGeneration: 选择器生成混入类，为Selector类提供自动生成选择器的能力

【主要特性】
- 自动生成CSS选择器：根据元素在DOM树中的位置生成唯一或完整路径的CSS选择器
- 自动生成XPath选择器：根据元素在DOM树中的位置生成唯一或完整路径的XPath选择器
- 智能路径优化：优先使用ID选择器，避免使用可能不唯一的class选择器

【设计说明】
这是一个混入类（Mixin），设计用于与Selector类多重继承。
通过self访问Selector实例的属性（._root, .parent, .attrib, .tag等）。

【灵感来源】
Firefox开发者工具的选择器生成逻辑
https://searchfox.org/mozilla-central/source/devtools/shared/inspector/css-logic.js#591
"""

from scrapling.core._types import Any, Dict


class SelectorsGeneration:
    """
    【功能说明】
    选择器生成混入类，提供自动生成CSS和XPath选择器的功能。

    该类通过遍历元素的父级链，构建从根元素到当前元素的完整路径选择器。
    生成的选择器可用于在页面中唯一定位该元素。

    【使用方式】
    此类作为混入类使用，与Selector类组合：
    class Selector(SelectorsGeneration, ...):
        pass

    【算法说明】
    1. 从目标元素开始，向上遍历父级链
    2. 如果元素有ID属性，使用ID选择器并停止（ID应该是唯一的）
    3. 否则使用标签名，并计算在同类型兄弟元素中的位置（nth-of-type）
    4. 到达html根元素时停止遍历
    """

    # Note: This is a mixin class meant to be used with Selector.
    # The methods access Selector attributes (._root, .parent, .attrib, .tag, etc.)
    # through self, which will be a Selector instance at runtime.

    def _general_selection(self: Any, selection: str = "css", full_path: bool = False) -> str:
        """【功能说明】生成当前元素的选择器（内部通用方法）

        :param selection: 选择器类型，"css" 或 "xpath"
        :param full_path: 是否生成完整路径（忽略ID优化，遍历到根元素）
        :return: 生成的选择器字符串
        """
        if self._is_text_node(self._root):
            return ""

        selectorPath = []
        target = self
        css = selection.lower() == "css"
        while target is not None:
            if target.parent:
                if target.attrib.get("id"):
                    # id is enough
                    part = f"#{target.attrib['id']}" if css else f"[@id='{target.attrib['id']}']"
                    selectorPath.append(part)
                    if not full_path:
                        return " > ".join(reversed(selectorPath)) if css else "//*" + "/".join(reversed(selectorPath))
                else:
                    part = f"{target.tag}"
                    # We won't use classes anymore because I some websites share exact classes between elements
                    # classes = target.attrib.get('class', '').split()
                    # if classes and css:
                    #     part += f".{'.'.join(classes)}"
                    # else:
                    counter: Dict[str, int] = {}
                    for child in target.parent.children:
                        counter.setdefault(child.tag, 0)
                        counter[child.tag] += 1
                        if child._root == target._root:
                            break

                    if counter[target.tag] > 1:
                        part += f":nth-of-type({counter[target.tag]})" if css else f"[{counter[target.tag]}]"

                selectorPath.append(part)
                target = target.parent
                if target is None or target.tag == "html":
                    return " > ".join(reversed(selectorPath)) if css else "//" + "/".join(reversed(selectorPath))
            else:
                break

        return " > ".join(reversed(selectorPath)) if css else "//" + "/".join(reversed(selectorPath))

    @property
    def generate_css_selector(self: Any) -> str:
        """【功能说明】生成当前元素的CSS选择器

        生成一个能够唯一定位当前元素的CSS选择器。
        如果元素有ID属性，则使用ID选择器；否则使用标签名和位置组合。

        :return: CSS选择器字符串
        """
        return self._general_selection()

    @property
    def generate_full_css_selector(self: Any) -> str:
        """【功能说明】生成当前元素的完整CSS选择器

        生成一个从根元素到当前元素的完整CSS路径选择器。
        即使遇到ID属性也会继续遍历到根元素。

        :return: 完整CSS选择器字符串
        """
        return self._general_selection(full_path=True)

    @property
    def generate_xpath_selector(self: Any) -> str:
        """【功能说明】生成当前元素的XPath选择器

        生成一个能够唯一定位当前元素的XPath选择器。
        如果元素有ID属性，则使用ID属性定位；否则使用标签名和位置组合。

        :return: XPath选择器字符串
        """
        return self._general_selection("xpath")

    @property
    def generate_full_xpath_selector(self: Any) -> str:
        """【功能说明】生成当前元素的完整XPath选择器

        生成一个从根元素到当前元素的完整XPath路径选择器。
        即使遇到ID属性也会继续遍历到根元素。

        :return: 完整XPath选择器字符串
        """
        return self._general_selection("xpath", full_path=True)
