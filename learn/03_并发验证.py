"""学习：asyncio + httpx 并发验证代理（对比顺序 vs 并发）。

asyncio 的原理（前面讲过）：
  同步 = 一个个"等"，总时间 = 数量 × 每个耗时
  异步 = 一起等，谁先好谁先回，总时间 ≈ 最慢的那个

跑法：PYTHONPATH=. .venv/bin/python learn/04_并发验证入门.py [模式]
  模式：sync（顺序） 或 async（并发），默认都跑对比
"""

import asyncio
import sys
import time

import httpx

# 用真实代理列表（并发时免费代理大多超时，正好看对比）
from fetcher.sources.geonode import GeonodeFetcher
from helper.check import HTTP_URL, TIMEOUT


def sync_verify(proxies):
    """顺序验证，返回 (成功数, 总耗时)"""
    t0 = time.time()
    ok = 0
    for p in proxies:
        try:
            r = httpx.get(HTTP_URL, proxy=f"http://{p}", timeout=TIMEOUT, verify=False)
            ok += r.status_code == 200
        except Exception:
            pass
    return ok, time.time() - t0


async def async_verify(proxies):
    """并发验证，返回 (成功数, 总耗时)。

    正确姿势：共用一个 AsyncClient（重复建连接很浪费），async with 自动关闭。
    """
    import asyncio
    t0 = time.time()

    async def one(client, p):
        try:
            r = await client.get(HTTP_URL, proxy=f"http://{p}")
            return r.status_code == 200
        except Exception:
            return False

    async with httpx.AsyncClient(timeout=TIMEOUT, verify=False) as client:
        results = await asyncio.gather(*[one(client, p) for p in proxies])
    return sum(results), time.time() - t0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "async"
    proxies = list(GeonodeFetcher().fetch())[:30]
    print(f"取前 {len(proxies)} 个代理测试")

    if mode == "async":
        ok, secs = asyncio.run(async_verify(proxies))
        print(f"[并发 async] 成功 {ok}/{len(proxies)}  用时 {secs:.2f}s")
    else:
        ok, secs = sync_verify(proxies)
        print(f"[顺序 sync ] 成功 {ok}/{len(proxies)}  用时 {secs:.2f}s")

    print('\n--- 用假延时演示"并发 vs 顺序"的纯时间差（不看代理死活）---')
    import asyncio as _asyncio

    async def _asym():
        t = time.time()
        await _asyncio.gather(*[_asyncio.sleep(2) for _ in range(10)])
        return time.time() - t

    t_sync = 2 * 10  # 顺序：10个 × 每个2秒
    t_async = _asyncio.run(_asym())
    print(f"10 个各延时2秒：顺序约 {t_sync}s，并发实测 {t_async:.2f}s")