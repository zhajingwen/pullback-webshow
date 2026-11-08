"""用 history.db 的真实数据核对回踩映射，结果对照源项目 docs/回踩前低.md。"""

import unittest
from datetime import datetime, timedelta, timezone

from monitor_hype_volume_rate_multi2_long import config
from monitor_hype_volume_rate_multi2_long.pullback_low import PullbackParams

from pullback_webshow.data import Bar, build_payload, default_db_path, find_retests, load_bars

TF_MS = config.PULLBACK_TF_MINUTES * 60_000
V1_TF_MS = 5 * 60_000
CST = timezone(timedelta(hours=8))


def cst_ms(month: int, day: int, hour: int, minute: int) -> int:
    return int(datetime(2026, month, day, hour, minute, tzinfo=CST).timestamp() * 1000)


# 文档第 6 节的统计数据：前 21,089 根 1m，最后一根 11-05 21:59；库以后增长也不影响这里的断言
DOC_END_MS = cst_ms(11, 5, 21, 59)
# v1 参数（文档 4.7 节例子用的 5m ATR14 参数）
V1_PARAMS = PullbackParams(14, 3.0, 1.5, 0.5, 1.0, 8.0, 24 * 3600_000)


def assert_first_touching(test: unittest.TestCase, bars, retests, tf_ms: int) -> None:
    by_start = {b.start_ms: b for b in bars}
    for r in retests:
        test.assertGreaterEqual(r["time_ms"], r["tf_start_ms"])
        test.assertLess(r["time_ms"], r["tf_start_ms"] + tf_ms)
        test.assertLessEqual(by_start[r["time_ms"]].low, r["threshold"])
        for t in range(r["tf_start_ms"], r["time_ms"], 60_000):
            if t in by_start:
                test.assertGreater(by_start[t].low, r["threshold"])


@unittest.skipUnless(default_db_path().exists(), "缺少 history.db")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bars = [b for b in load_bars(default_db_path(), "HYPE") if b.start_ms <= DOC_END_MS]
        cls.retests = find_retests(cls.bars, TF_MS, PullbackParams())

    def test_count_matches_doc(self) -> None:
        self.assertEqual(len(self.bars), 21089)
        self.assertEqual(len(self.retests), 254)

    def test_mark_is_first_touching_bar_in_tf(self) -> None:
        assert_first_touching(self, self.bars, self.retests, TF_MS)

    def test_worked_example_in_doc(self) -> None:
        # 文档 2.1 节：11-05 18:06 low 刺穿前低 83.048，仍按第 4 次回踩计数
        by_tf = {r["tf_start_ms"]: r for r in self.retests}
        r = by_tf[cst_ms(11, 5, 18, 6)]
        self.assertEqual(r["nth"], 4)
        self.assertEqual(r["anchor"], 83.048)

    def test_anchor_spike_present(self) -> None:
        self.assertTrue(all("anchor_spike" in r for r in self.retests))
        spikes = [r["anchor_spike"] for r in self.retests if r["anchor_spike"] is not None]
        self.assertTrue(spikes)
        self.assertTrue(all(s > 0 for s in spikes))

    def test_v1_5m_mapping(self) -> None:
        # 多周期口径：v1 参数在 5m 上回放，文档 4.7 节例子仍成立，且箭头落在 tf 内首根触及阈值的 1m
        retests = find_retests(self.bars, V1_TF_MS, V1_PARAMS)
        assert_first_touching(self, self.bars, retests, V1_TF_MS)
        by_tf = {r["tf_start_ms"]: r for r in retests}
        for nth, (hour, minute) in enumerate([(13, 45), (15, 0), (16, 15)], start=1):
            r = by_tf[cst_ms(11, 3, hour, minute)]
            self.assertEqual(r["nth"], nth)
            self.assertEqual(r["anchor"], 83.176)

    def test_payload_is_complete(self) -> None:
        payload = build_payload(default_db_path(), "HYPE")
        self.assertEqual(payload["coin"], "HYPE")
        self.assertEqual(payload["tf_minutes"], config.PULLBACK_TF_MINUTES)
        self.assertGreaterEqual(len(payload["bars"]), 21089)
        self.assertGreaterEqual(len(payload["retests"]), 254)


class EmptyDataTest(unittest.TestCase):
    def test_no_bars_no_retests(self) -> None:
        self.assertEqual(find_retests([], TF_MS, PullbackParams()), [])

    def test_too_few_bars_no_retests(self) -> None:
        bars = [Bar(i * 60_000, 1.0, 2.0, 0.5, 1.5, 10.0) for i in range(5)]
        self.assertEqual(find_retests(bars, TF_MS, PullbackParams()), [])


if __name__ == "__main__":
    unittest.main()
