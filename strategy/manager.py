"""取用策略注册中心：自动扫描 strategies/ 目录，按 name 分发。

与 fetcher/manager.py 同构 —— 加一个新策略 = 在 strategies/ 下放一个
继承 BaseStrategy 的文件，manager 自动发现，API 按 mode 参数分发。
"""

import importlib
import os

from strategy.base import BaseStrategy


def _discover_strategy_classes():
    """扫描 strategies/ 目录，返回所有继承 BaseStrategy 的类。"""
    strategies_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "strategies")
    classes = []
    if not os.path.isdir(strategies_dir):
        return classes
    for filename in sorted(os.listdir(strategies_dir)):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue
        module_name = f"strategy.strategies.{filename[:-3]}"
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and issubclass(attr, BaseStrategy)
                    and attr is not BaseStrategy and attr.name):
                classes.append(attr)
    return classes


class StrategyManager:
    def __init__(self):
        self._registry = {}
        self._instances = {}
        for cls in _discover_strategy_classes():
            self._registry[cls.name] = cls

    def list_strategies(self):
        return sorted(self._registry.keys())

    def get(self, service, mode="random", **params):
        """按 mode 分发到具体策略取一个代理。mode 不存在时回退 random。"""
        if mode not in self._registry:
            mode = "random"
        if mode not in self._instances:
            self._instances[mode] = self._registry[mode]()
        return self._instances[mode].get(service, **params)