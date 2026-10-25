#!/usr/bin/env python3
"""Run one bounded Check-Host check and preserve raw per-node results."""

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import time
from urllib.parse import quote, urlencode


BASE = "https://check-host.net"


def get_json(path, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Overall deadline exceeded")
    result = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--max-time",
         str(min(15, remaining)), "-H", "Accept: application/json", BASE + path],
        capture_output=True, text=True, timeout=remaining,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("type", choices=("http", "ping", "tcp", "dns", "udp"))
    parser.add_argument("host", help="Public target without secrets in the URL")
    parser.add_argument("--max-nodes", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--node", action="append", default=[])
    parser.add_argument("--deadline", type=float, default=45)
    args = parser.parse_args()
    if not 5 <= args.deadline <= 60:
        parser.error("--deadline must be between 5 and 60 seconds")
    if not args.host.strip() or any(c in args.host for c in "\r\n"):
        parser.error("Invalid target")
    if len(args.node) > 10:
        parser.error("Select at most 10 nodes for a one-off check")

    deadline = time.monotonic() + args.deadline
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "type": args.type, "target": args.host,
        "complete": False, "results": {}, "pending": [],
    }
    query = [("host", args.host)]
    query += [("node", node) for node in args.node] if args.node else [
        ("max_nodes", args.max_nodes)]
    try:
        started = get_json(f"/check-{args.type}?{urlencode(query)}", deadline)
        if not isinstance(started, dict) or started.get("ok") != 1:
            raise RuntimeError("API did not confirm check creation")
        for key in ("request_id", "permanent_link", "nodes"):
            report[key] = started.get(key)
        if not report["request_id"] or not isinstance(report["nodes"], dict) or not report["nodes"]:
            raise RuntimeError("Start response is missing request_id or nodes")
        report["pending"] = list(report["nodes"])
        path = "/check-result/" + quote(str(report["request_id"]), safe="")
        while time.monotonic() < deadline:
            results = get_json(path, deadline)
            if not isinstance(results, dict):
                raise RuntimeError("Unexpected API result format")
            report["results"].update({k: v for k, v in results.items() if v is not None})
            report["pending"] = [n for n in report["nodes"] if n not in report["results"]]
            if not report["pending"]:
                report["complete"] = True
                break
            time.sleep(min(3, max(0, deadline - time.monotonic())))
        if not report["complete"]:
            report["error"] = "Deadline exceeded; pending does not mean target failure"
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.TimeoutExpired) as error:
        report["error"] = str(error)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    sys.exit(main())
