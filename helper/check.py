"""校验器：判断一个代理是否可用，并维护淘汰计数，记录 https 能力。

核心思路：
  1. 格式校验：ip:port 合不合法（不合规直接失败，不发网络请求）
  2. http 校验：通过代理访问 HTTP_URL，拿到 200 → 可用
  3. https 校验：http 过了才验（通过代理访问 HTTPS_URL），决定 proxy.https
  4. 失败累计 fail_count，超过阈值(MAX_FAIL_COUNT) → 判定该淘汰

验证目标（HTTP_URL / HTTPS_URL）做成可配置：默认 baidu 测国内存活、
qq 测 https。以后想换目标（如国外站），改这里或传入即可。

参考资料：learn/02_httpx_代理验证入门.py（httpx 用法与踩坑）
"""

import re

import httpx

# 默认验证目标（可被构造函数覆盖）
HTTP_URL = "http://www.baidu.com"
HTTPS_URL = "https://www.qq.com"
# 请求超时：超过就不等了，算失败
TIMEOUT = 5
# 淘汰阈值：连续失败超过这个数，就认为代理死了
MAX_FAIL_COUNT = 3
# ip:port 合法格式正则（如 1.2.3.4:8080）
PROXY_FORMAT = re.compile(
    r'^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$')


class Checker:
    def __init__(self, http_url=HTTP_URL, https_url=HTTPS_URL,
                 timeout=TIMEOUT):
        self.http_url = http_url
        self.https_url = https_url
        self.timeout = timeout

    def check(self, proxy):
        """验证一个 proxy，更新其状态（fail_count / https / check_count）。

        返回 (是否可用, fail_count)。
        是否删除由调用方（调度器）依据 MAX_FAIL_COUNT 决定。
        """
        # 前置：格式不合法根本不用发网络请求，直接判失败
        if not self._format_check(proxy):
            proxy.fail_count += 1
            proxy.check_count += 1
            proxy.last_status = False
            return False, proxy.fail_count

        http_ok = self._http_check(proxy)
        if http_ok:
            # http 可用 → 进一步查它是否支持 https
            proxy.https = self._https_check(proxy)
            proxy.fail_count = 0
            proxy.last_status = True
        else:
            proxy.fail_count += 1
            proxy.last_status = False
            proxy.https = False
        proxy.check_count += 1
        return http_ok, proxy.fail_count

    def should_eliminate(self, fail_count):
        """判断该代理是否该被淘汰。"""
        return fail_count > MAX_FAIL_COUNT

    def _format_check(self, proxy):
        """格式校验：ip:port 是否合法。不合法根本没理由发网络请求。"""
        return bool(PROXY_FORMAT.match(proxy.proxy))

    def _http_check(self, proxy):
        """通过代理访问 http 目标，能拿到 200 就返回 True。"""
        return self._fetch_ok(self.http_url, proxy.proxy)

    def _https_check(self, proxy):
        """通过代理访问 https 目标，能拿到 200 就返回 True（支持 https）。"""
        return self._fetch_ok(self.https_url, proxy.proxy)

    def _fetch_ok(self, url, proxy_addr):
        proxy_url = f"http://{proxy_addr}"
        try:
            r = httpx.get(url, proxy=proxy_url, timeout=self.timeout,
                          verify=False)
            return r.status_code == 200
        except Exception:
            return False