"""取用策略测试：验证 manager 自动发现 + 各策略吐法（不联网）。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from model.proxy import Proxy
from strategy.manager import StrategyManager, _discover_strategy_classes
from test_proxy_service import FakePool
from handler.proxy_service import ProxyService


def _service_with_proxies(proxies):
    pool = FakePool()
    for p in proxies:
        pool.put(p)
    return ProxyService(checker=None, pool=pool), pool


def test_discover_strategies():
    names = sorted(c.name for c in _discover_strategy_classes())
    assert names == ["random", "rotate", "sticky"], names


def test_manager_random_fallback():
    m = StrategyManager()
    svc, pool = _service_with_proxies([
        Proxy(proxy="1.1.1.1:80", region="CN", score=2),
        Proxy(proxy="2.2.2.2:80", region="CN", score=5),
    ])
    # 未知 mode → 回退 random
    p = m.get(svc, mode="not_exist", need="cn")
    assert p is not None and p.region == "CN"


def test_sticky_reuses_same():
    m = StrategyManager()
    svc, pool = _service_with_proxies([
        Proxy(proxy="1.1.1.1:80", region="CN", score=5),
        Proxy(proxy="2.2.2.2:80", region="CN", score=4),
    ])
    first = m.get(svc, mode="sticky", session="s1", need="cn")
    second = m.get(svc, mode="sticky", session="s1", need="cn")
    assert first.proxy == second.proxy  # 同会话保持同一个


def test_sticky_switches_when_gone():
    m = StrategyManager()
    svc, pool = _service_with_proxies([
        Proxy(proxy="1.1.1.1:80", region="CN", score=5),
    ])
    first = m.get(svc, mode="sticky", session="s1", need="cn")
    assert first.proxy == "1.1.1.1:80"
    # 代理被淘汰（从池里删除）
    pool.delete(first)
    second = m.get(svc, mode="sticky", session="s1", need="cn")
    assert second is None or second.proxy != first.proxy


def test_rotate_spreads():
    m = StrategyManager()
    svc, pool = _service_with_proxies([
        Proxy(proxy="1.1.1.1:80", score=5),
        Proxy(proxy="2.2.2.2:80", score=5),
        Proxy(proxy="3.3.3.3:80", score=5),
    ])
    got = {m.get(svc, mode="rotate").proxy for _ in range(3)}
    # 三次尽量拿全 3 个不同代理
    assert len(got) == 3, got


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "OK")
    print("ALL PASSED")