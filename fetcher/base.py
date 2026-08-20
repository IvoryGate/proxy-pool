"""代理源基类：定义"所有代理源必须具备的统一接口"。

设计思想：
  这个项目将来会有很多个代理源 —— 有的是网站（用爬虫抓 HTML / XPath 抠出 ip:port）、
  有的是开放代理 API（读 JSON）、有的可能是被入侵的开放代理……
  它们的"内部实现"千差万别，但对外都只做一件事：交出 `"host:port"` 字符串。

  基类只做一件事：约定接口契约 —— 子类实现 fetch()，yield 出 "host:port"。
  其它"从文本抠代理"这类工具，不是所有源都需要，放到独立工具模块
  （fetcher/util.py），用到的源自己 import，不污染基类接口。

走代理抓源：
  不少免费代理网站对本机 IP 有反爬（429/403）。所以我们抓源时也可以
  绕一层"我们自己的代理"。基类提供 proxy 字段 + _http_get()：
    子类用 self.proxy 拿当前代理地址（manager 会给它赋值），
    用 self._http_get(url) 发请求（自动带上 self.proxy）。
"""

import httpx

from fetcher import util


class BaseFetcher:
    # ---- 子类必须声明的字段 ----
    name = ""        # 源的唯一标识，如 "geonode"、"zdaye"
    url = ""         # 源网站首页 URL（用于日志/排查）

    # ---- 子类可覆盖 ----
    enabled = True   # 设为 False 可禁用该源

    # 本源抓取上限：None = 不限量（用全局 max_per_source 或全取）。
    # 高质量源（通过率高的）声明显式放开；死源调小，别让无效候选
    # 占满验证时间和 API 配额。
    max_items = None

    def __init__(self):
        self.proxy = None   # 抓源时用的代理地址 "host:port"，manager 可选赋值

    def fetch(self):
        """爬取本源的代理，yield "host:port" 字符串。子类必须实现。"""
        raise NotImplementedError

    def _http_get(self, url, timeout=8, headers=None, **kwargs):
        """发 GET 请求。若设置了 self.proxy 就通过该代理抓取（绕反爬）。

        默认 timeout 8s，并拆 connect/read 超时——只设 read 时连接卡住
        会被内核 TCP 拖 30s+（实测），慢源会拖垮补源循环。
        """
        try:
            if self.proxy:
                kwargs["proxy"] = f"http://{self.proxy}"
            return httpx.get(
                url,
                timeout=httpx.Timeout(
                    timeout, connect=min(timeout, 5), read=timeout,
                    pool=timeout, write=timeout),
                follow_redirects=True,
                headers=headers or {
                    "User-Agent": util.random_user_agent(),
                }, **kwargs)
        except Exception:
            return None