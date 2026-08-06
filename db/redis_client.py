"""Redis 存储层：封装代理池的全部 Redis 操作。

对外暴露语义化方法（put/get/pop/delete/getAll/count...），
内部维护两个结构：
  - use_proxy         (hash)  所有代理：field=ip:port, value=Proxy JSON
  - use_proxy:https   (set)   只含支持 https 的代理名单（加速过滤）
"""

import random

import redis

from model.proxy import Proxy


class RedisPool:
    def __init__(self, host="127.0.0.1", port=6379, db=0,
                 password=None, table_name="use_proxy"):
        self._redis = redis.Redis(
            host=host, port=port, db=db, password=password,
            decode_responses=True,
        )
        self.table_name = table_name
        self._table = table_name
        self._table_https = f"{table_name}:https"

    def put(self, proxy):
        """存一个代理。若是 https，同时加入 https 名单。"""
        self._redis.hset(self.table_name, proxy.proxy, proxy.to_json())
        if proxy.https:
            self._redis.sadd(self._table_https, proxy.proxy)

    def get(self, https=False):
        """随机取一个代理（不删除）。https=True 时只从 https 名单挑。"""
        if https:
            pick = self._redis.srandmember(self._table_https)
            if not pick:
                return None
        else:
            keys = self._redis.hkeys(self._table)
            if not keys:
                return None
            pick = random.choice(keys)
        return self._get_proxy(pick)

    def pop(self, https=False):
        """随机取一个并删除（消费式）。返回被删的代理，或 None。"""
        proxy = self.get(https)
        if proxy:
            self.delete(proxy)
        return proxy

    def delete(self, proxy):
        """删除一个代理（同时从 https 名单移除）。"""
        self._redis.hdel(self._table, proxy.proxy)
        if proxy.https:
            self._redis.srem(self._table_https, proxy.proxy)

    def getAll(self, https=False):
        """取回全部代理（列表）。https=True 时只返回 https 的。"""
        if https:
            members = self._redis.smembers(self._table_https)
            return [self._get_proxy(p) for p in members if p]
        raw = self._redis.hgetall(self._table)
        return [self._proxy_from_dict(v) for v in raw.values()]

    def count(self):
        """统计池子：total 总代理数，https https 代理数。"""
        return {
            "total": self._redis.hlen(self._table),
            "https": self._redis.scard(self._table_https),
        }

    def clear(self):
        """清空整个池子（删除两个结构）。"""
        self._redis.delete(self._table)
        self._redis.delete(self._table_https)

    def exists(self, proxy):
        return self._redis.hexists(self._table, proxy.proxy)

    def _get_proxy(self, proxy_str):
        raw = self._redis.hget(self._table, proxy_str)
        return raw and Proxy.create_from_json(raw)

    def _proxy_from_dict(self, json_str):
        return Proxy.create_from_json(json_str)