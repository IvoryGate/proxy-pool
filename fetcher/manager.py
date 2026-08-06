"""统一采集器：驱动所有代理源，汇总去重。

对外统一入口是 run()：它把每个源的 fetch() 叫起来，把抓到的 "host:port"
汇总成一个字典（去重 + 记录来源），最后逐个返回。

先不搞"自动扫描目录 + 多线程并发"那些花活 —— 先把最基本的跑通，
让代码能读、能懂，之后再按需求逐步加强。
"""

from model.proxy import Proxy
from fetcher.base import BaseFetcher
from fetcher.sources.geonode import GeonodeFetcher
from fetcher.sources.scdn import ScdnFetcher


class Fetcher:
    def run(self, fetcher_classes=None):
        """返回一个生成器，逐个 yield 出 Proxy 对象（已去重、带来源标记）。

        fetcher_classes：要跑的源类列表，默认全部（目前手动列，后续可改自动扫描）。
        """
        if fetcher_classes is None:
            # 后续用"自动扫描 sources/ 目录"取代这个手动列表。
            fetcher_classes = [GeonodeFetcher, ScdnFetcher]

        proxy_dict = {}   # {"1.2.3.4:8080": Proxy, ...}，key 保证去重

        for cls in fetcher_classes:
            fetcher = cls()
            name = fetcher.name
            for proxy_str in fetcher.fetch():
                if proxy_str in proxy_dict:
                    # 同一个代理被多个源抓到：标记来源，不重复存
                    proxy_dict[proxy_str].source = name
                else:
                    proxy_dict[proxy_str] = Proxy(proxy=proxy_str, source=name)

        for proxy in proxy_dict.values():
            yield proxy


if __name__ == "__main__":
    for p in Fetcher().run():
        print(p.proxy, "->", p.source)