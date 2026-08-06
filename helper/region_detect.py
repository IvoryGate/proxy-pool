"""区域探测：给代理补打 region 标签（CN/其它）。

背景：hproxy / ip3366 等纯文本源只给 ip:port，不带国家码，
入库后 region 空 → 被错分到 global。而 CN 代理资源是国内核心，
必须正确标出。

方法：用 ip-api.com 免费接口反查代理 IP 归属地（countryCode）。
批量一次最多 100 IP（POST），免费无 key，约 45 请求/分钟限制，
一批 100 IP 就是 1 个请求，够用。

只给 region 为空的代理打标签，不覆盖已有标签。
"""

import httpx

from model.proxy import Proxy


def detect_regions(proxies, batch=100):
    """批量探测代理 IP 归属地，返回 {proxy_str: countryCode}。
    只探测 region 为空的代理。失败返回空 dict。
    """
    targets = {p.proxy for p in proxies if not p.region}
    if not targets:
        return {}
    result = {}
    items = list(targets)
    try:
        for i in range(0, len(items), batch):
            chunk = items[i:i + batch]
            payload = [{"query": x.split(":")[0]} for x in chunk]
            r = httpx.post("http://ip-api.com/batch",
                           json=payload, timeout=10)
            if r.status_code != 200:
                continue
            for query, resp in zip(chunk, r.json()):
                cc = (resp or {}).get("countryCode", "")
                if cc:
                    result[query] = cc
    except Exception:
        pass
    return result


def apply_regions(pool, proxies):
    """给池内 region 为空的代理补打 region 标签，写回 Redis。"""
    detected = detect_regions(proxies)
    updated = 0
    for p in proxies:
        if p.region:
            continue
        cc = detected.get(p.proxy)
        if cc:
            p.region = cc
            pool.put(p)
            updated += 1
    return updated


if __name__ == "__main__":
    from db.redis_client import RedisPool
    pool = RedisPool()
    ps = pool.getAll()
    updated = apply_regions(pool, ps)
    print(f"补打 region {updated} 个，池子 {pool.count()}")
    from collections import Counter
    print("region:", dict(Counter(p.region or '(空)' for p in pool.getAll())))
