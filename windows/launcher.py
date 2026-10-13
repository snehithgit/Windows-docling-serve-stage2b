"""Standalone Windows desktop controller for bundled Docling and Stage-2B."""
from __future__ import annotations

import dataclasses
import logging
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "runtime" / "python.exe"
DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "DoclingStage2B"
PORTS = {"docling": 5001, "embedding": 8090, "stage2b": 8080}
LOG = DATA / "logs"
PROCESSES: list[tuple[str, subprocess.Popen, object]] = []


def environment() -> dict[str, str]:
    env = os.environ.copy()
    models = ROOT / "models"
    env.update({
        "CONFIG_PATH": str(DATA / "config.yaml"),
        "HF_HOME": str(models / "hf-home"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "DOCLING_SERVE_ARTIFACTS_PATH": str(models / "docling"),
        "DOCLING_ARTIFACTS_PATH": str(models / "docling"),
        "DOCLING_SERVE_SCRATCH_PATH": str(DATA / "scratch"),
        "DOCLING_SERVE_ENG_KIND": "local",
        "PYTHONUNBUFFERED": "1",
        "OMP_NUM_THREADS": str(min(os.cpu_count() or 2, 4)),
    })
    # The source backend is not installed globally. Keep it isolated.
    env["PYTHONPATH"] = str(ROOT / "stage2b")
    return env


def initialize_data() -> Path:
    for folder in ("input", "converted", "processed", "db", "logs", "scratch"):
        (DATA / folder).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "stage2b"))
    from app.config import AppConfig, save_config
    target = DATA / "config.yaml"
    if not target.exists():
        config = AppConfig()
        config.docling_url = "http://127.0.0.1:5001"
        config.retrieval_embedding_url = "http://127.0.0.1:8090"
        config.input_dir = str(DATA / "input")
        config.output_dir = str(DATA / "converted")
        config.processed_dir = str(DATA / "processed")
        config.database_path = str(DATA / "db" / "jobs.db")
        config.colab_api_key_path = str(DATA / "db" / "colab_koboldcpp.key")
        config.text_cloud_quota_state_path = str(DATA / "db" / "groq_quota.json")
        config.watcher_auto_run = False
        config.external_verifiers_enabled = False
        config.telegram_enabled = False
        config.validate()
        save_config(target, config)
    return target


def port_is_busy(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def spawn(name: str, args: list[str], env: dict[str, str]) -> subprocess.Popen:
    logfile = open(LOG / (name + ".log"), "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            args,
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=logfile,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        logfile.close()
        raise
    PROCESSES.append((name, proc, logfile))
    return proc


def is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for(name: str, url: str, proc: subprocess.Popen, deadline_seconds: int, progress) -> None:
    stop_at = time.monotonic() + deadline_seconds
    while time.monotonic() < stop_at:
        progress("Starting " + name + " ...")
        if proc.poll() is not None:
            raise RuntimeError(name + " exited (code " + str(proc.returncode) + "). Check " + str(LOG / (name + ".log")))
        if is_ready(url):
            return
        time.sleep(0.8)
    raise TimeoutError(name + " did not become ready. Check logs in " + str(LOG))


def start_services(progress) -> None:
    if not PYTHON.is_file():
        raise FileNotFoundError("Bundled Python runtime missing: " + str(PYTHON))
    if not (ROOT / "models" / "docling").is_dir():
        raise FileNotFoundError("Offline Docling models missing from installer")
    initialize_data()
    for name, port in PORTS.items():
        if port_is_busy(port):
            raise RuntimeError("Port " + str(port) + " is occupied. Close the conflicting service; refusing to connect to an unknown service.")
    env = environment()
    # Run service components as children so closing the desktop UI stops them.
    docling = spawn("docling", [str(PYTHON), "-m", "docling_serve", "run",
                               "--host", "127.0.0.1", "--port", "5001",
                               "--artifacts-path", str(ROOT / "models" / "docling")], env)
    wait_for("Docling Serve", "http://127.0.0.1:5001/health", docling, 240, progress)
    embedding = spawn("embedding", [str(PYTHON), "-m", "uvicorn", "windows.embedding_service:app",
                                    "--host", "127.0.0.1", "--port", "8090"], env)
    wait_for("Embedding service", "http://127.0.0.1:8090/health", embedding, 180, progress)
    backend = spawn("stage2b", [str(PYTHON), "-m", "uvicorn", "app.main:app",
                                "--host", "127.0.0.1", "--port", "8080"], env)
    wait_for("Stage-2B", "http://127.0.0.1:8080/", backend, 150, progress)


def stop_services() -> None:
    for _, proc, _ in reversed(PROCESSES):
        if proc.poll() is None:
            proc.terminate()
    for _, proc, _ in reversed(PROCESSES):
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    for _, _, handle in PROCESSES:
        handle.close()
    PROCESSES.clear()


def main() -> int:
    import tkinter as tk
    from tkinter import messagebox

    DATA.mkdir(parents=True, exist_ok=True)
    splash = tk.Tk()
    splash.title("Docling Stage-2B")
    splash.geometry("490x160")
    splash.resizable(False, False)
    splash.configure(bg="#122037")
    header = tk.Label(splash, text="Docling Stage-2B", font=("Segoe UI", 21, "bold"),
                      fg="#ffffff", bg="#122037")
    header.pack(padx=20, pady=(24, 8))
    status = tk.StringVar(value="Checking offline services...")
    label = tk.Label(splash, textvariable=status, font=("Segoe UI", 11),
                     fg="#b3c5e5", bg="#122037")
    label.pack(pady=5)

    def progress(msg):
        status.set(msg)
        splash.update()

    try:
        start_services(progress)
        splash.destroy()
        import webview
        webview.create_window(
            "Docling Stage-2B · Offline",
            "http://127.0.0.1:8080/",
            width=1480, height=940, min_size=(980, 650),
            confirm_close=True,
        )
        webview.start(gui="edgechromium", debug=False, private_mode=True)
        return 0
    except Exception as exc:
        logging.exception("Unable to start Docling desktop services")
        try:
            messagebox.showerror("Docling Stage-2B - Startup error",
                                 str(exc) + "\n\nLogs: " + str(LOG))
        except Exception:
            pass
        return 1
    finally:
        stop_services()
        try:
            if splash.winfo_exists():
                splash.destroy()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
