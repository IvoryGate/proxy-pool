import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.redis_client import RedisPool
from model.proxy import Proxy


def make(pool):
    pool.clear()
    pool.put(Proxy(proxy="1.2.3.4:8080", https=False))
    pool.put(Proxy(proxy="5.6.7.8:900", https=True))
    pool.put(Proxy(proxy="9.9.9.9:80", https=True))


def _pool():
    # 测试用独立 Redis db（db=15），避免污染生产池（db=0）
    from db.redis_client import RedisPool
    return RedisPool(db=15)


def test_count():
    pool = _pool()
    make(pool)
    c = pool.count()
    # region 空 → 全进 global；anonymous 空 → 都不 safe
    assert c["total"] == 3
    assert c["https"] == 2
    assert c["global"] == 3
    assert c["cn"] == 0
    assert c["safe"] == 0
    pool.clear()


def test_get_https_only():
    pool = _pool()
    make(pool)
    got = pool.get(https=True)
    assert got is not None
    assert got.https is True
    pool.clear()


def test_pop_deletes():
    pool = _pool()
    make(pool)
    popped = pool.pop()
    assert popped is not None
    assert pool.count()["total"] == 2
    pool.clear()


def test_getAll_https_filter():
    pool = _pool()
    make(pool)
    all_https = pool.getAll(https=True)
    assert all(x.https for x in all_https)
    assert len(all_https) == 2
    pool.clear()


def test_bucket_filters():
    pool = _pool()
    pool.clear()
    pool.put(Proxy(proxy="1.2.3.4:8080", region="CN", https=True,
                   anonymous="elite", tampered=False))   # 国内安全
    pool.put(Proxy(proxy="2.2.2.2:88", region="CN", anonymous="transparent"))  # 国内透明
    pool.put(Proxy(proxy="3.3.3.3:80", region="", anonymous="elite"))  # 国外安全
    # 取国内
    g = pool.get(region="cn")
    assert g is not None and g.region == "CN"
    # 取国外
    g = pool.get(region="global")
    assert g is not None and g.region != "CN"
    # 取安全
    g = pool.get(safe=True)
    assert g is not None and g.anonymous == "elite" and not g.tampered
    # 取"国内且安全"：只有 1.2.3.4
    g = pool.get(region="cn", safe=True)
    assert g is not None and g.proxy == "1.2.3.4:8080"
    pool.clear()


if __name__ == "__main__":
    for fn in [test_count, test_get_https_only, test_pop_deletes,
               test_getAll_https_filter, test_bucket_filters]:
        fn()
        print(f"{fn.__name__} OK")
    print("ALL PASSED")