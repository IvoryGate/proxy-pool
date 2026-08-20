"""jetkai/proxy-list 代理源：GitHub 上的大型代理列表（在线可用库）。

仓库维护了运行中的代理并分类：online-proxies/txt/proxies-http.txt 是
http 代理纯文本，1800+ 条。全收不预筛，交给验证阶段筛选。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class JetkaiFetcher(BaseFetcher):
    name = "jetkai"
    url = "https://github.com/jetkai/proxy-list"
    # 实测通过率 ~0%，降权省验证时间，保留复活机会
    max_items = 50

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/jetkai/proxy-list/"
                   "main/online-proxies/txt/proxies-http.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in JetkaiFetcher().fetch():
        print(p.proxy)