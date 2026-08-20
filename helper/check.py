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
# 存活验证用纯 IP 回显：内容校验有效（拦截劫持代理/Cloudflare假代理），
# 且国内外网络都可达。原用 api.ipify.org，2026-08 起该域名在国内
# Connection refused（验证全灭 → 池子大缩水），改用 ip.3322.net
# （国内 3322 服务，http/https 均返回纯 IP，本机实测可达）。
HTTP_URL = "http://ip.3322.net"
HTTPS_URL = "https://ip.3322.net"
# 真实转发确认目标：能访问真实网站才算可用（拦"能回显但不转发"的伪代理）
REALITY_URL = "http://www.baidu.com"
REALITY_HTML_MARK = b"baidu"
# 请求超时：超过就不等了，算失败。
# 5s→3s：池里近 99% 是死代理，降超时让它们快速失败，全量验证提速明显。
# 免费代理延迟普遍 <1s，3s 足够覆盖活的；代价是极慢的活代理可能被误杀。
TIMEOUT = 3
# 淘汰阈值：连续失败超过这个数，就认为代理死了。
# 3→5：免费代理波动大（网络抖动/目标站限流），连续 3 次失败很容易误删
# 其实还活着的代理。5 次连续失败才淘汰，容错更稳。
MAX_FAIL_COUNT = 5
# ip:port 合法格式正则（如 1.2.3.4:8080）
PROXY_FORMAT = re.compile(
    r'^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$')


def _valid_ipv4(addr: str) -> bool:
    """严格校验 IPv4 四段：值域 0-255 且**无前导零**（httpx 拒绝 000 写法）。

    免费源常给 `141.000.11.253` 这类带前导零的脏 IP，PROXY_FORMAT 只校验
    位数放行，但 httpx 构造代理 URL 时会抛 InvalidURL 崩溃整个验证批次。
    在发网络请求前拦截，避免拖垮补源循环。
    """
    try:
        host, _, port = addr.rpartition(":")
        if not port.isdigit() or not (0 <= int(port) <= 65535):
            return False
        parts = host.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit():
                return False
            if len(part) > 1 and part[0] == "0":
                return False  # 前导零：000 / 08
            if not (0 <= int(part) <= 255):
                return False
        return True
    except (TypeError, ValueError):
        return False
# 纯 IPv4 正则：验证 ipify 返回体必须是纯 IP，拦截劫持代理
PROXY_IP_ONLY = re.compile(
    r'^\d{1,3}(?:\.\d{1,3}){3}$')

# 按区域分流验证目标：**已弃用**。
# 之前 CN→baidu、境外→youtube，但国内网络走境外代理访问 youtube 也会被墙，
# 会把"代理活着但目标被墙"的境外代理全误杀。现在统一 ipify 存活验证，
# 区域分桶交给源标签 + IP 归属地探测（helper/region_detect.py）。
REGION_TARGETS = {
    "CN":  {"http": HTTP_URL, "https": HTTPS_URL},
    "GLOBAL": {"http": HTTP_URL, "https": HTTPS_URL},
}


# 批量验证：一批并发多少个。
# 实测 500→1000 吞吐 +35%，但并发 1000 时部分代理被瞬时限流误杀（复核时
# CN 代理被成片删掉）。取 500 平衡吞吐与误杀率。
CHECK_BATCH_SIZE = 500


class Checker:
    def __init__(self, region_targets=None, timeout=TIMEOUT,
                 probe_safety=True):
        self.region_targets = region_targets or REGION_TARGETS
        # timeout 拆 connect/read：只设 read 时，连不上的死代理会被内核
        # TCP 超时拖住（几十秒），整批并发验证被拖慢。connect 短超时让
        # 死代理快速失败，验证吞吐显著提升。
        self.timeout = httpx.Timeout(
            timeout, connect=min(timeout, 2), read=timeout,
            pool=timeout, write=timeout)
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

    def check_all(self, proxies, batch_size=CHECK_BATCH_SIZE,
                  on_batch=None):
        """分批并发验证一批 proxy，逐个更新各自状态。

        返回 (可用数量, 总列表)。每批内并发（同时发出），批间串行，
        防止几万个代理一次全并发把连接/内存打爆。

        on_batch: 可选回调 fn(batch_no, batch_ok)，每批完成后调用，
            用于打进度日志（大批量验证时避免看起来像卡住）。

        参考：learn/03_并发验证.py
        """
        proxies = list(proxies)
        results = []
        ok_count = 0
        # 分批跑：每批 batch_size 个并发，跑完再下一批
        total = len(proxies)
        for i in range(0, total, batch_size):
            batch = proxies[i:i + batch_size]
            ok, pairs = asyncio.run(self._check_all_async(batch))
            ok_count += ok
            results.extend(pairs)
            if on_batch:
                on_batch(i // batch_size + 1, ok, min(i + batch_size, total))
        return ok_count, results

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
                # 存活通过后：baidu(真实转发) 与 https 能力 **并行**检测。
                # 之前串行 3 次请求，慢代理要 3×timeout 累积（10s+）；
                # 并行后一个慢代理最快 ~timeout 就出结果，整批吞吐翻 3 倍。
                reality_ok, https_ok = await asyncio.gather(
                    self._reality_ok(client),
                    self._async_fetch_ok(client, targets["https"]),
                )
                proxy.https = https_ok
                if reality_ok:
                    proxy.fail_count = 0
                    proxy.last_status = True
                else:
                    proxy.fail_count += 1
                    proxy.last_status = False
            else:
                proxy.fail_count += 1
                proxy.last_status = False
                proxy.https = False
        proxy.check_count += 1
        self._update_score(proxy, http_ok)

        # 存活通过后，做安全/质量探测（只打标签，不参与淘汰）
        if http_ok and self.probe_safety:
            await self._probe_safety_async(proxy, client)
            await self._measure_latency(proxy)

        return http_ok, proxy.fail_count

    def _update_score(self, proxy, ok):
        """更新信任分：成功 +1、失败 -2（失败惩罚更重），封顶 10。

        注意：fail_count 是"连续失败"，会被重置；score 是"累计信任"。
        封顶避免分数无限上涨导致 stable 分级（stable1=1/2=3/3=5）失效。
        """
        if ok:
            proxy.score = min(10, proxy.score + 1)
        else:
            proxy.score = max(0, proxy.score - 2)

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

    async def _probe_safety_async(self, proxy, client):
        """异步安全探测：匿名性 + 篡改并行（生产用，比同步快一个量级）。

        client 是验证阶段已建立的"走该代理"的 AsyncClient，探针复用它，
        不重复建连接。
        """
        anon_ok, seen_ip = await probe.check_anonymity_async(proxy.proxy, client)
        if seen_ip is not None:
            proxy.anonymous = "elite" if anon_ok else "transparent"
        tamper_ok, _ = await probe.check_tamper_async(proxy.proxy, client)
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

    async def _reality_ok(self, client):
        """第二道验证：走代理访问真实网站(baidu)，确认代理真转发流量。

        ipify 只验证"能回显 IP"，有些伪代理/Cloudflare 边缘能回显但不转发
        到任意目标。用 baidu 确认代理真能访问真实站点。
        """
        try:
            r = await client.get(REALITY_URL)
            if r.status_code != 200:
                return False
            return REALITY_HTML_MARK in r.content
        except Exception:
            return False

    async def _async_fetch_ok(self, client, url):
        """GET 目标并判断"验证通过"。

        不只查 status_code==200，还要校验返回体是合法 IP 地址
        （ipify 返回纯 IP）。因为免费代理里有很多"劫持代理"：
        它们收到请求后返回自己的网页（status 也是 200），
        会把爬虫带沟里去。必须用内容兜底拦截它们。
        """
        try:
            r = await client.get(url)
            if r.status_code != 200:
                return False
            body = r.text.strip()
            # 合法 IP 格式才通过（ipify 会返回一个 IPv4）
            if not PROXY_IP_ONLY.match(body):
                return False
            return True
        except Exception:
            return False

    def should_eliminate(self, fail_count):
        """判断该代理是否该被淘汰。"""
        return fail_count > MAX_FAIL_COUNT

    def _format_check(self, proxy):
        """格式校验：ip:port 是否合法。不合法根本没理由发网络请求。"""
        return bool(PROXY_FORMAT.match(proxy.proxy)) and _valid_ipv4(proxy.proxy)

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
            if r.status_code != 200:
                return False
            return bool(PROXY_IP_ONLY.match(r.text.strip()))
        except Exception:
            return False