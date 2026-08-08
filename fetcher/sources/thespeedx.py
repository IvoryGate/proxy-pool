"""TheSpeedX/PROXY-List 代理源：GitHub 上维护的超大 HTTP/SOCKS 列表。

仓库按协议分文件：http.txt / socks4.txt / socks5.txt，纯 `ip:port` 文本，
http.txt 单文件就 2000+ 条。全收不预筛，交给验证阶段按区域分流筛选。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class TheSpeedXHttpFetcher(BaseFetcher):
    name = "thespeedx-http"
    url = "https://github.com/TheSpeedX/PROXY-List"

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/TheSpeedX/"
                   "PROXY-List/master/http.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in TheSpeedXHttpFetcher().fetch():
        print(p.proxy)