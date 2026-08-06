"""代理池的门面服务：把"抓取 → 验证 → 入库/淘汰"组合成完整操作。

这里把底层组件（Fetcher / Checker / RedisPool）串起来，
对外提供语义化的操作，调度器和 API 只调用这些，不碰底层细节。

当前能力：
  - refresh()     抓一批新代理，验证后首次入库（raw 入库，不重复放）
  - check_pool()  定期复核池内代理，失效超过阈值则淘汰（use 复核）
"""

import random

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool


class ProxyService:
    def __init__(self, fetcher=None, checker=None, pool=None):
        # 允许注入假组件（测试用）；不传就用真实的
        self.fetcher = fetcher or Fetcher()
        self.checker = checker or Checker()
        self.pool = pool or RedisPool()

    def refresh(self, max_per_source=None):
        """抓取一批新代理 → 并发验证 → 首次入库（不重复放）。

        只放进"验证通过"且"池里还没有"的代理。
        max_per_source：每个源最多抓几个（None 不限），防止超大源阻塞。
        返回 (新增数量, 本次可用数量)。
        """
        proxies = list(self.fetcher.run(max_per_source=max_per_source))
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

    def get(self, need="any", https=False, security=None, quality=None,
            fast=False):
        """按业务语义取一个代理（不删除）。

        need       : 'cn' | 'global' | 'any' —— 要能访问哪
        https      : True 只要支持 https 的
        security   : 'strict' 匿名+未篡改 | 'anon' 只要匿名 | None 不要求
        quality    : 'stable' 只要信任分高的 | None 不要求
        fast       : True 只选低延迟的
        策略：先按条件粗筛一批候选，再按信任分加权挑一个（越稳越优先）。
        """
        region = None if need in ("any", None) else need
        safe = (security == "strict")
        candidates = self.pool.get_many(20, https=https, region=region,
                                        safe=safe)
        if not candidates:
            return None

        if security == "anon":
            candidates = [p for p in candidates
                          if p.anonymous in ("elite", "anonymous")]
        if quality == "stable":
            candidates = [p for p in candidates if p.score >= 2]
        if fast:
            candidates = [p for p in candidates
                          if p.latency_ms is not None and p.latency_ms <= 3000]
        if not candidates:
            return None

        # 信任分加权：score 越高的代理，被选中的概率越大
        weights = [max(1, p.score + 1) for p in candidates]
        total = sum(weights)
        r = random.random() * total
        acc = 0
        for p, w in zip(candidates, weights):
            acc += w
            if r <= acc:
                return p
        return candidates[-1]

    def pop(self, https=False, need="any", security=None):
        """按需取一个并删除（消费式）。"""
        region = None if need in ("any", None) else need
        safe = (security == "strict")
        return self.pool.pop(https=https, region=region, safe=safe)