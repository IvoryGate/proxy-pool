"""复核池内代理并打安全标签（带探针）。

用法：PYTHONPATH=. setsid bash -c 'cd ... && nohup .venv/bin/python scripts/full_check.py > check.log 2>&1 < /dev/null'
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from handler.proxy_service import ProxyService
from db.redis_client import RedisPool

print(f"[{time.strftime('%H:%M:%S')}] 开始复核池内代理（带探针打安全标签）...", flush=True)
s = ProxyService()
t = time.time()
checked, eliminated = s.check_pool()
print(f"[{time.strftime('%H:%M:%S')}] 复核 {checked} 个，淘汰 {eliminated}，耗时 {time.time()-t:.0f}s",
      flush=True)
print(f"[{time.strftime('%H:%M:%S')}] 复核后池子: {s.count()}", flush=True)

pool = RedisPool()
anon = Counter(); region = Counter()
for p in pool.getAll():
    anon[p.anonymous] += 1
    region[p.region or 'global'] += 1
print("匿名性分布:", dict(anon), flush=True)
print("区域分布:", dict(region), flush=True)