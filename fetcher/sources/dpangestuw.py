"""dpangestuw/Free-Proxy 代理源：超大聚合列表（http_proxies.txt 4600+）。

GitHub raw 托管的纯 `ip:port` 文本，候选量全站最大之一，实测通过率
~31%。大而杂，但按量堆也能贡献数百合格代理。

走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class DPangestuwFetcher(BaseFetcher):
    name = "dpangestuw"
    url = "https://github.com/dpangestuw/Free-Proxy"
    # 4665 候选，~31% 通过率；全量太多验证慢，取前 1500 平衡量/验证耗时
    max_items = 1500

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/dpangestuw/"
                   "Free-Proxy/master/http_proxies.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/dpangestuw/"
                   "Free-Proxy@master/http_proxies.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in DPangestuwFetcher().fetch():
        print(p.proxy)