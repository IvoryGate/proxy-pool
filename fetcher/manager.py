"""统一采集器：驱动所有代理源，汇总去重。

对外统一入口是 run()：它自动扫描 sources/ 目录发现所有源，
把每个源的 fetch() 叫起来，把抓到的代理汇总成一个字典
（去重 + 记录来源），最后逐个返回。

自动扫描的好处：加一个新源 = 在 sources/ 下加一个文件，manager 不用改。
"""

import importlib
import itertools
import os
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def _timed_items(items, timeout, max_scan=None):
    """把源抓取流包成"限时消费"：超过 timeout 秒就中断，不再产出。

    慢源（一次 HTTP 请求可能卡 30s+）不能拖垮整个补源循环，所以给每个
    源一个总时限。实现：在独立线程里消费源生成器，主线程限时接收。
    线程结束前把最终结果放进 queue，主线程靠超时退出循环。
    """
    q = queue.Queue(maxsize=128)
    stop = threading.Event()

    def worker():
        try:
            count = 0
            for item in items:
                if stop.is_set():
                    return
                if max_scan is not None and count >= max_scan:
                    return
                q.put(item)
                count += 1
        except Exception:
            pass
        finally:
            q.put(None)  # 结束哨兵

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop.set()  # 超时，通知 worker 停止
            break
        try:
            item = q.get(timeout=remaining)
        except queue.Empty:
            break
        if item is None:
            break
        yield item
    stop.set()
    t.join(timeout=0.5)


class Fetcher:
    def __init__(self, pool=None):
        """pool：可选，一个提供 get()/put() 的对象（如 RedisPool）。
        若给了，抓源时会给每个源发一个池内代理（fetcher.proxy），
        让源通过它抓取以绕反爬；抓完把代理还回池。不给则源直连抓取。
        """
        self.pool = pool

    def run(self, fetcher_classes=None, max_per_source=None,
            source_timeout=15, max_workers=8):
        """返回一个生成器，逐个 yield 出 Proxy 对象（已去重、带来源标记）。

        fetcher_classes：要跑的源类列表，默认自动扫描 sources/ 目录。
        max_per_source：每个源最多抓取多少个代理，None 表示不限量。
            防止超大源（如 hproxy 2.6 万）阻塞整个调度。
        source_timeout：单个源抓取的总时限（秒）。慢源超时即中断，
            不拖垮整体。默认 15s。
        max_workers：并行抓源的线程数。默认 8 —— 慢源不再拖累整体，
            总耗时 ≈ 最慢单个源，而非所有源耗时之和。
        """
        if fetcher_classes is None:
            fetcher_classes = _discover_fetcher_classes()
            # 打乱源顺序：避免每次固定从同一批源开始抓（均衡各源抓取频率）
            random.shuffle(fetcher_classes)

        proxy_dict = {}   # {"1.2.3.4:8080": Proxy, ...}，key 保证去重
        dict_lock = threading.Lock()
        pool_lock = threading.Lock()

        def grab(cls):
            """在独立线程里抓一个源，结果并入 proxy_dict。"""
            fetcher = cls()
            name = fetcher.name
            src_proxy = None
            if self.pool:
                with pool_lock:
                    src_proxy = self.pool.get()
                if src_proxy:
                    fetcher.proxy = src_proxy.proxy
            try:
                source_items = fetcher.fetch()
                if max_per_source is not None:
                    # 直接取前 N：代理列表源顺序无关，无须遍历全流做
                    # 等概率抽样（reservoir_sample 遍历大源很慢）。
                    source_items = itertools.islice(
                        source_items, max_per_source)
                local = {}
                for item in source_items:
                    if item is None:
                        break
                    item_proxy = item.proxy if isinstance(item, Proxy) else item
                    if item_proxy in local:
                        existing = local[item_proxy]
                        if not existing.source:
                            existing.source = name
                    else:
                        p = item if isinstance(item, Proxy) else Proxy(proxy=item)
                        if not p.source:
                            p.source = name
                        local[item_proxy] = p
                with dict_lock:
                    for addr, p in local.items():
                        if addr in proxy_dict:
                            existing = proxy_dict[addr]
                            if not existing.source:
                                existing.source = name
                        else:
                            proxy_dict[addr] = p
            except Exception:
                pass
            finally:
                if src_proxy and self.pool:
                    with pool_lock:
                        self.pool.put(src_proxy)

        with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="fetch") as ex:
            futures = [ex.submit(grab, cls) for cls in fetcher_classes]
            # 限时等待：最慢源超时后整体结束（防单源永久卡住拖死补源）
            try:
                for fut in as_completed(futures, timeout=source_timeout * 2):
                    fut.result()
            except (TimeoutError, Exception):
                pass  # 有源超时：已完成的结果保留，未完成的丢弃

        for proxy in proxy_dict.values():
            yield proxy


if __name__ == "__main__":
    for p in Fetcher().run():
        print(p.proxy, "->", p.source)