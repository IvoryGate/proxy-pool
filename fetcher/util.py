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