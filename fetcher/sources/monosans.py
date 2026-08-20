"""monosans/proxy-list 代理源：GitHub 上维护的干净代理列表。

仓库按协议分文件，all.txt 聚合 http/https/socks（~874 条），
实测通过率 ~28%，是全站质量较高的源之一。纯 `ip:port` 文本。
全收不预筛，交给验证阶段筛选。

抓取走双通道（raw 优先，jsdelivr 兜底），规避 raw 在服务器上的抖动。
"""

from fetcher.base import BaseFetcher
from fetcher.util import fetch_text, parse_proxies_from_text, yield_unique_proxies
from model.proxy import Proxy


class MonosansFetcher(BaseFetcher):
    name = "monosans"
    url = "https://github.com/monosans/proxy-list"
    # 实测通过率最高（~20% 全量），全量抓取不截断（614 候选，约 120 合格）
    max_items = None

    def fetch(self):
        # 用 all.txt（http+socks 混合，~874 条）比 http.txt 候选更多，
        # 验证阶段会自动过滤非 http（socks 的 ip:port 也能过格式，但验证
        # 走 http 协议失败即淘汰，天然只留 http 可用）。实测通过率更高。
        raw_url = ("https://raw.githubusercontent.com/monosans/proxy-list/"
                   "main/proxies/all.txt")
        text, _ = fetch_text(raw_url)
        if not text:
            return  # 源挂了就当没抓到，不影响其它源

        for proxy in yield_unique_proxies(parse_proxies_from_text(text)):
            yield Proxy(proxy=proxy)


if __name__ == "__main__":
    for p in MonosansFetcher().fetch():
        print(p.proxy)