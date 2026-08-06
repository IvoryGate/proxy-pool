"""一轮补源测试：抓取+验证+入库，输出新增和各层水位。"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time

from handler.proxy_service import ProxyService
from config.services import SERVICE_MIN, MAX_PER_SOURCE

s = ProxyService()
t = time.time()
added, ok = s.refresh(max_per_source=MAX_PER_SOURCE)
print(f"新增 {added} 可用{ok} 耗时{time.time()-t:.0f}s", flush=True)
levels = s.service_levels(SERVICE_MIN)
for region in ["cn", "global"]:
    for svc, mn in SERVICE_MIN[region].items():
        cur = levels[(region, svc)][0]
        mark = "OK" if cur >= mn else f"缺口{mn-cur}"
        print(f"{region}/{svc}: {cur}/{mn} {mark}", flush=True)
