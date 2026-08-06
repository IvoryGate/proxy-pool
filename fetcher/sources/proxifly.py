"""Proxifly 代理源：一个"全球代理列表 JSON API"源。

返回 JSON，每条含 proxy / ip / port / https / geolocation.country 等信息。
这个源的数据里国内国外代理都有，我们**全收不预筛**（多多益善），
并把 region / https 信息带上，交给验证阶段按区域分流、由用户按需筛选。
"""

import httpx

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class ProxiflyFetcher(BaseFetcher):
    name = "proxifly"
    url = "https://proxifly.dev/"

    def fetch(self):
        api_url = ("https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list"
                   "@main/proxies/all/data.json")
        try:
            r = httpx.get(api_url, timeout=15)
            data = r.json()
        except Exception:
            return  # 源挂了就当没抓到，不影响其它源

        for item in data:
            ip = item.get("ip", "")
            port = item.get("port", "")
            if not (ip and port):
                continue
            p = Proxy(proxy=f"{ip}:{port}")
            p.region = item.get("geolocation", {}).get("country", "")
            p.https = bool(item.get("https", False))
            p.anonymous = item.get("anonymity", "")
            yield p


if __name__ == "__main__":
    for p in ProxiflyFetcher().fetch():
        print(p.proxy, p.region, p.https)