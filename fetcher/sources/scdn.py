"""SCDN 代理源：一个"网站源"。

和 geonode（JSON API 源）不同，这个源返回的是 HTML 纯文本，
代理 ip:port 就混在 HTML 里。所以我们用正则从文本里抠出来。

这正是"两个源、内部实现完全不同、对外同一个 fetch() 接口"的例子：
  - geonode：读 JSON 的 ip/port 字段
  - scdn：  从 HTML 文本用正则抠
两者都 yield "host:port"，上层完全无感知。
"""

import httpx

from fetcher.base import BaseFetcher
from fetcher.util import parse_proxies_from_text, yield_unique_proxies


class ScdnFetcher(BaseFetcher):
    name = "scdn"
    url = "https://proxy.scdn.io/"
    # 分页抓取页数：每页 per_page=100 个候选，多抓几页攒量。
    page_count = 3

    def fetch(self):
        proxies = []
        for page in range(1, self.page_count + 1):
            api_url = ("https://proxy.scdn.io/get_proxies.php?"
                       f"protocol=&country=&per_page=100&page={page}")
            r = self._http_get(api_url, timeout=10)
            if not r:
                continue
            proxies += parse_proxies_from_text(r.text)

        for proxy in yield_unique_proxies(proxies):
            yield proxy


if __name__ == "__main__":
    for proxy in ScdnFetcher().fetch():
        print(proxy)