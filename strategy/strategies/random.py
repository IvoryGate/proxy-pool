"""随机策略：从符合业务条件的候选里，按信任分加权随机挑一个。

这是默认策略，行为等于原来的 service.get —— 加权随机保证
"稳定代理更容易被选中"，而不是纯均匀随机。
"""

from strategy.base import BaseStrategy


class RandomStrategy(BaseStrategy):
    name = "random"

    # service.get 认识的参数（其余如 session 不传给随机策略）
    _SERVICE_PARAMS = ("need", "https", "security", "quality", "fast")

    def get(self, service, **params):
        service_kwargs = {k: params[k] for k in self._SERVICE_PARAMS
                          if k in params}
        return service.get(**service_kwargs)
