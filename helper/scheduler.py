"""调度器：让池子定时自动运转，不需要人守着。

用 APScheduler 的 BlockingScheduler 安排两个定时任务：
  - refresh_job：抓一批新代理入库（每 REFRESH_INTERVAL 分钟）
  - check_job  ：复核池内老代理，淘汰失效（每 CHECK_INTERVAL 分钟）
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from handler.proxy_service import ProxyService

# 抓取 / 复核间隔（分钟）
REFRESH_INTERVAL = 5
CHECK_INTERVAL = 2


def make_refresh_job(service):
    """返回抓取任务闭包，注入 service 以便测试替换。"""
    def refresh_job():
        print(">> 抓取任务触发")
        added, ok = service.refresh()
        print(f"   本次可用 {ok}，新增 {added}，池子 {service.count()}")
    return refresh_job


def make_check_job(service):
    """返回复核任务闭包，注入 service 以便测试替换。"""
    def check_job():
        print(">> 复核任务触发")
        checked, eliminated = service.check_pool()
        print(f"   复核 {checked} 个，淘汰 {eliminated}，池子 {service.count()}")
    return check_job


def run_scheduler():
    service = ProxyService()
    scheduler = BlockingScheduler()

    scheduler.add_job(make_refresh_job(service), "interval",
                      minutes=REFRESH_INTERVAL)
    scheduler.add_job(make_check_job(service), "interval",
                      minutes=CHECK_INTERVAL)
    print(f"调度器启动：每 {REFRESH_INTERVAL} 分钟抓取，"
          f"每 {CHECK_INTERVAL} 分钟复核。Ctrl+C 停止。")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    run_scheduler()