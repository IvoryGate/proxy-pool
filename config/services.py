"""服务与水位配置：定义"哪些服务必须达标"及各自下限。

服务 = 一个业务可交付的代理类型，用筛选条件描述。
水位 = 该服务池子里至少要有的数量。

结构：
  SERVICE_MIN = {
      "cn":   {"all": 50, "safe": 10, "stable": 20},
      "global": {"all": 50, "safe": 10, "stable": 20},
  }

即：国内普通池至少 40、能访问 opencode.ai 的 HTTPS 至少 10；国外普通至少 200、
HTTPS 至少 60。低于下限时，调度器触发补源循环，直到达标或源耗尽。
"""

# 各区域的服务下限
# 说明：cn 曾降为 0（免费源里国内代理多为假端口/短命死货，且此前不使用）。
#       但网关/zen 实际不区分区域，只要 IP 能发通 + 稳定 + https 就可用，
#       且 ip89/ip3366 等国内源持续供给新 IP。恢复 cn 为硬性补源目标，
#       让补源循环也维护国内池（新增候选 -> 网关 zen 探测自会筛选）。
#       水位给保守值：国内免费代理 https 通过率低，目标不宜追太高。
#
# 2026-10 现实值调整：免费源在"能访问 opencode.ai 的 HTTPS"这一项上通过率
# 只有个位数百分比，原 global/all=1000、stable1=400、safe=100 永远达不到，
# 调度器 5 分钟一轮、每轮验证 2000 个候选，把出口和目标站都打到限流，反而
# 制造大量假死。这里改成"够用且可达"的水位，并新增 https 目标（网关真正
# 消费的维度）。global/all 1000 → 200，safe 100 → 0（安全探针默认关闭）。
SERVICE_MIN = {
    "cn": {
        "all": 40,       # 国内普通
        "https": 10,     # 国内且能访问 opencode.ai
        "safe": 0,       # 国内且安全：免费源难以稳定维持，尽力而为
        "stable1": 20,
        "stable2": 8,
        "stable3": 3,
    },
    "global": {
        "all": 200,
        "https": 60,     # 网关真正需要的：HTTPS + 目标可达
        "safe": 0,       # 安全探针默认关闭，不再把 safe 当补源目标
        "stable1": 100,
        "stable2": 50,
        "stable3": 25,
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
# 一轮补源：候选翻倍（多源多量）会显著拉长验证时间（一次 ~400s），
# 配合下面增大单源抓取量，让一轮补源贡献更多合格代理（当前池子 https 太少、
# 换号空间不足，限流覆盖率太高）。验证仍是瓶颈，800 在可接受范围。
MAX_PER_SOURCE = 800
# 一轮 refresh 最多验证多少个新候选。抓取广度放开后候选可达 2万+（游标轮转），
# 全验证会卡死补源循环（验证才是瓶颈，万级候选要 10min+）。截断到上限：
# 超出的下轮游标继续前进自然补到，不会漏。配合游标实现"广撒网、分批验证"。
# 2000 → 一轮 ~200s；2 轮 ~400s，8 分钟水位周期内能完成（3000 时 2 轮 580s
# 超过周期导致 APScheduler skip，补源反而每 2 周期才跑一次）。
MAX_VERIFY_PER_REFRESH = 2000
# https 通过率优先的源：这些源的候选优先验证（放截断名单前）。
# 实测 https 通过率（抽样 60）：monosans 10%、dpangestuw 8.3%、aliilapro 6.7%、
# besjs/iplocate 3%。免费池里真 https 稀缺，优先验证高通过率源能让 https
# 以最快速度入库（网关 zen 只认 https 代理）。其它源候选在限额内仍会验证。
HTTPS_PRIORITY_SOURCES = ("monosans", "dpangestuw", "aliilapro",
                          "besjs", "iplocate")


def service_candidates():
    """返回所有服务键列表，如 [("cn","all"),("cn","safe"),...]。"""
    out = []
    for region, specs in SERVICE_MIN.items():
        for svc in specs:
            out.append((region, svc))
    return out
