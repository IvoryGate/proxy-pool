"""Redis 存储层：封装代理池的全部 Redis 操作。

对外暴露语义化方法（put/get/pop/delete/getAll/count...），
内部维护一个主结构 + 若干索引 set：
  - use_proxy         (hash)  所有代理：field=ip:port, value=Proxy JSON
  - use_proxy:https   (set)   支持 https 的代理名单（加速过滤）
  - use_proxy:cn      (set)   region=CN 的代理
  - use_proxy:global  (set)   region!=CN 的代理
  - use_proxy:safe    (set)   匿名(elite)且未篡改的代理

一致性说明：索引是"尽力同步"的——代理属性变化时 put 会增删索引，
但 get 从索引取到候选后仍会二次校验属性，过期索引不影响取用正确性
（留待下次 put 纠正）。
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
        self._table_cn = f"{table_name}:cn"
        self._table_global = f"{table_name}:global"
        self._table_safe = f"{table_name}:safe"

    def put(self, proxy):
        """存一个代理，并同步维护各索引 set。"""
        self._redis.hset(self.table_name, proxy.proxy, proxy.to_json())
        # https 索引
        if proxy.https:
            self._redis.sadd(self._table_https, proxy.proxy)
        else:
            self._redis.srem(self._table_https, proxy.proxy)
        # 区域索引
        cn = (proxy.region == "CN")
        if cn:
            self._redis.sadd(self._table_cn, proxy.proxy)
            self._redis.srem(self._table_global, proxy.proxy)
        else:
            self._redis.sadd(self._table_global, proxy.proxy)
            self._redis.srem(self._table_cn, proxy.proxy)
        # 安全索引：匿名(elite) 且 未篡改
        safe = (proxy.anonymous == "elite" and not proxy.tampered)
        if safe:
            self._redis.sadd(self._table_safe, proxy.proxy)
        else:
            self._redis.srem(self._table_safe, proxy.proxy)

    def get(self, https=False, region=None, safe=False):
        """按需取一个代理（不删除）。

        https=True：只要支持 https 的。
        region='cn'/'global'：限定区域。
        safe=True：只要安全（匿名+未篡改）的。
        满足条件越多，候选越少；取到后仍二次校验，防过期索引。
        """
        candidates = self._hkeys_all()
        if https:
            candidates &= self._redis.smembers(self._table_https)
        if region == "cn":
            candidates &= self._redis.smembers(self._table_cn)
        elif region == "global":
            candidates &= self._redis.smembers(self._table_global)
        if safe:
            candidates &= self._redis.smembers(self._table_safe)
        if not candidates:
            return None

        # 随机抽，逐个二次校验属性（索引可能过期）
        for _ in range(min(20, len(candidates))):
            pick = random.choice(list(candidates))
            proxy = self._get_proxy(pick)
            if not proxy:
                candidates.discard(pick)
                continue
            if self._matches(proxy, https, region, safe):
                return proxy
            candidates.discard(pick)
        return None

    def pop(self, https=False, region=None, safe=False):
        """按需取一个并删除（消费式）。返回被删的代理，或 None。"""
        proxy = self.get(https, region, safe)
        if proxy:
            self.delete(proxy)
        return proxy

    def get_many(self, count=10, https=False, region=None, safe=False):
        """按需取一批候选代理（不删除），供上层做信任分加权选优。

        返回尽量多的匹配代理（可能少于 count，取决于候选池）。
        """
        candidates = self._hkeys_all()
        if https:
            candidates &= self._redis.smembers(self._table_https)
        if region == "cn":
            candidates &= self._redis.smembers(self._table_cn)
        elif region == "global":
            candidates &= self._redis.smembers(self._table_global)
        if safe:
            candidates &= self._redis.smembers(self._table_safe)
        if not candidates:
            return []

        proxies = []
        for pick in candidates:
            proxy = self._get_proxy(pick)
            if proxy and self._matches(proxy, https, region, safe):
                proxies.append(proxy)
            if len(proxies) >= count:
                break
        return proxies

    def delete(self, proxy):
        """删除一个代理（从所有索引同步移除）。"""
        self._redis.hdel(self._table, proxy.proxy)
        for idx in (self._table_https, self._table_cn,
                    self._table_global, self._table_safe):
            self._redis.srem(idx, proxy.proxy)

    def getAll(self, https=False):
        """取回全部代理（列表）。https=True 时只返回 https 的。"""
        if https:
            members = self._redis.smembers(self._table_https)
            return [self._get_proxy(p) for p in members if p]
        raw = self._redis.hgetall(self._table)
        return [self._proxy_from_dict(v) for v in raw.values()]

    def count(self):
        """统计池子：total 总代理数，https https 代理数，及各索引规模。"""
        return {
            "total": self._redis.hlen(self._table),
            "https": self._redis.scard(self._table_https),
            "cn": self._redis.scard(self._table_cn),
            "global": self._redis.scard(self._table_global),
            "safe": self._redis.scard(self._table_safe),
        }

    def count_by_region(self, region, safe_only=False, stable_only=False):
        """统计某区域下符合条件的代理数。

        region      : 'cn' / 'global'
        safe_only   : True 只要匿名且未篡改的
        stable_only : True 只要信任分高的（score>=2）
        返回数量。基于主数据实时统计（不依赖索引），准确但略慢。
        """
        if region == "cn":
            keys = self._redis.smembers(self._table_cn)
        else:
            keys = self._redis.smembers(self._table_global)
        n = 0
        for key in keys:
            raw = self._redis.hget(self._table, key)
            if not raw:
                continue
            proxy = Proxy.create_from_json(raw)
            if safe_only and not (proxy.anonymous == "elite"
                                  and not proxy.tampered):
                continue
            if stable_only and (proxy.score < 2):
                continue
            n += 1
        return n

    def clear(self):
        """清空整个池子（删除主结构和所有索引）。"""
        self._redis.delete(self._table)
        for idx in (self._table_https, self._table_cn,
                    self._table_global, self._table_safe):
            self._redis.delete(idx)

    def exists(self, proxy):
        return self._redis.hexists(self._table, proxy.proxy)

    def _hkeys_all(self):
        return set(self._redis.hkeys(self._table))

    def _matches(self, proxy, https, region, safe):
        if https and not proxy.https:
            return False
        if region == "cn" and proxy.region != "CN":
            return False
        if region == "global" and proxy.region == "CN":
            return False
        if safe and not (proxy.anonymous == "elite"
                         and not proxy.tampered):
            return False
        return True

    def _get_proxy(self, proxy_str):
        raw = self._redis.hget(self._table, proxy_str)
        return raw and Proxy.create_from_json(raw)

    def _proxy_from_dict(self, json_str):
        return Proxy.create_from_json(json_str)