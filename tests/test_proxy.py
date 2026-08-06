import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis
from model.proxy import Proxy


def test_proxy_roundtrip():
    p = Proxy(proxy="1.2.3.4:8080", https=True, fail_count=2, source="daili66")
    r = redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

    r.hset("use_proxy", p.proxy, p.to_json())
    raw = r.hget("use_proxy", p.proxy)

    restored = Proxy.create_from_json(raw)
    assert restored.proxy == p.proxy
    assert restored.https == p.https
    assert restored.fail_count == p.fail_count
    assert restored.source == p.source

    r.hdel("use_proxy", p.proxy)
    print("roundtrip OK")


if __name__ == "__main__":
    test_proxy_roundtrip()