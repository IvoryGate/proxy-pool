"""Ch4120N/Ch4120N-Proxy-List 代理源：多协议聚合列表（http/socks）。

GitHub raw 托管的纯 `ip:port` 文本（http.txt），每日更新，候选量中等。
全收不预筛，交给验证阶段筛选。走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class Ch4120NFetcher(BaseFetcher):
    name = "ch4120n"
    url = "https://github.com/Ch4120N/Ch4120N-Proxy-List"
    max_items = 800

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/Ch4120N/"
                   "Ch4120N-Proxy-List/main/proxies/http.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/Ch4120N/"
                   "Ch4120N-Proxy-List@main/proxies/http.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in Ch4120NFetcher().fetch():
        print(p.proxy)
