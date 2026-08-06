import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model.proxy import Proxy


class FakeService:
    def __init__(self):
        self.pop_https = None
        self.get_https = None
        self.last_kwargs = None

    def get(self, https=False, **kwargs):
        self.get_https = https
        self.last_kwargs = kwargs
        return Proxy(proxy="1.2.3.4:8080")

    def pop(self, https=False, **kwargs):
        self.pop_https = https
        return Proxy(proxy="5.6.7.8:900")

    def count(self):
        return {"total": 2, "https": 1}


class EmptyService(FakeService):
    def get(self, https=False, **kwargs):
        return None

    def pop(self, https=False, **kwargs):
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


def test_get_passes_business_params():
    from api.proxy_api import create_app

    svc = FakeService()
    client = create_app(svc).test_client()

    client.get("/get?need=cn&security=strict&fast=1")
    k = svc.last_kwargs
    assert k["need"] == "cn"
    assert k["security"] == "strict"
    assert k["fast"] is True


def test_strategies_list():
    from api.proxy_api import create_app

    svc = FakeService()
    client = create_app(svc).test_client()
    r = client.get("/strategies")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert "random" in data and "sticky" in data and "rotate" in data


if __name__ == "__main__":
    tests = [test_get_returns_proxy, test_get_https_passes_flag,
             test_pop_returns_and_pops, test_empty_pool_404,
             test_get_passes_business_params, test_strategies_list]
    for t in tests:
        t()
        print(f"{t.__name__} OK")
    print("ALL PASSED")