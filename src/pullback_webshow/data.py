"""读取 1m K 线，回放回踩前低状态机，并把 5m 上的回踩映射到 1m K 线。"""

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Sequence
from urllib.parse import quote

from monitor_hype_volume_rate_multi2_long import config
from monitor_hype_volume_rate_multi2_long.pullback_low import (
    RETEST,
    PullbackParams,
    PullbackTracker,
    merge_bars,
)

BAR_MS = 60_000


class Bar(NamedTuple):
    start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


def default_db_path() -> Path:
    """与 pullback_stats 相同的来源：ARCHIVE_DB_PATH，否则为源项目的 data/history.db。"""
    if config.ARCHIVE_DB_PATH:
        return Path(config.ARCHIVE_DB_PATH)
    return Path(config.__file__).resolve().parents[2] / "data" / "history.db"


def load_bars(db_path: Path, coin: str) -> List[Bar]:
    """只读打开数据库，按时间升序返回全部 1m K 线。"""
    uri = f"file:{quote(str(Path(db_path).resolve()))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        rows = conn.execute(
            """
            SELECT start_ms, open, high, low, close, volume FROM candles
            WHERE coin=? AND interval='1m' ORDER BY start_ms
            """,
            (coin,),
        ).fetchall()
    finally:
        conn.close()
    return [Bar(*row) for row in rows]


def find_retests(bars: Sequence[Bar], tf_ms: int, params: PullbackParams) -> List[Dict[str, Any]]:
    """回放状态机，把每次回踩标到所属 tf K 线内第一根 low ≤ 阈值的 1m K 线上。"""
    if not bars:
        return []
    bars_in_tf: Dict[int, List[Bar]] = defaultdict(list)
    for bar in bars:
        bars_in_tf[bar.start_ms // tf_ms * tf_ms].append(bar)

    tracker = PullbackTracker(tf_ms, params)
    retests = []
    for candle in merge_bars(bars, tf_ms, bars[-1].start_ms + BAR_MS):
        event = tracker.update(candle)
        if event is None or event.kind != RETEST:
            continue
        # tracker.atr 是判定本次回踩时用的 ATR，必须在推进下一根之前读取
        threshold = event.anchor + params.touch_atr * tracker.atr
        touched = next((b for b in bars_in_tf[candle.start_ms] if b.low <= threshold), None)
        if touched is None:
            raise ValueError(f"回踩 K 线 {candle.start_ms} 内找不到 low ≤ {threshold} 的 1m K 线")
        retests.append(
            {
                "time_ms": touched.start_ms,
                "tf_start_ms": candle.start_ms,
                "nth": event.retests,
                "anchor": event.anchor,
                "atr": tracker.atr,
                "threshold": threshold,
            }
        )
    return retests


def build_payload(db_path: Path, coin: str) -> Dict[str, Any]:
    """页面所需的全部数据。"""
    bars = load_bars(db_path, coin)
    params = PullbackParams()
    tf_minutes = config.PULLBACK_TF_MINUTES
    return {
        "coin": coin,
        "tf_minutes": tf_minutes,
        "params": params._asdict(),
        "bars": bars,
        "retests": find_retests(bars, tf_minutes * BAR_MS, params),
    }
