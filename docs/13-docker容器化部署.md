# 阶段 13：Docker Compose 容器化部署

## 背景思考

阶段 12 评估出"基本可上线,但缺进程守护 + API debug"。用户最终拍板用
**Docker Compose** 编排 Redis / API / 调度器,替代手动 `setsid` + systemd。
目标:一条 `docker compose up -d` 完成部署,自带 `restart: unless-stopped`
自动拉起(进程守护)、Redis 彻底隔离、环境一致(避免"我本机好好的,服务器挂了")。

## 完成内容

### 1. 代码改造(Docker 化必要改动)
- **Redis host 环境变量化**(`db/redis_client.py`):`RedisPool` 默认从
  `REDIS_HOST` / `REDIS_PORT` 读,支持容器里连 compose 服务名 `redis`。
- **API 关 debug**(`api/proxy_api.py`):`debug=True` → `debug=False`,
  去掉 reloader/调试器;生产走 gunicorn。
- **requirements 加 `gunicorn==26.0.0`**:多 worker WSGI 服务器。

### 2. 编排文件
- **`Dockerfile`**:`python:3.10-slim`(与本机 venv 一致) + 装依赖 + COPY 源码。
  默认命令 `python api/proxy_api.py`(compose 覆盖)。
- **`docker-compose.yml`** 三个服务:
  - `redis`: `redis:7-alpine`,开 AOF 持久化到 volume `redis-data`,
    healthcheck(redis-cli ping)做依赖门禁。
  - `api`: 4 workers gunicorn,映射 `0.0.0.0:5010`,注入 `REDIS_HOST=redis`,
    `depends_on: redis (condition: service_healthy)`。
  - `scheduler`: `python helper/scheduler.py`,含 `PYTHONPATH=/app`。
- **`.dockerignore`**:排除 `.venv/`(56MB)、`*.log`、`docs/scripts/learn/tests/.git`,
  只打包运行所需源码,镜像最小化。

## 技术决策及理由

1. **`depends_on: condition: service_healthy`**:API/调度器等到 Redis 健康才启动,
   避免"连不上就崩"的启动竞态。
2. **Redis AOF + volume**:`appendonly yes` + `<redis-data` 卷,容器重建不丢池子
   (生产要求)。
3. **PYTHONPATH=/app 陷阱**:`python helper/scheduler.py` 直接运行会以
   `helper/` 为 `sys.path[0]`,import 不到 `handler` 顶层包 → 必须显式加
   `/app`(本机调试 `PYTHONPATH=.` 同理)。
4. **gunicorn 4 workers**: 单 worker 阻塞(慢代理验证)不会拖垮整个 API;
   并发能力强于 Flask 自带单线程 server。

## 实际命令

```bash
# 首次需配镜像加速器(默认 Docker Hub 被墙)
#   /etc/docker/daemon.json:  {"registry-mirrors": [...]}

# 构建 + 启动
sg docker -c 'docker compose build'
sg docker -c 'docker compose up -d'

# 查看状态 / 日志 / 监控
sg docker -c 'docker compose ps'
sg docker -c 'docker compose logs scheduler --tail 20'
sg docker -c 'docker compose top proxy-pool-api-1'

# 取用验证
curl http://127.0.0.1:5010/count
curl "http://127.0.0.1:5010/get?need=global&type=https"
```

## 踩坑记录

- **坑 1(WSL2 无 Docker)**: `docker` / docker.sock 全无。装
  `docker.io docker-compose-v2`,把用户加 `docker` 组(需重登会话才免 sudo;
  本会话临时用 `sg docker -c '...'` 包裹,避开"重新登录"阻塞)。
- **坑 2:Docker Hub 拉不动**:`registry-1.docker.io` i/o timeout(网络被墙)。
  配置国内镜像加速器(daocloud / dockerproxy / 阿里云 registry-mirror)解决。
- **坑 3:scheduler 崩溃重启**：`No module named 'handler'` —— 脚本直接运行
  sys.path[0] 是脚本目录。compose 加 `PYTHONPATH=/app` 修复。
- **坑 4:`docker kill` 不触发 restart 计数**:  `compose kill` 会把容器置为
  "手动停止",`unless-stopped` 不会拉起(这是有意行为,非 bug)。但容器重建后
  `restart: unless-stopped` 生效。

## 验证结果(Docker 内)

- `docker compose ps`:api/redis/scheduler 三容器 Up,redis Healthy。
- API `:5010` 正常:
  ```
  /count → {"total":208, "global":184, "require stable1:87, stable3":0}
  /get?need=global&type=https → {"data":"103.75.198.236:8080"}
  ```
- 调度器在容器网络里正常工作:自动抓源补池(刚起 11 分钟 global 0→184、
  stable 持续累积),复核 job 每 1 分钟触发——**核心流水线在容器内全通**。
- 隔离验证:宿主机 redis 已停,数据不冲突,全部状态在容器 volume。

## 下一步

- 新增业务 API(鉴权/批量取用/分页列表/健康检查/统计/黑白名单等)——用户已确认要加。
- 生产部署:代码 + Dockerfile + compose 同步到生产 Ubuntu 服务器,
  一条 `docker compose up -d` 完成上线。
- 上线后观测:水位、交付 IP 连通率、稳定后定受正式版上线。