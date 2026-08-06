import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.proxy import Proxy


class FakeChecker:
    """假验证器：控制哪些代理通过/失败，不发网络请求。"""

    def __init__(self, good_set, max_fail=3):
        self.good = good_set      # 验证通过的 ip:port 集合
        self.max_fail = max_fail

    def check_all(self, proxies):
        for p in proxies:
            if p.proxy in self.good:
                p.last_status = True
                p.fail_count = 0
            else:
                p.last_status = False
                p.fail_count += 1
            p.check_count += 1

    def should_eliminate(self, fail_count):
        return fail_count > self.max_fail


class FakePool:
    """内存字典模拟 Redis 池子。"""

    def __init__(self):
        self.store = {}

    def getAll(self):
        return list(self.store.values())

    def put(self, proxy):
        self.store[proxy.proxy] = proxy

    def delete(self, proxy):
        self.store.pop(proxy.proxy, None)

    def get_many(self, count=10, https=False, region=None, safe=False):
        out = []
        for p in self.store.values():
            if https and not p.https:
                continue
            if region == "cn" and p.region != "CN":
                continue
            if region == "global" and p.region == "CN":
                continue
            if safe and not (p.anonymous == "elite" and not p.tampered):
                continue
            out.append(p)
            if len(out) >= count:
                break
        return out


def test_check_pool_eliminates_dead():
    from handler.proxy_service import ProxyService

    # 池里有 3 个：一个活、一个失败几次、一个已死很久
    alive = Proxy(proxy="1.1.1.1:80", fail_count=0, last_status=True)
    retry = Proxy(proxy="2.2.2.2:80", fail_count=2, last_status=False)  # 没超阈值
    dead = Proxy(proxy="3.3.3.3:80", fail_count=3, last_status=False)   # 再失败就超

    pool = FakePool()
    for p in [alive, retry, dead]:
        pool.put(p)

    # alive 通过，retry/dead 失败
    checker = FakeChecker(good_set={"1.1.1.1:80"}, max_fail=3)

    service = ProxyService(checker=checker, pool=pool)
    checked, eliminated = service.check_pool()

    assert checked == 3
    assert eliminated == 1                    # 只淘汰 dead
    assert "3.3.3.3:80" not in pool.store      # dead 被删
    assert "1.1.1.1:80" in pool.store          # alive 保留
    assert "2.2.2.2:80" in pool.store          # retry 保留（给机会）


def test_get_business_semantics():
    from handler.proxy_service import ProxyService

    pool = FakePool()
    pool.put(Proxy(proxy="1.1.1.1:80", region="CN", https=True,
                   anonymous="elite", tampered=False, score=5))
    pool.put(Proxy(proxy="2.2.2.2:80", region="CN", anonymous="transparent",
                   score=1))   # 透明，不安全
    pool.put(Proxy(proxy="3.3.3.3:80", region="", https=True,
                   anonymous="elite", tampered=True, score=3))  # 被篡改

    svc = ProxyService(checker=FakeChecker(set()), pool=pool)

    # 要国内安全的：只有 1.1.1.1 满足
    p = svc.get(need="cn", security="strict")
    assert p is not None and p.proxy == "1.1.1.1:80"

    # 要国外：3.3.3.3 虽是 elite 但 tampered=True，strict 排除它
    p = svc.get(need="global", security="strict")
    assert p is None  # 唯一国外的是被篡改的

    # 国外但不要求安全 → 能拿到 3.3.3.3
    p = svc.get(need="global")
    assert p is not None and p.proxy == "3.3.3.3:80"

    # 要 https 的国内 → 1.1.1.1
    p = svc.get(need="cn", https=True)
    assert p is not None and p.https is True


def test_get_stable_quality():
    from handler.proxy_service import ProxyService

    pool = FakePool()
    pool.put(Proxy(proxy="1.1.1.1:80", score=0))   # 不够稳
    pool.put(Proxy(proxy="2.2.2.2:80", score=5))   # 稳

    svc = ProxyService(checker=FakeChecker(set()), pool=pool)
    p = svc.get(quality="stable")
    assert p is not None and p.proxy == "2.2.2.2:80"


if __name__ == "__main__":
    test_check_pool_eliminates_dead()
    test_get_business_semantics()
    test_get_stable_quality()
    print("test_check_pool_eliminates_dead OK")
    print("test_get_business_semantics OK")
    print("test_get_stable_quality OK")
    print("ALL PASSED")