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
        验证通过但 region 为空的代理会做一次 IP 归属地探测补标签
        （hproxy 等纯文本源的代理才有这情况），否则被错分到 global。
        返回 (新增数量, 本次可用数量)。

        优化：验证前先按"池里是否已有"过滤，只验证真正的新 IP——
        大批量抓取时大量是重复/已存在，跳过它们能省下大部分验证时间。
        """
        proxies = list(self.fetcher.run(max_per_source=max_per_source))

        # 已有地址集合（供过滤重复）
        existing = set()
        try:
            for p in self.pool.getAll():
                existing.add(p.proxy)
        except Exception:
            existing = set()

        # 只验证新 IP（池里没有的）；格式无效的直接筛掉。
        # _valid_ipv4 拦截带前导零的脏 IP（141.000.11.253），避免 httpx 崩溃。
        from helper.check import PROXY_FORMAT, _valid_ipv4
        new_proxies = [p for p in proxies
                       if p.proxy not in existing
                       and PROXY_FORMAT.match(p.proxy)
                       and _valid_ipv4(p.proxy)]
        ok_count, pairs = self.checker.check_all(new_proxies)

        # 验证通过且 region 为空的 → 补打 region 标签
        fresh = [p for p, _ in pairs if p.last_status and not p.region]
        if fresh:
            from helper.region_detect import detect_regions
            detected = detect_regions(fresh)
            for p in fresh:
                cc = detected.get(p.proxy)
                if cc:
                    p.region = cc

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
        """池子统计：总数 + https/cn/global/safe + 各稳定档位。"""
        c = self.pool.count()
        from config.services import STABLE_LEVELS
        for lvl, ms in STABLE_LEVELS.items():
            c[lvl] = self.pool.count_by_region("global", min_score=ms) \
                + self.pool.count_by_region("cn", min_score=ms)
        return c

    # ---------- 水位控制（目标驱动补源） ----------

    def service_levels(self, service_min=None):
        """读各服务当前水位，返回 {("cn","all"): (current, min), ...}。"""
        if service_min is None:
            from config.services import SERVICE_MIN, service_candidates
            service_min = SERVICE_MIN
            candidates = service_candidates()
        else:
            candidates = [(r, s) for r, specs in service_min.items()
                          for s in specs]

        levels = {}
        for region, svc in candidates:
            if svc == "all":
                cur = self.pool.count_by_region(region)
            elif svc == "safe":
                cur = self.pool.count_by_region(region, safe_only=True)
            elif svc == "https":
                # https 池：用 Redis 的 use_proxy:https 索引直接数（网关最关心）
                cur = self.pool.count()["https"]
            elif svc in ("stable1", "stable2", "stable3"):
                # 稳定性分级：按档位对应的最低信任分统计
                from config.services import STABLE_LEVELS
                cur = self.pool.count_by_region(region,
                                                min_score=STABLE_LEVELS[svc])
            else:
                cur = 0
            levels[(region, svc)] = (cur, service_min[region][svc])
        return levels

    def below_waterline(self, levels):
        """返回所有未达标服务的 (region, svc, current, min) 列表。"""
        return [(r, s, cur, mn) for (r, s), (cur, mn) in levels.items()
                if cur < mn]

    def ensure_waterlines(self, service_min=None, max_per_source=None,
                          max_stall_rounds=None, max_rounds=None):
        """目标驱动补源：把低于下限的服务补齐。

        循环：
          1. 读水位 → 找出未达标服务
          2. 全达标 → 停
          3. 有缺口 → 跑一轮 refresh（重跑所有源），统计新增
          4. 连续 max_stall_rounds 轮无新增 → 视为源耗尽，停
          5. 累计跑满 max_rounds 轮 → 硬性停（防 job 单实例霸占调度器，
             给复核 / 下一轮补源留出时间；配合第 4 条双保险）
        返回 (各服务水位, 补源轮数, 是否达标)。
        """
        from config.services import MAX_STALL_ROUNDS as _DEFAULT_STALL
        from config.services import MAX_WATERLINE_ROUNDS as _DEFAULT_ROUNDS
        stall_rounds = max_stall_rounds or _DEFAULT_STALL
        max_rounds = max_rounds or _DEFAULT_ROUNDS

        levels = self.service_levels(service_min)
        rounds = 0
        stalls = 0
        while self.below_waterline(levels):
            added, _ = self.refresh(max_per_source=max_per_source)
            rounds += 1
            if rounds >= max_rounds:
                break
            if added == 0:
                stalls += 1
                if stalls >= stall_rounds:
                    break
            else:
                stalls = 0
            levels = self.service_levels(service_min)
        ok = not self.below_waterline(levels)
        return levels, rounds, ok

    def get(self, need="any", https=False, security=None, quality=None,
            fast=False, max_latency_ms=None):
        """按业务语义取一个代理（不删除）。

        need       : 'cn' | 'global' | 'any' —— 要能访问哪
        https      : True 只要支持 https 的
        security   : 'strict' 匿名+未篡改 | 'anon' 只要匿名 | None 不要求
        quality    : 'stable1'|'stable2'|'stable3' 按稳定性档位筛选
                     （stable 视为 stable1，None 不要求）
        fast       : True 只选低延迟的
        max_latency_ms : 只返回延迟不超过该值（毫秒）的代理
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
        if quality:
            # 稳定性档位：stable1/stable2/stable3 → 最低信任分
            from config.services import STABLE_LEVELS
            q = "stable1" if quality == "stable" else quality
            min_score = STABLE_LEVELS.get(q)
            if min_score:
                candidates = [p for p in candidates if p.score >= min_score]
        if fast:
            candidates = [p for p in candidates
                          if p.latency_ms is not None and p.latency_ms <= 3000]
        if max_latency_ms is not None:
            candidates = [p for p in candidates
                          if p.latency_ms is not None
                          and p.latency_ms <= max_latency_ms]
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

    def get_many(self, count=10, need="any", https=False, security=None,
                 quality=None, fast=False, max_latency_ms=None):
        """按业务语义批量取多个代理（不删除）。

        参数与 get() 一致，多一个 count（每批取的候选数放大，确保够 N 个）。
        逐个按信任分加权选优、去重，返回尽量多的匹配代理（可能少于 count）。
        """
        region = None if need in ("any", None) else need
        safe = (security == "strict")
        # 候选要多取一些，才有空间去重选优
        want = max(count, 20)
        candidates = self.pool.get_many(want, https=https, region=region,
                                        safe=safe)
        if not candidates:
            return []

        if security == "anon":
            candidates = [p for p in candidates
                          if p.anonymous in ("elite", "anonymous")]
        if quality:
            from config.services import STABLE_LEVELS
            q = "stable1" if quality == "stable" else quality
            min_score = STABLE_LEVELS.get(q)
            if min_score:
                candidates = [p for p in candidates if p.score >= min_score]
        if fast:
            candidates = [p for p in candidates
                          if p.latency_ms is not None and p.latency_ms <= 3000]
        if max_latency_ms is not None:
            candidates = [p for p in candidates
                          if p.latency_ms is not None
                          and p.latency_ms <= max_latency_ms]

        # 去重 + 按信任分加权挑 count 个（分高优先，但不绝对按分序）
        seen = set()
        picked = []
        while candidates and len(picked) < count:
            weights = [max(1, p.score + 1) for p in candidates]
            total = sum(weights)
            r = random.random() * total
            acc = 0
            idx = len(candidates) - 1
            for i, w in enumerate(weights):
                acc += w
                if r <= acc:
                    idx = i
                    break
            p = candidates.pop(idx)
            if p.proxy not in seen:
                seen.add(p.proxy)
                picked.append(p)
        return picked

    def list_all(self, page=1, size=20, https=False, need="any"):
        """分页返回池内代理明细（调试/维护用，不删除）。

        page 从 1 起；size 每页条数（默认 20，上限 100）。
        返回 (总数, 本页列表[Proxy])，按信任分降序。
        """
        region = None if need in ("any", None) else need
        proxies = self.pool.getAll(https=https)
        if region == "cn":
            proxies = [p for p in proxies if p.region == "CN"]
        elif region == "global":
            proxies = [p for p in proxies if p.region != "CN"]
        proxies.sort(key=lambda p: p.score, reverse=True)
        total = len(proxies)
        start = (page - 1) * size
        return total, proxies[start:start + size]