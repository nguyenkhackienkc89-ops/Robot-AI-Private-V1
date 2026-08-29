#!/usr/bin/env python3
from pathlib import Path
import os,re,secrets,sys

if len(sys.argv)<3:
    raise SystemExit("Usage: patch_public_server_config.py <data/.config.yaml> <public_host>")

cfg=Path(sys.argv[1]).expanduser().resolve()
host=sys.argv[2].strip()
if not re.fullmatch(r"[A-Za-z0-9.-]+",host):
    raise SystemExit("public_host invalid")

here=Path(__file__).resolve().parent
envp=here/".env"
vals={}
for line in envp.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k,v=line.split("=",1); vals[k.strip()]=v.strip()
secret=vals.get("ROBOT_GATEWAY_SECRET","")
if not secret:
    raise SystemExit("ROBOT_GATEWAY_SECRET missing; run render_gateway.py first")

text=cfg.read_text(encoding="utf-8")
backup=cfg.with_name(cfg.name+".pre-v68.bak")
if not backup.exists():
    backup.write_text(text,encoding="utf-8")

ws=f"wss://{host}/r/{secret}/xiaozhi/v1/"
vision=f"https://{host}/r/{secret}/mcp/vision/explain"

# YAML is intentionally patched line-by-line to preserve the user's full config.
lines=text.splitlines()
out=[]
in_server=False
server_indent=None
seen_ws=False
seen_vision=False
seen_auth_key=False
auth_block_present=False
for i,line in enumerate(lines):
    if re.match(r"^server:\s*$",line):
        in_server=True; server_indent=0; out.append(line); continue
    if in_server and line and not line.startswith(" "):
        # add missing keys before leaving server block
        if not seen_ws: out.append(f'  websocket: "{ws}"')
        if not seen_vision: out.append(f'  vision_explain: "{vision}"')
        if not seen_auth_key:
            out.append(f'  auth_key: "{secrets.token_urlsafe(48)}"')
        if not auth_block_present:
            out += ["  auth:","    enabled: true","    allowed_devices: []","    expire_seconds: 3600"]
        in_server=False

    if in_server:
        if re.match(r"^\s{2}websocket:\s*",line):
            out.append(f'  websocket: "{ws}"'); seen_ws=True; continue
        if re.match(r"^\s{2}vision_explain:\s*",line):
            out.append(f'  vision_explain: "{vision}"'); seen_vision=True; continue
        if re.match(r"^\s{2}auth_key:\s*",line):
            out.append(line); seen_auth_key=True; continue
        if re.match(r"^\s{2}auth:\s*$",line):
            auth_block_present=True
    out.append(line)

if in_server:
    if not seen_ws: out.append(f'  websocket: "{ws}"')
    if not seen_vision: out.append(f'  vision_explain: "{vision}"')
    if not seen_auth_key: out.append(f'  auth_key: "{secrets.token_urlsafe(48)}"')
    if not auth_block_present:
        out += ["  auth:","    enabled: true","    allowed_devices: []","    expire_seconds: 3600"]

# If auth block already existed, force only enabled=true, preserve other values.
joined="\n".join(out)+"\n"
joined=re.sub(r"(?ms)(^\s{2}auth:\s*\n(?:^\s{4}.*\n)*)",lambda m:
    re.sub(r"(?m)^(\s{4})enabled:\s*\S+\s*$",r"\1enabled: true",m.group(1))
    if re.search(r"(?m)^\s{4}enabled:",m.group(1))
    else m.group(1)+"    enabled: true\n",joined, count=1)

cfg.write_text(joined,encoding="utf-8")
print("Updated:",cfg)
print("server.websocket =",ws)
print("server.vision_explain =",vision)
print("server.auth.enabled = true")
