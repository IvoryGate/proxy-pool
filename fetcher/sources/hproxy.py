"""HProxy 代理源：一个"全球免费代理纯文本"源。

返回纯文本，每一行一个 `ip:port`，量大（2万+）。
这个源的数据国内国外都有，为了配合"国内可用"需求：
默认全收（多多益善）；若要侧重国内，可把 country=CN 让 fetch 只取 by-country/CN.txt。
当前先全收，验证阶段按区域分流。
"""

import httpx

from fetcher.base import BaseFetcher
from fetcher.util import parse_proxies_from_text, yield_unique_proxies


class HProxyFetcher(BaseFetcher):
    name = "hproxy"
    url = "https://cdn.jsdelivr.net/gh/hproxy-com/free-proxy-list@main/all.txt"
    # 实测通过率 ~6%，放开配额
    max_items = 400

    def __init__(self, country="CN"):
        # country="CN" 只取中国（by-country/CN.txt）：这个源的全量列表 2 万+
        # 但可用率极低（~10%），定向 CN 才能出高质量国内代理。
        # country="" 全量（量大低质，慎用）。
        self.country = country

    def fetch(self):
        if self.country:
            api_url = (f"https://cdn.jsdelivr.net/gh/hproxy-com/free-proxy-list"
                       f"@main/by-country/{self.country}.txt")
        else:
            api_url = ("https://cdn.jsdelivr.net/gh/hproxy-com/free-proxy-list"
                       "@main/all.txt")
        try:
            r = httpx.get(api_url, timeout=15)
            text = r.text
        except Exception:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield proxy


if __name__ == "__main__":
    n = 0
    for proxy in HProxyFetcher(country="CN").fetch():
        print(proxy)
        n += 1
        if n >= 10:
            break