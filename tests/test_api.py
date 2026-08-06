import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.proxy import Proxy


class FakeService:
    def __init__(self):
        self.pop_https = None
        self.get_https = None

    def get(self, https=False):
        self.get_https = https
        return Proxy(proxy="1.2.3.4:8080")

    def pop(self, https=False):
        self.pop_https = https
        return Proxy(proxy="5.6.7.8:900")

    def count(self):
        return {"total": 2, "https": 1}


class EmptyService(FakeService):
    def get(self, https=False):
        return None

    def pop(self, https=False):
        return None


def test_get_returns_proxy():
    from api.proxy_api import create_app

    svc = FakeService()
    client = create_app(svc).test_client()

    r = client.get("/get")
    assert r.status_code == 200
    assert r.get_json()["data"] == "1.2.3.4:8080"


def test_get_https_passes_flag():
    from api.proxy_api import create_app

    svc = FakeService()
    client = create_app(svc).test_client()

    client.get("/get?type=https")
    assert svc.get_https is True


def test_pop_returns_and_pops():
    from api.proxy_api import create_app

    svc = FakeService()
    client = create_app(svc).test_client()

    r = client.get("/pop")
    assert r.status_code == 200
    assert r.get_json()["data"] == "5.6.7.8:900"


def test_empty_pool_404():
    from api.proxy_api import create_app

    client = create_app(EmptyService()).test_client()
    r = client.get("/get")
    assert r.status_code == 404


if __name__ == "__main__":
    tests = [test_get_returns_proxy, test_get_https_passes_flag,
             test_pop_returns_and_pops, test_empty_pool_404]
    for t in tests:
        t()
        print(f"{t.__name__} OK")
    print("ALL PASSED")