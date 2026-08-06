"""粘性策略：同一会话(session)尽量复用同一个代理。

场景：登录态、反爬会话、长任务 —— 换 IP 反而坏事。
行为：
  - session 第一次来：从候选里挑一个，记下 (session, 筛选条件) → proxy
  - 之后再来：若上次给的代理还在候选里（没死/没被淘汰），继续给同一个
  - 若上次的不在了：换一个新的并更新记录
记录存在 self.record（进程内），单机够用。
"""

from strategy.base import BaseStrategy


class StickyStrategy(BaseStrategy):
    name = "sticky"

    def get(self, service, session=None, **params):
        if not session:
            # 没给 session，粘性无从谈起，退化为随机
            return service.get(**params)

        if self.record is None:
            self.record = {}

        key = (session, self._filter_key(params))
        last = self.record.get(key)

        # 先看看候选里上次那个还活着吗
        candidates = service.pool.get_many(50, **self._pool_kwargs(params))
        pool_keys = {p.proxy for p in candidates}

        if last in pool_keys:
            return next(p for p in candidates if p.proxy == last)

        # 换个新的：优先信任分高的
        if candidates:
            chosen = max(candidates, key=lambda p: p.score)
            self.record[key] = chosen.proxy
            return chosen
        return None

    @staticmethod
    def _filter_key(params):
        """把会影响"候选范围"的参数摘出来，形成粘性 key 的一部分。"""
        return tuple(sorted(k for k in params if k != "session"))

    @staticmethod
    def _pool_kwargs(params):
        """把 params 转成 pool.get_many 能用的 kwargs。"""
        kwargs = {}
        need = params.get("need")
        if need and need != "any":
            kwargs["region"] = need
        if params.get("https"):
            kwargs["https"] = True
        if params.get("security") == "strict":
            kwargs["safe"] = True
        return kwargs
