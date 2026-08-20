"""SoliSpirit/proxy-list 代理源：超大型代理聚合（http.txt 13万+ 候选）。

GitHub raw 托管的纯 `ip:port` 文本，全站最大候选源，实测抽样通过率
~8%。即使取前 3000 也能贡献 ~250 合格代理，是冲量关键源。

超大文件用 raw 直连抓取，jsdelivr 对超大文件不稳所以不回退 CDN。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class SoliSpiritHttpFetcher(BaseFetcher):
    name = "solispirit-http"
    url = "https://github.com/SoliSpirit/proxy-list"
    # 134k 候选，~8% 通过率；全量验证不现实，取前 15000 冲量
    max_items = 15000

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/SoliSpirit/"
                   "proxy-list/main/http.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in SoliSpiritHttpFetcher().fetch():
        print(p.proxy)