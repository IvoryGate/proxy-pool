"""跑满版验证入库：不限抓取量，分批验证，写入 Redis（跑通第一要务）。

用法：PYTHONPATH=. nohup .venv/bin/python scripts/full_refresh.py > fill.log 2>&1 &
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool
from collections import Counter

print(f"[{time.strftime('%H:%M:%S')}] 开始全量抓取...", flush=True)
t0 = time.time()
proxies = list(Fetcher().run(max_per_source=None))
print(f"[{time.strftime('%H:%M:%S')}] 抓取去重后 {len(proxies)} 个候选，耗时 {time.time()-t0:.0f}s",
      flush=True)
print(f"[{time.strftime('%H:%M:%S')}] 按源: {dict(Counter(p.source for p in proxies))}", flush=True)

chk = Checker(probe_safety=False)   # 先关探针快速填池，安全标签后续 check_pool 补打
pool = RedisPool()
print(f"[{time.strftime('%H:%M:%S')}] 开始分批验证（每批500并发）...", flush=True)
t1 = time.time()
def on_batch(n, ok, done):
    print(f"[{time.strftime('%H:%M:%S')}] 批次 {n} 完成，本批可用 {ok}，累计 {done}/{len(proxies)}",
          flush=True)
ok, pairs = chk.check_all(proxies, on_batch=on_batch)
print(f"[{time.strftime('%H:%M:%S')}] 验证结束，可用 {ok}，耗时 {time.time()-t1:.0f}s", flush=True)

# 入库顺序：可用优先
added = 0
for p, _ in pairs:
    if p.last_status and not pool.exists(p):
        pool.put(p)
        added += 1
print(f"[{time.strftime('%H:%M:%S')}] 实际入库 {added}", flush=True)
print(f"[{time.strftime('%H:%M:%S')}] 池子 {pool.count()}", flush=True)

# 按质量展示
from collections import defaultdict
buckets = defaultdict(int)
for p, _ in pairs:
    if p.last_status:
        buckets[f"{p.region or 'global'}/{('safe' if (p.anonymous=='elite' and not p.tampered) else 'plain')}"] += 1
print("可用代理质量分布：", dict(buckets), flush=True)