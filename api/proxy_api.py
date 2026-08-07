"""代理池对外 API：让外部能按业务语义取用代理。

路由 / 参数：
  GET /get?need=cn|global|any &type=http|https &security=strict|anon
           &quality=stable1|stable2|stable3 &fast=1 &count=N &max_latency_ms=2000
       随机/粘性/轮换取代理（不删除）；quality 是稳定性档位
       （stable1=通过≥1次验证、stable2=≥3次、stable3=≥5次）
       count=N 时批量返回 N 个（去重、按信任分加权选优，可能少于 N）
       max_latency_ms 只返回延迟不超过该值的代理
  GET /pop?type=https&need=cn     按条件取一个并删除（消费式）
  GET /list?page=1&size=20&need=global&type=https
       分页列出池内代理明细（按信任分降序，调试/维护用）
  GET /count                       池子统计（含分桶 + 各层水位是否达标）
  GET /health                      健康检查：池子水位 + 各服务达标情况
  GET /strategies                  列出当前可用取用策略

返回统一 JSON：{"code": 200/404, "data": ...}
"""

from flask import Flask, jsonify, request

from handler.proxy_service import ProxyService
from strategy.manager import StrategyManager


def _get_conf(request):
    """从 request 解析取用筛选条件。返回 (https, need, security, quality, fast, max_latency_ms)。"""
    https = request.args.get("type") == "https"
    need = request.args.get("need", "any")
    security = request.args.get("security")
    quality = request.args.get("quality")
    fast = request.args.get("fast") in ("1", "true")
    raw_lat = request.args.get("max_latency_ms")
    max_latency_ms = int(raw_lat) if raw_lat and raw_lat.isdigit() else None
    return https, need, security, quality, fast, max_latency_ms


def _mode_conf(request):
    """解析策略 mode 和 session。"""
    mode = request.args.get("mode", "random")
    session = request.args.get("session")
    return mode, session


def _safe_int(value, default, low=1, high=None):
    """把字符串安全转成整数，非法/越界回退默认。"""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    if v < low:
        return default
    if high is not None and v > high:
        return high
    return v


def _proxy_brief(p):
    """代理的简要信息（列表/健康用，不含内部计分细节）。"""
    return {
        "proxy": p.proxy,
        "region": p.region,
        "https": p.https,
        "latency_ms": p.latency_ms,
        "score": p.score,
    }


def create_app(service=None, strategies=None):
    """创建 Flask 应用。service/strategies 可注入（测试换假实现）。"""
    service = service or ProxyService()
    strategy_mgr = strategies or StrategyManager()
    app = Flask(__name__)

    @app.route("/get")
    def get_proxy():
        https, need, security, quality, fast, max_latency_ms = _get_conf(request)
        mode, session = _mode_conf(request)
        count = _safe_int(request.args.get("count"), 1, low=1, high=200)

        if count > 1:
            proxies = service.get_many(
                count, need=need, https=https, security=security,
                quality=quality, fast=fast, max_latency_ms=max_latency_ms)
            if not proxies:
                return jsonify({"code": 404, "data": None,
                                "msg": "池子里没有符合条件的代理"}), 404
            return jsonify({"code": 200, "data": [p.proxy for p in proxies]})

        proxy = strategy_mgr.get(
            service, mode=mode, session=session, need=need, https=https,
            security=security, quality=quality, fast=fast,
            max_latency_ms=max_latency_ms)
        if not proxy:
            return jsonify({"code": 404, "data": None,
                            "msg": "池子里没有符合条件的代理"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/pop")
    def pop_proxy():
        https, need, security, _, _, _ = _get_conf(request)
        proxy = service.pop(https=https, need=need, security=security)
        if not proxy:
            return jsonify({"code": 404, "data": None,
                            "msg": "池子里没有符合条件的代理"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/list")
    def list_proxies():
        https, need, _, _, _, _ = _get_conf(request)
        page = _safe_int(request.args.get("page"), 1, low=1)
        size = _safe_int(request.args.get("size"), 20, low=1, high=100)
        total, proxies = service.list_all(
            page=page, size=size, https=https, need=need)
        return jsonify({
            "code": 200,
            "data": {
                "total": total,
                "page": page,
                "size": size,
                "items": [_proxy_brief(p) for p in proxies],
            },
        })

    @app.route("/count")
    def count():
        return jsonify({"code": 200, "data": service.count()})

    @app.route("/health")
    def health():
        levels = service.service_levels()
        ok = not service.below_waterline(levels)
        return jsonify({
            "code": 200,
            "data": {
                "status": "ok" if ok else "degraded",
                "pool": service.count(),
                "levels": {
                    f"{r}/{s}": {"current": cur, "min": mn}
                    for (r, s), (cur, mn) in levels.items()
                },
            },
        })

    @app.route("/strategies")
    def strategies_list():
        return jsonify({"code": 200, "data": strategy_mgr.list_strategies()})

    return app


if __name__ == "__main__":
    # 生产环境用 gunicorn 跑（见 Dockerfile / docker-compose.yml），
    # 这里仅保留本地开发入口并关闭 debug/reloader，避免调试器暴露。
    create_app().run(host="0.0.0.0", port=5010, debug=False)
