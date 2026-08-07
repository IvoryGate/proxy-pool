# 阶段 14：业务 API 基础供给（批量取用 / 延迟筛选 / 分页 / 健康检查）

## 背景思考

本地 Docker 化跑通后，用户明确了项目边界，确立了"本仓库只做 IP 基础供给"的定位：

> 本仓库只提供所需的基础服务——稳定地提供若干 IP；另起一个项目做
> opencode/zen 连通性、封装 API-Key 服务、用量统计等业务能力。

因此**凡偏业务的能力（鉴权、黑白名单、业务用量统计、粘性会话）都划到网关项目**，
本仓库 API 收敛为纯"IP 供给底座"，供网关项目/内部服务取用。

## 完成内容（本仓库最终 API）

在已有 `/get` `/pop` `/count` `/strategies` 上新增：

### 1. 批量取用 `GET /get?count=N`
- `service.get_many()`：取候选 → 按信任分加权选 N 个、去重，可能少于 N。
- `count` 范围 1-200，`count>1` 时返回 `data` 为 IP 数组。
- 场景：网关项目一次取多个 IP 做连通性批量筛选。

### 2. 延迟筛选 `GET /get?max_latency_ms=3000`
- `service.get/get_many` 新增 `max_latency_ms` 参数，只返回延迟<=该值的代理。
- random 策略 `_SERVICE_PARAMS` 加该参数透传（rotate/sticky 走 pool 不走此筛选，保持原语义）。

### 3. 分页列表 `GET /list?page=&size=&need=&type=`
- `service.list_all()`：按信任分降序分页，返回 total + 本页明细。
- size 默认 20 上限 100，page 从 1 起。
- 用途：网关/运维查看池内概况（IP、region、https、latency、score）。

### 4. 健康检查 `GET /health`
- 返回 `of status ok|degraded` + 池子水位 + 各服务 current/min。
- 用途：监控探活、判断池子健康度（哪层低于下限一眼可见）。

## 技术决策及理由

1. **批量取权偏好用"加权随机去重"**而非简单取前 N 个：每个候选仍按信任分加权，
   保证高可靠代理更常被选中，同时去重避免重复 IP。
2. **max_latency_ms 只透传给 random 策略**：rotate（纯轮换）、sticky（粘性）
   是特殊用途，不掺入延迟筛选，保持各自语义纯净。
3. **/health 直接复用 service.service_levels()**：不重写统计逻辑，水位判定与
   调度器同一口径，避免两套标准漂移。
4. **业务统计/鉴权/黑白名单不做**：明确归属网关项目（用户决策），避免本仓库
   膨胀、被无关敏感逻辑污染。

## 实际命令

```bash
# 批量取 5 个
curl "http://127.0.0.1:5010/get?need=global&count=5"
# 低延迟
curl "http://127.0.0.1:5010/get?need=global&max_latency_ms=3000"
# 分页
curl "http://127.0.0.1:5010/list?page=1&size=3&need=global"
# 健康检查
curl "http://127.0.0.1:5010/health"
```

## 验证结果（容器内）

```
/get?need=global&count=5 → 5 个去重 IP           ✅
/get?need=global&max_latency_ms=3000 → 低延迟 IP  ✅（latency<=3000）
/list?page=1&size=3 → {total:73, 按score降序}     ✅
/health → status:ok, 各层 current/min, global 全达标 ✅
```
pytest：test_proxy_service / test_strategy / test_api 共 17 passed。

## 下一步

- 生产部署：代码 + compose 同步到生产 Ubuntu 服务器，一条 `docker compose up -d`。
- 网关新项目：基于本仓库 `/get`（批量取用）取 IP → 测 opencode/zen 连通 →
  封装 OpenAI 兼容 API → 用量统计。见仓库外另一个新项目。