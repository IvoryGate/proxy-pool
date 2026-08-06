"""Geonode 代理源：一个"开放代理列表 API"源。

它返回 JSON，里面 data[] 一项一项的，每项有 ip、port 字段。
所以我们这个源的处理方式就是：调 API → 读 JSON → 拼成 "host:port" → yield。
"""

import httpx

from fetcher.base import BaseFetcher


class GeonodeFetcher(BaseFetcher):
    name = "geonode"
    url = "https://geonode.com/"

    def fetch(self):
        api_url = ("https://proxylist.geonode.com/api/proxy-list?"
                   "filterLastChecked=10&page=1&limit=100"
                   "&sort_by=lastChecked&sort_type=desc")
        try:
            r = httpx.get(api_url, timeout=10)
            data = r.json().get("data", [])
        except Exception:
            return  # 源挂了就当没抓到，不影响其它源

        proxies = []
        for item in data:
            ip = item.get("ip", "")
            port = item.get("port", "")
            if ip and port:
                proxies.append(f"{ip}:{port}")

        for proxy in self.yield_unique_proxies(proxies):
            yield proxy


if __name__ == "__main__":
    for proxy in GeonodeFetcher().fetch():
        print(proxy)