"""iplocate/free-proxy-list 代理源：每日维护的聚合列表。

GitHub raw 托管的纯 `ip:port` 文本（all-proxies.txt 1520 条），实测
通过率 ~17%。仓库 star 239，每日持续更新。

走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class IplocateFetcher(BaseFetcher):
    name = "iplocate"
    url = "https://github.com/iplocate/free-proxy-list"
    # 1520 候选，~17% 通过率；取前 800 平衡验证耗时
    max_items = 800

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/iplocate/"
                   "free-proxy-list/main/all-proxies.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/iplocate/"
                   "free-proxy-list@main/all-proxies.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in IplocateFetcher().fetch():
        print(p.proxy)