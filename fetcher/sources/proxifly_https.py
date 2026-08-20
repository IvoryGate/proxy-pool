"""Proxifly https 专用源：从 proxifly/free-proxy-list 的 https 协议数据抓取。

同 proxifly 源但专抓 https 协议子列表（~1288 条），候选虽少但 https 占比
100%——网关（zen 探测走 HTTPS CONNECT）只认 https 代理，这是定向冲 https
水位的关键源。全收不预筛，交给验证阶段筛选。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class ProxiflyHttpsFetcher(BaseFetcher):
    name = "proxifly-https"
    url = "https://github.com/proxifly/free-proxy-list"
    max_items = 800

    def fetch(self):
        # 数据行形如 "http://ip:port"（http:// 前缀），正则抠出 ip:port
        raw_url = ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list"
                   "@main/proxies/protocols/https/data.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in ProxiflyHttpsFetcher().fetch():
        print(p.proxy)
