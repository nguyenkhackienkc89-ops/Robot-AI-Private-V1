#!/usr/bin/env python3
import html, json, os, re, socket, subprocess, threading, time, urllib.parse, shutil
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TOKEN_FILE = Path(os.environ.get(
    "ROBOT_MAC_BRIDGE_TOKEN_FILE",
    str(Path.home() / ".config" / "robot-ai-private" / "mac_bridge_token"),
))

def load_token():
    token = os.environ.get("ROBOT_MAC_BRIDGE_TOKEN", "").strip()
    if not token and TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if len(token) < 40:
        raise RuntimeError("ROBOT_MAC_BRIDGE_TOKEN chưa được cấu hình an toàn")
    return token

TOKEN = load_token()
ROBOT_ADMIN_PORT = 8769
ROBOT_HELLO_PORT = 8770
WEB_PORT = 8767
STATE = {"robot_ip":"", "robot_last_seen":0}

SERVER_CFG = ROOT / "private_server_mac" / "data" / ".config.yaml"
SERVER_TEMPLATE = ROOT / "private_server_mac" / "data" / ".config.template.yaml"
PERSONA_FILE = ROOT / "agent_prompt_vi.txt"
OTA_DIR = ROOT / "private_server_mac" / "data" / "bin"
MUSIC_DIR = ROOT / "private_server_mac" / "music"

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=False)

def listen_robot():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    s.bind(("",ROBOT_HELLO_PORT))
    prefix="ROBOT_HELLO "+TOKEN+" "
    while True:
        data,addr=s.recvfrom(512)
        msg=data.decode(errors="ignore").strip()
        if msg.startswith(prefix):
            STATE["robot_ip"]=addr[0]
            STATE["robot_last_seen"]=int(time.time())

def robot_cmd(cmd):
    ip=STATE["robot_ip"]
    if not ip:
        return "ERR chưa phát hiện robot"
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.settimeout(1.2)
    s.sendto(("ROBOT_ADMIN "+TOKEN+" "+cmd).encode(),(ip,ROBOT_ADMIN_PORT))
    try:
        data,_=s.recvfrom(2048)
        return data.decode(errors="ignore")
    except Exception as e:
        return "ERR "+str(e)

def server_status():
    docker=sh(["docker","ps","--filter","name=robot-ai-private-xiaozhi","--format","{{.Status}}"]).stdout.strip()
    ollama=sh(["curl","-fsS","http://127.0.0.1:11434/api/tags"]).returncode==0
    return {"docker":docker or "không chạy", "ollama":ollama}


def brain_status():
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:11435/status",timeout=1.2) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok":False,"mode":"?","last_route":"","cloud_ready":False,"last_error":str(e)}

def set_brain_mode(mode):
    import urllib.request
    data=json.dumps({"mode":mode}).encode()
    req=urllib.request.Request(
        "http://127.0.0.1:11435/mode",data=data,
        headers={"Content-Type":"application/json"},method="POST"
    )
    with urllib.request.urlopen(req,timeout=2) as r:
        return r.read().decode()

def render(msg=""):
    st=server_status()
    bs=brain_status()
    rs=robot_cmd("STATUS") if STATE["robot_ip"] else "Chưa phát hiện"
    age=(int(time.time())-STATE["robot_last_seen"]) if STATE["robot_last_seen"] else -1
    music_count=sum(1 for p in MUSIC_DIR.rglob("*") if p.suffix.lower() in {".mp3",".wav",".m4a"}) if MUSIC_DIR.exists() else 0
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot AI Private V6</title>
<style>
body{font-family:-apple-system,BlinkMacSystemFont,Arial;margin:0;background:#0b1018;color:#e9f2ff}
main{max-width:980px;margin:auto;padding:24px} .card{background:#131c28;border:1px solid #27384d;border-radius:16px;padding:18px;margin:14px 0}
h1,h2{margin-top:0} input,textarea,button{font:inherit;border-radius:10px;border:1px solid #39506c;padding:10px;background:#0e1722;color:#fff}
button{cursor:pointer;margin:4px} input{width:140px} textarea{width:100%;min-height:260px;box-sizing:border-box}
.ok{color:#a9f5c4} .warn{color:#ffd58a} code{background:#09111a;padding:3px 6px;border-radius:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
</style></head><body><main>
<h1>Robot AI Private V6.1 · Smart-Free Dual Brain</h1>
<p>Trung tâm quản trị riêng trên Mac mini.</p>
{('<div class="card ok">'+html.escape(msg)+'</div>') if msg else ''}

<div class="grid">
<div class="card"><h2>Robot</h2>
<p>IP: <code>{html.escape(STATE["robot_ip"] or "chưa thấy")}</code></p>
<p>Lần thấy gần nhất: {age if age>=0 else "-"} giây</p>
<p><code>{html.escape(rs)}</code></p>
<form method="post" action="/robot">
<button name="cmd" value="STOP">Dừng khẩn cấp</button>
<button name="cmd" value="MOVE forward 35 300">Tiến thử</button>
<button name="cmd" value="MOVE backward 35 300">Lùi thử</button>
<button name="cmd" value="MOVE left 38 300">Trái</button>
<button name="cmd" value="MOVE right 38 300">Phải</button>
<button name="cmd" value="MOVE spin_right 40 1700">Quay 1 vòng</button>
</form>
<form method="post" action="/calibrate">
<p>Quay 360 ms: <input name="spin" value="1700" type="number" min="600" max="3000"></p>
<p>Dừng vật cản mm: <input name="stop" value="130" type="number" min="60" max="500"></p>
<button>Lưu hiệu chuẩn vào robot</button>
</form></div>


<div class="card"><h2>Hai bộ não</h2>
<p>Chế độ: <code>{html.escape(str(bs.get("mode","?")))}</code></p>
<p>Lượt gần nhất: <code>{html.escape(str(bs.get("last_route","")))}</code></p>
<p>Não mây GLM-4-Flash: <code>{"Sẵn sàng" if bs.get("cloud_ready") else "Chưa có API key"}</code></p>
<p>Lượt não mây hôm nay: <code>{bs.get("cloud_count_today",0)} / {bs.get("cloud_daily_limit",200)}</code></p>
<form method="post" action="/brain">
<button name="mode" value="local">Não nhà</button>
<button name="mode" value="cloud">Não mây GLM</button>
<button name="mode" value="auto">Tự động thông minh</button>
<button name="mode" value="council">Hội ý hai não</button>
</form>
<p class="warn">{html.escape(str(bs.get("last_error","")))}</p>
</div>

<div class="card"><h2>Máy chủ AI</h2>
<p>XiaoZhi: <code>{html.escape(st["docker"])}</code></p>
<p>Ollama: <code>{"OK" if st["ollama"] else "không chạy"}</code></p>
<form method="post" action="/server"><button name="op" value="restart">Khởi động lại AI</button></form>
<p>Giọng khóa: <code>vi-VN-NamMinhNeural</code></p>
<p>Vai: <b>Tiểu Đệ</b> · gọi người dùng: <b>Đại Ca</b></p></div>

<div class="card"><h2>Nhạc & radio</h2>
<p>Nhạc cục bộ trong server: <b>{music_count}</b> file.</p>
<p>Chép MP3/WAV vào <code>private_server_mac/music/</code>. XiaoZhi có plugin phát nhạc cục bộ qua loa robot.</p>
<form method="post" action="/media">
<input name="q" placeholder="Tên bài hát">
<button name="op" value="youtube">Tìm nhạc YouTube trên Mac</button>
<button name="op" value="vov1">VOV1</button>
<button name="op" value="vov2">VOV2</button>
<button name="op" value="vovgt">VOV Giao thông</button>
</form></div>

<div class="card"><h2>OTA</h2>
<p>Thư mục OTA: <code>{html.escape(str(OTA_DIR))}</code></p>
<p>Đặt file app OTA theo tên <code>robot-ai-private-v1_4.x.x.bin</code>.</p>
<form method="post" action="/open_ota"><button>Mở thư mục OTA</button></form>
<p class="warn">OTA dùng <b>xiaozhi.bin/app bin</b>, không dùng merged.bin.</p></div>
</div>

<div class="card"><h2>Tính cách</h2>
<form method="post" action="/persona">
<textarea name="persona">{html.escape(PERSONA_FILE.read_text(encoding="utf-8") if PERSONA_FILE.exists() else "")}</textarea>
<br><button>Lưu prompt nhân vật</button>
</form>
<p>Sau khi đổi prompt, khởi động lại AI để áp dụng.</p></div>

<div class="card"><h2>Từ đánh thức “Tiểu Đệ”</h2>
<p>Firmware đã chuẩn bị đường custom wake word. Để nhận câu “Tiểu Đệ” cục bộ cần <code>assets.bin</code> có model/command tương ứng.</p>
<p>Không dùng một file assets giả. Xem <code>wake_word/TIEU_DE_WAKE_WORD_VI.md</code>.</p></div>
</main></body></html>"""

def form(req):
    n=int(req.headers.get("Content-Length","0"))
    return urllib.parse.parse_qs(req.rfile.read(n).decode(errors="ignore"))

class H(BaseHTTPRequestHandler):
    def reply(self, body, code=200):
        data=body.encode()
        self.send_response(code); self.send_header("Content-Type","text/html; charset=utf-8")
        self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        self.reply(render())
    def do_POST(self):
        f=form(self); msg=""
        if self.path=="/robot":
            msg=robot_cmd(f.get("cmd",["STATUS"])[0])
        elif self.path=="/calibrate":
            spin=int(f.get("spin",["1700"])[0]); stop=int(f.get("stop",["130"])[0])
            msg=robot_cmd("SET_SPIN "+str(spin))+" | "+robot_cmd("SET_STOP "+str(stop))
        elif self.path=="/brain":
            try:
                msg=set_brain_mode(f.get("mode",["auto"])[0])
            except Exception as e:
                msg="ERR "+str(e)
        elif self.path=="/server":
            if f.get("op",[""])[0]=="restart":
                sh(["docker","restart","robot-ai-private-xiaozhi"]); msg="Đã yêu cầu khởi động lại XiaoZhi."
        elif self.path=="/persona":
            PERSONA_FILE.write_text(f.get("persona",[""])[0],encoding="utf-8")
            msg="Đã lưu prompt. Chạy lại SETUP hoặc đồng bộ config rồi restart AI."
        elif self.path=="/open_ota":
            OTA_DIR.mkdir(parents=True,exist_ok=True); sh(["open",str(OTA_DIR)]); msg="Đã mở thư mục OTA."
        elif self.path=="/media":
            op=f.get("op",[""])[0]; q=f.get("q",[""])[0]
            if op=="youtube": sh(["open","-a","Google Chrome","https://www.youtube.com/results?search_query="+urllib.parse.quote(q or "nhạc")])
            elif op=="vov1": sh(["open","https://vov1.vov.vn/"])
            elif op=="vov2": sh(["open","https://vov2.vov.vn/"])
            elif op=="vovgt": sh(["open","https://vovgiaothong.vn/"])
            msg="Đã gửi lệnh media."
        self.reply(render(msg))
    def log_message(self, *a): pass

if __name__=="__main__":
    threading.Thread(target=listen_robot,daemon=True).start()
    OTA_DIR.mkdir(parents=True,exist_ok=True); MUSIC_DIR.mkdir(parents=True,exist_ok=True)
    print("Robot AI Control Center: http://127.0.0.1:8767")
    ThreadingHTTPServer(("0.0.0.0",WEB_PORT),H).serve_forever()
