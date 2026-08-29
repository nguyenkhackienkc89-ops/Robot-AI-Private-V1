#!/usr/bin/env python3
from pathlib import Path
import shutil,datetime,sys

compose=Path(sys.argv[1]).expanduser().resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]/"docker-compose.yml"
text=compose.read_text(encoding="utf-8")
if "robot-ai-anywhere-gateway" in text:
    print("Anywhere gateway already present.")
    raise SystemExit(0)
if not text.lstrip().startswith("services:"):
    raise SystemExit("Unexpected compose structure; merge manually.")

snippet="""
  anywhere-gateway:
    image: nginx:1.27-alpine
    container_name: robot-ai-anywhere-gateway
    restart: unless-stopped
    depends_on:
      - xiaozhi-private
    volumes:
      - ./anywhere_gateway/nginx.conf:/etc/nginx/nginx.conf:ro
    ports:
      - "127.0.0.1:11438:8080"
    mem_limit: 96m
"""
stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak=compose.with_name(compose.name+f".pre-v68-{stamp}.bak")
shutil.copy2(compose,bak)
compose.write_text(text.rstrip()+"\n"+snippet.lstrip("\n"),encoding="utf-8")
print("Merged anywhere-gateway.")
print("Backup:",bak)
