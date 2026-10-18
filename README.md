# proxy-pool

自研免费 HTTP/HTTPS 代理池：从 18 个全球免费代理源抓取 `ip:port`，
经格式/可用性/HTTPS 能力多层验证后存入 Redis，对外提供取用 API。
供上游项目（如 poverty-gateway）批量取 IP 做转发。

## 架构

```
scheduler (每 5min 补源 + 每 3min 滚动复核 100 个)
    │
    ├─ Fetcher: 18 源并行抓取 (ThreadPool 8) + 双通道 (raw/jsdelivr)
    │     └─ 验证: ip.3322.net 存活 + opencode.ai HTTPS 目标可达 + 匿名度
    ├─ Checker: 并发验证 (batch 500), score/stable1-3 分级
    └─ RedisPool: use_proxy hash (带 region/https/anonymity/score)
               ↓
api (gunicorn :5010) → GET /get?need=global&type=https&quality=stable3
```

共享状态在 Redis（db0 `use_proxy`）。docker compose 三容器：
`redis / api / scheduler`。

> 阶段 21：https 能力改为验证真实上游 `opencode.ai/zen/v1/models`，
> 不再验证 ip.3322.net；复核从「每分钟全量」改为「每 3 分钟滚动 100 个」，
> 每个代理的网络请求从 5～6 次降到 2 次。水位调为现实值并新增 https 维度。

## 快速开始

```bash
docker compose up -d --build
```

## 可用源（18 个）

GitHub 纯文本大列表（thespeedx/jetkai/monosans/clarketm/sunny9577/shiftytr）、
API 源（databay/proxyscrape/geonode）、国内表格站（ip89/ip3366/kuaidaili/zdaye）、
聚合站（hproxy/openproxylist/proxifly/scdn/free-proxy-list）。

抓取双通道：`raw.githubusercontent` 短超时快速失败，`jsdelivr` 稳定兜底。

## API

- `GET /get?count=N&need=global&type=https&quality=stable1|2|3&max_latency_ms=3000`
  — 批量取用（按 trust score 加权）
- `GET /list?page=1&size=20` — 分页明细
- `GET /health` — 健康检查

## 配置

`config/services.py`：水位下限（`SERVICE_MIN`，含 `https` 维度）、stable 分级
阈值、补源轮数/每源抓取量。`helper/check.py`：验证目标、超时、淘汰阈值。

常用环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `HTTPS_CHECK_URL` | `https://opencode.ai/zen/v1/models` | HTTPS 能力验证目标 |
| `REALITY_CHECK` | `0` | 是否额外做 baidu 真实转发验证（更严格，更慢） |
| `PROBE_SAFETY` | `0` | 是否做匿名性/篡改探针（`safe` 维度需要） |

## 测试

```bash
python3 -m venv .venv
.venv/bin/pip install -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt pytest ruff
.venv/bin/python -m pytest tests/ -q      # 41 passed
.venv/bin/ruff check .
```

## 文档

阶段式开发记录见 `docs/PROGRESS.md`（索引）+ `docs/NN-<阶段>.md`（详录）。
