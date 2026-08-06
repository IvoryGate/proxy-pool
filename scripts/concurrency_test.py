"""并发度压力测试：同一批候选,不同 batch_size 对比吞吐。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time

from model.proxy import Proxy
from helper.check import Checker

cands = json.load(open("/tmp/opencode/cands.json"))
proxies = [Proxy(proxy=p) for p in cands]
print(f"候选 {len(proxies)} 个，测试并发度...", flush=True)

for batch in [200, 500, 1000, 2000, 4000]:
    t = time.time()
    chk = Checker(probe_safety=False)
    try:
        ok, _ = chk.check_all(proxies, batch_size=batch)
        dt = time.time() - t
        print(f"  批并发 {batch:5d}: {ok} 可用, 耗时 {dt:.1f}s, 吞吐 {len(proxies)/dt:.0f}/s", flush=True)
    except Exception as e:
        print(f"  批并发 {batch:5d}: FAIL {type(e).__name__} {str(e)[:60]}", flush=True)
