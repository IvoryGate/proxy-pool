"""代理池的门面服务：把"抓取 → 验证 → 入库/淘汰"组合成完整操作。

这里把底层组件（Fetcher / Checker / RedisPool）串起来，
对外提供语义化的操作，调度器和 API 只调用这些，不碰底层细节。

当前能力：
  - refresh()   抓一批新代理，验证后首次入库（raw 入库，不重复放）
  - 后续会加 check_pool()  定期复核池内代理，淘汰失效
"""

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool


class ProxyService:
    def __init__(self):
        self.fetcher = Fetcher()
        self.checker = Checker()
        self.pool = RedisPool()

    def refresh(self):
        """抓取一批新代理 → 并发验证 → 首次入库（不重复放）。

        只放进"验证通过"且"池里还没有"的代理。
        返回 (新增数量, 本次可用数量)。
        """
        proxies = list(self.fetcher.run())
        ok_count, pairs = self.checker.check_all(proxies)

        added = 0
        for proxy, _ in pairs:
            if proxy.last_status and not self.pool.exists(proxy):
                self.pool.put(proxy)
                added += 1
        return added, ok_count

    def count(self):
        return self.pool.count()