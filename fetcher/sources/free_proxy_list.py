"""Free-Proxy-List 代理源：老牌免费代理站，HTML 表格源。

表格列：IP | Port | Code | Country | Anonymity | Google | Https | Last Checked。
每行带国家代码/匿名度/https 能力，直接填到 Proxy 字段，
交给验证阶段按区域分流、按用户需求筛选。
"""

import httpx
from lxml import html

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class FreeProxyListFetcher(BaseFetcher):
    name = "free-proxy-list"
    url = "https://free-proxy-list.net"

    # 主列表 + 高匿专页（anonymous 定向补 safe 层）
    PAGES = [
        "https://free-proxy-list.net",
        "https://free-proxy-list.net/anonymous-proxy.html",
    ]

    def fetch(self):
        seen = set()
        for page_url in self.PAGES:
            r = self._http_get(page_url, timeout=15)
            if not r:
                continue
            doc = html.fromstring(r.text)
            for tr in doc.xpath('//table/tbody/tr[td]'):
                cells = [td.text_content().strip() for td in tr.xpath('./td')]
                if len(cells) < 4:
                    continue
                ip, port = cells[0], cells[1]
                if not ip or not port:
                    continue
                addr = f"{ip}:{port}"
                if addr in seen:
                    continue
                seen.add(addr)
                p = Proxy(proxy=addr)
                p.region = cells[2]
                p.anonymous = cells[4]
                p.https = (cells[6].lower() == "yes")
                yield p


if __name__ == "__main__":
    for p in FreeProxyListFetcher().fetch():
        print(p.proxy, p.region, p.anonymous, "https" if p.https else "http")
