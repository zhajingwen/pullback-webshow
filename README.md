# pullback-webshow

本地网页：查看全部 1 分钟 K 线和成交量，并标出被"回踩前低"算法打标的 K 线。

K 线来自 `monitor-hype-volume-rate-multi2-long` 的 `data/history.db`（只读）。库里不存回踩结果，每次请求都用该项目的 `pullback_low.py` 回放计算，所以算法和参数（`PULLBACK_*` 环境变量）与源项目保持一致。两个项目需放在同一目录下。

## 启动

```bash
uv run pullback-webshow
# 然后打开 http://127.0.0.1:8000
```

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--db` | 源项目的 `data/history.db`（或 `ARCHIVE_DB_PATH`） | K 线库 |
| `--coin` | `HYPE` | 币种 |
| `--port` | `8000` | 端口，只监听 `127.0.0.1` |

## 页面操作

- 滚轮缩放，拖动平移，"全览"回到全部 K 线
- "上一个 / 下一个"在回踩之间跳转
- 悬停查看 OHLCV；回踩 K 线还会显示第几次、前低、阈值、ATR 和锚点放量（`anchor_spike`）

## 标记口径

算法为 v2.1（见源项目 `docs/回踩前低.md`）：默认 `PULLBACK_TF_MINUTES=1`，状态机直接跑 1m（ATR60），箭头就标在触发回踩的那根 1m 上，数字表示这是该前低的第几次回踩。算法要等这根 1m **收盘**才确认回踩。

若把 `PULLBACK_TF_MINUTES` 设为大于 1（如 v1 的 5），算法在合成 K 线上判定回踩，箭头标在**该 tf 内第一根 `low ≤ 前低 + touch_atr × ATR` 的 1m K 线**上；此时箭头所在的 1m 早于确认时刻（tf 收盘），不能当作当根可知的信号。

## 测试

```bash
uv run python -m unittest discover -s tests
```

`static/lightweight-charts.standalone.production.js` 是 TradingView Lightweight Charts v5.2.1（Apache-2.0），内置在项目中，离线可用。
