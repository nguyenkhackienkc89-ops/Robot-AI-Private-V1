#!/bin/bash
set -euo pipefail
ollama stop qwen3.5:35b-a3b-int4 >/dev/null 2>&1 || true
ollama stop qwen3.5:35b-a3b >/dev/null 2>&1 || true
ollama ps || true
