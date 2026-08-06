import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helper.check import Checker, MAX_FAIL_COUNT
from model.proxy import Proxy


class FakeAsyncChecker(Checker):
    """假异步验证器：不发网络请求，返回模拟结果。"""

    def __init__(self):
        super().__init__()
        self.current = ""  # 记录当前正在验证的代理，供 _async_fetch_ok 判断

    async def _check_one_async(self, proxy):
        # 用假的单代理逻辑，覆盖真实联网的 _check_one_async
        self.current = proxy.proxy
        if not self._format_check(proxy):
            proxy.fail_count += 1
            proxy.check_count += 1
            proxy.last_status = False
            return False, proxy.fail_count
        ok = proxy.proxy.endswith(":8080")
        if ok:
            proxy.https = True
            proxy.fail_count = 0
            proxy.last_status = True
        else:
            proxy.fail_count += 1
            proxy.last_status = False
            proxy.https = False
        proxy.check_count += 1
        return ok, proxy.fail_count


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

        def _https_check(self, proxy):
            return True

    c = FakeOkChecker()
    p = Proxy(proxy="1.2.3.4:8080", fail_count=5)
    ok, fc = c.check(p)
    assert ok is True
    assert fc == 0  # 成功一次就把之前的失败清零
    assert p.https is True  # http https 都通 → 支持 https


def test_https_flag_follows_https_check():
    # http 通、https 不通 → 代理可用但 https 标记为 False
    class NoHttpsChecker(Checker):
        def _http_check(self, proxy):
            return True

        def _https_check(self, proxy):
            return False

    c = NoHttpsChecker()
    p = Proxy(proxy="1.2.3.4:8080")
    ok, fc = c.check(p)
    assert ok is True
    assert p.https is False

    # http 不通 → 根本不查 https，https 保持 False
    c = FakeFailChecker()
    p = Proxy(proxy="1.2.3.4:8080", https=True)  # 旧值会被清掉
    ok, fc = c.check(p)
    assert ok is False
    assert p.https is False


def test_check_all_batch():
    c = FakeAsyncChecker()
    good = Proxy(proxy="1.2.3.4:8080", fail_count=0)
    bad = Proxy(proxy="5.6.7.8:900", fail_count=0)
    bad2 = Proxy(proxy="9.9.9.9:80", fail_count=0)

    ok_count, pairs = c.check_all([good, bad, bad2])
    assert ok_count == 1  # 只有 :8080 的通过
    assert good.fail_count == 0  # 成功 → 清零
    assert bad.fail_count == 1   # 失败 → 加一
    assert len(pairs) == 3


def test_format_check_rejects_bad_proxy():
    # 格式不合法（缺端口），根本不该发网络请求就直接判失败
    c = FakeFailChecker()
    bad = Proxy(proxy="不是代理格式", fail_count=0)
    ok, fc = c.check(bad)
    assert ok is False
    assert fc == 1

    # 合法格式但连不通（假验证器判失败）→ fail_count 照常累计
    valid = Proxy(proxy="1.2.3.4:8080", fail_count=0)
    ok, fc = c.check(valid)
    assert ok is False
    assert fc == 1


if __name__ == "__main__":
    for fn in [test_failure_count_grows, test_elimination_after_max_fail,
               test_success_resets_fail_count, test_format_check_rejects_bad_proxy,
               test_https_flag_follows_https_check, test_check_all_batch]:
        fn()
        print(f"{fn.__name__} OK")
    print("ALL PASSED")