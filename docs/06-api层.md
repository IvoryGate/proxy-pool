# 阶段 06：API 层（Flask 对外服务）

## 背景思考

池子内部（抓取→验证→入库/淘汰）已能自动运转，但还没法"对外用"。
外部程序（爬虫、业务）需要一套 HTTP 接口来取代理。这就是 API 层。

## 完成内容

- `api/proxy_api.py`：`create_app(service)` 工厂创建 Flask 应用
  - `GET /get?type=https` → 随机取一个代理（不删除），空池返 404
  - `GET /pop?type=https` → 随机取一个并删除（消费式），空池返 404
  - `GET /count` → 池子统计 `{"total": n, "https": n}`
  - 统一返回 `{"code", "data", "msg:?}` JSON
- `handler/proxy_service.py` 增加 `get()` / `pop()` 方法（透传 pool.get/pop）。
- `tests/test_api.py`：用假 service + Flask test_client 测 /get、https 参数透传、
  /pop、空池 404。

## 技术决策及理由

- **工厂函数 `create_app(service=None)`**：不把 service 写成模块级全局变量，
  而是工厂注入，测试能传假 service，避免每次测试都连 Redis。跟 ProxyService 的依赖注入一脉相承。
- **/get 不删 vs /pop 删**：get 给"想反复用同一代理"的场景；pop 给"用完即弃、
  强制轮换"的场景（防封号）。两种消费语义分开。
- **type=https 筛选**：复用 pool.get 的 https 辅助 set，取 https 代理是 O(1)，
  不走全表扫。

## 实际命令

```bash
.venv/bin/python tests/test_api.py        # → ALL PASSED

# 真实起服务器验证
PYTHONPATH=. .venv/bin/python -c "
from api.proxy_api import create_app
create_app().run(host='127.0.0.1', port=5010)"
curl http://127.0.0.1:5010/get
curl http://127.0.0.1:5010/count
```

## 踩坑记录

- 坑 1：curl `/count` 第一次返回空 → 是服务器还没就绪（sleep 太短），
  请求没到达，不是 bug。多等几秒或重试即可。
- 坑 2：`/pop` 把池里唯一代理取走后，池子 `total:0` —— 这不是错误，
  是"消费式取用"的预期效果，count 也如实反映，顺带验证了流程闭环。

## 下一步

- 补全测试为 pytest 标准用例（CI 需要），适配 CI 工作流。
- 用 gunicorn/Docker 部署（生产形态）。
- 补爬触发：池子数量低于阈值时自动补爬。
- 验证目标国外化（改 HTTP_URL 可测国外）。