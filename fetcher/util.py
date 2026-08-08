"""fetcher 通用小工具。

这些不是"所有源都该有"的接口方法，而是"某些源才用得上"的工具函数。
放到独立模块，用到的源自己 import —— 不污染 BaseFetcher 的接口契约。
"""

import random
import re

# 从一段文本里抠 "ip:port" 的正则
PROXY_PATTERN = re.compile(
    r'(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?:\s*:\s*|\s+)(\d{2,5})(?!\d)')

# 常见浏览器 UA，抓网页源时轮流伪装
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/41.0.2272.101 Safari/537.36",
]


def random_user_agent():
    """随机返回一个浏览器 UA，降低被反爬识别的概率。"""
    return random.choice(USER_AGENTS)


def parse_proxies_from_text(text):
    """从一段文本里，正则抠出所有 "host:port"。

    给"网站源"用：很多网站返回纯文本/HTML，里面混着代理，直接提出来。
    返回 list[str]，如 ["1.2.3.4:8080", ...]。
    """
    if not text:
        return []
    return [f"{ip}:{port}" for ip, port in PROXY_PATTERN.findall(text)]


def yield_unique_proxies(proxies):
    """去重后逐个 yield（同一代理被本页抓到多次，只吐一次）。"""
    seen = set()
    for proxy in proxies:
        if proxy not in seen:
            seen.add(proxy)
            yield proxy


def fetch_text(url, jsdelivr_url=None, timeout=20, retries=1):
    """双通道抓取代理列表文本：raw 短超时快速失败，jsdelivr 稳定兜底。

    国内服务器直连 raw.githubusercontent.com 常抖动（1s~60s 不定），
    jsdelivr CDN 稳定但需要 tag。策略：raw 用短超时(做最快路径)，
    一旦超时/失败立即切到 jsdelivr（稳定通道），谁成功返回谁。
    都失败返回 (None, None)。

    jsdelivr_url 传 None 时自动把 GitHub 仓库地址转成 jsdelivr 地址。
    """
    import httpx
    # raw 通道：短超时快速失败（抖了就立即换 jsdelivr，不干等）。
    # 注意用 httpx.Timeout 分别设 connect/read —— 只设 read 时连接卡住
    # 仍会被内核 TCP 超时拖住（实测能卡 30s+）。
    raw_timeout = min(timeout, 8)
    try:
        r = httpx.get(url, timeout=httpx.Timeout(
            raw_timeout, connect=min(raw_timeout, 5), read=raw_timeout,
            pool=raw_timeout, write=raw_timeout))
        if r.status_code == 200:
            return r.text, url
    except Exception:
        pass
    # jsdelivr 通道：稳定，多试几次
    if jsdelivr_url:
        cand = jsdelivr_url
    elif "raw.githubusercontent.com" in url:
        # raw -> jsdelivr：把 /user/repo/branch/path 转成 /user/repo@branch/path
        # （jsdelivr 必须有 @branch，否则 404）
        parts = url.split("raw.githubusercontent.com/", 1)
        if len(parts) == 2:
            seg = parts[1].split("/", 2)   # [user, repo, branch/path]
            if len(seg) == 3:
                user, repo, rest = seg
                branch, _, path = rest.partition("/")
                cand = (f"https://cdn.jsdelivr.net/gh/{user}/{repo}"
                        f"@{branch}/{path}")
            else:
                cand = None
        else:
            cand = None
    else:
        return None, None  # 非 GitHub 源且 raw 失败：无兜底
    if not cand:
        return None, None
    to = httpx.Timeout(20, connect=5, read=20, pool=20, write=20)
    for _ in range(retries):
        try:
            r = httpx.get(cand, timeout=to)
            if r.status_code == 200:
                return r.text, cand
        except Exception:
            continue
    return None, None


def reservoir_sample(iterable, k, max_scan=5000):
    """水塘抽样：从流式 iterable 中**等概率**随机抽 k 个。

    为什么需要：
      manager 抓大源（如 hproxy 2 万+）时限制 max_per_source=100，
      如果"取前 100"，会反复取到同一批早期代理，漏掉后面更新的。
      水塘抽样保证：每个代理被抽中的概率相同（= k / 总数），
      每次跑的样本不同，覆盖更全面。

    实现：
      先填满 k 大小的"蓄水池"，之后第 i 个元素以 k/(i+1) 概率
      随机替换池中一个元素。最终池中每个元素概率均等。
    内存：只占 O(k)，不把整个流加载进来。

    代价：需要遍历整个流（大源 2 万+ 全读完才能等概率抽）。
    为限制耗时，max_scan 设定最多扫描多少个就停（默认 5000）：
      在 max_scan 范围内等概率抽样，既保证样本多样（不是总取前 k），
      又不至于为抽 k 个把整个大源拖完。
    """
    pool = []
    for i, item in enumerate(iterable):
        if i >= max_scan:
            break
        if i < k:
            pool.append(item)
        else:
            # 第 i 个元素（i>=k）以 k/(i+1) 概率替换蓄水池中随机一个
            j = random.randint(0, i)
            if j < k:
                pool[j] = item
    yield from pool