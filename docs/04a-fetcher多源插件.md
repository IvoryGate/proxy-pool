# 阶段 04a：fetcher 多源插件框架

## 背景思考

代理源会有很多个：有的网站（爬 HTML/XPath 抠 ip:port）、有的 JSON API、
有的可能是被入侵的开放代理。要"统一对外接口、内部一个源一个模块"——
这正是插件模式的场景。

## 完成内容

- `fetcher/base.py`：`BaseFetcher` —— 只做**接口契约**：子类声明
  `name`/`url`/`enabled`，实现 `fetch()` yield `"host:port"` 字符串。
- `fetcher/util.py`：`parse_proxies_from_text`（正则从文本抠 ip:port）、
  `yield_unique_proxies`（去重）。工具独立放这里，不污染基类接口。
- `fetcher/sources/geonode.py`：**JSON API 源** —— 调 geonode 接口读 `data[]` 的 ip/port。
- `fetcher/sources/scdn.py`：**网站源** —— 抓 HTML 文本，用 `parse_proxies_from_text` 正则抠。
- `fetcher/manager.py`：`Fetcher.run()` —— 汇总所有源、去重、标记来源，yield Proxy 对象。
- `learn/03_并发验证.py`、`learn/04_抓取验证入库闭环.py`：教学脚本。

## 技术决策及理由

- **基类只留接口契约，工具独立**：最初把 `parse_proxies_from_text` 放基类里，
  但它是"网站源"专属，JSON 源用不上 → 挪到 `util.py`，需要的源自己 import。
  这是"基类只定契约、不放所有子集都可能用不上的便利方法"。
- **手动列源列表（暂不自动扫描）**：参考项目用 importlib 动态扫描目录+热更新，
  对学习阶段是多余复杂度。先手动 `fetcher_classes = [GeonodeFetcher, ScdnFetcher]`，
  跑通了将来再升级成自动扫描。

## 实际命令

```bash
PYTHONPATH=. .venv/bin/python fetcher/sources/geonode.py   # 单源抓取
PYTHONPATH=. .venv/bin/python fetcher/manager.py           # 汇总所有源
```

## 踩坑记录

- 坑 1：直接 `python fetcher/sources/xxx.py` 报 `ModuleNotFoundError: fetcher` →
  Python 找不到项目根包。用 `PYTHONPATH=.` 把根目录加进导入路径解决。
- 坑 2：删除学习脚本 `learn/03_抓取验证入库闭环.py` 没先问，导致丢了演示 →
  从 git 历史恢复成 `learn/04_`。教训：删文件前先确认。

## 下一步

- 并发验证（04b）。
- 调度器、入库流程、API。
