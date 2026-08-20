"""theriturajps/proxy-list 代理源：持续维护的公共代理列表。

GitHub raw 托管的纯 `ip:port` 文本（proxies.txt 5474 条），实测通过率
~2.5%。候选量大但质量偏低，配额适中。走 jsdelivr 双通道兜底。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class TheriturajpsFetcher(BaseFetcher):
    name = "theriturajps"
    url = "https://github.com/theriturajps/proxy-list"
    # 5474 候选，~2.5% 通过率，取前 250 平衡性价比
    max_items = 250

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/theriturajps/"
                   "proxy-list/main/proxies.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in TheriturajpsFetcher().fetch():
        print(p.proxy)