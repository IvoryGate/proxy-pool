"""KangProxy 代理源：officialputuid/KangProxy 的 https 专用列表。

GitHub raw 托管的纯 `ip:port` 文本，https 目录下专列 https 代理，
候选量大且专一。全收不预筛，交给验证阶段筛选。
走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class KangProxyFetcher(BaseFetcher):
    name = "kangproxy"
    url = "https://github.com/officialputuid/KangProxy"
    max_items = 3000

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/officialputuid/"
                   "KangProxy/main/https/https.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/officialputuid/"
                   "KangProxy@main/https/https.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in KangProxyFetcher().fetch():
        print(p.proxy)
