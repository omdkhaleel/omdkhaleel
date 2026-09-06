"""Local launcher: picks a free port, starts the API, waits for it to
report healthy, then opens the browser. This is what run.bat / run.sh
invoke, so the "pick another port if 8000 is busy" and "open the browser
only once the server is ready" requirements live in one place instead of
being reimplemented in batch/shell script.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
import uvicorn

from app import config
from app.main import app

HOST = "127.0.0.1"


def find_free_port(preferred: int, attempts: int = 25) -> int:
    for offset in range(attempts):
        port = preferred + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((HOST, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Could not find a free port near {preferred}")


def wait_and_open_browser(port: int) -> None:
    url = f"http://{HOST}:{port}"
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            response = httpx.get(f"{url}/api/health", timeout=1.0)
            if response.status_code == 200:
                print(f"\nServer is ready. Opening {url} in your browser...\n")
                webbrowser.open(url)
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.3)
    print(f"\nServer did not report healthy in time. Try opening {url} manually.\n")


def main() -> None:
    port = find_free_port(config.DEFAULT_PORT)
    if port != config.DEFAULT_PORT:
        print(f"Port {config.DEFAULT_PORT} was busy, using {port} instead.")

    threading.Thread(target=wait_and_open_browser, args=(port,), daemon=True).start()

    print(f"Starting Real-Time Property Finder on http://{HOST}:{port}")
    uvicorn.run(app, host=HOST, port=port, log_level="info")


if __name__ == "__main__":
    main()
