#!/usr/bin/env python3
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
ENV_FILE = HERE / ".env"
LOCK = Lock()
VALID_MODES = {"local", "cloud", "auto", "council"}

DEFAULTS = {
    "LOCAL_BASE_URL": "http://host.docker.internal:11434/v1",
    "LOCAL_MODEL": "tieude:qwen3-8b",
    "LOCAL_THINK": "false",
    "CLOUD_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
    "CLOUD_MODEL": "glm-4-flash",
    "CLOUD_API_KEY": "",
    "CLOUD_DAILY_LIMIT": "200",
    "AUTO_COMPLEXITY_THRESHOLD": "5",
    "AUTO_POLICY": "smart_free",
    "BLOCK_NONFREE_CLOUD": "true",
    "REQUEST_TIMEOUT_SECONDS": "90",
}

def load_env():
    env = dict(DEFAULTS)
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            env[k.strip()]=v.strip()
    for k in list(env):
        if os.getenv(k) is not None:
            env[k]=os.getenv(k)
    return env

def load_state():
    base={"mode":"auto","cloud_date":"","cloud_count":0,"last_route":"","last_error":""}
    if STATE_FILE.exists():
        try:
            obj=json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(obj,dict):
                base.update(obj)
        except Exception:
            pass
    if base["mode"] not in VALID_MODES:
        base["mode"]="auto"
    return base

def save_state(st):
    tmp=STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(STATE_FILE)

def is_true(v):
    return str(v).strip().lower() in {"1","true","yes","on"}

def free_glm_preset(env):
    base=env.get("CLOUD_BASE_URL","").rstrip("/")
    model=env.get("CLOUD_MODEL","").strip().lower()
    return (
        base=="https://open.bigmodel.cn/api/paas/v4"
        and model=="glm-4-flash"
    )

def cloud_ready(env):
    if not (env.get("CLOUD_BASE_URL") and env.get("CLOUD_MODEL") and env.get("CLOUD_API_KEY")):
        return False
    # V6.1 mặc định chặn mọi cloud không phải preset GLM-4-Flash.
    if is_true(env.get("BLOCK_NONFREE_CLOUD","true")) and not free_glm_preset(env):
        return False
    return True

def cloud_allow(env, st):
    today=time.strftime("%Y-%m-%d")
    if st.get("cloud_date") != today:
        st["cloud_date"]=today
        st["cloud_count"]=0
    limit=max(0,int(env.get("CLOUD_DAILY_LIMIT","50") or "50"))
    return cloud_ready(env) and (limit == 0 or int(st.get("cloud_count",0)) < limit)

def last_user_text(messages):
    for m in reversed(messages or []):
        if m.get("role")=="user":
            c=m.get("content","")
            if isinstance(c,str):
                return c
            return json.dumps(c,ensure_ascii=False)
    return ""

def action_like(text):
    t=text.casefold()
    words=[
        "tiến","lùi","quay","dừng","nhảy","múa","mở chrome","mở youtube",
        "mở word","finder","âm lượng","phát nhạc","radio","vov","đèn","khoảng cách"
    ]
    return any(x in t for x in words)

def privacy_sensitive(text):
    t=text.casefold()
    words=[
        "mật khẩu","password","mã otp","otp","cccd","căn cước","số tài khoản",
        "thẻ ngân hàng","mã pin","pin code","api key","khóa api","bí mật",
        "hợp đồng nội bộ","dữ liệu nội bộ","private","riêng tư"
    ]
    return any(x in t for x in words)

def casual_local(text):
    t=text.strip().casefold()
    if len(t) <= 24 and any(x in t for x in [
        "xin chào","chào","cảm ơn","mày là ai","tao đẹp trai","đẹp trai không",
        "tiểu đệ","đại ca"
    ]):
        return True
    return False

def complexity_score(messages):
    text=last_user_text(messages)
    t=text.casefold()
    score=0
    if len(text)>280: score+=1
    if len(text)>700: score+=2
    for k in [
        "phân tích","chiến lược","so sánh","đánh giá","nghiên cứu","lập kế hoạch",
        "phương án","rủi ro","tối ưu","dự báo","tổng hợp","phản biện","hội ý"
    ]:
        if k in t: score+=1
    if text.count("?")>=3: score+=1
    return score

def api_url(base):
    return base.rstrip("/") + "/chat/completions"

def http_json(url, payload, api_key="", timeout=90):
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    headers={"Content-Type":"application/json"}
    if api_key:
        headers["Authorization"]="Bearer "+api_key
    req=urllib.request.Request(url,data=data,headers=headers,method="POST")
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def normalize_messages_for_local(messages, model):
    out=json.loads(json.dumps(messages,ensure_ascii=False))
    if str(model).lower().startswith("qwen3"):
        for m in reversed(out):
            if m.get("role")=="user" and isinstance(m.get("content"),str):
                if not m["content"].lstrip().startswith("/no_think"):
                    m["content"]="/no_think "+m["content"]
                break
    return out

def call_brain(kind, incoming, env):
    body=dict(incoming)
    body["stream"]=False

    if kind=="local":
        model=env["LOCAL_MODEL"]
        body["model"]=model
        body["messages"]=normalize_messages_for_local(body.get("messages",[]),model)
        body["think"]=is_true(env.get("LOCAL_THINK","false"))
        return http_json(
            api_url(env["LOCAL_BASE_URL"]), body, "",
            int(env.get("REQUEST_TIMEOUT_SECONDS","90"))
        )

    if kind=="cloud":
        if not cloud_ready(env):
            raise RuntimeError("Não mây chưa được cấu hình API.")
        body["model"]=env["CLOUD_MODEL"]
        return http_json(
            api_url(env["CLOUD_BASE_URL"]), body, env["CLOUD_API_KEY"],
            int(env.get("REQUEST_TIMEOUT_SECONDS","90"))
        )

    raise ValueError(kind)

def extract_answer(resp):
    try:
        msg=resp["choices"][0]["message"]
        return msg.get("content") or ""
    except Exception:
        return ""

def sanitize_response(resp):
    clean=json.loads(json.dumps(resp,ensure_ascii=False))
    for choice in clean.get("choices",[]) or []:
        msg=choice.get("message")
        if isinstance(msg,dict):
            msg.pop("reasoning",None)
            msg.pop("thinking",None)
        delta=choice.get("delta")
        if isinstance(delta,dict):
            delta.pop("reasoning",None)
            delta.pop("thinking",None)
    return clean

def council(incoming, env):
    # Hội ý chỉ dùng cho phân tích, không để hai não cùng gọi hành động.
    stripped=dict(incoming)
    stripped.pop("tools",None)
    stripped.pop("tool_choice",None)
    local=call_brain("local",stripped,env)
    cloud=call_brain("cloud",stripped,env)
    a=extract_answer(local)
    b=extract_answer(cloud)

    synth_messages=[
        {
            "role":"system",
            "content":"Bạn là bộ tổng hợp. Hãy hợp nhất hai phương án dưới đây thành một câu trả lời cuối rõ ràng, chính xác, không nhắc tới việc có hai mô hình."
        },
        {
            "role":"user",
            "content":"PHƯƠNG ÁN NÃO NHÀ:\n"+a+"\n\nPHƯƠNG ÁN NÃO MÂY:\n"+b
        }
    ]
    synth={
        "model":env["LOCAL_MODEL"],
        "messages":synth_messages,
        "stream":False,
        "temperature":incoming.get("temperature",0.4)
    }
    return call_brain("local",synth,env)

def route(incoming):
    env=load_env()
    with LOCK:
        st=load_state()
        mode=st["mode"]

        if mode=="local":
            selected="local"
        elif mode=="cloud":
            if not cloud_allow(env,st):
                raise RuntimeError("Não mây chưa sẵn sàng hoặc đã chạm giới hạn ngày.")
            selected="cloud"
        elif mode=="council":
            if not cloud_allow(env,st):
                raise RuntimeError("Hội ý cần não mây được cấu hình và còn hạn mức.")
            selected="council"
        else:
            # AUTO V6.1 SMART-FREE:
            # - robot/Mac/sensitive/câu xã giao -> local
            # - câu hỏi kiến thức/đối thoại thông minh -> GLM-4-Flash nếu key sẵn sàng
            # - GLM lỗi/hết hạn mức -> local
            text=last_user_text(incoming.get("messages",[]))
            threshold=int(env.get("AUTO_COMPLEXITY_THRESHOLD","5") or "5")
            policy=env.get("AUTO_POLICY","smart_free").strip().lower()

            if action_like(text) or privacy_sensitive(text) or casual_local(text):
                selected="local"
            elif policy=="smart_free" and cloud_allow(env,st):
                selected="cloud"
            elif cloud_allow(env,st) and complexity_score(incoming.get("messages",[])) >= threshold:
                selected="cloud"
            else:
                selected="local"

        try:
            if selected=="council":
                st["cloud_count"]=int(st.get("cloud_count",0))+1
                resp=council(incoming,env)
            else:
                if selected=="cloud":
                    st["cloud_count"]=int(st.get("cloud_count",0))+1
                resp=call_brain(selected,incoming,env)
            st["last_route"]=selected
            st["last_error"]=""
            save_state(st)
            return resp, selected
        except Exception as first:
            st["last_error"]=str(first)
            # Fallback tự động giữa local/cloud, trừ council.
            if selected=="local" and cloud_allow(env,st):
                try:
                    st["cloud_count"]=int(st.get("cloud_count",0))+1
                    resp=call_brain("cloud",incoming,env)
                    st["last_route"]="cloud_fallback"
                    st["last_error"]=""
                    save_state(st)
                    return resp,"cloud_fallback"
                except Exception as second:
                    st["last_error"]=f"local={first}; cloud={second}"
            elif selected=="cloud":
                try:
                    resp=call_brain("local",incoming,env)
                    st["last_route"]="local_fallback"
                    st["last_error"]=""
                    save_state(st)
                    return resp,"local_fallback"
                except Exception as second:
                    st["last_error"]=f"cloud={first}; local={second}"
            save_state(st)
            raise RuntimeError(st["last_error"])

def openai_chunk_from_response(resp):
    choice=(resp.get("choices") or [{}])[0]
    msg=choice.get("message") or {}
    delta={"role":"assistant"}
    if msg.get("content") is not None:
        delta["content"]=msg.get("content")
    if msg.get("tool_calls"):
        delta["tool_calls"]=msg["tool_calls"]
    finish=choice.get("finish_reason") or ("tool_calls" if msg.get("tool_calls") else "stop")
    return delta, finish

class H(BaseHTTPRequestHandler):
    server_version="RobotDualBrain/6"

    def send_json(self,obj,code=200):
        data=json.dumps(obj,ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        n=int(self.headers.get("Content-Length","0"))
        raw=self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        env=load_env()
        st=load_state()
        if self.path in ("/health","/status"):
            self.send_json({
                "ok":True,
                "mode":st["mode"],
                "last_route":st.get("last_route",""),
                "last_error":st.get("last_error",""),
                "local_model":env["LOCAL_MODEL"],
                "cloud_ready":cloud_ready(env),
                "cloud_model":env.get("CLOUD_MODEL",""),
                "cloud_count_today":st.get("cloud_count",0),
                "cloud_daily_limit":int(env.get("CLOUD_DAILY_LIMIT","200") or "200"),
                "cloud_is_free_glm_preset":free_glm_preset(env),
                "block_nonfree_cloud":is_true(env.get("BLOCK_NONFREE_CLOUD","true")),
                "auto_policy":env.get("AUTO_POLICY","smart_free")
            })
            return
        if self.path=="/mode":
            self.send_json({"mode":st["mode"]})
            return
        if self.path=="/v1/models":
            self.send_json({
                "object":"list",
                "data":[{"id":"dual-brain","object":"model","owned_by":"robot-ai-private"}]
            })
            return
        self.send_json({"error":"not_found"},404)

    def do_POST(self):
        if self.path=="/mode":
            try:
                obj=self.read_json()
                mode=str(obj.get("mode","")).strip().lower()
                if mode not in VALID_MODES:
                    raise ValueError("mode phải là local/cloud/auto/council")
                with LOCK:
                    st=load_state()
                    st["mode"]=mode
                    save_state(st)
                self.send_json({"ok":True,"mode":mode})
            except Exception as e:
                self.send_json({"ok":False,"error":str(e)},400)
            return

        if self.path=="/v1/chat/completions":
            try:
                incoming=self.read_json()
                wants_stream=bool(incoming.get("stream",False))
                resp,selected=route(incoming)
                resp=sanitize_response(resp)

                if not wants_stream:
                    resp.setdefault("robot_brain",selected)
                    self.send_json(resp)
                    return

                delta,finish=openai_chunk_from_response(resp)
                rid=resp.get("id","chatcmpl-"+uuid.uuid4().hex)
                model=resp.get("model","dual-brain")
                created=int(time.time())

                first={
                    "id":rid,"object":"chat.completion.chunk","created":created,"model":model,
                    "choices":[{"index":0,"delta":delta,"finish_reason":None}]
                }
                last={
                    "id":rid,"object":"chat.completion.chunk","created":created,"model":model,
                    "choices":[{"index":0,"delta":{},"finish_reason":finish}]
                }

                self.send_response(200)
                self.send_header("Content-Type","text/event-stream")
                self.send_header("Cache-Control","no-cache")
                self.send_header("Connection","close")
                self.end_headers()

                for obj in (first,last):
                    self.wfile.write(("data: "+json.dumps(obj,ensure_ascii=False)+"\n\n").encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except Exception as e:
                err={
                    "error":{
                        "message":str(e),
                        "type":"dual_brain_error",
                        "code":"dual_brain_error"
                    }
                }
                self.send_json(err,502)
            return

        self.send_json({"error":"not_found"},404)

    def log_message(self,fmt,*args):
        print(time.strftime("%H:%M:%S"), fmt%args)

if __name__=="__main__":
    print("Robot AI Dual Brain Router :11435")
    print("Modes: local | cloud | auto | council")
    ThreadingHTTPServer(("0.0.0.0",11435),H).serve_forever()
