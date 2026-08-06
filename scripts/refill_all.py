"""当前最优源组合全量验证入库（开代理环境填池用）。

抓取全部启用源 + databay elite 定向，验证后入库（去重）。
用法：PYTHONPATH=. setsid bash -c '... nohup .venv/bin/python scripts/refill_all.py > refill.log 2>&1 < /dev/null'
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from fetcher.manager import Fetcher
from fetcher.sources.databay import DatabayFetcher
from helper.check import Checker
from db.redis_client import RedisPool

print(f"[{time.strftime('%H:%M:%S')}] 开始抓取...", flush=True)
t0 = time.time()
ps = list(Fetcher().run(max_per_source=None))
ps += list(DatabayFetcher(elite_only=True).fetch())
print(f"[{time.strftime('%H:%M:%S')}] 候选 {len(ps)}，按源 {dict(Counter(p.source for p in ps))}",
      flush=True)

chk = Checker(probe_safety=False)
print(f"[{time.strftime('%H:%M:%S')}] 分批验证...", flush=True)
ok, pairs = chk.check_all(ps)
print(f"[{time.strftime('%H:%M:%S')}] 可用 {ok}，耗时 {time.time()-t0:.0f}s", flush=True)

pool = RedisPool()
added = 0
for p, _ in pairs:
    if p.last_status and not pool.exists(p):
        pool.put(p)
        added += 1
print(f"[{time.strftime('%H:%M:%S')}] 新增 {added}，池子 {pool.count()}", flush=True)
