"""Bes-js/public-proxy-list 代理源：持续维护的聚合列表。

GitHub raw 托管的纯 `ip:port` 文本（proxies.txt 2013 条），实测通过率
~9%。每日持续更新的免费公共源。

走 jsdelivr 双通道兜底。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class BesjsFetcher(BaseFetcher):
    name = "besjs"
    url = "https://github.com/Bes-js/public-proxy-list"
    # 2013 候选，~9% 通过率，全量抓取
    max_items = None

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/Bes-js/"
                   "public-proxy-list/main/proxies.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in BesjsFetcher().fetch():
        print(p.proxy)