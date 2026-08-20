"""调度器：让池子定时自动运转，不需要人守着。

用 APScheduler 的 BlockingScheduler 安排任务：
  - waterline_job：检查各服务水位，低于下限就持续补源（目标驱动）
  - check_job    ：复核池内老代理，淘汰失效
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from handler.proxy_service import ProxyService

# 检查水位 / 复核间隔（分钟）。
# 免费代理寿命分钟级：复核太快删不干净、太慢留死代理；补源太慢跟不上死亡速度。
# 实测：复核 1 分钟、补源 3 分钟，能让池子"边漏边补"保持水位。
# 2026-08 补源提速（多页抓取+游标轮转）后单轮 refresh 耗时 ~100-350s
# （抓取广度放开、验证量受控）。周期太短会导致补源 job 尚未结束就触发下轮
# （APScheduler 默认 max_instances=1 会 skip，补源频率反而下降）。
# 放宽到 8 分钟：给 1-2 轮补源留足时间，复核仍 1 分钟兜底。
WATERLINE_INTERVAL = 8
CHECK_INTERVAL = 1


def make_waterline_job(service):
    """返回水位检查任务闭包，注入 service 以便测试替换。"""
    def waterline_job():
        from config.services import MAX_PER_SOURCE
        print(">> 水位检查触发", flush=True)
        try:
            levels, rounds, ok = service.ensure_waterlines(
                max_per_source=MAX_PER_SOURCE)
            below = service.below_waterline(levels)
            if below:
                print(f"   补源 {rounds} 轮后仍未达标：", flush=True)
                for r, s, cur, mn in below:
                    print(f"     {r}/{s}: {cur}/{mn}", flush=True)
            else:
                print(f"   所有服务达标（补源 {rounds} 轮）", flush=True)
            print(f"   池子 {service.count()}", flush=True)
        except Exception:
            import traceback
            traceback.print_exc()
            print("   [waterline_job 异常，跳过本轮]", flush=True)
    return waterline_job


def make_check_job(service):
    """返回复核任务闭包，注入 service 以便测试替换。"""
    def check_job():
        print(">> 复核任务触发", flush=True)
        try:
            checked, eliminated = service.check_pool()
            print(f"   复核 {checked} 个，淘汰 {eliminated}，池子 {service.count()}",
                  flush=True)
        except Exception:
            import traceback
            traceback.print_exc()
            print("   [check_job 异常，跳过本轮]", flush=True)
    return check_job


def run_scheduler():
    service = ProxyService()
    scheduler = BlockingScheduler()

    scheduler.add_job(make_waterline_job(service), "interval",
                      minutes=WATERLINE_INTERVAL)
    scheduler.add_job(make_check_job(service), "interval",
                      minutes=CHECK_INTERVAL)
    print(f"调度器启动：每 {WATERLINE_INTERVAL} 分钟检查水位并补源，"
          f"每 {CHECK_INTERVAL} 分钟复核。Ctrl+C 停止。")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    run_scheduler()