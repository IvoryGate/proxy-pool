"""校验器：判断一个代理是否可用，并维护淘汰计数。

核心思路：
  1. 通过代理向测试目标(http://www.baidu.com)发请求
  2. 拿到 200 → 可用，fail_count 归零
  3. 超时/异常 → 不可用，fail_count +1
  4. fail_count 超过阈值(MAX_FAIL_COUNT) → 判定该淘汰

参考资料：learn/02_httpx_代理验证入门.py（httpx 用法与踩坑）
"""

import re

import httpx

# 测试目标：我们判别"代理能否访问外网"的基准站点
HTTP_URL = "http://www.baidu.com"
# 请求超时：超过就不等了，算失败
TIMEOUT = 5
# 淘汰阈值：连续失败超过这个数，就认为代理死了
MAX_FAIL_COUNT = 3
# ip:port 合法格式正则（如 1.2.3.4:8080）
PROXY_FORMAT = re.compile(
    r'^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$')


class Checker:
    def check(self, proxy):
        """验证一个 proxy，返回它的最新状态（把 fail_count 更新到内部）。

        注意：这里是纯验证，只返回 (成功与否, 失败次数)，不决定是否删除，
        删除与否由调用方（调度器）依据 MAX_FAIL_COUNT 决定。
        """
        # 前置：格式不合法根本不用发网络请求，直接判失败
        if not self._format_check(proxy):
            proxy.fail_count += 1
            proxy.check_count += 1
            return False, proxy.fail_count

        ok = self._http_check(proxy)
        if ok:
            proxy.fail_count = 0
        else:
            proxy.fail_count += 1
        proxy.check_count += 1
        return ok, proxy.fail_count

    def should_eliminate(self, fail_count):
        """判断该代理是否该被淘汰。"""
        return fail_count > MAX_FAIL_COUNT

    def _format_check(self, proxy):
        """格式校验：ip:port 是否合法。不合法根本没理由发网络请求。"""
        return bool(PROXY_FORMAT.match(proxy.proxy))

    def _http_check(self, proxy):
        """通过代理访问 HTTP_URL，能拿到 200 就返回 True。"""
        proxy_url = f"http://{proxy.proxy}"
        try:
            r = httpx.get(HTTP_URL, proxy=proxy_url, timeout=TIMEOUT, verify=False)
            return r.status_code == 200
        except Exception:
            return False