"""统一采集器：驱动所有代理源，汇总去重。

对外统一入口是 run()：它自动扫描 sources/ 目录发现所有源，
把每个源的 fetch() 叫起来，把抓到的代理汇总成一个字典
（去重 + 记录来源），最后逐个返回。

自动扫描的好处：加一个新源 = 在 sources/ 下加一个文件，manager 不用改。
"""

import importlib
import os
import random

from model.proxy import Proxy
from fetcher.base import BaseFetcher
from fetcher.util import reservoir_sample


def _discover_fetcher_classes():
    """扫描 fetcher/sources/ 目录，返回所有继承 BaseFetcher 的类。"""
    sources_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sources")
    classes = []
    for filename in sorted(os.listdir(sources_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        module_name = f"fetcher.sources.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue  # 单个源坏了不影响其它源
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and issubclass(attr, BaseFetcher)
                    and attr is not BaseFetcher and attr.enabled):
                classes.append(attr)
    return classes


class Fetcher:
    def __init__(self, pool=None):
        """pool：可选，一个提供 get()/put() 的对象（如 RedisPool）。
        若给了，抓源时会给每个源发一个池内代理（fetcher.proxy），
        让源通过它抓取以绕反爬；抓完把代理还回池。不给则源直连抓取。
        """
        self.pool = pool

    def run(self, fetcher_classes=None, max_per_source=None):
        """返回一个生成器，逐个 yield 出 Proxy 对象（已去重、带来源标记）。

        fetcher_classes：要跑的源类列表，默认自动扫描 sources/ 目录。
        max_per_source：每个源最多抓取多少个代理，None 表示不限量。
            防止超大源（如 hproxy 2.6 万）阻塞整个调度。
        """
        if fetcher_classes is None:
            fetcher_classes = _discover_fetcher_classes()
            # 打乱源顺序：避免每次固定从同一批源开始抓（均衡各源抓取频率）
            random.shuffle(fetcher_classes)

        proxy_dict = {}   # {"1.2.3.4:8080": Proxy, ...}，key 保证去重

        for cls in fetcher_classes:
            fetcher = cls()
            name = fetcher.name
            # 抓源前：从池子里借一个代理给源用（绕反爬），抓完还回
            src_proxy = self.pool.get() if self.pool else None
            if src_proxy:
                fetcher.proxy = src_proxy.proxy
            try:
                # max_per_source 有值时：对源的 fetch 流做水塘抽样（等概率随机取 N 个）
                # 而不是取前 N 个 —— 大源（如 hproxy 2 万+）反复取前 N 会漏掉更新的代理
                source_items = fetcher.fetch()
                if max_per_source is not None:
                    source_items = reservoir_sample(source_items, max_per_source)
                for item in source_items:
                    # 源可以 yield 字符串 "ip:port"，也可以 yield Proxy（带 region 等信息）
                    item_proxy = item.proxy if isinstance(item, Proxy) else item
                    if item_proxy in proxy_dict:
                        # 同一个代理被多个源抓到：标记来源，不重复存
                        existing = proxy_dict[item_proxy]
                        if not existing.source:
                            existing.source = name
                    else:
                        p = item if isinstance(item, Proxy) else Proxy(proxy=item)
                        if not p.source:
                            p.source = name
                        proxy_dict[item_proxy] = p
            finally:
                # 抓完把借出去的代理还回池子
                if src_proxy and self.pool:
                    self.pool.put(src_proxy)

        for proxy in proxy_dict.values():
            yield proxy


if __name__ == "__main__":
    for p in Fetcher().run():
        print(p.proxy, "->", p.source)