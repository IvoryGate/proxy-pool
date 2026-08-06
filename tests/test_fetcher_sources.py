"""网页源解析逻辑单元测试（不联网，用假 HTML 验证抠取正确性）。"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fetcher.sources.ip3366 import Ip3366Fetcher
from fetcher.sources.ip89 import Ip89Fetcher


def _p(F, body_html):
    """用一个返回假 HTML 的源，抓取所有代理。"""
    src = F()
    src._http_get = lambda url, **k: type("R", (), {"text": body_html})()
    return list(src.fetch())


def test_ip3366_parses_table():
    body = ("<tr><td>1.2.3.4</td><td>8080</td></tr>"
            "<tr><td>5.6.7.8</td><td>3128</td></tr>")
    assert _p(Ip3366Fetcher, body) == ["1.2.3.4:8080", "5.6.7.8:3128"]


def test_ip89_parses_table():
    body = ("<tr><td>9.9.9.9</td><td>80</td></tr>")
    assert _p(Ip89Fetcher, body) == ["9.9.9.9:80"]


def test_dedup():
    body = ("<tr><td>1.2.3.4</td><td>80</td></tr>"
            "<tr><td>1.2.3.4</td><td>80</td></tr>")
    assert _p(Ip3366Fetcher, body) == ["1.2.3.4:80"]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "OK")
    print("ALL PASSED")