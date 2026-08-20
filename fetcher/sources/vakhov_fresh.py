"""vakhov/fresh-proxy-list 代理源：持续刷新的高质量代理列表。

这是 GitHub raw 托管的纯 `ip:port` HTTP 列表（524 条），关键优势是
**实时刷新**——仓库主人持续验证并剔除死代理，实测全量验证通过率高达
~75%，是全站质量最高的源（对比其它源普遍 2-20%）。

走 jsdelivr 双通道兜底防 raw 抖动（GitHub raw 在服务器上连通不稳定）。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class VakhovFreshProxyFetcher(BaseFetcher):
    name = "vakhov-fresh"
    url = "https://github.com/vakhov/fresh-proxy-list"
    # 全量 524 条，~75% 通过率，全取不浪费
    max_items = None

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/vakhov/"
                   "fresh-proxy-list/master/http.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/vakhov/"
                   "fresh-proxy-list@master/http.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in VakhovFreshProxyFetcher().fetch():
        print(p.proxy)