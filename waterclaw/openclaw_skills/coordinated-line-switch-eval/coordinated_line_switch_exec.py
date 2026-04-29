#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {"ok": True, "data": None, "error": None}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"network_error: {e.reason}") from e


def get_base_url(args_url: str | None) -> str:
    """
    获取 SCADA API base URL，优先级：
    1. 命令行参数 --base-url
    2. 环境变量 SCADA_BASE_URL
    3. 默认值 http://127.0.0.1:8081
    """
    if args_url:
        return args_url
    env_url = os.environ.get("SCADA_BASE_URL")
    if env_url:
        return env_url
    return "http://127.0.0.1:8081"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute coordinated line switch via SCADA WebAPI."
    )
    parser.add_argument(
        "--close-line",
        type=int,
        required=True,
        choices=[1, 2, 3],
        help="Line id to close (1|2|3).",
    )
    parser.add_argument(
        "--running",
        type=int,
        nargs="+",
        required=True,
        help="Current running lines (e.g., --running 1 2).",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="SCADA API base URL. 可从环境变量 SCADA_BASE_URL 读取，默认 http://127.0.0.1:8081",
    )
    parser.add_argument(
        "--requested-by",
        default="",
        help="Optional operator/agent identity for audit.",
    )
    args = parser.parse_args()

    # 构建新的 payload 格式
    # running: 当前运行的线路
    # close_line: 要关闭的线路数组
    payload = {
        "line_switch_state": {
            "running": args.running,
            "close_line": [args.close_line],
        }
    }
    if args.requested_by:
        payload["requested_by"] = args.requested_by

    base_url = get_base_url(args.base_url)
    url = f"{base_url.rstrip('/')}/monitor/apiForward/api/writeplc"
    
    try:
        result = post_json(url, payload)
    except RuntimeError as e:
        print(json.dumps({"ok": False, "data": None, "error": str(e)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
