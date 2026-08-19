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
# 说明：cn 曾降为 0（免费源里国内代理多为假端口/短命死货，且此前不使用）。
#       但网关/zen 实际不区分区域，只要 IP 能发通 + 稳定 + https 就可用，
#       且 ip89/ip3366 等国内源持续供给新 IP。恢复 cn 为硬性补源目标，
#       让补源循环也维护国内池（新增候选 -> 网关 zen 探测自会筛选）。
#       水位给保守值：国内免费代理 https 通过率低，目标不宜追太高。
SERVICE_MIN = {
    "cn": {
        "all": 100,      # 国内普通
        "safe": 0,       # 国内且安全：免费源难以稳定维持，尽力而为
        "stable1": 30,
        "stable2": 10,
        "stable3": 5,
    },
    "global": {
        "all": 1000,
        "safe": 100,
        "stable1": 400,
        "stable2": 200,
        "stable3": 100,
    },
}

# 稳定性档位 → 最低信任分
STABLE_LEVELS = {
    "stable1": 1,
    "stable2": 3,
    "stable3": 5,
}

# 补源循环：连续多少轮无新增就停止（避免无限追）
MAX_STALL_ROUNDS = 2
# 补源循环：单次最多补多少轮（含"每轮都新增"的情况），防止 job 单实例霸占调度器
# （配合 MAX_STALL_ROUNDS 双保险：无新增 2 轮停、或累计 MAX_WATERLINE_ROUNDS 轮必停）
# 注意：一轮 refresh 抓取+验证要 40-80s，轮数多了单次 job 跑不完 3 分钟周期，
# 下个周期会 skip（补源严重滞后）。2 轮内快速返回，保证每周期都能补。
MAX_WATERLINE_ROUNDS = 2
# 每轮源抓多少（直接取前 N；源已并行抓取，量别太大，验证才是瓶颈）。
# 120->250：主要大源(thespeedx/jetkai/monosans/databay)候选质量不错，
# 适度提高抓取量让它们贡献更多；验证仍是瓶颈，250 在可接受范围。
MAX_PER_SOURCE = 250


def service_candidates():
    """返回所有服务键列表，如 [("cn","all"),("cn","safe"),...]。"""
    out = []
    for region, specs in SERVICE_MIN.items():
        for svc in specs:
            out.append((region, svc))
    return out
