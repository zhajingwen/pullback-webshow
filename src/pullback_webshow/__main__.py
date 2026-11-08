"""本地 HTTP 服务：/ 返回页面和静态文件，/api/data 返回 K 线与回踩数据。"""

import argparse
import json
import sys
import traceback
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .data import build_payload, default_db_path

STATIC_DIR = Path(__file__).parent / "static"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, db_path: Path, coin: str, **kwargs) -> None:
        self.db_path = db_path
        self.coin = coin
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/api/data":
            self._send_data()
        else:
            super().do_GET()

    def _send_data(self) -> None:
        try:
            status, body = 200, build_payload(self.db_path, self.coin)
        except Exception as e:
            traceback.print_exc()
            status, body = 500, {"error": f"{type(e).__name__}: {e}"}
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="pullback-webshow", description=__doc__)
    parser.add_argument("--db", type=Path, default=default_db_path(), help="K 线库路径")
    parser.add_argument("--coin", default="HYPE")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(f"K 线库不存在: {args.db}", file=sys.stderr)
        return 1

    handler = partial(Handler, db_path=args.db, coin=args.coin)
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"K 线库: {args.db}\n页面地址: http://127.0.0.1:{args.port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
