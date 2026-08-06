import redis

r = redis.Redis(host="127.0.0.1", port=6379, db=0, decode_responses=True)

r.hset("use_proxy", "1.2.3.4:8080", '{"proxy":"1.2.3.4:8080","https":false,"fail_count":0}')
r.hset("use_proxy", "5.6.7.8:900", '{"proxy":"5.6.7.8:900","https":true,"fail_count":0}')

print("全部代理:", r.hgetall("use_proxy"))

keys = r.hkeys("use_proxy")
import random
pick = random.choice(keys)
print("随机抽到:", pick)
print("它的信息:", r.hget("use_proxy", pick))
