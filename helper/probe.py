"""安全与质量探针：检测代理的匿名性 / 篡改 / 延迟。

设计：这些都是"走代理 vs 直连对照"的检测，共用一套探针函数。
  - 匿名性(privacy)：走代理访问 ip 检测接口，看"目标看到的 IP"
    是否等于"代理声称的 IP"。一致 → 高匿(它没暴露你真实出口)；
    不一致 → 透明代理(你的真实 IP 被目标看到)，隐私上不能用。
  - 篡改(security)：走代理和直连都 GET 一个"内容稳定"的页面，
    比内容哈希。不同 → 代理注入/篡改了响应，安全上不能用。
  - 延迟(quality)：验证时记录 TTFB（首个字节耗时）。

每个探针返回 (是否通过, 证据)。调用方据此给代理打标签。
"""

import hashlib

import httpx

# 返回"目标看到的 IP"的接口（纯文本 IP）
IP_ECHO_URL = "http://api.ipify.org"
# 内容极稳定的页面，用来对比"走代理 vs 直连"的内容是否被改
STABLE_URL = "http://www.example.com"
# 探针超时：探测代理本身，给短一点，别拖太久
PROBE_TIMEOUT = 6


def _get(url, proxy_addr=None):
    """GET 请求。proxy_addr 给就走代理。失败返回 None。"""
    try:
        kwargs = {"timeout": PROBE_TIMEOUT}
        if proxy_addr:
            kwargs["proxy"] = f"http://{proxy_addr}"
        return httpx.get(url, **kwargs)
    except Exception:
        return None


def check_anonymity(proxy_addr):
    """匿名性检测：走代理看目标看到的 IP 是不是代理自己的。

    返回 (是否高匿, 目标看到IP)。目标看到的 IP == 代理IP → 高匿。
    注意：目标看到 IP 无法获取（请求失败）时返回 (False, None)。
    """
    r = _get(IP_ECHO_URL, proxy_addr)
    if r is None:
        return False, None
    seen_ip = r.text.strip()
    claimed_ip = proxy_addr.split(":")[0]
    return seen_ip == claimed_ip, seen_ip


def check_tamper(proxy_addr):
    """篡改检测：走代理 vs 直连对比稳定页面内容哈希。

    返回 (是否未篡改, 直连hash or None)。直连拿不到就不判（保守通过）。
    走代理拿到但内容 hash 与直连不同 → 篡改。
    """
    direct = _get(STABLE_URL)
    if direct is None:
        return True, None  # 直连失败，无法对照，不冤枉它
    direct_hash = hashlib.md5(direct.content).hexdigest()
    via_proxy = _get(STABLE_URL, proxy_addr)
    if via_proxy is None:
        return True, direct_hash  # 代理访问失败交给存活检测判，这里不判篡改
    via_hash = hashlib.md5(via_proxy.content).hexdigest()
    return via_hash == direct_hash, direct_hash
