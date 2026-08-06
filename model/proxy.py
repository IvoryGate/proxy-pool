"""Proxy 数据模型：池子里每个代理的"身份证"。

对应 Redis 里一格 field->value 的 value（一个 JSON 字符串）。
字段定义见 __init__。
"""


class Proxy:
    def __init__(self, proxy, https=False, fail_count=0, check_count=0,
                 last_status=False, last_time=None, source="", region="",
                 anonymous=""):
        self.proxy = proxy            # ip:port，唯一标识
        self.https = https            # 是否支持 https
        self.fail_count = fail_count  # 连续失败次数（淘汰依据）
        self.check_count = check_count  # 累计校验次数
        self.last_status = last_status  # 上次校验是否成功
        self.last_time = last_time    # 上次校验时间
        self.source = source          # 从哪个源抓来的
        self.region = region          # 地域
        self.anonymous = anonymous    # 匿名级别

    def to_dict(self):
        """转成字典，供 to_json 用。"""
        return {
            "proxy": self.proxy,
            "https": self.https,
            "fail_count": self.fail_count,
            "check_count": self.check_count,
            "last_status": self.last_status,
            "last_time": self.last_time,
            "source": self.source,
            "region": self.region,
            "anonymous": self.anonymous,
        }

    def to_json(self):
        """序列化成 JSON 字符串，存进 Redis。"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def create_from_json(cls, json_str):
        """从 Redis 里取出的 JSON 字符串还原成 Proxy 对象。"""
        import json
        data = json.loads(json_str)
        return cls(**data)
