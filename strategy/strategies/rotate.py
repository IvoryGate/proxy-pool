"""轮换策略：尽量不重复、轮流给不同的代理。

场景：批量采集 —— 希望均匀分摊到所有代理，别老用那几个。
行为：
  - 维护一个"最近给过"的名单（进程内）
  - 优先给候选里"最近没给过"的；候选太少则允许复用
  - 给过的记录上限 100 个，防止无限膨胀
"""

from strategy.base import BaseStrategy


class RotateStrategy(BaseStrategy):
    name = "rotate"

    def __init__(self):
        super().__init__()
        self._recent = []   # 最近给过的代理，新的在前
        self._MAX_RECENT = 100

    def get(self, service, **params):
        candidates = service.pool.get_many(50, **self._pool_kwargs(params))
        if not candidates:
            return None

        recent_set = set(self._recent)
        fresh = [p for p in candidates if p.proxy not in recent_set]
        # 尽量给没给过的；没有就给所有候选里信任分最高的（但别老给同一个）
        if fresh:
            chosen = max(fresh, key=lambda p: p.score)
        else:
            chosen = candidates[len(self._recent) % len(candidates)]

        self._recent.insert(0, chosen.proxy)
        if len(self._recent) > self._MAX_RECENT:
            self._recent = self._recent[:self._MAX_RECENT]
        return chosen

    @staticmethod
    def _pool_kwargs(params):
        kwargs = {}
        need = params.get("need")
        if need and need != "any":
            kwargs["region"] = need
        if params.get("https"):
            kwargs["https"] = True
        if params.get("security") == "strict":
            kwargs["safe"] = True
        return kwargs
