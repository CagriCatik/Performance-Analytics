from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .live_activity import LiveActivityTracker


class _Handler(BaseHTTPRequestHandler):
    tracker: LiveActivityTracker
    elapsed_seconds: float = 30.0

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def _send_json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/activity":
            self._send_json(self.tracker.get_activity())
        elif self.path == "/tick":
            self._send_json(self.tracker.tick(self.elapsed_seconds))
        elif self.path == "/health":
            self._send_json({"status": "ok", "subscriptions": len(self.tracker.get_activity())})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        if self.path == "/tick":
            self._send_json(self.tracker.tick(self.elapsed_seconds))
        else:
            self._send_json({"error": "not found"}, 404)


def create_server(config_path: Path) -> tuple[HTTPServer, LiveActivityTracker]:
    from .config import load_config, load_yaml
    from .accounts import generate_accounts
    from .subscriptions import generate_subscriptions
    import random

    config = load_config(config_path)
    project_root = Path(config["_project_root"])
    seed = int(config["seed"])
    rng = random.Random(seed)
    regions_cfg = load_yaml(project_root / "config" / "regions.yaml")
    plans_cfg = load_yaml(project_root / "config" / "plans.yaml")
    live_cfg = config.get("live_feed", {})
    domain_cfg = config.get("domain_rules", {})

    accounts = generate_accounts(rng, int(config["dataset"]["accounts"]), regions_cfg, domain_cfg=domain_cfg)
    subscriptions, _ = generate_subscriptions(rng, int(config["dataset"]["subscriptions"]), accounts, plans_cfg, 0.0, domain_cfg=domain_cfg)

    tracker = LiveActivityTracker(subscriptions, live_cfg=live_cfg, seed=seed)

    class Handler(_Handler):
        pass

    Handler.tracker = tracker
    Handler.elapsed_seconds = float(live_cfg.get("update_interval_seconds", 30))

    host = live_cfg.get("server", {}).get("host", "127.0.0.1")
    port = int(live_cfg.get("server", {}).get("port", 8080))
    server = HTTPServer((host, port), Handler)
    return server, tracker


def run_server(config_path: Path) -> None:
    server, _ = create_server(config_path)
    host, port = server.server_address
    print(f"Live activity server running at http://{host}:{port}")
    print("  GET /activity  — current subscription activity")
    print("  POST /tick     — advance simulation one step")
    print("  GET /health    — server health check")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
