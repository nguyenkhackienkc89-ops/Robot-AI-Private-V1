#!/usr/bin/env python3
from pathlib import Path
import os,re,secrets,sys

here=Path(__file__).resolve().parent
envp=here/".env"
vals={}
if envp.exists():
    for line in envp.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k,v=line.split("=",1); vals[k.strip()]=v.strip()

secret=vals.get("ROBOT_GATEWAY_SECRET","")
if not re.fullmatch(r"[A-Za-z0-9_-]{32,96}",secret):
    secret=secrets.token_urlsafe(36)
    vals["ROBOT_GATEWAY_SECRET"]=secret

host=vals.get("ANYWHERE_PUBLIC_HOST","").strip()
provider=vals.get("ANYWHERE_PROVIDER","tailscale").strip() or "tailscale"

envp.write_text(
    "\n".join(f"{k}={v}" for k,v in vals.items())+"\n",
    encoding="utf-8"
)
os.chmod(envp,0o600)

tpl=(here/"nginx.conf.template").read_text(encoding="utf-8")
(here/"nginx.conf").write_text(
    tpl.replace("__ROBOT_GATEWAY_SECRET__",secret),
    encoding="utf-8"
)

print("ROBOT_GATEWAY_SECRET generated/preserved.")
print("ANYWHERE_PROVIDER=",provider)
if host:
    print("PUBLIC_OTA_URL=https://%s/r/%s/xiaozhi/ota/"%(host,secret))
    print("PUBLIC_WS_URL=wss://%s/r/%s/xiaozhi/v1/"%(host,secret))
else:
    print("ANYWHERE_PUBLIC_HOST is not set yet.")
    print("After Tailscale Funnel/Cloudflare hostname is known, set it in .env and rerun.")
