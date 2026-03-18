"""
【模块功能】
浏览器配置工具，提供默认User-Agent生成功能。

【核心常量】
- __default_useragent__: 默认Chromium User-Agent
- __default_chrome_useragent__: 默认Chrome User-Agent

【使用场景】
为浏览器会话提供默认的User-Agent字符串，
确保浏览器指纹的一致性。
"""

"""
【模块功能】
浏览器配置工具，提供默认User-Agent生成功能。

【核心常量】
- __default_useragent__: 默认Chromium User-Agent
- __default_chrome_useragent__: 默认Chrome User-Agent

【使用场景】
为浏览器会话提供默认的User-Agent字符串，
确保浏览器指纹的一致性。
"""
"""
【模块功能】
浏览器配置工具，提供默认User-Agent生成功能。

【核心常量】
- __default_useragent__: 默认Chromium User-Agent
- __default_chrome_useragent__: 默认Chrome User-Agent

【使用场景】
为浏览器会话提供默认的User-Agent字符串，
确保浏览器指纹的一致性。
"""
"""
【模块功能】
浏览器配置工具，提供默认User-Agent生成功能。

【核心常量】
- __default_useragent__: 默认Chromium User-Agent
- __default_chrome_useragent__: 默认Chrome User-Agent

【使用场景】
为浏览器会话提供默认的User-Agent字符串，
确保浏览器指纹的一致性。
"""
from scrapling.engines.toolbelt.fingerprints import generate_headers

__default_useragent__ = generate_headers(browser_mode=True).get("User-Agent")
__default_chrome_useragent__ = generate_headers(browser_mode="chrome").get("User-Agent")
