"""学习：httpx 怎么通过代理访问目标网站。

跑法：.venv/bin/python learn/02_httpx_代理验证入门.py [proxy]
不带参数 = 直连；带参数 = 通过代理访问（如 1.2.3.4:8080）
"""

import sys

import httpx

target = "http://www.baidu.com"


def check(proxy=None):
    """返回 (是否成功, 用时秒, 状态码或错误)"""
    proxies = f"http://{proxy}" if proxy else None
    try:
        r = httpx.get(target, proxy=proxies, timeout=5)
        return True, r.elapsed.total_seconds(), r.status_code
    except Exception as e:
        return False, 0, f"{type(e).__name__}: {e}"


if __name__ == "__main__":
    proxy = sys.argv[1] if len(sys.argv) > 1 else None
    ok, secs, info = check(proxy)
    mode = "直连" if not proxy else f"代理 {proxy}"
    print(f"[{mode}] 结果={ok} 用时={secs}s 详情={info}")
