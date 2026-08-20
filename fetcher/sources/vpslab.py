"""VPSLabCloud/VPSLab-Free-Proxy-List 代理源：持续刷新的高质量聚合。

GitHub raw 托管的纯 `ip:port` 文本（http_all.txt 731 条），实测通过率
~49%，全站质量第一梯队（仅次于 vakhov-fresh）。仓库每日持续维护。

走 jsdelivr 双通道兜底防 raw 抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class VPSLabFetcher(BaseFetcher):
    name = "vpslab-http"
    url = "https://github.com/VPSLabCloud/VPSLab-Free-Proxy-List"
    # 731 候选，~49% 通过率，全量抓取
    max_items = None

    def fetch(self):
        raw_url = ("https://raw.githubusercontent.com/VPSLabCloud/"
                   "VPSLab-Free-Proxy-List/main/http_all.txt")
        jsd_url = ("https://cdn.jsdelivr.net/gh/VPSLabCloud/"
                   "VPSLab-Free-Proxy-List@main/http_all.txt")
        text, _ = fetch_text(raw_url, jsdelivr_url=jsd_url)
        if not text:
            return

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in VPSLabFetcher().fetch():
        print(p.proxy)