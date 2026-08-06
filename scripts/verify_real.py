"""用 baidu(统一真实目标)验证一批代理的真实可用率，找出真代理。

背景：ipify 验证目标太宽松，会放过 Cloudflare 边缘/劫持等"假代理"。
baidu 是国内可达的真实网站，真代理(能转发流量)可过、假代理被拦。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from helper.check import Checker
import helper.check as chkmod

chkmod.HTTP_URL = "http://www.baidu.com"
chkmod.HTTPS_URL = "https://www.baidu.com"
chkmod.REGION_TARGETS = {
    "CN": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
    "GLOBAL": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
}
chk = Checker(probe_safety=False)


def verify(proxies, label=""):
    t = time.time()
    ok, pairs = chk.check_all(proxies)
    alive = [p for p, _ in pairs if p.last_status]
    print(f"[{label}] baidu 可用 {ok}/{len(proxies)} 耗时{time.time()-t:.0f}s", flush=True)
    print(f"  区域: {dict(Counter(p.region or '(空)' for p in alive).most_common(6))}", flush=True)
    print(f"  来源: {dict(Counter(p.source for p in alive).most_common(6))}", flush=True)
    return alive


if __name__ == "__main__":
    from fetcher.sources.databay import DatabayFetcher
    from fetcher.sources.free_proxy_list import FreeProxyListFetcher
    from fetcher.sources.proxifly import ProxiflyFetcher

    for label, ps in [
        ("databay境外elite", [p for p in DatabayFetcher(elite_only=True).fetch() if p.region != 'CN']),
        ("databay全量", list(DatabayFetcher().fetch())),
        ("free-proxy-list", list(FreeProxyListFetcher().fetch())),
        ("proxifly", list(ProxiflyFetcher().fetch())[:300]),
    ]:
        alive = verify(ps, label)
        for p in alive[:8]:
            print(f"    OK {p.proxy:22s} {p.region or '?':4s} src={p.source or '-':12s} anon={p.anonymous or '-'}")
