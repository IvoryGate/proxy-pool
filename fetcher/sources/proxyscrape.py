"""ProxyScrape 代理源：官方 API + 开源 JSON 双通道。

官方 API（http/https，可指定国家）实时性好：
  https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies
  &protocol=http&proxy_format=ipport&format=text[&country=cn]
默认拉全量（不指定 country），region 交给验证阶段探测分流。

开源 JSON（jsdelivr 镜像）带 country_code/ssl 元数据，作补充。
"""

import httpx

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class ProxyScrapeFetcher(BaseFetcher):
    name = "proxyscrape"
    url = "https://proxyscrape.com/free-proxy-list"
    # 实测通过率 ~16%，放开配额
    max_items = 500

    def fetch(self):
        seen = set()
        # 官方 API：纯 ip:port 文本，实时性好
        api_url = ("https://api.proxyscrape.com/v4/free-proxy-list/get"
                   "?request=display_proxies&protocol=http"
                   "&proxy_format=ipport&format=text&timeout=3000")
        try:
            r = httpx.get(api_url, timeout=15)
            for line in r.text.splitlines():
                line = line.strip()
                if line and line not in seen:
                    seen.add(line)
                    yield Proxy(proxy=line)
        except Exception:
            pass  # 官方 API 挂了就退到 jsdelivr

        # 开源 JSON：带元数据（country_code/ssl/anonymity）
        json_url = ("https://cdn.jsdelivr.net/gh/proxyscrape/free-proxy-list"
                    "@main/proxies/all/data.json")
        try:
            r = httpx.get(json_url, timeout=15)
            data = r.json()
        except Exception:
            return
        for item in data:
            ip = item.get("ip", "")
            port = item.get("port", "")
            if not (ip and port):
                continue
            addr = f"{ip}:{port}"
            if addr in seen:
                continue
            seen.add(addr)
            p = Proxy(proxy=addr)
            p.region = item.get("country_code", "")
            p.https = bool(item.get("ssl", False))
            p.anonymous = item.get("anonymity", "")
            yield p


if __name__ == "__main__":
    for p in ProxyScrapeFetcher().fetch():
        print(p.proxy, p.region, "https" if p.https else "http")