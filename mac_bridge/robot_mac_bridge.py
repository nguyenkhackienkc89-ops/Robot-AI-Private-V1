#!/usr/bin/env python3
import json, os, socket, subprocess, threading, urllib.parse, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "c86b643d7a75fa037d0538a909923a1c9543c9a235629029"
HTTP_PORT = 8765
DISCOVERY_PORT = 8766

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

if __name__=="__main__":
    threading.Thread(target=discovery,daemon=True).start()
    print(f"Robot Mac Bridge: HTTP {HTTP_PORT}, discovery {DISCOVERY_PORT}")
    ThreadingHTTPServer(("0.0.0.0",HTTP_PORT),Handler).serve_forever()
