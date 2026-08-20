"""gproxynet/free-proxy-list 代理源：每日更新的免费代理列表。

GitHub raw 托管的纯 `ip:port` 文本（all.txt 200 条），实测通过率 ~7%。
列表较短但持续更新。走 jsdelivr 双通道兜底。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class GproxynetFetcher(BaseFetcher):
    name = "gproxynet"
    url = "https://github.com/gproxynet/free-proxy-list"
    # 200 候选，~7% 通过率，全量抓取
    max_items = None

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/gproxynet/"
                   "free-proxy-list/main/all.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in GproxynetFetcher().fetch():
        print(p.proxy)