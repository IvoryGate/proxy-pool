"""服务与水位配置：定义"哪些服务必须达标"及各自下限。

服务 = 一个业务可交付的代理类型，用筛选条件描述。
水位 = 该服务池子里至少要有的数量。

结构：
  SERVICE_MIN = {
      "cn":   {"all": 50, "safe": 10, "stable": 20},
      "global": {"all": 50, "safe": 10, "stable": 20},
  }

即：国内普通池至少 50、安全池至少 10、稳定池至少 20；国外同理。
低于下限时，调度器触发补源循环，直到达标或源耗尽。
"""

# 各区域的服务下限
SERVICE_MIN = {
    "cn": {
        "all": 30,      # 国内普通（能访问国内即可）
        "safe": 5,      # 国内且安全（匿名+未篡改）
        "stable": 10,   # 国内且稳定（信任分高）
    },
    "global": {
        "all": 30,
        "safe": 5,
        "stable": 10,
    },
}

# 补源循环：连续多少轮无新增就停止（避免无限抓）
MAX_STALL_ROUNDS = 3
# 每轮补源时每个源最多抓多少
MAX_PER_SOURCE = 100


def service_candidates():
    """返回所有服务键列表，如 [("cn","all"),("cn","safe"),...]。"""
    out = []
    for region, specs in SERVICE_MIN.items():
        for svc in specs:
            out.append((region, svc))
    return out
