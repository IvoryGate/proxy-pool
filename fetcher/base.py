"""代理源基类：定义"所有代理源必须具备的统一接口"。

设计思想：
  这个项目将来会有很多个代理源 —— 有的是网站（用爬虫抓 HTML / XPath 抠出 ip:port）、
  有的是开放代理 API（读 JSON）、有的可能是被入侵的开放代理……
  它们的"内部实现"千差万别，但对外都只做一件事：交出 `"host:port"` 字符串。

  所以基类只强制一件事：子类实现 `fetch()`，yield 出 `"host:port"`。
  上层（Fetcher）只需统一调用 fetch()，完全无须关心每个源内部怎么抓的。
"""

import re


class BaseFetcher:
    # ---- 子类必须声明的字段 ----
    name = ""        # 源的唯一标识，如 "geonode"、"zdaye"
    url = ""         # 源网站首页 URL（用于日志/排查）

    # ---- 子类可覆盖 ----
    enabled = True   # 设为 False 可禁用该源

    def fetch(self):
        """爬取本源的代理，yield "host:port" 字符串。子类必须实现。"""
        raise NotImplementedError

    @staticmethod
    def parse_proxies_from_text(text):
        """从一段文本里，用正则抠出所有 "ip:port"。

        这是给"网站源"用的公共工具：很多网站返回纯文本/HTML，
        里面混着代理，直接一个正则就能提出来。
        """
        if not text:
            return []
        pattern = re.compile(
            r'(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?:\s*:\s*|\s+)(\d{2,5})(?!\d)')
        return [f"{ip}:{port}" for ip, port in pattern.findall(text)]

    @staticmethod
    def yield_unique_proxies(proxies):
        """去重后逐个 yield（同一代理被本页抓到多次，只吐一次）。"""
        seen = set()
        for proxy in proxies:
            if proxy not in seen:
                seen.add(proxy)
                yield proxy