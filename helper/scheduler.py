"""调度器：让池子定时自动抓取，不需要人守着。

用 APScheduler 的 BlockingScheduler 安排定时任务：
  - 抓取任务：每 REFRESH_INTERVAL 分钟抓一批新代理入库（refresh_job）

先只挂抓取任务，等 check_pool（复核+淘汰）写好后再加上。
"""

from apscheduler.schedulers.blocking import BlockingScheduler

from handler.proxy_service import ProxyService

# 抓取间隔（分钟）
REFRESH_INTERVAL = 5


def make_refresh_job(service):
    """返回一个定时抓取任务闭包，注入 service 以便测试替换。"""
    def refresh_job():
        print(">> 抓取任务触发")
        added, ok = service.refresh()
        print(f"   本次可用 {ok}，新增 {added}，池子 {service.count()}")
    return refresh_job


def run_scheduler():
    service = ProxyService()
    scheduler = BlockingScheduler()

    scheduler.add_job(make_refresh_job(service), "interval",
                      minutes=REFRESH_INTERVAL)
    print(f"调度器启动，每 {REFRESH_INTERVAL} 分钟抓取一次。Ctrl+C 停止。")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    run_scheduler()