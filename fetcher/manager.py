"""统一采集器：驱动所有代理源，汇总去重。

对外统一入口是 run()：它自动扫描 sources/ 目录发现所有源，
把每个源的 fetch() 叫起来，把抓到的代理汇总成一个字典
（去重 + 记录来源），最后逐个返回。

自动扫描的好处：加一个新源 = 在 sources/ 下加一个文件，manager 不用改。
"""

import importlib
import os

from model.proxy import Proxy
from fetcher.base import BaseFetcher


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
    def run(self, fetcher_classes=None):
        """返回一个生成器，逐个 yield 出 Proxy 对象（已去重、带来源标记）。

        fetcher_classes：要跑的源类列表，默认自动扫描 sources/ 目录。
        """
        if fetcher_classes is None:
            fetcher_classes = _discover_fetcher_classes()

        proxy_dict = {}   # {"1.2.3.4:8080": Proxy, ...}，key 保证去重

        for cls in fetcher_classes:
            fetcher = cls()
            name = fetcher.name
            for item in fetcher.fetch():
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

        for proxy in proxy_dict.values():
            yield proxy


if __name__ == "__main__":
    for p in Fetcher().run():
        print(p.proxy, "->", p.source)