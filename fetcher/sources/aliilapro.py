"""ALIILAPRO/Proxy 代理源：持续维护的聚合列表。

GitHub raw 托管的纯 `ip:port` 文本（http.txt 830 条），实测通过率
~12%，质量不错。每日持续更新。

走 jsdelivr 双通道兜底。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class ALIILAPROFetcher(BaseFetcher):
    name = "aliilapro"
    url = "https://github.com/ALIILAPRO/Proxy"
    # 830 候选，~12% 通过率，全量抓取
    max_items = None

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/ALIILAPRO/"
                   "Proxy/main/http.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in ALIILAPROFetcher().fetch():
        print(p.proxy)