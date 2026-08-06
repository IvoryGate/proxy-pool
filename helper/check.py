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

import asyncio
import re

import httpx

from helper import probe

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

# 按区域分流验证目标：国内代理测国内站（baidu），
# 其它（国外/未知）代理测国际站（youtube）。区域不对口才失败，
# 而不是代理本身死了 —— 国外代理连不上 baidu 不代表它没用。
REGION_TARGETS = {
    "CN":  {"http": "http://www.baidu.com",  "https": "https://www.qq.com"},
    "GLOBAL": {"http": "http://www.youtube.com", "https": "https://www.youtube.com"},
}


class Checker:
    def __init__(self, region_targets=None, timeout=TIMEOUT,
                 probe_safety=True):
        self.region_targets = region_targets or REGION_TARGETS
        self.timeout = timeout
        # 安全/质量探针开关：默认开。测试关掉（探针要联网，测试不依赖网络）。
        self.probe_safety = probe_safety

    def _targets_for(self, proxy):
        """按代理区域选择验证目标。区域为 CN → 国内，否则 → 国际。"""
        key = "CN" if proxy.region == "CN" else "GLOBAL"
        return self.region_targets[key]

    # ---------- 同步单个验证（测试/单代理场景友好） ----------

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
        self._update_score(proxy, http_ok)

        if http_ok and self.probe_safety:
            self._probe_safety(proxy)
            self._measure_latency_sync(proxy)

        return http_ok, proxy.fail_count

    # ---------- 异步批量验证（生产用：整批并发，快一个量级） ----------

    def check_all(self, proxies):
        """并发验证一批 proxy，逐个更新各自状态。

        返回 (可用数量, 总列表)。内部用 asyncio 把所有验证同时发出去，
        总耗时 ≈ 最慢那一个，而不是"数量 × 单个耗时"。

        参考：learn/03_并发验证.py
        """
        return asyncio.run(self._check_all_async(list(proxies)))

    async def _check_all_async(self, proxies):
        # 每个代理用它自己的代理地址建独立 AsyncClient（proxy 必须挂 client 而非请求）
        results = await asyncio.gather(
            *(self._check_one_async(p) for p in proxies))
        ok_count = sum(1 for ok, _ in results if ok)
        return ok_count, list(zip(proxies, results))

    async def _check_one_async(self, proxy):
        """异步验证单个 proxy（格式 + http + https），更新其状态。"""
        if not self._format_check(proxy):
            proxy.fail_count += 1
            proxy.check_count += 1
            proxy.last_status = False
            return False, proxy.fail_count

        proxy_url = f"http://{proxy.proxy}"
        # 走代理的请求：proxy 必须作为 AsyncClient 参数，请求级不能传
        async with httpx.AsyncClient(proxy=proxy_url, timeout=self.timeout,
                                     verify=False) as client:
            targets = self._targets_for(proxy)
            http_ok = await self._async_fetch_ok(client, targets["http"])
            if http_ok:
                proxy.https = await self._async_fetch_ok(client, targets["https"])
                proxy.fail_count = 0
                proxy.last_status = True
            else:
                proxy.fail_count += 1
                proxy.last_status = False
                proxy.https = False
        proxy.check_count += 1
        self._update_score(proxy, http_ok)

        # 存活通过后，做安全/质量探测（只打标签，不参与淘汰）
        if http_ok and self.probe_safety:
            self._probe_safety(proxy)
            await self._measure_latency(proxy)

        return http_ok, proxy.fail_count

    def _update_score(self, proxy, ok):
        """更新信任分：成功 +1，失败 -1。累计反映长期稳定性。

        注意：fail_count 是"连续失败"，会被重置；score 是"累计信任"，
        不因一次成功清零，能反映代理长期靠不靠谱。
        """
        proxy.score = max(0, proxy.score + (1 if ok else -1))

    def _probe_safety(self, proxy):
        """安全探测：匿名性 + 篡改，只打标签不判生死。

        结果写入 proxy.anonymous（真实检测）和 proxy.tampered。
        """
        anon_ok, seen_ip = probe.check_anonymity(proxy.proxy)
        if seen_ip is not None:
            # 能拿到"目标看到的IP"才下结论；拿不到就保留源标签不动
            proxy.anonymous = "elite" if anon_ok else "transparent"
        tamper_ok, _ = probe.check_tamper(proxy.proxy)
        proxy.tampered = not tamper_ok

    async def _measure_latency(self, proxy):
        """异步延迟测量：记录到目标站的首字节耗时（毫秒）。"""
        try:
            targets = self._targets_for(proxy)
            async with httpx.AsyncClient(proxy=f"http://{proxy.proxy}",
                                         timeout=self.timeout) as client:
                start = asyncio.get_event_loop().time()
                await client.get(targets["http"])
                proxy.latency_ms = int(
                    (asyncio.get_event_loop().time() - start) * 1000)
        except Exception:
            proxy.latency_ms = None

    def _measure_latency_sync(self, proxy):
        """同步延迟测量：记录到目标站的首字节耗时（毫秒）。"""
        try:
            targets = self._targets_for(proxy)
            start = asyncio.get_event_loop().time()
            httpx.get(targets["http"], proxy=f"http://{proxy.proxy}",
                      timeout=self.timeout)
            proxy.latency_ms = int(
                (asyncio.get_event_loop().time() - start) * 1000)
        except Exception:
            proxy.latency_ms = None

    async def _async_fetch_ok(self, client, url):
        try:
            r = await client.get(url)
            return r.status_code == 200
        except Exception:
            return False

    def should_eliminate(self, fail_count):
        """判断该代理是否该被淘汰。"""
        return fail_count > MAX_FAIL_COUNT

    def _format_check(self, proxy):
        """格式校验：ip:port 是否合法。不合法根本没理由发网络请求。"""
        return bool(PROXY_FORMAT.match(proxy.proxy))

    def _http_check(self, proxy):
        """通过代理访问 http 目标，能拿到 200 就返回 True。"""
        return self._fetch_ok(self._targets_for(proxy)["http"], proxy.proxy)

    def _https_check(self, proxy):
        """通过代理访问 https 目标，能拿到 200 就返回 True（支持 https）。"""
        return self._fetch_ok(self._targets_for(proxy)["https"], proxy.proxy)

    def _fetch_ok(self, url, proxy_addr):
        proxy_url = f"http://{proxy_addr}"
        try:
            r = httpx.get(url, proxy=proxy_url, timeout=self.timeout,
                          verify=False)
            return r.status_code == 200
        except Exception:
            return False