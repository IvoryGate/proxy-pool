"""取用策略基类：定义"所有取用策略必须具备的统一接口"。

与 fetcher 的 BaseFetcher 同构 —— 一个策略就是一个可插拔模块：
  - 接口统一：实现 get(service, **params)，返回一个 Proxy 或 None
  - 目录扫描：manager 自动发现 strategies/ 下所有策略
  - 加新策略 = 放一个文件，零侵入

每个策略只回答一个问题：给定 service（能拿候选的代理池服务），
按自己的"吐法"挑一个出来。random 随机，sticky 粘会话，rotate 轮换。
"""


class BaseStrategy:
    name = ""   # 策略唯一标识，如 "random"、"sticky"

    def __init__(self):
        self.record = None   # 策略的持久化状态（粘会话/游标等），可被 manager 复用

    def get(self, service, **params):
        """按本策略取一个代理。service 提供 get_many 等候选能力。

        返回 Proxy 或 None（没合适的）。
        """
        raise NotImplementedError
