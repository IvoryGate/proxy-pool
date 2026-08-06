"""云代理（ip3366）：表格类 HTML 源。

和 scdn（HTML 纯文本混着 ip:port）不同，这个站把 ip 和 port 放在相邻的
<td> 单元格里。参考项目用正则 `(<td>ip</td>...<td>port</td>)` 抠。
我们用基类的 _http_get（自动带 self.proxy 走代理抓取，绕反爬）。
"""

import re

from fetcher.base import BaseFetcher
from fetcher.util import yield_unique_proxies

IP_PORT_CELLS = re.compile(
    r"<td>(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})</td>[\s\S]*?<td>(\d+)</td>")


class Ip3366Fetcher(BaseFetcher):
    name = "ip3366"
    url = "http://www.ip3366.net/"

    def fetch(self):
        urls = [
            "http://www.ip3366.net/free/?stype=1",
            "http://www.ip3366.net/free/?stype=2",
        ]
        all_proxies = []
        for url in urls:
            r = self._http_get(url, timeout=10)
            if not r:
                continue
            all_proxies += [":".join(m)
                            for m in IP_PORT_CELLS.findall(r.text)]

        for proxy in yield_unique_proxies(all_proxies):
            yield proxy