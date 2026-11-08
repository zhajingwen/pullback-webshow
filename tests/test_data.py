"""用 history.db 的真实数据核对回踩映射，结果对照源项目 docs/回踩前低.md。"""

import unittest
from datetime import datetime, timedelta, timezone

from monitor_hype_volume_rate_multi2_long.pullback_low import PullbackParams

from pullback_webshow.data import Bar, build_payload, default_db_path, find_retests, load_bars

TF_MS = 5 * 60_000
CST = timezone(timedelta(hours=8))
# 文档第 6 节的统计截止时间；库以后增长也不影响这里的断言
DOC_END_MS = int(datetime(2026, 11, 4, 17, 33, tzinfo=CST).timestamp() * 1000)


def cst_ms(month: int, day: int, hour: int, minute: int) -> int:
    return int(datetime(2026, month, day, hour, minute, tzinfo=CST).timestamp() * 1000)


@unittest.skipUnless(default_db_path().exists(), "缺少 history.db")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bars = [b for b in load_bars(default_db_path(), "HYPE") if b.start_ms <= DOC_END_MS]
        cls.retests = find_retests(cls.bars, TF_MS, PullbackParams())

    def test_count_matches_doc(self) -> None:
        self.assertEqual(len(self.bars), 19384)
        self.assertEqual(len(self.retests), 126)

    def test_mark_is_first_touching_bar_in_tf(self) -> None:
        by_start = {b.start_ms: b for b in self.bars}
        for r in self.retests:
            self.assertGreaterEqual(r["time_ms"], r["tf_start_ms"])
            self.assertLess(r["time_ms"], r["tf_start_ms"] + TF_MS)
            self.assertLessEqual(by_start[r["time_ms"]].low, r["threshold"])
            for t in range(r["tf_start_ms"], r["time_ms"], 60_000):
                if t in by_start:
                    self.assertGreater(by_start[t].low, r["threshold"])

    def test_worked_example_in_doc(self) -> None:
        by_tf = {r["tf_start_ms"]: r for r in self.retests}
        for nth, (hour, minute) in enumerate([(13, 45), (15, 0), (16, 15)], start=1):
            r = by_tf[cst_ms(11, 3, hour, minute)]
            self.assertEqual(r["nth"], nth)
            self.assertEqual(r["anchor"], 83.176)

    def test_payload_is_complete(self) -> None:
        payload = build_payload(default_db_path(), "HYPE")
        self.assertEqual(payload["coin"], "HYPE")
        self.assertEqual(payload["tf_minutes"], 5)
        self.assertGreaterEqual(len(payload["bars"]), 19384)
        self.assertGreaterEqual(len(payload["retests"]), 126)


class EmptyDataTest(unittest.TestCase):
    def test_no_bars_no_retests(self) -> None:
        self.assertEqual(find_retests([], TF_MS, PullbackParams()), [])

    def test_too_few_bars_no_retests(self) -> None:
        bars = [Bar(i * 60_000, 1.0, 2.0, 0.5, 1.5, 10.0) for i in range(5)]
        self.assertEqual(find_retests(bars, TF_MS, PullbackParams()), [])


if __name__ == "__main__":
    unittest.main()
