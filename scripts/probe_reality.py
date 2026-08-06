"""用 baidu 独立验证池内代理真实可用率（检验 ipify 验证目标是否误判）。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from collections import Counter

from db.redis_client import RedisPool
from helper.check import Checker
import helper.check as chkmod

pool = RedisPool()
ps = pool.getAll()
print(f"池内 {len(ps)}，用 baidu 独立验证真实可用率...", flush=True)

chkmod.HTTP_URL = "http://www.baidu.com"
chkmod.HTTPS_URL = "https://www.baidu.com"
chkmod.REGION_TARGETS = {
    "CN": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
    "GLOBAL": {"http": chkmod.HTTP_URL, "https": chkmod.HTTPS_URL},
}
chk = Checker(probe_safety=False)
t = time.time()
ok, pairs = chk.check_all(ps)
print(f"baidu 可用 {ok}/{len(ps)} 耗时{time.time()-t:.0f}s", flush=True)
alive = [p for p, _ in pairs if p.last_status]
print("baidu存活区域:", dict(Counter(p.region or "(空)" for p in alive).most_common(8)), flush=True)
print("baidu存活匿名:", dict(Counter(p.anonymous or "(空)" for p in alive).most_common(6)), flush=True)
