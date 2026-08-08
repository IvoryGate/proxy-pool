"""sunny9577/proxy-scraper 代理源：GitHub Pages 上的全球代理聚合。

proxy-scraper 从多个来源聚合代理，proxies.txt 纯 `ip:port` 文本，
1000+ 条。全收不预筛，交给验证阶段筛选。

注意：这是 GitHub Pages 站点（sunny9577.github.io），无 jsdelivr 通道，
用 fetch_text 直连抓取（失败返回 None 不影响其它源）。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class Sunny9577Fetcher(BaseFetcher):
    name = "sunny9577"
    url = "https://github.com/sunny9577/proxy-scraper"

    def fetch(self):
        url = "https://sunny9577.github.io/proxy-scraper/proxies.txt"
        text, _ = fetch_text(url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in Sunny9577Fetcher().fetch():
        print(p.proxy)