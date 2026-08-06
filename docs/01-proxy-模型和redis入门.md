# 阶段 01：Proxy 模型与 Redis 存取

## 背景思考

这是从零自研代理池的第一块正式业务代码。在写任何爬取/验证之前，必须先确定两件最底层的事：
1. **一个代理怎么表示**（数据模型）——存哪些字段、怎么序列化
2. **存到哪、怎么读写**——用 Redis 的哪种结构

用"先讲原理、再动手"的方式推进，同时把过程中学到的 Redis 知识沉淀到 `learn/` 目录当笔记。

## 完成内容

- **Redis 入门教学**：安装 redis-server、用 `redis-cli` 手动演练 `HSET/HGET/HKEYS/HLEN/HDEL/SADD/SRANDMEMBER`，
  存进 `learn/01_redis_入门.py`（含 Python 版对应实现）。
- **Proxy 数据模型** `model/proxy.py`：
  - 9 字段：`proxy, https, fail_count, check_count, last_status, last_time, source, region, anonymous`
  - `to_dict()` 转字典、`to_json()` JSON 序列化（存 Redis 用）、`create_from_json()` 反序列化（取回用）
- **落地测试** `tests/test_proxy.py`：验证 Proxy 存入 Redis → 取回 → 字段完全一致（roundtrip）。

## 技术决策及理由

- **字段只放了"当下够用"的**：第 3 层（region/anonymous）先留着但尚未用，避免过度设计。
- **序列化用 JSON**：Redis 无法直接存 Python 对象，用 ensure_ascii=False 存可读中文。
- **Redis 版本不动**：环境是 6.0.16，实测 `HRANDFIELD` 不存在，改用 `HKEYS` + 自随机 + `HGET` 的兼容做法。
  该取舍在代码注释和 learn 笔记里都交代了。
- **虚拟环境 .venv**：隔离依赖，不污染系统 Python；redis-py 8.1.0。

## 实际命令

```bash
# Redis（已装，略）
redis-cli ping                 # → PONG

# 建 venv 装依赖
python3 -m venv .venv
.venv/bin/pip install redis

# 跑测试
.venv/bin/python tests/test_proxy.py     # → roundtrip OK

# 提交
git commit -m "feat: Proxy 数据模型 + Redis 存取测试 (stage: 01)"
```

## 踩坑记录

- **坑 1：WSL 无 python3-venv**。现象：`python3 -m venv` 报 ensurepip 不可用 →
  解决：`sudo apt install python3.10-venv`。
- **坑 2：redis `HRANDFIELD` 命令不存在**。现象：redis-cli 报 unknown command →
  原因：Redis 6.0 版本太老（该命令是 7.2+）→ 解决：改用 `HKEYS`+随机+`HGET`，
  并决定本项目代码按 6.0 兼容写法，暂不升级。
- **坑 3：编辑工具 LSP 报 `import redis could not be resolved`** →
  原因：LSP 用的是系统 Python，找不到 venv 里的包 → 非真实错误，用 `.venv/bin/python` 运行即可，可忽略。

## 下一步

- 阶段 02：db 存储层（把 hash/set 操作封装成 DbClient 供全局复用）。
- 阶段 03：验证层（http/https validator + 失败淘汰策略）。
- 阶段 04：fetcher 插件框架（爬取源）。
- 阶段 05：调度器（APScheduler 定时抓取/校验）。
- 阶段 06：Flask API。
- 待办：把测试从裸脚本改造成 pytest 标准用例（CI 需要）。