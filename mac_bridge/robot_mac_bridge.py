#!/usr/bin/env python3
import json, os, socket, subprocess, threading, urllib.parse, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN_FILE = os.environ.get(
    "ROBOT_MAC_BRIDGE_TOKEN_FILE",
    os.path.expanduser("~/.config/robot-ai-private/mac_bridge_token")
)

def _load_token():
    token = os.environ.get("ROBOT_MAC_BRIDGE_TOKEN", "").strip()
    if not token and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            token = f.read().strip()
    if len(token) < 40:
        raise RuntimeError("ROBOT_MAC_BRIDGE_TOKEN chưa được cấu hình an toàn")
    return token

TOKEN = _load_token()
HTTP_PORT = 8765
DISCOVERY_PORT = 8766
ROBOT_ADMIN_PORT = 8769
ROBOT_HELLO_PORT = 8770
LATEST_ROBOT = {"ip":"", "last_seen":0}

def run(cmd):
    return subprocess.run(cmd, check=False, capture_output=True, text=True)

def osa(script):
    return run(["/usr/bin/osascript", "-e", script])

def open_url(url, app=None):
    if app:
        run(["/usr/bin/open", "-a", app, url])
    else:
        run(["/usr/bin/open", url])

def paste_text(text):
    p = subprocess.Popen(["/usr/bin/pbcopy"], stdin=subprocess.PIPE, text=True)
    p.communicate(text)
    osa('tell application "System Events" to keystroke "v" using command down')

def execute(action, value):
    if action == "open_chrome":
        run(["/usr/bin/open","-a","Google Chrome"])
    elif action == "open_safari":
        run(["/usr/bin/open","-a","Safari"])
    elif action == "open_youtube":
        open_url("https://www.youtube.com","Google Chrome")
    elif action == "youtube_search":
        open_url("https://www.youtube.com/results?search_query="+urllib.parse.quote(value),"Google Chrome")
    elif action == "web_search":
        open_url("https://www.google.com/search?q="+urllib.parse.quote(value),"Google Chrome")
    elif action == "open_word":
        run(["/usr/bin/open","-a","Microsoft Word"])
    elif action == "word_write":
        run(["/usr/bin/open","-a","Microsoft Word"])
        time.sleep(1.2)
        osa('tell application "System Events" to keystroke "n" using command down')
        time.sleep(0.8)
        paste_text(value)
    elif action == "open_finder":
        run(["/usr/bin/open", value or os.path.expanduser("~")])
    elif action == "open_app":
        if not value or "/" in value or "\\" in value:
            raise ValueError("Tên ứng dụng không hợp lệ")
        run(["/usr/bin/open","-a",value])
    elif action == "type_text":
        paste_text(value)
    elif action == "volume_up":
        osa('set volume output volume ((output volume of (get volume settings)) + 10)')
    elif action == "volume_down":
        osa('set volume output volume ((output volume of (get volume settings)) - 10)')
    elif action == "play_pause":
        osa('tell application "System Events" to key code 16 using {command down}')
    elif action == "play_music_youtube":
        open_url("https://www.youtube.com/results?search_query="+urllib.parse.quote(value or "nhạc"),"Google Chrome")
    elif action == "radio_vov1":
        open_url("https://vov1.vov.vn/","Google Chrome")
    elif action == "radio_vov2":
        open_url("https://vov2.vov.vn/","Google Chrome")
    elif action == "radio_vov_gt":
        open_url("https://vovgiaothong.vn/","Google Chrome")
    else:
        raise ValueError("Action không được cho phép: "+action)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/command" or self.headers.get("X-Robot-Token") != TOKEN:
            self.send_response(403); self.end_headers(); return
        try:
            n=int(self.headers.get("Content-Length","0"))
            body=json.loads(self.rfile.read(n) or b"{}")
            execute(str(body.get("action","")), str(body.get("value","")))
            out=json.dumps({"ok":True}).encode()
            self.send_response(200)
        except Exception as e:
            out=json.dumps({"ok":False,"error":str(e)}).encode()
            self.send_response(400)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(out)))
        self.end_headers(); self.wfile.write(out)

    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

def discovery():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("",DISCOVERY_PORT))
    while True:
        data,addr=s.recvfrom(256)
        if data.decode(errors="ignore").strip() == "ROBOT_DISCOVER "+TOKEN:
            s.sendto(("ROBOT_MAC "+TOKEN).encode(),addr)


def robot_hello_listener():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("",ROBOT_HELLO_PORT))
    prefix="ROBOT_HELLO "+TOKEN+" "
    while True:
        data,addr=s.recvfrom(512)
        msg=data.decode(errors="ignore").strip()
        if msg.startswith(prefix):
            LATEST_ROBOT["ip"]=addr[0]
            LATEST_ROBOT["last_seen"]=int(time.time())

def robot_admin(command, timeout=1.2):
    ip=LATEST_ROBOT.get("ip","")
    if not ip:
        raise RuntimeError("Chưa phát hiện robot trong LAN")
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(timeout)
    msg=("ROBOT_ADMIN "+TOKEN+" "+command).encode()
    s.sendto(msg,(ip,ROBOT_ADMIN_PORT))
    data,_=s.recvfrom(1024)
    return data.decode(errors="ignore")

if __name__=="__main__":
    threading.Thread(target=discovery,daemon=True).start()
    threading.Thread(target=robot_hello_listener,daemon=True).start()
    print(f"Robot Mac Bridge: HTTP {HTTP_PORT}, discovery {DISCOVERY_PORT}")
    ThreadingHTTPServer(("0.0.0.0",HTTP_PORT),Handler).serve_forever()
