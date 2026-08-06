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


def test_count():
    pool = RedisPool()
    make(pool)
    c = pool.count()
    assert c == {"total": 3, "https": 2}
    pool.clear()


def test_get_https_only():
    pool = RedisPool()
    make(pool)
    got = pool.get(https=True)
    assert got is not None
    assert got.https is True
    pool.clear()


def test_pop_deletes():
    pool = RedisPool()
    make(pool)
    popped = pool.pop()
    assert popped is not None
    assert pool.count()["total"] == 2
    pool.clear()


def test_getAll_https_filter():
    pool = RedisPool()
    make(pool)
    all_https = pool.getAll(https=True)
    assert all(x.https for x in all_https)
    assert len(all_https) == 2
    pool.clear()


if __name__ == "__main__":
    for fn in [test_count, test_get_https_only, test_pop_deletes,
               test_getAll_https_filter]:
        fn()
        print(f"{fn.__name__} OK")
    print("ALL PASSED")