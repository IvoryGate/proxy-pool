"""clarketm/proxy-list 代理源：GitHub 上的"已验证"代理列表。

proxy-list-raw.txt 是纯 `ip:port` 文本（另有带国家/协议的带注释版本）。
约 400 条。全收不预筛，交给验证阶段筛选。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class ClarketmFetcher(BaseFetcher):
    name = "clarketm"
    url = "https://github.com/clarketm/proxy-list"

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/clarketm/proxy-list/"
                   "master/proxy-list-raw.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in ClarketmFetcher().fetch():
        print(p.proxy)