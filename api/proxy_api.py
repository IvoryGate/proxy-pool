"""代理池对外 API：让外部能取用代理。

路由：
  GET /get?type=https   随机取一个代理（不删除）
  GET /pop?type=https   随机取一个并删除（消费式）
  GET /count            池子统计

返回统一 JSON：{"code": 200/404, "data": ...}
"""

from flask import Flask, jsonify, request

from handler.proxy_service import ProxyService


def create_app(service=None):
    """创建 Flask 应用。service 可注入（测试换假服务）。"""
    service = service or ProxyService()
    app = Flask(__name__)

    def _is_https_request():
        return request.args.get("type") == "https"

    @app.route("/get")
    def get_proxy():
        proxy = service.get(https=_is_https_request())
        if not proxy:
            return jsonify({"code": 404, "data": None, "msg": "池子空了"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/pop")
    def pop_proxy():
        proxy = service.pop(https=_is_https_request())
        if not proxy:
            return jsonify({"code": 404, "data": None, "msg": "池子空了"}), 404
        return jsonify({"code": 200, "data": proxy.proxy})

    @app.route("/count")
    def count():
        return jsonify({"code": 200, "data": service.count()})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5010, debug=True)