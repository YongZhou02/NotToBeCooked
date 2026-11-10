"""Start the existing local NTBC database/API/web without changing saved configuration."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"
LOGS = ROOT / "output" / "demo-run"
sys.path.insert(0, str(API))
from app.core.config import settings


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def http_ok(url, expected):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return expected in response.read().decode("utf-8")
    except (OSError, ValueError):
        return False


def wait_for(check, label, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            print(f"[OK] {label}", flush=True)
            return
        time.sleep(1)
    raise RuntimeError(f"{label} did not become ready. See {LOGS}")


def background(args, cwd, env, name):
    LOGS.mkdir(parents=True, exist_ok=True)
    with (LOGS / f"{name}.log").open("ab") as log:
        process = subprocess.Popen(
            args,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    print(f"Started {name}, PID {process.pid}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Only check already running services")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if settings.LLM_FAKE_MODE:
        raise RuntimeError("LLM_FAKE_MODE is enabled; real interview Q&A requires false.")
    if not settings.GEMINI_API_KEY.get_secret_value():
        raise RuntimeError("GEMINI_API_KEY is not configured in apps/api/.env.")
    print("[OK] Real-model configuration is present (no secrets displayed).", flush=True)

    if not port_open(5432) and not args.check:
        docker = shutil.which("docker")
        if not docker:
            raise RuntimeError("Docker Desktop is required for the saved local database.")
        # Start only the existing container. Never recreate a database or volume.
        result = subprocess.run([docker, "start", "not_to_be_cooked_db"], capture_output=True, check=False)
        if result.returncode:
            raise RuntimeError("Open Docker Desktop, wait until it is ready, then run this launcher again.")
    wait_for(lambda: port_open(5432), "Existing local PostgreSQL", timeout=15 if args.check else 60)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if os.name == "nt":
        # The installed Docling/PyTorch pipeline otherwise tries to invoke cl.exe.
        env["TORCHDYNAMO_DISABLE"] = "1"
    if not port_open(8000) and not args.check:
        background([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], API, env, "api")
    wait_for(lambda: http_ok("http://127.0.0.1:8000/health", '"ok"'), "NTBC API", timeout=10 if args.check else 90)

    if not port_open(5173) and not args.check:
        pnpm = shutil.which("pnpm.cmd") or shutil.which("pnpm")
        if not pnpm:
            raise RuntimeError("pnpm is not installed or not on PATH.")
        env["VITE_API_URL"] = "http://127.0.0.1:8000"
        background([pnpm, "--filter", "web", "dev", "--host", "127.0.0.1", "--port", "5173", "--strictPort"], ROOT, env, "web")
    wait_for(lambda: http_ok("http://127.0.0.1:5173", "NotToBeCooked"), "NTBC web", timeout=10 if args.check else 45)
    print("\nOpen http://127.0.0.1:5173/dashboard", flush=True)
    print("Use the existing local account. Online server accounts are separate.", flush=True)
    if not args.check and not args.no_browser:
        webbrowser.open("http://127.0.0.1:5173/dashboard")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        sys.exit(1)
