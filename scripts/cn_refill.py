"""CN 定向补充：抓国内源 + 境外源里的 CN，验证入库，region_detect 打标签。

目标：把 cn/all 补到 30。用当前标准(ipify 存活 + baidu 真实转发)。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from model.proxy import Proxy
from fetcher.sources.hproxy import HProxyFetcher
from fetcher.sources.databay import DatabayFetcher
from fetcher.sources.free_proxy_list import FreeProxyListFetcher
from fetcher.sources.ip3366 import Ip3366Fetcher
from fetcher.sources.ip89 import Ip89Fetcher
from fetcher.sources.kuaidaili import KuaidailiFetcher
from helper.check import Checker
from helper.region_detect import detect_regions
from db.redis_client import RedisPool

ps = []
# hproxy 国内定向（纯文本，量大）
for s in HProxyFetcher(country="CN").fetch():
    p = Proxy(proxy=s)
    p.source = "hproxy"
    ps.append(p)
# databay / free-proxy-list 里的 CN
ps += [p for p in DatabayFetcher().fetch() if p.region == "CN"]
ps += [p for p in FreeProxyListFetcher().fetch() if p.region == "CN"]
# 国内网页源
for cls, src in [(Ip3366Fetcher, "ip3366"), (Ip89Fetcher, "ip89"),
                 (KuaidailiFetcher, "kuaidaili")]:
    try:
        for item in cls().fetch():
            if isinstance(item, Proxy):
                item.source = item.source or src
                ps.append(item)
            else:
                p = Proxy(proxy=item)
                p.source = src
                ps.append(p)
    except Exception as e:
        print(f"{src} ERR {e}", flush=True)

print(f"CN 定向候选 {len(ps)}", flush=True)
chk = Checker(probe_safety=False)
t = time.time()
ok, pairs = chk.check_all(ps)
alive = [p for p, _ in pairs if p.last_status]
print(f"可用 {ok}/{len(ps)} 耗时{time.time()-t:.0f}s", flush=True)

# region_detect 给空 region 的打标签
detected = detect_regions(alive)
for p in alive:
    if not p.region:
        cc = detected.get(p.proxy)
        if cc:
            p.region = cc

pool = RedisPool()
added = 0
for p in alive:
    if p.region == "CN" and not pool.exists(p):
        pool.put(p)
        added += 1
print(f"新增 CN {added}，池子 {pool.count()}", flush=True)

from config.services import SERVICE_MIN
for region in ["cn", "global"]:
    for svc, mn in SERVICE_MIN[region].items():
        if svc == "all":
            cur = pool.count_by_region(region)
        elif svc == "safe":
            cur = pool.count_by_region(region, safe_only=True)
        elif svc == "stable":
            cur = pool.count_by_region(region, stable_only=True)
        else:
            cur = 0
        mark = "OK" if cur >= mn else f"缺口{mn-cur}"
        print(f"{region}/{svc}: {cur}/{mn} {mark}", flush=True)
