"""修复后的验证器全量验证,看真实可用率(ipify 存活 + baidu 真实转发双保险)。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from fetcher.manager import Fetcher
from helper.check import Checker

ps = list(Fetcher().run(max_per_source=400))
print(f"候选 {len(ps)}", flush=True)
chk = Checker(probe_safety=False)
t = time.time()
ok, pairs = chk.check_all(ps)
print(f"可用 {ok}/{len(ps)} 耗时{time.time()-t:.0f}s", flush=True)
alive = [p for p, _ in pairs if p.last_status]
print("区域:", dict(Counter(p.region or "(空)" for p in alive).most_common(8)), flush=True)
print("来源:", dict(Counter(p.source for p in alive).most_common(8)), flush=True)
for p in alive[:12]:
    print(f"  OK {p.proxy:22s} {p.region or '?'} https={p.https}", flush=True)
