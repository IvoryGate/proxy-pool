"""代理池的门面服务：把"抓取 → 验证 → 入库/淘汰"组合成完整操作。

这里把底层组件（Fetcher / Checker / RedisPool）串起来，
对外提供语义化的操作，调度器和 API 只调用这些，不碰底层细节。

当前能力：
  - refresh()     抓一批新代理，验证后首次入库（raw 入库，不重复放）
  - check_pool()  定期复核池内代理，失效超过阈值则淘汰（use 复核）
"""

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool


class ProxyService:
    def __init__(self, fetcher=None, checker=None, pool=None):
        # 允许注入假组件（测试用）；不传就用真实的
        self.fetcher = fetcher or Fetcher()
        self.checker = checker or Checker()
        self.pool = pool or RedisPool()

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

    def check_pool(self):
        """复核池内全部代理，淘汰失效的。

        流程：取出池里所有代理 → 并发验证 → 逐个更新：
          验证通过 → fail_count 归零，写回池子
          验证失败 → fail_count +1，超过 MAX_FAIL_COUNT 则删除，否则写回
        返回 (复核数量, 淘汰数量)。
        """
        proxies = self.pool.getAll()
        self.checker.check_all(proxies)   # 逐个更新 last_status / fail_count

        eliminated = 0
        for proxy in proxies:
            if proxy.last_status:
                self.pool.put(proxy)          # 通过 → 写回
            elif self.checker.should_eliminate(proxy.fail_count):
                self.pool.delete(proxy)       # 超阈值 → 淘汰
                eliminated += 1
            else:
                self.pool.put(proxy)          # 失败但没超 → 留着再试
        return len(proxies), eliminated

    def count(self):
        return self.pool.count()