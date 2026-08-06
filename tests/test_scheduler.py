import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeService:
    def __init__(self):
        self.calls = 0

    def refresh(self):
        self.calls += 1
        return (2, 5)  # (added, ok)

    def count(self):
        return {"total": 2, "https": 1}


def test_refresh_job_calls_service():
    from helper.scheduler import make_refresh_job

    svc = FakeService()
    job = make_refresh_job(svc)
    job()
    assert svc.calls == 1


if __name__ == "__main__":
    test_refresh_job_calls_service()
    print("test_refresh_job_calls_service OK")
    print("ALL PASSED")