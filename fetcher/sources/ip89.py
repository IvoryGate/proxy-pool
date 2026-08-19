"""89免费代理（ip89）：表格类 HTML 源。

ip 和 port 分列在 <td> 里，用正则抠相邻单元格。
参考项目：re.findall 两个 <td> 之间的 ip + 后面的端口。
"""

import re

from fetcher.base import BaseFetcher
from fetcher.util import yield_unique_proxies

IP_PORT = re.compile(
    r"<td.*?>[\s\S]*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[\s\S]*?</td>"
    r"[\s\S]*?<td.*?>[\s\S]*?(\d+)[\s\S]*?</td>")


class Ip89Fetcher(BaseFetcher):
    name = "ip89"
    url = "https://www.89ip.cn/"
    # 分页抓取页数：站每页 ~40 个代理，抓前几页攒新 IP。
    # 页间有部分重叠（最新几条会重复），跨页去重后仍是净增量。
    page_count = 3

    def fetch(self):
        proxies = []
        for page in range(1, self.page_count + 1):
            r = self._http_get(
                f"https://www.89ip.cn/index_{page}.html", timeout=10)
            if not r:
                continue
            proxies += [":".join(m) for m in IP_PORT.findall(r.text)]
        for proxy in yield_unique_proxies(proxies):
            yield proxy