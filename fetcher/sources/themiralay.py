"""themiralay/Proxy-List-World 代理源：全球代理聚合大文件（data.txt）。

GitHub raw 托管的纯 `ip:port` 文本，候选量大（数千级），master 分支。
全收不预筛，交给验证阶段筛选。走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class ThemiralayFetcher(BaseFetcher):
    name = "themiralay"
    url = "https://github.com/themiralay/Proxy-List-World"
    max_items = 800

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/themiralay/"
                   "Proxy-List-World/master/data.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/themiralay/"
                   "Proxy-List-World@master/data.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in ThemiralayFetcher().fetch():
        print(p.proxy)
