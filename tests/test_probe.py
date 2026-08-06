"""探针逻辑单元测试：不联网，用假响应验证判定正确性。"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from helper import probe


class FakeResp:
    def __init__(self, text="", content=b""):
        self.text = text
        self.content = content


def test_anonymity_elite():
    # 目标看到了代理自己的 IP → 高匿
    probe._get = lambda url, proxy_addr=None: FakeResp("1.2.3.4")
    ok, seen = probe.check_anonymity("1.2.3.4:8080")
    assert ok is True and seen == "1.2.3.4"


def test_anonymity_transparent():
    # 目标看到的 IP 不是代理的 → 透明代理，泄露真实 IP
    probe._get = lambda url, proxy_addr=None: FakeResp("9.9.9.9")
    ok, seen = probe.check_anonymity("1.2.3.4:8080")
    assert ok is False and seen == "9.9.9.9"


def test_tamper_detected():
    # 走代理内容与直连不同 → 篡改
    probe._get = lambda url, proxy_addr=None: (
        FakeResp(content=b"A" * 100) if proxy_addr is None
        else FakeResp(content=b"B" * 100))
    ok, _ = probe.check_tamper("1.2.3.4:8080")
    assert ok is False


def test_tamper_clean():
    # 走代理与直连内容一致 → 未篡改
    probe._get = lambda url, proxy_addr=None: FakeResp(content=b"clean")
    ok, _ = probe.check_tamper("1.2.3.4:8080")
    assert ok is True


def test_tamper_direct_fail_passes():
    # 直连失败 → 保守通过，不冤枉代理
    probe._get = lambda url, proxy_addr=None: None
    ok, _ = probe.check_tamper("1.2.3.4:8080")
    assert ok is True


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(name, "OK")
    print("ALL PASSED")