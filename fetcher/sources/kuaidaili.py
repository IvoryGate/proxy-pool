"""快代理（kuaidaili）：xpath 表格类源。

这个站每行 <tr> 里 <td> 单元格：第0个是 ip，第1个是 port。
比正则更稳的地方是：用 xpath 明确地按表格结构取，不看 HTML 细节。
参考项目还 sleep(1) 防止请求太频繁被限；我们走代理抓，限得轻些。
"""

from time import sleep

from lxml import etree

from fetcher.base import BaseFetcher
from fetcher.util import yield_unique_proxies


class KuaidailiFetcher(BaseFetcher):
    name = "kuaidaili"
    url = "https://www.kuaidaili.com"

    def fetch(self, page_count=3):
        url_patterns = [
            "https://www.kuaidaili.com/free/inha/{}/",
            "https://www.kuaidaili.com/free/intr/{}/",
        ]
        all_proxies = []
        for page in range(1, page_count + 1):
            for pattern in url_patterns:
                r = self._http_get(pattern.format(page), timeout=10)
                if not r or not r.content:
                    continue
                tree = etree.HTML(r.content)
                rows = tree.xpath(".//table//tr")
                if rows:
                    all_proxies += [
                        ":".join(tr.xpath("./td/text()")[0:2])
                        for tr in rows[1:]
                        if len(tr.xpath("./td/text()")) >= 2
                    ]
                sleep(1)  # 防被限速，间隔一下

        for proxy in yield_unique_proxies(all_proxies):
            yield proxy