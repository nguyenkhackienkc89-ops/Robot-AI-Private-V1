#!/usr/bin/env python3
import json
import os
import time
import urllib.request

OLLAMA = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434").rstrip("/")
TARGET = os.getenv("LOCAL_PREWARM_MODEL", "tieude:qwen3.5-9b")
KEEP_ALIVE = os.getenv("LOCAL_KEEP_ALIVE", "10m")
NUM_CTX = int(os.getenv("LOCAL_NUM_CTX", "8192") or "8192")
INTERVAL = int(os.getenv("PREWARM_INTERVAL_SECONDS", "120") or "120")


def post(path, payload, timeout=60):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
    return json.loads(raw) if raw else {}


def get(path, timeout=10):
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def qwen_family(name):
    n = (name or "").lower()
    if ":cloud" in n:
        return False
    return "qwen3.5" in n or "qwen35" in n or "qwen3" in n


def loaded_models():
    try:
        return [m.get("name") or m.get("model") for m in get("/api/ps").get("models", [])]
    except Exception:
        return []


def unload_other_qwens():
    for name in loaded_models():
        if not name or name.lower() == TARGET.lower() or not qwen_family(name):
            continue
        try:
            post("/api/generate", {"model": name, "keep_alive": 0, "stream": False}, timeout=30)
            print(f"unloaded {name}", flush=True)
        except Exception as exc:
            print(f"failed to unload {name}: {exc}", flush=True)


def warm_once():
    unload_other_qwens()
    post(
        "/api/chat",
        {
            "model": TARGET,
            "messages": [{"role": "user", "content": "ping"}],
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"num_ctx": NUM_CTX, "num_predict": 1},
        },
        timeout=120,
    )
    loaded = [name for name in loaded_models() if name]
    print(
        f"{time.strftime('%Y-%m-%d %H:%M:%S')} prewarmed {TARGET} "
        f"keep_alive={KEEP_ALIVE} num_ctx={NUM_CTX} loaded={loaded}",
        flush=True,
    )


if __name__ == "__main__":
    while True:
        try:
            warm_once()
        except Exception as exc:
            print(f"prewarm failed: {exc}", flush=True)
        time.sleep(INTERVAL)
