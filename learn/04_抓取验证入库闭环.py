"""学习脚本：把"抓取 → 验证 → 入库"整个闭环打通。

这是从 0 到 1 的第一次完整跑通 —— 让你亲眼看到真实代理
从网络飞进 Redis 池子（尽管免费代理存活率低，能进去一两个就算成功）。

只做记录，不改动正式代码。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetcher.manager import Fetcher
from helper.check import Checker
from db.redis_client import RedisPool


def main():
    pool = RedisPool()
    pool.clear()
    print("== 1. 抓取 ==")
    proxies = list(Fetcher().run())
    print(f"抓到了 {len(proxies)} 个原始代理")

    print("== 2. 验证（先只验前 BATCH 个，避免一个个跑太久）==")
    checker = Checker()
    BATCH = 10
    ok_count = 0
    for proxy in proxies[:BATCH]:
        ok, fail_count = checker.check(proxy)
        if ok:
            ok_count += 1
            pool.put(proxy)
            print(f"  [可用] {proxy.proxy} (fail_count={fail_count})")

    print("== 3. 结果 ==")
    print(f"验了 {BATCH} 个，可用 {ok_count}，池子里现有 {pool.count()['total']} 个")


if __name__ == "__main__":
    main()