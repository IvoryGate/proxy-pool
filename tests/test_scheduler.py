import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeService:
    def __init__(self):
        self.calls = 0
        self.check_calls = 0

    def ensure_waterlines(self, max_per_source=None):
        self.calls += 1
        return ({"('cn','all')": (30, 30)}, 1, True)  # (levels, rounds, ok)

    def below_waterline(self, levels):
        return []

    def check_pool(self):
        self.check_calls += 1
        return (3, 1)  # (checked, eliminated)

    def count(self):
        return {"total": 2, "https": 1}


def test_waterline_job_calls_service():
    from helper.scheduler import make_waterline_job

    svc = FakeService()
    job = make_waterline_job(svc)
    job()
    assert svc.calls == 1


def test_check_job_calls_service():
    from helper.scheduler import make_check_job

    svc = FakeService()
    job = make_check_job(svc)
    job()
    assert svc.check_calls == 1


if __name__ == "__main__":
    test_waterline_job_calls_service()
    test_check_job_calls_service()
    print("ALL PASSED")