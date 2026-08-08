"""monosans/proxy-list 代理源：GitHub 上维护的干净代理列表。

仓库按协议分文件，proxies/http.txt 是大小合理的 http 代理列表。
纯 `ip:port` 文本，约 450 条。全收不预筛，交给验证阶段筛选。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class MonosansFetcher(BaseFetcher):
    name = "monosans"
    url = "https://github.com/monosans/proxy-list"

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/monosans/proxy-list/"
                   "main/proxies/http.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in MonosansFetcher().fetch():
        print(p.proxy)