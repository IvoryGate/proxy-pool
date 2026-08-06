"""ProxyScrape 代理源：一个"全球免费代理 JSON API"源。

返回 JSON 列表，每条含 protocol / ip / port / country_code / ssl 等 metadata。
我们全收不预筛，并把 region / https 填上，交给验证阶段按区域分流。
"""

import httpx

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class ProxyScrapeFetcher(BaseFetcher):
    name = "proxyscrape"
    url = "https://proxyscrape.com/free-proxy-list"

    def fetch(self):
        api_url = ("https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list"
                   "@main/proxies/all/data.json")
        try:
            r = httpx.get(api_url, timeout=15)
            data = r.json()
        except Exception:
            return

        for item in data:
            ip = item.get("ip", "")
            port = item.get("port", "")
            if not (ip and port):
                continue
            p = Proxy(proxy=f"{ip}:{port}")
            p.region = item.get("country_code", "")
            p.https = bool(item.get("ssl", False))
            p.anonymous = item.get("anonymity", "")
            yield p


if __name__ == "__main__":
    for p in ProxyScrapeFetcher().fetch():
        print(p.proxy, p.region, "https" if p.https else "http")