"""代理池对外 API：让外部能按业务语义取用代理。

路由 / 参数：
  GET /get?mode=random|sticky|rotate&need=cn|global|any
           &type=http|https &security=strict|anon &quality=stable1|stable2|stable3
           &fast=1 &session=xxx &count=N
      随机/粘性/轮换取代理（不删除）；quality 是稳定性档位
      （stable1=通过≥1次验证、stable2=≥3次、stable3=≥5次）
  GET /pop?type=https&need=cn     按条件取一个并删除（消费式）
  GET /count                       池子统计（含分桶）
  GET /strategies                  列出当前可用取用策略

返回统一 JSON：{"code": 200/404, "data": ...}
"""

from flask import Flask, jsonify, request

from handler.proxy_service import ProxyService
from strategy.manager import StrategyManager


def _get_conf(request):
    """从 request 解析取用筛选条件。返回 (https, need, security, quality, fast)。"""
    https = request.args.get("type") == "https"
    need = request.args.get("need", "any")
    security = request.args.get("security")
    quality = request.args.get("quality")
    fast = request.args.get("fast") in ("1", "true")
    return https, need, security, quality, fast


def _mode_conf(request):
    """解析策略 mode 和 session。"""
    mode = request.args.get("mode", "random")
    session = request.args.get("session")
    return mode, session


def create_app(service=None, strategies=None):
    """创建 Flask 应用。service/strategies 可注入（测试换假实现）。"""
    service = service or ProxyService()
    strategy_mgr = strategies or StrategyManager()
    app = Flask(__name__)

    @app.route("/get")
    def get_proxy():
        https, need, security, quality, fast = _get_conf(request)
        mode, session = _mode_conf(request)
        proxy = strategy_mgr.get(
            service, mode=mode, session=session, need=need, https=https,
            security=security, quality=quality, fast=fast)
        if not proxy:
            return jsonify({"code": 404, "data": None, "msg": "池子里没有符合条件的代理"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/pop")
    def pop_proxy():
        https, need, security, _, _ = _get_conf(request)
        proxy = service.pop(https=https, need=need, security=security)
        if not proxy:
            return jsonify({"code": 404, "data": None, "msg": "池子里没有符合条件的代理"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/count")
    def count():
        return jsonify({"code": 200, "data": service.count()})

    @app.route("/strategies")
    def strategies_list():
        return jsonify({"code": 200, "data": strategy_mgr.list_strategies()})

    return app


if __name__ == "__main__":
    # 生产环境用 gunicorn 跑（见 Dockerfile / docker-compose.yml），
    # 这里仅保留本地开发入口并关闭 debug/reloader，避免调试器暴露。
    create_app().run(host="0.0.0.0", port=5010, debug=False)