# AGENTS.md — proxy-pool

> 任何 agent 进入本项目应首先阅读本文件。它保证每个 agent 会话都能：
> 知道项目在做什么、怎么运行、有哪些约定、当前推进到哪里、有哪些禁忌。

## 项目背景

**proxy-pool**：自研免费 HTTP/HTTPS 代理池。从多个第三方免费代理源抓取 `ip:port`，
经过格式/可用性/HTTPS 能力多层验证后存入 Redis，对外提供 `/get` `/pop` 等取用接口。

- 技术栈：Python 3.12 + redis + httpx（异步验证）+ Flask（API）+ APScheduler（调度）
- 最终形态：Docker 部署，Flask 服务对外提供取用接口，Redis 作唯一共享状态

## 仓库现状

- 本仓库为**从零自研**项目（区别于参考实现 `../proxy_pool`）。
- 当前进度以 `docs/PROGRESS.md` 为准。
- 可运行命令（随阶段补充）：
  - `pip install -r requirements.txt`（安装依赖）
  - `python proxy_pool.py`（启动调度 + API）
  - `python -m pytest`（测试）
  - `ruff check .`（lint）

## Skills（agent 可用技能）

- `engineering-discipline`：工程纪律（阶段化推进 + Conventional Commits + CI）

## 工程纪律约定（勿删）

1. 每个**开发阶段**建立独立文档 `docs/XX-<阶段名>.md`，口语化、尽量详细地记录过程。
   - 字段模板：背景思考 / 完成内容 / 技术决策及理由 / 实际命令 / 踩坑记录 / 下一步
2. 阶段完成时更新 `docs/PROGRESS.md`（总索引）：追加一行阶段记录 + 指向详细文档。
3. 阶段完成时使用规范的 git commit 消息（附 `stage: <编号>`，如 `stage: 02`）。
4. **不要跨目录修改无关文件**；如需联动外部仓库，遵守其自身边界。
5. 提交时绝不 include 密钥 / 凭证。

## Git 提交规范（Conventional Commits）

| type | 用途 |
|---|---|
| `feat:` | 新功能 |
| `fix:` | 修复 |
| `refactor:` | 重构（不改行为） |
| `docs:` | 文档 / 进度记录 |
| `chore:` | 杂项 / 依赖 / CI |
| `perf:` | 性能 |

阶段完成时建议附加 `stage: <阶段名>`。

## 当前阶段

以 `docs/PROGRESS.md` 最新记录为准。
