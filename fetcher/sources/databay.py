"""Databay 代理源：免费无 key API 源（严格 SSL 验证）。

API：https://databay.com/api/v1/proxy-list?protocol=http
返回 JSON 数组，每条含 ip/port/iso/protocol/ssl/anonymity/latency/uptime。
协议我们只收 HTTP/HTTPS（项目是 HTTP/HTTPS 代理池），SOCKS 不要。
字段直接填到 Proxy，交给验证阶段。

默认拉全量；anonymity=elite 时定向拉高匿代理（补 safe 层）。
"""

import httpx

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class DatabayFetcher(BaseFetcher):
    name = "databay"
    url = "https://databay.com/free-proxy-list"

    def __init__(self, elite_only=False):
        super().__init__()
        self.elite_only = elite_only

    def fetch(self):
        api_url = "https://databay.com/api/v1/proxy-list?protocol=http"
        if self.elite_only:
            api_url += "&anonymity=elite"
        r = self._http_get(api_url, timeout=15)
        if not r:
            return
        try:
            data = r.json()
        except Exception:
            return
        for item in data.get("data", []):
            ip = item.get("ip", "")
            port = item.get("port", "")
            if not (ip and port):
                continue
            p = Proxy(proxy=f"{ip}:{port}")
            p.region = item.get("iso", "") or item.get("country", "")
            p.https = bool(item.get("ssl", False))
            anon = (item.get("anonymity", "") or "").lower()
            p.anonymous = "elite" if anon in ("elite", "anonymous") else anon
            p.latency_ms = item.get("latency")
            yield p


if __name__ == "__main__":
    for p in DatabayFetcher().fetch():
        print(p.proxy, p.region, "https" if p.https else "http", p.anonymous)
