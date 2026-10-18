"""调度器：让池子定时自动运转，不需要人守着。

用 APScheduler 的 BlockingScheduler 安排任务：
  - waterline_job：检查各服务水位，低于下限就持续补源（目标驱动）
  - check_job    ：复核池内老代理，淘汰失效
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from handler.proxy_service import ProxyService

# 检查水位 / 复核间隔（分钟）。
# 免费代理寿命分钟级：复核太快删不干净、太慢留死代理；补源太慢跟不上死亡速度。
# 复核从 1 分钟全量改为 3 分钟滚动复核（默认每次 100 个）：
# 全量复核每个代理要 2 次网络请求，160 个池子每分钟就是 300+ 请求，
# 既占满出口带宽，也容易把免费代理/目标站打出限流，反而制造假死。
WATERLINE_INTERVAL = 5
CHECK_INTERVAL = 3
CHECK_BATCH_LIMIT = 100


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
            checked, eliminated = service.check_pool(limit=CHECK_BATCH_LIMIT)
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