"""严格全量填池：baidu 验证目标（拦假代理）+ 实时复核入库。

只保留当下真实可用的代理。验证目标统一 baidu（国内可达真站，
真代理能转发流量、Cloudflare/劫持假代理被拦）。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool
import helper.check as chkmod

# 统一用 baidu 验证（真站，拦假代理）
chkmod.HTTP_URL = "http://www.baidu.com"
chkmod.HTTPS_URL = "https://www.baidu.com"
chkmod.REGION_TARGETS = {
    "CN": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
    "GLOBAL": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
}
chk = Checker(probe_safety=False)

print(f"[{time.strftime('%H:%M:%S')}] 抓取...", flush=True)
t0 = time.time()
ps = list(Fetcher().run(max_per_source=500))
print(f"[{time.strftime('%H:%M:%S')}] 候选 {len(ps)}，按源 {dict(Counter(p.source for p in ps))}", flush=True)

print(f"[{time.strftime('%H:%M:%S')}] baidu 严格验证...", flush=True)
ok, pairs = chk.check_all(ps)
print(f"[{time.strftime('%H:%M:%S')}] 可用 {ok}/{len(ps)} 耗时{time.time()-t0:.0f}s", flush=True)

alive = [p for p, _ in pairs if p.last_status]
print("可用区域:", dict(Counter(p.region or '(空)' for p in alive).most_common(8)), flush=True)
print("可用来源:", dict(Counter(p.source for p in alive).most_common(8)), flush=True)
for p in alive[:15]:
    print(f"  OK {p.proxy:24s} {p.region or '?':4s} src={p.source or '-':12s}", flush=True)
