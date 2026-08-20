"""OpenProxyList 代理源：GitHub raw 上的"已验证 HTTP(S) 列表"源。

主站 https://openproxylist.com 把已验证代理同步到 GitHub 仓库
roosterkid/openproxylist，HTTPS_RAW.txt 是纯 ip:port 格式，最稳。
抓回来不预筛，交给验证阶段按区域分流、由用户按需筛选。

注意：仓库在 GitHub，raw.githubusercontent.com 国内被墙，
必须走 jsdelivr CDN（与 proxifly/proxyscrape 一致）才能在国内环境拉到。
"""

import httpx

from fetcher.base import BaseFetcher
from model.proxy import Proxy


class OpenProxyListFetcher(BaseFetcher):
    name = "openproxylist"
    url = "https://openproxylist.com/proxy/"
    # 实测通过率 ~0%，降权省验证时间，保留复活机会
    max_items = 50

    def fetch(self):
        raw_url = ("https://cdn.jsdelivr.net/gh/roosterkid/"
                   "openproxylist@main/HTTPS_RAW.txt")
        try:
            r = httpx.get(raw_url, timeout=15)
            r.raise_for_status()
            text = r.text
        except Exception:
            return  # 源挂了就当没抓到，不影响其它源

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            p = Proxy(proxy=line)
            yield p


if __name__ == "__main__":
    for p in OpenProxyListFetcher().fetch():
        print(p.proxy)
