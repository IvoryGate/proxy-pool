"""ShiftyTR/Proxy-List 代理源：GitHub 上的超大 HTTP/SOCKS 混合列表。

单文件 proxy.txt 纯 `ip:port` 文本，800+ 条，含 http/socks4/socks5 混合
（无法从文本区分协议）。全收交给验证阶段统一 http 验证，能过的就是
http 兼容代理，过不了的自动滤掉，不浪费。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class ShiftyTRFetcher(BaseFetcher):
    name = "shiftytr"
    url = "https://github.com/ShiftyTR/Proxy-List"

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/ShiftyTR/"
                   "Proxy-List/master/proxy.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in ShiftyTRFetcher().fetch():
        print(p.proxy)