#!/usr/bin/env python3
import json, subprocess, sys, pathlib

if len(sys.argv) != 4:
    print("Dùng: python3 flash_custom_assets.py flasher_args.json assets.bin /dev/cu.usbmodemXXXX")
    raise SystemExit(1)

flasher = pathlib.Path(sys.argv[1])
assets = pathlib.Path(sys.argv[2])
port = sys.argv[3]

data=json.loads(flasher.read_text(encoding="utf-8"))
flash_files=data.get("flash_files",{})
addr=None
for a,f in flash_files.items():
    if "assets" in str(f).lower():
        addr=a; break

if addr is None:
    print("Không tìm thấy partition assets trong flasher_args.json; không đoán địa chỉ.")
    raise SystemExit(2)

cmd=[sys.executable,"-m","esptool","--chip","esp32s3","--port",port,
     "write-flash",str(addr),str(assets)]
print(" ".join(cmd))
raise SystemExit(subprocess.call(cmd))
