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
# 说明：cn 已降为 0 —— 免费源里国内代理多为假端口/短命死货，无法长期维持水位，
#       也不再作为补源循环的硬性目标（不阻塞调度）。取用 cn 时池里有就用，没有就 404。
#       global 是当前系统真正可持续供给的区域，作为补源循环的唯一目标。
SERVICE_MIN = {
    "cn": {
        "all": 0,        # 国内普通 —— 尽力而为，不设硬下限
        "safe": 0,       # 国内且安全：同上
        "stable1": 0,
        "stable2": 0,
        "stable3": 0,
    },
    "global": {
        "all": 50,
        "safe": 10,
        "stable1": 20,
        "stable2": 10,
        "stable3": 5,
    },
}

# 稳定性档位 → 最低信任分
STABLE_LEVELS = {
    "stable1": 1,
    "stable2": 3,
    "stable3": 5,
}

# 补源循环：连续多少轮无新增就停止（避免无限追）
MAX_STALL_ROUNDS = 3
# 补源循环：单次最多补多少轮（含"每轮都新增"的情况），防止 job 单实例霸占调度器
# （配合 MAX_STALL_ROUNDS 双保险：无新增 3 轮停、或累计 MAX_WATERLINE_ROUNDS 轮必停）
MAX_WATERLINE_ROUNDS = 4
# 每轮源抓多少（水塘抽样，允许每次取不同批次，可放心取多些）
MAX_PER_SOURCE = 300


def service_candidates():
    """返回所有服务键列表，如 [("cn","all"),("cn","safe"),...]。"""
    out = []
    for region, specs in SERVICE_MIN.items():
        for svc in specs:
            out.append((region, svc))
    return out
