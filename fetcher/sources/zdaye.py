"""站大爷（zdaye）：国内代理源，量较大。

特点：首页是"最新代理"列表，带发布时间；若数据不够新就不抓。
抓取页是分页表格，ip 在 <td>[1]</td>、port 在 <td>[2]</td>。
参考项目用 xpath 解析。我们照做，但通过 self._http_get 走代理绕反爬。
"""

from datetime import datetime
from time import sleep

from lxml import etree

from fetcher.base import BaseFetcher
from fetcher.util import yield_unique_proxies


class ZdayeFetcher(BaseFetcher):
    name = "zdaye"
    url = "https://www.zdaye.com/dayProxy.html"
    enabled = False  # 站反爬严（405），需登录/验证码，暂禁用，待后续处理

    def fetch(self):
        start_url = "https://www.zdaye.com/free/"
        r = self._http_get(start_url, verify=False, timeout=10)
        if not r or not r.content:
            return
        tree = etree.HTML(r.content)

        times = tree.xpath("//span[@class='thread_time_info']/text()")
        if not times:
            return
        latest = times[0].strip()
        try:
            interval = datetime.now() - datetime.strptime(
                latest, "%Y/%m/%d %H:%M:%S")
            if interval.total_seconds() >= 300:
                return  # 数据太旧，不值得抓
        except ValueError:
            pass  # 时间格式解析失败，还是试着抓一下

        hrefs = tree.xpath("//h3[@class='thread_title']/a/@href")
        if not hrefs:
            return
        target = "https://www.zdaye.com/" + hrefs[0].strip()

        all_proxies = []
        while target:
            r = self._http_get(target, verify=False, timeout=10)
            if not r or not r.content:
                break
            tree = etree.HTML(r.content)
            for tr in tree.xpath("//table//tr"):
                cells = tr.xpath("./td/text()")
                if len(cells) >= 2:
                    ip = "".join(cells[0]).strip()
                    port = "".join(cells[1]).strip()
                    if ip and port:
                        all_proxies.append(f"{ip}:{port}")
            next_page = tree.xpath(
                "//div[@class='page']/a[@title='下一页']/@href")
            target = ("https://www.zdaye.com/" + next_page[0].strip()
                      if next_page else None)
            sleep(5)  # 别打太狠

        for proxy in yield_unique_proxies(all_proxies):
            yield proxy