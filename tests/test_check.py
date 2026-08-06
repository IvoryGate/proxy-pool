import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helper.check import Checker, MAX_FAIL_COUNT
from model.proxy import Proxy


class FakeFailChecker(Checker):
    """假验证器：永远判失败，用来测淘汰逻辑（不依赖网络）。"""

    def _http_check(self, proxy):
        return False


def test_failure_count_grows():
    c = FakeFailChecker()
    p = Proxy(proxy="1.2.3.4:9999", fail_count=0, check_count=0)
    ok, fc = c.check(p)
    assert ok is False
    assert fc == 1


def test_elimination_after_max_fail():
    c = FakeFailChecker()
    p = Proxy(proxy="1.2.3.4:9999", fail_count=0)
    # 连续失败 MAX_FAIL_COUNT 次
    for _ in range(MAX_FAIL_COUNT):
        c.check(p)
    # 还没到淘汰线（fail_count == MAX_FAIL_COUNT）
    assert c.should_eliminate(p.fail_count) is False
    # 再失败一次，越过阈值 → 该淘汰
    c.check(p)
    assert c.should_eliminate(p.fail_count) is True


def test_success_resets_fail_count():
    class FakeOkChecker(Checker):
        def _http_check(self, proxy):
            return True

    c = FakeOkChecker()
    p = Proxy(proxy="1.2.3.4:8080", fail_count=5)
    ok, fc = c.check(p)
    assert ok is True
    assert fc == 0  # 成功一次就把之前的失败清零


if __name__ == "__main__":
    for fn in [test_failure_count_grows, test_elimination_after_max_fail,
               test_success_resets_fail_count]:
        fn()
        print(f"{fn.__name__} OK")
    print("ALL PASSED")