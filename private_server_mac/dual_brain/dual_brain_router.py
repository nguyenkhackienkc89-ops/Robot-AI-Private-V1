#!/usr/bin/env python3
import json
import os
import re
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
import socket
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

HERE = Path(__file__).resolve().parent
STATE_FILE = HERE / "state.json"
ENV_FILE = HERE / ".env"
LOCK = Lock()
VALID_MODES = {"local", "fast", "deep", "cloud", "auto", "council"}

DEFAULTS = {
    # "auto" sẽ tìm tieude:qwen3-8b trước rồi qwen3:8b.
    "LOCAL_MODEL": "auto",
    "LOCAL_MODEL_CANDIDATES": "tieude:qwen3.5-9b,qwen3.5:9b,tieude:qwen3-8b,qwen3:8b",
    "LOCAL_BASE_URL": "http://host.docker.internal:11434/v1",

    # V6.1.1 FAST RESPONSE
    # Local đi qua native Ollama /api/chat để ép think=false chắc chắn.
    "LOCAL_API_MODE": "native",
    "LOCAL_THINK_DEFAULT": "false",
    "LOCAL_ALLOW_DEEP_THINK_TRIGGER": "true",
    "LOCAL_KEEP_ALIVE": "10m",
    "LOCAL_FALLBACK_KEEP_ALIVE": "2m",
    "LOCAL_NUM_CTX": "8192",
    "LOCAL_SINGLE_RESIDENT": "true",
    "LOCAL_MODEL_FALLBACK": "true",
    "LOCAL_SKIP_MODEL_DISCOVERY": "false",
    "LOCAL_NUM_PREDICT": "512",

    # Não mây miễn phí theo preset XiaoZhi công khai.
    "CLOUD_BASE_URL": "https://open.bigmodel.cn/api/paas/v4",
    "CLOUD_MODEL": "glm-4-flash",
    "CLOUD_API_KEY": "",
    "CLOUD_DAILY_LIMIT": "200",
    "AUTO_COMPLEXITY_THRESHOLD": "5",
    "AUTO_POLICY": "smart_free",
    "BLOCK_NONFREE_CLOUD": "true",
    "REQUEST_TIMEOUT_SECONDS": "90",
    "STREAMING_ENABLED": "true",
    "LOCAL_STREAMING_ENABLED": "true",
    "CLOUD_STREAMING_ENABLED": "true",
    "FAST_COMMANDS_ENABLED": "true",

    "DEEP_ENABLED": "true",
    "DEEP_BASE_URL": "http://host.docker.internal:31434/v1",
    "DEEP_MODEL": "qwen3.5:35b-a3b-int4",
    "DEEP_MODEL_CANDIDATES": "qwen3.5:35b-a3b-int4,qwen3.5:35b-a3b",
    "DEEP_NUM_CTX": "4096",
    "DEEP_NUM_PREDICT": "768",
    "DEEP_KEEP_ALIVE": "30m",
    "DEEP_THINK_DEFAULT": "false",
    "DEEP_COMPLEXITY_THRESHOLD": "2",
    "DEEP_HEALTH_TIMEOUT_SECONDS": "2",
    "DEEP_MAX_RTT_MS": "120",
    "DEEP_FALLBACK_TO_FAST": "true",
    "AUTO_PREFER_DEEP_FOR_COMPLEX": "true",
    "AUTO_CLOUD_FALLBACK_ONLY": "true",

    # V6.6 failover hardening.
    # Health check nhanh để tunnel down không làm robot chờ ~4 giây.
    "LOCAL_HEALTH_TIMEOUT_SECONDS": "3",
    "DEEP_HEALTH_TIMEOUT_SECONDS": "0.35",
    "DEEP_TCP_PREFLIGHT_TIMEOUT_SECONDS": "0.25",
    "DEEP_HEALTH_CACHE_SECONDS": "0.75",
    "DEEP_CIRCUIT_OPEN_SECONDS": "8",
    "DEEP_REQUEST_TIMEOUT_SECONDS": "2.0",
    "DEEP_FAILOVER_TARGET_MS": "1000",

    # V6.7 REAL-TIME KNOWLEDGE — FREE FIRST
    "LIVE_KNOWLEDGE_ENABLED": "true",
    "LIVE_KNOWLEDGE_URL": "http://live-knowledge:11437",
    "LIVE_KNOWLEDGE_TIMEOUT_SECONDS": "6.0",
    "LIVE_FORCE_DEEP": "true",
    "LIVE_MAX_SOURCES": "5",
    "LIVE_STRICT_GROUNDING": "true",
    "LIVE_PAID_SEARCH_ENABLED": "false",
}

_MODEL_CACHE = {"at": 0.0, "name": None}
_DEEP_HEALTH = {
    "at": 0.0,
    "result": None,
    "circuit_until": 0.0,
    "failures": 0,
    # V6.6 live hardening preserved into V6.7:
    # once the configured 35B model has been confirmed installed,
    # routine health checks use TCP-only to avoid /api/tags false circuit opens.
    "confirmed_model": "",
}
_DEEP_HEALTH_LOCK = Lock()

def load_env():
    env = dict(DEFAULTS)
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in list(env):
        if os.getenv(k) is not None:
            env[k] = os.getenv(k)
    return env

def load_state():
    base = {
        "mode": "auto",
        "cloud_date": "",
        "cloud_count": 0,
        "last_route": "",
        "last_error": "",
        "last_elapsed_ms": 0,
        "last_local_model": "",
        "last_local_think": False,
        "last_model_total_ms": 0,
        "last_model_load_ms": 0,
        "last_tokens_per_second": 0.0,
        "last_ttft_ms": 0,
        "last_stream_total_ms": 0,
        "last_stream_chunks": 0,
        "last_fast_command": "",
        "last_deep_model": "",
        "last_deep_rtt_ms": 0,
        "last_deep_ready": False,
        "last_deep_health_reason": "",
        "last_deep_failover_ms": 0,
        "last_live_used": False,
        "last_live_kind": "",
        "last_live_status": "",
        "last_live_sources": 0,
        "last_live_elapsed_ms": 0,
        "last_live_checked_at": "",
    }
    if STATE_FILE.exists():
        try:
            obj = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                base.update(obj)
        except Exception:
            pass
    if base["mode"] not in VALID_MODES:
        base["mode"] = "auto"
    return base

def save_state(st):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)

def is_true(v):
    return str(v).strip().lower() in {"1", "true", "yes", "on"}

def free_glm_preset(env):
    base = env.get("CLOUD_BASE_URL", "").rstrip("/")
    model = env.get("CLOUD_MODEL", "").strip().lower()
    return base == "https://open.bigmodel.cn/api/paas/v4" and model == "glm-4-flash"

def cloud_ready(env):
    if not (env.get("CLOUD_BASE_URL") and env.get("CLOUD_MODEL") and env.get("CLOUD_API_KEY")):
        return False
    if is_true(env.get("BLOCK_NONFREE_CLOUD", "true")) and not free_glm_preset(env):
        return False
    return True

def cloud_allow(env, st):
    today = time.strftime("%Y-%m-%d")
    if st.get("cloud_date") != today:
        st["cloud_date"] = today
        st["cloud_count"] = 0
    limit = max(0, int(env.get("CLOUD_DAILY_LIMIT", "200") or "200"))
    return cloud_ready(env) and (limit == 0 or int(st.get("cloud_count", 0)) < limit)

def last_user_text(messages):
    for m in reversed(messages or []):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, str):
                return c
            return json.dumps(c, ensure_ascii=False)
    return ""

def action_like(text):
    t = text.casefold()
    words = [
        "tiến", "lùi", "quay", "dừng", "nhảy", "múa", "mở chrome", "mở youtube",
        "mở word", "finder", "âm lượng", "phát nhạc", "radio", "vov", "đèn", "khoảng cách"
    ]
    return any(x in t for x in words)

def privacy_sensitive(text):
    t = text.casefold()
    words = [
        "mật khẩu", "password", "mã otp", "otp", "cccd", "căn cước", "số tài khoản",
        "thẻ ngân hàng", "mã pin", "pin code", "api key", "khóa api", "bí mật",
        "hợp đồng nội bộ", "dữ liệu nội bộ", "private", "riêng tư"
    ]
    return any(x in t for x in words)

def casual_local(text):
    t = text.strip().casefold()
    return len(t) <= 32 and any(x in t for x in [
        "xin chào", "chào", "cảm ơn", "mày là ai", "tao đẹp trai", "đẹp trai không",
        "tiểu đệ", "đại ca"
    ])

def force_local_request(text):
    t = text.casefold()
    return (
        "/think" in t
        or "/no_think" in t
        or "dùng não nhà" in t
        or "bằng não nhà" in t
        or "não nhà phân tích" in t
        or "não nhà suy luận" in t
    )

def wants_deep_local(text, env):
    t = text.casefold()
    if "/no_think" in t or "trả lời nhanh" in t or "không suy luận" in t:
        return False
    if not is_true(env.get("LOCAL_ALLOW_DEEP_THINK_TRIGGER", "true")):
        return is_true(env.get("LOCAL_THINK_DEFAULT", "false"))
    if "/think" in t:
        return True
    phrases = [
        "não nhà suy luận sâu",
        "dùng não nhà suy luận sâu",
        "bằng não nhà suy luận sâu",
        "não nhà nghĩ kỹ",
        "dùng não nhà nghĩ kỹ",
    ]
    if any(x in t for x in phrases):
        return True
    return is_true(env.get("LOCAL_THINK_DEFAULT", "false"))

def complexity_score(messages):
    text = last_user_text(messages)
    t = text.casefold()
    score = 0
    if len(text) > 280:
        score += 1
    if len(text) > 700:
        score += 2
    for k in [
        "phân tích", "chiến lược", "so sánh", "đánh giá", "nghiên cứu", "lập kế hoạch",
        "phương án", "rủi ro", "tối ưu", "dự báo", "tổng hợp", "phản biện", "hội ý"
    ]:
        if k in t:
            score += 1
    if text.count("?") >= 3:
        score += 1
    return score

def api_url(base):
    return base.rstrip("/") + "/chat/completions"

def ollama_root(base):
    b = base.rstrip("/")
    if b.endswith("/v1"):
        b = b[:-3]
    if b.endswith("/api"):
        b = b[:-4]
    return b.rstrip("/")

def http_json(url, payload, api_key="", timeout=90):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def http_get_json(url, timeout=5):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def list_local_models(env):
    timeout=float(env.get("LOCAL_HEALTH_TIMEOUT_SECONDS","3") or "3")
    data = http_get_json(ollama_root(env["LOCAL_BASE_URL"]) + "/api/tags", timeout=timeout)
    names = []
    for m in data.get("models", []):
        name = m.get("name") or m.get("model")
        if name:
            names.append(name)
    return names

def _model_family(name):
    n=(name or "").lower()
    if "qwen3.5" in n or "qwen35" in n:
        return "qwen3.5"
    if "qwen3" in n:
        return "qwen3"
    return ""

def resolve_local_models(env):
    configured=env.get("LOCAL_MODEL","auto").strip()
    if is_true(env.get("LOCAL_SKIP_MODEL_DISCOVERY","false")) and configured and configured.lower()!="auto":
        return [configured]
    try:
        installed=list_local_models(env)
    except Exception:
        installed=[]

    candidates=[x.strip() for x in env.get(
        "LOCAL_MODEL_CANDIDATES",
        "tieude:qwen3.5-9b,qwen3.5:9b,tieude:qwen3-8b,qwen3:8b"
    ).split(",") if x.strip()]

    if configured and configured.lower() != "auto":
        ordered=[configured]
        if is_true(env.get("LOCAL_MODEL_FALLBACK","true")):
            ordered += [x for x in candidates if x.lower()!=configured.lower()]
    else:
        ordered=candidates

    if not installed:
        return ordered if is_true(env.get("LOCAL_MODEL_FALLBACK","true")) else ordered[:1]

    actual_by_lower={x.lower():x for x in installed}
    resolved=[]
    for candidate in ordered:
        actual=actual_by_lower.get(candidate.lower())
        if actual and actual not in resolved:
            resolved.append(actual)

    for candidate in ordered:
        fam=_model_family(candidate)
        if not fam: continue
        for actual in installed:
            if actual not in resolved and _model_family(actual)==fam:
                resolved.append(actual)

    return resolved or ordered[:1]

def resolve_local_model(env):
    models=resolve_local_models(env)
    return models[0] if models else "qwen3.5:9b"

def list_loaded_models(env):
    try:
        data=http_get_json(ollama_root(env["LOCAL_BASE_URL"])+"/api/ps", timeout=3)
    except Exception:
        return []
    out=[]
    for m in data.get("models",[]):
        name=m.get("name") or m.get("model")
        if name: out.append(name)
    return out

def unload_local_model(env, model):
    try:
        http_json(
            ollama_root(env["LOCAL_BASE_URL"])+"/api/generate",
            {"model":model,"keep_alive":0,"stream":False},
            "", 15,
        )
        return True
    except Exception:
        return False

def enforce_single_resident(env, target):
    if not is_true(env.get("LOCAL_SINGLE_RESIDENT","true")):
        return []
    unloaded=[]
    for loaded in list_loaded_models(env):
        if loaded.lower()==target.lower():
            continue
        if _model_family(loaded) in {"qwen3.5","qwen3"}:
            if unload_local_model(env, loaded):
                unloaded.append(loaded)
    return unloaded



LIVE_REGEXES=[
    r"\bhôm nay\b",r"\bhôm qua\b",r"\bmới nhất\b",r"\bhiện tại\b",
    r"\bbây giờ\b",r"\bvừa xảy ra\b",r"\bvừa mới\b",r"\bsáng nay\b",
    r"\bchiều nay\b",r"\btối nay\b",r"\btrong ngày\b",r"\bthời tiết\b",
    r"\btỷ giá\b",r"\bgiá vàng\b",r"\bgiá bitcoin\b",r"\bgiá btc\b",
    r"\bgiá ethereum\b",r"\bgiá eth\b",r"\bkết quả mới\b",
    r"\btin mới\b",r"\btin tức\b",r"\btra cứu\b",r"\btìm trên mạng\b",
    r"\btìm trên web\b",r"\binternet\b",r"\bđang diễn ra\b",
]

def live_request(text):
    t=(text or "").casefold()
    return any(re.search(p,t) for p in LIVE_REGEXES)

def _post_json(url,obj,timeout=6.0):
    raw=json.dumps(obj,ensure_ascii=False).encode("utf-8")
    req=urllib.request.Request(
        url,data=raw,
        headers={"Content-Type":"application/json","User-Agent":"RobotAIRouter/6.7"},
        method="POST"
    )
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def live_fetch(text,env):
    if not is_true(env.get("LIVE_KNOWLEDGE_ENABLED","true")):
        return {
            "status":"disabled","kind":"none","sources":[],
            "checked_at":"","elapsed_ms":0
        }
    base=env.get("LIVE_KNOWLEDGE_URL","http://live-knowledge:11437").rstrip("/")
    timeout=float(env.get("LIVE_KNOWLEDGE_TIMEOUT_SECONDS","6.0") or "6.0")
    started=time.monotonic()
    try:
        obj=_post_json(base+"/query",{"query":text},timeout=timeout)
        if not isinstance(obj,dict):
            raise RuntimeError("live service returned non-object")
        obj.setdefault("elapsed_ms",round((time.monotonic()-started)*1000,1))
        return obj
    except Exception as e:
        return {
            "status":"unavailable",
            "kind":"unknown",
            "sources":[],
            "checked_at":"",
            "elapsed_ms":round((time.monotonic()-started)*1000,1),
            "summary":str(e)[:300],
        }

def live_grounding_message(text,live,env):
    status=str(live.get("status") or "unknown")
    checked=str(live.get("checked_at") or "")
    kind=str(live.get("kind") or "unknown")
    sources=live.get("sources") or []
    strict=is_true(env.get("LIVE_STRICT_GROUNDING","true"))

    if status!="ok" or not sources:
        return (
            "DỮ LIỆU THỜI GIAN THỰC KHÔNG XÁC MINH ĐƯỢC.\n"
            f"Trạng thái: {status}. Loại: {kind}. Kiểm tra lúc: {checked or 'không rõ'}.\n"
            "CÂU HỎI NGƯỜI DÙNG CẦN THÔNG TIN HIỆN TẠI.\n"
            "BẮT BUỘC: không dùng trí nhớ mô hình để bịa dữ liệu hiện tại. "
            "Hãy nói ngắn gọn rằng chưa xác minh được dữ liệu mới nhất và có thể thử lại."
        )

    lines=[
        "DỮ LIỆU THỜI GIAN THỰC ĐÃ TRA CỨU",
        f"Loại: {kind}",
        f"Kiểm tra lúc: {checked}",
        "Quy tắc: Chỉ dùng bằng chứng dưới đây cho các tuyên bố về hiện tại.",
        "Không suy diễn số liệu/diễn biến không có trong nguồn.",
        "Nếu các nguồn mâu thuẫn, phải nói rõ là chưa thống nhất.",
        "Khi nói, nêu tên 1-3 nguồn quan trọng và thời điểm nếu có; không cần đọc URL dài.",
    ]
    if strict:
        lines.append("Không thay thế bằng kiến thức cũ của mô hình khi nguồn không đủ.")
    for i,s in enumerate(sources[:int(env.get("LIVE_MAX_SOURCES","5") or "5")],1):
        lines.append(
            f"[{i}] {s.get('title','')} | {s.get('domain','')} | "
            f"{s.get('published','')} | {s.get('snippet','')}"
        )
    facts=live.get("facts")
    if facts:
        lines.append("DỮ LIỆU CÓ CẤU TRÚC: "+json.dumps(facts,ensure_ascii=False))
    return "\n".join(lines)

def apply_live_grounding(incoming,env,st):
    messages=list(incoming.get("messages") or [])
    text=last_user_text(messages)
    requested=live_request(text)
    if not requested:
        st["last_live_used"]=False
        return incoming,None

    live=live_fetch(text,env)
    ground=live_grounding_message(text,live,env)
    out=dict(incoming)
    # Put a system grounding message immediately before the last user message.
    insert_at=len(messages)
    for i in range(len(messages)-1,-1,-1):
        if messages[i].get("role")=="user":
            insert_at=i
            break
    messages.insert(insert_at,{"role":"system","content":ground})
    out["messages"]=messages

    st["last_live_used"]=True
    st["last_live_kind"]=str(live.get("kind") or "")
    st["last_live_status"]=str(live.get("status") or "")
    st["last_live_sources"]=len(live.get("sources") or [])
    st["last_live_elapsed_ms"]=float(live.get("elapsed_ms") or 0)
    st["last_live_checked_at"]=str(live.get("checked_at") or "")
    save_state(st)
    return out,live


def deep_env(env):
    d=dict(env)
    d["LOCAL_BASE_URL"]=env.get("DEEP_BASE_URL","http://host.docker.internal:31434/v1")
    d["LOCAL_MODEL"]=env.get("DEEP_MODEL","qwen3.5:35b-a3b-int4")
    d["LOCAL_MODEL_CANDIDATES"]=env.get(
        "DEEP_MODEL_CANDIDATES",
        "qwen3.5:35b-a3b-int4,qwen3.5:35b-a3b"
    )
    d["LOCAL_NUM_CTX"]=env.get("DEEP_NUM_CTX","4096")
    d["LOCAL_NUM_PREDICT"]=env.get("DEEP_NUM_PREDICT","768")
    d["LOCAL_KEEP_ALIVE"]=env.get("DEEP_KEEP_ALIVE","30m")
    d["LOCAL_FALLBACK_KEEP_ALIVE"]=env.get("DEEP_KEEP_ALIVE","30m")
    d["LOCAL_THINK_DEFAULT"]=env.get("DEEP_THINK_DEFAULT","false")
    d["LOCAL_MODEL_FALLBACK"]="false"
    d["LOCAL_SKIP_MODEL_DISCOVERY"]="true"
    d["LOCAL_SINGLE_RESIDENT"]="true"
    d["LOCAL_HEALTH_TIMEOUT_SECONDS"]=env.get("DEEP_HEALTH_TIMEOUT_SECONDS","0.35")
    d["REQUEST_TIMEOUT_SECONDS"]=env.get("DEEP_REQUEST_TIMEOUT_SECONDS","2.0")
    return d

def _deep_tcp_preflight(env):
    base=env.get("DEEP_BASE_URL","http://host.docker.internal:31434/v1")
    u=urllib.parse.urlparse(base)
    host=u.hostname or "host.docker.internal"
    port=u.port or (443 if u.scheme=="https" else 80)
    timeout=float(env.get("DEEP_TCP_PREFLIGHT_TIMEOUT_SECONDS","0.25") or "0.25")
    started=time.monotonic()
    with socket.create_connection((host,port),timeout=timeout):
        pass
    return round((time.monotonic()-started)*1000,1)

def mark_deep_failure(env, reason):
    now=time.monotonic()
    open_s=float(env.get("DEEP_CIRCUIT_OPEN_SECONDS","8") or "8")
    with _DEEP_HEALTH_LOCK:
        _DEEP_HEALTH["at"]=now
        _DEEP_HEALTH["failures"]=int(_DEEP_HEALTH.get("failures",0))+1
        _DEEP_HEALTH["circuit_until"]=now+open_s
        _DEEP_HEALTH["result"]={
            "ready":False,
            "reachable":False,
            "rtt_ms":0,
            "model":"",
            "reason":str(reason),
            "circuit_open":True,
            "circuit_remaining_ms":round(open_s*1000),
            "failures":_DEEP_HEALTH["failures"],
        }

def mark_deep_success(result=None):
    now=time.monotonic()
    with _DEEP_HEALTH_LOCK:
        _DEEP_HEALTH["failures"]=0
        _DEEP_HEALTH["circuit_until"]=0.0
        if result is not None:
            _DEEP_HEALTH["at"]=now
            _DEEP_HEALTH["result"]=dict(result)
            if result.get("model"):
                _DEEP_HEALTH["confirmed_model"]=str(result.get("model"))

def deep_health(env, force=False):
    if not is_true(env.get("DEEP_ENABLED","true")):
        return {"ready":False,"rtt_ms":0,"model":"","reason":"disabled"}

    now=time.monotonic()
    cache_s=float(env.get("DEEP_HEALTH_CACHE_SECONDS","0.75") or "0.75")
    with _DEEP_HEALTH_LOCK:
        circuit_until=float(_DEEP_HEALTH.get("circuit_until",0) or 0)
        cached=_DEEP_HEALTH.get("result")
        cached_at=float(_DEEP_HEALTH.get("at",0) or 0)
        failures=int(_DEEP_HEALTH.get("failures",0) or 0)
        confirmed_model=str(_DEEP_HEALTH.get("confirmed_model","") or "")

    if not force and circuit_until>now:
        left=max(0,circuit_until-now)
        return {
            "ready":False,
            "reachable":False,
            "rtt_ms":0,
            "model":"",
            "reason":"circuit_open",
            "circuit_open":True,
            "circuit_remaining_ms":round(left*1000),
            "failures":failures,
        }

    if not force and cached and (now-cached_at)<=cache_s:
        out=dict(cached)
        out["cached"]=True
        out["cache_age_ms"]=round((now-cached_at)*1000)
        return out

    # Once 35B has been confirmed installed, port reachability is enough for
    # routine health. Ollama may legitimately have the model unloaded from RAM;
    # the next chat request can load it. Avoid repeated /api/tags probes that
    # previously caused false circuit opens on a healthy tunnel.
    if confirmed_model:
        started=time.monotonic()
        try:
            tcp_ms=_deep_tcp_preflight(env)
            result={
                "ready":True,
                "reachable":True,
                "rtt_ms":tcp_ms,
                "tcp_ms":tcp_ms,
                "model":confirmed_model,
                "installed_models":[confirmed_model],
                "reason":"tcp_confirmed_model",
                "rtt_ok":True,
                "circuit_open":False,
                "failures":0,
                "cached":False,
                "tcp_only":True,
            }
            mark_deep_success(result)
            return result
        except Exception as e:
            mark_deep_failure(env,e)
            return {
                "ready":False,
                "reachable":False,
                "rtt_ms":round((time.monotonic()-started)*1000,1),
                "model":confirmed_model,
                "reason":str(e),
                "circuit_open":True,
                "failures":int(_DEEP_HEALTH.get("failures",0) or 0),
                "tcp_only":True,
            }

    d=deep_env(env)
    started=time.monotonic()
    try:
        tcp_ms=_deep_tcp_preflight(env)
        models=list_local_models(d)
        rtt=(time.monotonic()-started)*1000
        wanted=[
            x.strip()
            for x in d.get("LOCAL_MODEL_CANDIDATES","").split(",")
            if x.strip()
        ]
        actual_by_lower={x.lower():x for x in models}
        found=""
        for name in wanted:
            if name.lower() in actual_by_lower:
                found=actual_by_lower[name.lower()]
                break
        if not found:
            for name in models:
                n=name.lower()
                if "qwen3.5" in n and "35b" in n:
                    found=name
                    break

        max_rtt=float(env.get("DEEP_MAX_RTT_MS","120") or "120")
        result={
            "ready":bool(found) and rtt<=max_rtt,
            "reachable":True,
            "rtt_ms":round(rtt,1),
            "tcp_ms":tcp_ms,
            "model":found,
            "installed_models":models,
            "reason":"" if found else "deep_model_missing",
            "rtt_ok":rtt<=max_rtt,
            "circuit_open":False,
            "failures":0,
            "cached":False,
        }
        if result["ready"]:
            mark_deep_success(result)
        else:
            # Model missing is not a transient tunnel failure; still avoid hammering.
            mark_deep_failure(env,result["reason"] or "deep_not_ready")
            result["circuit_open"]=True
        return result
    except Exception as e:
        mark_deep_failure(env,e)
        return {
            "ready":False,
            "reachable":False,
            "rtt_ms":round((time.monotonic()-started)*1000,1),
            "model":"",
            "reason":str(e),
            "circuit_open":True,
            "failures":int(_DEEP_HEALTH.get("failures",0) or 0),
        }


def deep_request(text, messages, env):
    t=(text or "").casefold()
    if not is_true(env.get("AUTO_PREFER_DEEP_FOR_COMPLEX","true")):
        return False
    explicit=[
        "dùng não mạnh","não mạnh","dùng 35b","dùng qwen 35",
        "phân tích sâu","nghĩ kỹ","suy luận sâu","phản biện sâu",
        "chiến lược chi tiết","đánh giá toàn diện","lập kế hoạch chi tiết",
        "so sánh chuyên sâu","nghiên cứu chuyên sâu"
    ]
    if any(x in t for x in explicit):
        return True
    threshold=int(env.get("DEEP_COMPLEXITY_THRESHOLD","2") or "2")
    return complexity_score(messages) >= threshold

def call_deep_native(incoming, env):
    try:
        out=call_local_native(incoming, deep_env(env))
        mark_deep_success()
        return out
    except Exception as e:
        mark_deep_failure(env,e)
        raise


def _json_args(v):
    if isinstance(v, dict):
        return v
    if v is None:
        return {}
    if isinstance(v, str):
        try:
            obj = json.loads(v)
            return obj if isinstance(obj, dict) else {"value": obj}
        except Exception:
            return {"value": v}
    return {"value": v}

def openai_messages_to_ollama(messages):
    out = []
    call_names = {}

    for msg in messages or []:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "assistant":
            native = {"role": "assistant", "content": content or ""}
            calls = []
            for idx, tc in enumerate(msg.get("tool_calls") or []):
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                call_id = tc.get("id")
                if call_id and name:
                    call_names[call_id] = name
                calls.append({
                    "type": "function",
                    "function": {
                        "index": idx,
                        "name": name,
                        "arguments": _json_args(fn.get("arguments")),
                    }
                })
            if calls:
                native["tool_calls"] = calls
            out.append(native)
            continue

        if role == "tool":
            tool_name = (
                msg.get("tool_name")
                or msg.get("name")
                or call_names.get(msg.get("tool_call_id"))
                or "tool"
            )
            out.append({
                "role": "tool",
                "tool_name": tool_name,
                "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
            })
            continue

        native = {
            "role": role,
            "content": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
        }
        if msg.get("images"):
            native["images"] = msg["images"]
        out.append(native)

    return out

def openai_tools_to_ollama(tools):
    clean = []
    for tool in tools or []:
        if tool.get("type") != "function":
            continue
        fn = tool.get("function") or {}
        clean.append({
            "type": "function",
            "function": {
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
            }
        })
    return clean

def ollama_native_to_openai(resp, model):
    native_msg = resp.get("message") or {}
    tool_calls = []
    for idx, tc in enumerate(native_msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        args = fn.get("arguments") or {}
        tool_calls.append({
            "id": "call_" + uuid.uuid4().hex[:24],
            "type": "function",
            "function": {
                "name": fn.get("name", ""),
                "arguments": json.dumps(args, ensure_ascii=False, separators=(",", ":")),
            },
        })

    msg = {
        "role": "assistant",
        "content": native_msg.get("content") or "",
    }
    if tool_calls:
        msg["tool_calls"] = tool_calls

    prompt_tokens = int(resp.get("prompt_eval_count") or 0)
    completion_tokens = int(resp.get("eval_count") or 0)
    total_ns = int(resp.get("total_duration") or 0)
    load_ns = int(resp.get("load_duration") or 0)
    eval_ns = int(resp.get("eval_duration") or 0)
    tps = (completion_tokens / (eval_ns / 1e9)) if completion_tokens and eval_ns else 0.0

    result = {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": msg,
            "finish_reason": "tool_calls" if tool_calls else "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "_robot_metrics": {
            "model_total_ms": round(total_ns / 1e6),
            "model_load_ms": round(load_ns / 1e6),
            "tokens_per_second": round(tps, 2),
        },
    }
    return result

def local_native_body(incoming, env, model, keep_alive=None, stream=False):
    body = {
        "model": model,
        "messages": openai_messages_to_ollama(incoming.get("messages", [])),
        "stream": bool(stream),
        "think": wants_deep_local(last_user_text(incoming.get("messages", [])), env),
        "keep_alive": keep_alive or env.get("LOCAL_KEEP_ALIVE", "10m"),
    }

    tools = openai_tools_to_ollama(incoming.get("tools"))
    if tools:
        body["tools"] = tools

    options = {}
    num_ctx=int(env.get("LOCAL_NUM_CTX","8192") or "8192")
    if num_ctx > 0:
        options["num_ctx"] = num_ctx
    if incoming.get("temperature") is not None:
        options["temperature"] = incoming["temperature"]
    if incoming.get("top_p") is not None:
        options["top_p"] = incoming["top_p"]
    if incoming.get("seed") is not None:
        options["seed"] = incoming["seed"]

    max_tokens = incoming.get("max_tokens")
    if max_tokens is None:
        max_tokens = int(env.get("LOCAL_NUM_PREDICT", "512") or "512")
    if max_tokens:
        options["num_predict"] = int(max_tokens)

    if options:
        body["options"] = options
    return body

def call_local_native(incoming, env):
    models=resolve_local_models(env)
    if not models:
        raise RuntimeError("Không tìm thấy model local phù hợp.")

    errors=[]
    for idx, model in enumerate(models):
        unloaded=enforce_single_resident(env, model)
        keep_alive=(env.get("LOCAL_KEEP_ALIVE","10m") if idx==0
                    else env.get("LOCAL_FALLBACK_KEEP_ALIVE","2m"))
        body=local_native_body(incoming, env, model, keep_alive=keep_alive)
        try:
            native=http_json(
                ollama_root(env["LOCAL_BASE_URL"])+"/api/chat",
                body, "", int(env.get("REQUEST_TIMEOUT_SECONDS","90")),
            )
            result=ollama_native_to_openai(native, model)
            result["_robot_metrics"]["think"]=bool(body.get("think"))
            result["_robot_metrics"]["local_model"]=model
            result["_robot_metrics"]["unloaded_models"]=unloaded
            result["_robot_metrics"]["num_ctx"]=int((body.get("options") or {}).get("num_ctx") or 0)
            result["_robot_metrics"]["keep_alive"]=body.get("keep_alive")
            return result
        except Exception as e:
            errors.append(f"{model}: {e}")
            unload_local_model(env, model)
            if not is_true(env.get("LOCAL_MODEL_FALLBACK","true")):
                break
    raise RuntimeError("Local models failed: "+" | ".join(errors))

def call_local_openai_compat(incoming, env):
    # Compatibility fallback. Ollama /v1 không dùng native `think:false`;
    # cách chuẩn là reasoning_effort="none".
    body = dict(incoming)
    body["stream"] = False
    model = resolve_local_model(env)
    body["model"] = model
    deep = wants_deep_local(last_user_text(body.get("messages", [])), env)
    body["reasoning_effort"] = "high" if deep else "none"

    result = http_json(
        api_url(env["LOCAL_BASE_URL"]),
        body,
        "",
        int(env.get("REQUEST_TIMEOUT_SECONDS", "90")),
    )
    result["_robot_metrics"] = {
        "think": deep,
        "local_model": model,
        "model_total_ms": 0,
        "model_load_ms": 0,
        "tokens_per_second": 0.0,
    }
    return result

def call_brain(kind, incoming, env):
    if kind == "local":
        mode = env.get("LOCAL_API_MODE", "native").strip().lower()
        if mode == "native":
            return call_local_native(incoming, env)
        return call_local_openai_compat(incoming, env)

    if kind == "deep":
        health=deep_health(env)
        if not health.get("ready"):
            raise RuntimeError("Não 35B chưa sẵn sàng: "+str(health.get("reason") or health))
        return call_deep_native(incoming, env)

    if kind == "cloud":
        if not cloud_ready(env):
            raise RuntimeError("Não mây chưa được cấu hình API.")
        body = dict(incoming)
        body["stream"] = False
        body["model"] = env["CLOUD_MODEL"]
        return http_json(
            api_url(env["CLOUD_BASE_URL"]),
            body,
            env["CLOUD_API_KEY"],
            int(env.get("REQUEST_TIMEOUT_SECONDS", "90")),
        )

    raise ValueError(kind)

def extract_answer(resp):
    try:
        msg = resp["choices"][0]["message"]
        return msg.get("content") or ""
    except Exception:
        return ""

def council(incoming, env):
    stripped = dict(incoming)
    stripped.pop("tools", None)
    stripped.pop("tool_choice", None)

    local = call_brain("local", stripped, env)
    cloud = call_brain("cloud", stripped, env)
    a = extract_answer(local)
    b = extract_answer(cloud)

    synth_messages = [
        {
            "role": "system",
            "content": "Bạn là bộ tổng hợp. Hãy hợp nhất hai phương án thành một câu trả lời cuối rõ ràng, chính xác, không nhắc tới việc có hai mô hình."
        },
        {
            "role": "user",
            "content": "PHƯƠNG ÁN NÃO NHÀ:\n" + a + "\n\nPHƯƠNG ÁN NÃO MÂY:\n" + b
        }
    ]
    synth = {
        "model": resolve_local_model(env),
        "messages": synth_messages,
        "stream": False,
        "temperature": incoming.get("temperature", 0.4),
        "max_tokens": incoming.get("max_tokens", 768),
    }
    return call_brain("local", synth, env)

def _record_metrics(st, resp, selected, elapsed_ms):
    metrics = resp.pop("_robot_metrics", {}) if isinstance(resp, dict) else {}
    st["last_elapsed_ms"] = round(elapsed_ms)
    if selected.startswith("local") or selected == "council":
        st["last_local_model"] = metrics.get("local_model", st.get("last_local_model", ""))
        st["last_local_think"] = bool(metrics.get("think", False))
        st["last_model_total_ms"] = int(metrics.get("model_total_ms", 0) or 0)
        st["last_model_load_ms"] = int(metrics.get("model_load_ms", 0) or 0)
        st["last_tokens_per_second"] = float(metrics.get("tokens_per_second", 0.0) or 0.0)

def route(incoming):
    env=load_env()
    with LOCK:
        st=load_state()
        mode=st["mode"]
        text=last_user_text(incoming.get("messages",[]))
        incoming,live=apply_live_grounding(incoming,env,st)
        dh=deep_health(env)

        if mode in ("local","fast"):
            selected="local"
        elif mode=="deep":
            selected="deep" if dh.get("ready") else "local"
        elif mode=="cloud":
            if not cloud_allow(env,st):
                raise RuntimeError("Não mây chưa sẵn sàng hoặc đã chạm giới hạn ngày.")
            selected="cloud"
        elif mode=="council":
            selected="council"
        else:
            if live is not None:
                if is_true(env.get("LIVE_FORCE_DEEP","true")) and dh.get("ready"):
                    selected="deep"
                else:
                    selected="local"
            elif force_local_request(text) or action_like(text) or privacy_sensitive(text) or casual_local(text):
                selected="local"
            elif deep_request(text,incoming.get("messages",[]),env) and dh.get("ready"):
                selected="deep"
            else:
                selected="local"

        started=time.monotonic()
        try:
            if selected=="council":
                stripped=dict(incoming)
                stripped.pop("tools",None); stripped.pop("tool_choice",None)
                fast_resp=call_brain("local",stripped,env)
                a=extract_answer(fast_resp)
                if dh.get("ready"):
                    deep_resp=call_brain("deep",stripped,env)
                    b=extract_answer(deep_resp)
                    synth={
                        "messages":[
                            {"role":"system","content":"Bạn là bộ tổng hợp. Hợp nhất hai phương án thành một câu trả lời cuối chính xác, rõ ràng, không nhắc tới việc có hai mô hình."},
                            {"role":"user","content":"PHƯƠNG ÁN 9B:\n"+a+"\n\nPHƯƠNG ÁN 35B:\n"+b}
                        ],
                        "stream":False,
                        "temperature":incoming.get("temperature",0.4),
                        "max_tokens":incoming.get("max_tokens",768),
                    }
                    resp=call_brain("deep",synth,env)
                else:
                    resp=fast_resp
            else:
                if selected=="cloud":
                    st["cloud_count"]=int(st.get("cloud_count",0))+1
                resp=call_brain(selected,incoming,env)

            elapsed=(time.monotonic()-started)*1000
            _record_metrics(st,resp,selected,elapsed)
            st["last_route"]=selected
            st["last_deep_ready"]=bool(dh.get("ready"))
            st["last_deep_rtt_ms"]=dh.get("rtt_ms",0)
            st["last_deep_health_reason"]=dh.get("reason","")
            if selected=="deep": st["last_deep_model"]=dh.get("model","")
            st["last_error"]=""
            save_state(st)
            return resp,selected

        except Exception as first:
            st["last_error"]=str(first)

            if selected=="deep":
                try:
                    resp=call_brain("local",incoming,env)
                    _record_metrics(st,resp,"local_fallback",(time.monotonic()-started)*1000)
                    st["last_route"]="local_fallback"; st["last_error"]=""
                    save_state(st); return resp,"local_fallback"
                except Exception as e:
                    st["last_error"]=f"deep={first}; local={e}"

            elif selected=="local":
                if dh.get("ready"):
                    try:
                        resp=call_brain("deep",incoming,env)
                        _record_metrics(st,resp,"deep_fallback",(time.monotonic()-started)*1000)
                        st["last_route"]="deep_fallback"; st["last_error"]=""
                        save_state(st); return resp,"deep_fallback"
                    except Exception as e:
                        st["last_error"]=f"local={first}; deep={e}"
                if cloud_allow(env,st):
                    try:
                        st["cloud_count"]=int(st.get("cloud_count",0))+1
                        resp=call_brain("cloud",incoming,env)
                        _record_metrics(st,resp,"cloud_fallback",(time.monotonic()-started)*1000)
                        st["last_route"]="cloud_fallback"; st["last_error"]=""
                        save_state(st); return resp,"cloud_fallback"
                    except Exception as e:
                        st["last_error"]+=f"; cloud={e}"

            elif selected=="cloud":
                try:
                    resp=call_brain("local",incoming,env)
                    _record_metrics(st,resp,"local_fallback",(time.monotonic()-started)*1000)
                    st["last_route"]="local_fallback"; st["last_error"]=""
                    save_state(st); return resp,"local_fallback"
                except Exception as e:
                    st["last_error"]=f"cloud={first}; local={e}"

            save_state(st)
            raise RuntimeError(st["last_error"])

def openai_chunk_from_response(resp):
    choice = (resp.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    delta = {"role": "assistant"}
    if msg.get("content") is not None:
        delta["content"] = msg.get("content")
    if msg.get("tool_calls"):
        delta["tool_calls"] = msg["tool_calls"]
    finish = choice.get("finish_reason") or ("tool_calls" if msg.get("tool_calls") else "stop")
    return delta, finish


# -------------------------------------------------------------------
# V6.3 TRUE STREAMING + FAST DIRECT TOOLS
# -------------------------------------------------------------------

_FAST_TOOL_MAP = {
    # Robot
    "dừng": ("self.robot.motion", {"action":"stop"}),
    "dừng lại": ("self.robot.motion", {"action":"stop"}),
    "đứng lại": ("self.robot.motion", {"action":"stop"}),
    "tiến": ("self.robot.motion", {"action":"forward"}),
    "tiến lên": ("self.robot.motion", {"action":"forward"}),
    "đi thẳng": ("self.robot.motion", {"action":"forward"}),
    "lùi": ("self.robot.motion", {"action":"backward"}),
    "lùi lại": ("self.robot.motion", {"action":"backward"}),
    "quay trái": ("self.robot.motion", {"action":"left"}),
    "rẽ trái": ("self.robot.motion", {"action":"left"}),
    "quay phải": ("self.robot.motion", {"action":"right"}),
    "rẽ phải": ("self.robot.motion", {"action":"right"}),
    "quay một vòng": ("self.robot.motion", {"action":"spin_right"}),
    "xoay một vòng": ("self.robot.motion", {"action":"spin_right"}),
    "quay 360": ("self.robot.motion", {"action":"spin_right"}),
    "quay 360 độ": ("self.robot.motion", {"action":"spin_right"}),
    "nhảy": ("self.robot.dance", {}),
    "nhảy đi": ("self.robot.dance", {}),
    "múa": ("self.robot.dance", {}),
    "múa đi": ("self.robot.dance", {}),

    # Mac whitelist
    "mở chrome": ("self.mac.command", {"action":"open_chrome"}),
    "mở safari": ("self.mac.command", {"action":"open_safari"}),
    "mở youtube": ("self.mac.command", {"action":"open_youtube"}),
    "mở word": ("self.mac.command", {"action":"open_word"}),
    "mở finder": ("self.mac.command", {"action":"open_finder"}),
    "tăng âm lượng": ("self.mac.command", {"action":"volume_up"}),
    "giảm âm lượng": ("self.mac.command", {"action":"volume_down"}),
    "phát tạm dừng": ("self.mac.command", {"action":"play_pause"}),
    "tạm dừng": ("self.mac.command", {"action":"play_pause"}),
}

def _normalize_fast_text(text):
    import unicodedata
    t=unicodedata.normalize("NFC", (text or "").strip().casefold())
    # chỉ bỏ dấu câu ở đầu/cuối; không biến câu dài thành lệnh
    t=t.strip(" \t\r\n.!?…,:;\"'“”‘’")
    t=" ".join(t.split())
    return t

def _available_tool_names(incoming):
    names=set()
    for tool in incoming.get("tools") or []:
        if tool.get("type")!="function":
            continue
        name=(tool.get("function") or {}).get("name")
        if name:
            names.add(name)
    return names

def fast_command_match(incoming, env):
    if not is_true(env.get("FAST_COMMANDS_ENABLED","true")):
        return None
    text=_normalize_fast_text(last_user_text(incoming.get("messages",[])))
    # Chỉ cho phép lệnh cực ngắn. Câu dài phải qua AI để tránh hiểu nhầm.
    if not text or len(text)>32:
        return None
    hit=_FAST_TOOL_MAP.get(text)
    if not hit:
        return None
    tool_name,args=hit
    if tool_name not in _available_tool_names(incoming):
        return None
    return tool_name,args,text

def _sse_obj(model, delta, finish_reason=None, rid=None):
    return {
        "id": rid or ("chatcmpl-"+uuid.uuid4().hex),
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "delta": delta,
            "finish_reason": finish_reason,
        }],
    }

def _sse_start(handler):
    if getattr(handler, "_v63_sse_started", False):
        return
    handler.send_response(200)
    handler.send_header("Content-Type","text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control","no-cache")
    handler.send_header("Connection","close")
    handler.send_header("X-Accel-Buffering","no")
    handler.end_headers()
    handler._v63_sse_started=True

def _sse_send(handler, obj):
    _sse_start(handler)
    data=("data: "+json.dumps(obj,ensure_ascii=False,separators=(",",":"))+"\n\n").encode("utf-8")
    handler.wfile.write(data)
    handler.wfile.flush()

def _sse_done(handler):
    _sse_start(handler)
    handler.wfile.write(b"data: [DONE]\n\n")
    handler.wfile.flush()

def emit_fast_tool(handler, incoming, env, st, match):
    tool_name,args,text=match
    rid="chatcmpl-fast-"+uuid.uuid4().hex
    call_id="call_"+uuid.uuid4().hex[:24]
    started=time.monotonic()

    _sse_send(handler, _sse_obj(
        "dual-brain-fast",
        {
            "role":"assistant",
            "tool_calls":[{
                "index":0,
                "id":call_id,
                "type":"function",
                "function":{
                    "name":tool_name,
                    "arguments":json.dumps(args,ensure_ascii=False,separators=(",",":")),
                },
            }],
        },
        rid=rid,
    ))
    _sse_send(handler, _sse_obj("dual-brain-fast", {}, "tool_calls", rid))
    _sse_done(handler)

    total=(time.monotonic()-started)*1000
    st["last_route"]="fast_tool"
    st["last_fast_command"]=text
    st["last_ttft_ms"]=round(total)
    st["last_stream_total_ms"]=round(total)
    st["last_stream_chunks"]=1
    st["last_error"]=""
    save_state(st)

def _select_stream_brain(incoming, env, st):
    mode=st.get("mode","auto")
    text=last_user_text(incoming.get("messages",[]))
    dh=deep_health(env)

    if mode in ("local","fast"): return "local"
    if mode=="deep": return "deep" if dh.get("ready") else "local"
    if mode=="cloud":
        if not cloud_allow(env,st):
            raise RuntimeError("Não mây chưa sẵn sàng hoặc đã chạm giới hạn ngày.")
        return "cloud"
    if mode=="council": return "council"

    if force_local_request(text) or action_like(text) or privacy_sensitive(text) or casual_local(text):
        return "local"
    if deep_request(text,incoming.get("messages",[]),env) and dh.get("ready"):
        return "deep"
    return "local"


def _open_json_stream(url, payload, api_key="", timeout=90):
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8")
    headers={
        "Content-Type":"application/json",
        "Accept":"text/event-stream",
        "Connection":"close",
    }
    if api_key:
        headers["Authorization"]="Bearer "+api_key
    req=urllib.request.Request(url,data=data,headers=headers,method="POST")
    return urllib.request.urlopen(req,timeout=timeout)

def _ollama_stream_delta(native, call_ids):
    msg=native.get("message") or {}
    content=msg.get("content") or ""
    tool_calls=msg.get("tool_calls") or []
    delta={}
    if content:
        delta["content"]=content

    if tool_calls:
        out=[]
        for idx,tc in enumerate(tool_calls):
            fn=tc.get("function") or {}
            if idx not in call_ids:
                call_ids[idx]="call_"+uuid.uuid4().hex[:24]
            args=fn.get("arguments") or {}
            if not isinstance(args,str):
                args=json.dumps(args,ensure_ascii=False,separators=(",",":"))
            out.append({
                "index":idx,
                "id":call_ids[idx],
                "type":"function",
                "function":{
                    "name":fn.get("name",""),
                    "arguments":args,
                },
            })
        delta["tool_calls"]=out
    return delta, bool(tool_calls)

def stream_local_native(handler, incoming, env, st, label="local"):
    models=resolve_local_models(env)
    if not models:
        raise RuntimeError("Không tìm thấy model local phù hợp.")

    errors=[]
    for idx,model in enumerate(models):
        unloaded=enforce_single_resident(env,model)
        keep_alive=(env.get("LOCAL_KEEP_ALIVE","10m")
                    if idx==0 else env.get("LOCAL_FALLBACK_KEEP_ALIVE","2m"))
        body=local_native_body(incoming,env,model,keep_alive=keep_alive,stream=True)
        url=ollama_root(env["LOCAL_BASE_URL"])+"/api/chat"

        started=time.monotonic()
        first_at=None
        chunks=0
        call_ids={}
        had_tools=False
        final_native={}
        rid="chatcmpl-local-"+uuid.uuid4().hex
        try:
            resp=_open_json_stream(
                url,body,"",float(env.get("REQUEST_TIMEOUT_SECONDS","90"))
            )
            role_sent=False

            for raw in resp:
                line=raw.decode("utf-8","replace").strip()
                if not line:
                    continue
                try:
                    native=json.loads(line)
                except Exception:
                    continue
                final_native=native
                delta,has_tools=_ollama_stream_delta(native,call_ids)
                had_tools=had_tools or has_tools
                if delta:
                    if first_at is None:
                        first_at=time.monotonic()
                    if not role_sent:
                        _sse_send(handler,_sse_obj(model,{"role":"assistant"},rid=rid))
                        role_sent=True
                    chunks+=1
                    _sse_send(handler,_sse_obj(model,delta,rid=rid))
                if native.get("done"):
                    break

            finish="tool_calls" if had_tools else "stop"
            if not role_sent:
                _sse_send(handler,_sse_obj(model,{"role":"assistant"},rid=rid))
                role_sent=True
            _sse_send(handler,_sse_obj(model,{},finish,rid))
            _sse_done(handler)

            total_ms=(time.monotonic()-started)*1000
            ttft_ms=((first_at-started)*1000) if first_at else total_ms

            st["last_route"]=label
            st["last_fast_command"]=""
            st["last_ttft_ms"]=round(ttft_ms)
            st["last_stream_total_ms"]=round(total_ms)
            st["last_stream_chunks"]=chunks
            st["last_local_model"]=model
            st["last_local_think"]=bool(body.get("think"))
            st["last_model_total_ms"]=round((final_native.get("total_duration") or 0)/1e6)
            st["last_model_load_ms"]=round((final_native.get("load_duration") or 0)/1e6)
            ec=int(final_native.get("eval_count") or 0)
            ens=int(final_native.get("eval_duration") or 0)
            st["last_tokens_per_second"]=round(ec/(ens/1e9),2) if ec and ens else 0.0
            st["last_error"]=""
            save_state(st)
            return
        except Exception as e:
            errors.append(f"{model}: {e}")
            unload_local_model(env,model)
            # Nếu đã gửi SSE ra client thì không thể đổi model an toàn giữa chừng.
            if getattr(handler,"_v63_sse_started",False):
                raise
            if not is_true(env.get("LOCAL_MODEL_FALLBACK","true")):
                break

    raise RuntimeError("Local streaming failed: "+" | ".join(errors))


def stream_deep_native(handler,incoming,env,st,label="deep"):
    dh=deep_health(env)
    if not dh.get("ready"):
        raise RuntimeError("Não 35B chưa sẵn sàng: "+str(dh.get("reason") or dh))
    st["last_deep_ready"]=True
    st["last_deep_rtt_ms"]=dh.get("rtt_ms",0)
    st["last_deep_health_reason"]=dh.get("reason","")
    st["last_deep_model"]=dh.get("model","")
    try:
        out=stream_local_native(handler,incoming,deep_env(env),st,label)
        mark_deep_success()
        return out
    except Exception as e:
        if not getattr(handler,"_v63_sse_started",False):
            mark_deep_failure(env,e)
        raise


def stream_cloud_openai(handler,incoming,env,st,label="cloud"):
    if not cloud_ready(env):
        raise RuntimeError("Não mây chưa được cấu hình API.")

    body=dict(incoming)
    body["stream"]=True
    body["model"]=env["CLOUD_MODEL"]
    started=time.monotonic()
    first_at=None
    chunks=0
    done_sent=False
    url=api_url(env["CLOUD_BASE_URL"])

    resp=_open_json_stream(
        url,body,env["CLOUD_API_KEY"],
        int(env.get("REQUEST_TIMEOUT_SECONDS","90"))
    )
    _sse_start(handler)

    for raw in resp:
        line=raw.decode("utf-8","replace").strip()
        if not line:
            continue
        if line.startswith("data:"):
            payload=line[5:].strip()
            if payload=="[DONE]":
                handler.wfile.write(b"data: [DONE]\n\n")
                handler.wfile.flush()
                done_sent=True
                break
            try:
                obj=json.loads(payload)
                choices=obj.get("choices") or []
                if choices:
                    delta=(choices[0].get("delta") or {})
                    if delta.get("content") or delta.get("tool_calls"):
                        if first_at is None:
                            first_at=time.monotonic()
                        chunks+=1
            except Exception:
                pass
            handler.wfile.write(("data: "+payload+"\n\n").encode("utf-8"))
            handler.wfile.flush()
        else:
            # Một số endpoint trả JSON một dòng dù stream=true.
            try:
                obj=json.loads(line)
            except Exception:
                continue
            choice=(obj.get("choices") or [{}])[0]
            msg=choice.get("message") or {}
            delta={"role":"assistant"}
            if msg.get("content") is not None:
                delta["content"]=msg.get("content")
            if msg.get("tool_calls"):
                delta["tool_calls"]=msg["tool_calls"]
            if first_at is None:
                first_at=time.monotonic()
            chunks+=1
            rid=obj.get("id") or ("chatcmpl-cloud-"+uuid.uuid4().hex)
            _sse_send(handler,_sse_obj(
                obj.get("model",env["CLOUD_MODEL"]),delta,rid=rid
            ))
            _sse_send(handler,_sse_obj(
                obj.get("model",env["CLOUD_MODEL"]),{},
                choice.get("finish_reason") or "stop",rid
            ))

    if not done_sent:
        _sse_done(handler)

    total_ms=(time.monotonic()-started)*1000
    ttft_ms=((first_at-started)*1000) if first_at else total_ms
    st["last_route"]=label
    st["last_fast_command"]=""
    st["last_ttft_ms"]=round(ttft_ms)
    st["last_stream_total_ms"]=round(total_ms)
    st["last_stream_chunks"]=chunks
    st["last_error"]=""
    save_state(st)

def stream_nonstream_result(handler,incoming,selected):
    # Council vẫn cần chờ hai não; sau đó trả kết quả theo chuẩn SSE.
    resp,_=route(incoming)
    delta,finish=openai_chunk_from_response(resp)
    rid=resp.get("id","chatcmpl-"+uuid.uuid4().hex)
    model=resp.get("model","dual-brain")
    _sse_send(handler,_sse_obj(model,delta,rid=rid))
    _sse_send(handler,_sse_obj(model,{},finish,rid))
    _sse_done(handler)

def stream_request(handler,incoming):
    env=load_env()
    st=load_state()

    fast=fast_command_match(incoming,env)
    if fast:
        return emit_fast_tool(handler,incoming,env,st,fast)

    original_text=last_user_text(incoming.get("messages",[]))
    incoming,live=apply_live_grounding(incoming,env,st)

    if live is not None and st.get("mode","auto")=="auto":
        dh=deep_health(env)
        selected="deep" if is_true(env.get("LIVE_FORCE_DEEP","true")) and dh.get("ready") else "local"
    else:
        selected=_select_stream_brain(incoming,env,st)

    if selected=="council":
        return stream_nonstream_result(handler,incoming,selected)

    if selected=="deep":
        deep_started=time.monotonic()
        try:
            return stream_deep_native(handler,incoming,env,st,"deep")
        except Exception as deep_err:
            if getattr(handler,"_v63_sse_started",False):
                raise
            st["last_deep_failover_ms"]=round((time.monotonic()-deep_started)*1000)
            save_state(st)
            try:
                return stream_local_native(handler,incoming,env,st,"local_fallback")
            except Exception as local_err:
                if cloud_allow(env,st):
                    st["cloud_count"]=int(st.get("cloud_count",0))+1
                    save_state(st)
                    try:
                        return stream_cloud_openai(handler,incoming,env,st,"cloud_fallback")
                    except Exception as cloud_err:
                        raise RuntimeError(f"deep={deep_err}; local={local_err}; cloud={cloud_err}")
                raise RuntimeError(f"deep={deep_err}; local={local_err}")

    if selected=="cloud":
        st["cloud_count"]=int(st.get("cloud_count",0))+1
        save_state(st)
        try:
            return stream_cloud_openai(handler,incoming,env,st,"cloud")
        except Exception as cloud_err:
            if getattr(handler,"_v63_sse_started",False):
                raise
            try:
                return stream_local_native(handler,incoming,env,st,"local_fallback")
            except Exception as local_err:
                st["last_error"]=f"cloud={cloud_err}; local={local_err}"
                save_state(st)
                raise RuntimeError(st["last_error"])

    try:
        return stream_local_native(handler,incoming,env,st,"local")
    except Exception as local_err:
        if getattr(handler,"_v63_sse_started",False):
            raise
        dh=deep_health(env)
        if dh.get("ready"):
            try:
                return stream_deep_native(handler,incoming,env,st,"deep_fallback")
            except Exception as deep_err:
                if getattr(handler,"_v63_sse_started",False):
                    raise
                local_err=RuntimeError(f"local={local_err}; deep={deep_err}")
        if cloud_allow(env,st):
            st["cloud_count"]=int(st.get("cloud_count",0))+1
            save_state(st)
            try:
                return stream_cloud_openai(handler,incoming,env,st,"cloud_fallback")
            except Exception as cloud_err:
                st["last_error"]=f"{local_err}; cloud={cloud_err}"
                save_state(st)
                raise RuntimeError(st["last_error"])
        raise

class H(BaseHTTPRequestHandler):
    server_version = "RobotDualBrain/6.7-realtime"

    def send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        env = load_env()
        st = load_state()
        if self.path in ("/health", "/status"):
            try:
                resolved = resolve_local_model(env)
            except Exception:
                resolved = env.get("LOCAL_MODEL", "")
            self.send_json({
                "ok": True,
                "version": "6.7-realtime",
                "mode": st["mode"],
                "last_route": st.get("last_route", ""),
                "last_error": st.get("last_error", ""),
                "local_api_mode": env.get("LOCAL_API_MODE", "native"),
                "local_model_config": env.get("LOCAL_MODEL", "auto"),
                "local_model_resolved": resolved,
                "local_think_default": is_true(env.get("LOCAL_THINK_DEFAULT", "false")),
                "local_keep_alive": env.get("LOCAL_KEEP_ALIVE", "10m"),
                "local_fallback_keep_alive": env.get("LOCAL_FALLBACK_KEEP_ALIVE", "2m"),
                "local_num_ctx": int(env.get("LOCAL_NUM_CTX", "8192") or "8192"),
                "local_single_resident": is_true(env.get("LOCAL_SINGLE_RESIDENT", "true")),
                "local_model_candidates": resolve_local_models(env),
                "local_loaded_models": list_loaded_models(env),
                "last_local_think": st.get("last_local_think", False),
                "last_elapsed_ms": st.get("last_elapsed_ms", 0),
                "last_model_total_ms": st.get("last_model_total_ms", 0),
                "last_model_load_ms": st.get("last_model_load_ms", 0),
                "last_tokens_per_second": st.get("last_tokens_per_second", 0.0),
                "cloud_ready": cloud_ready(env),
                "cloud_model": env.get("CLOUD_MODEL", ""),
                "cloud_count_today": st.get("cloud_count", 0),
                "cloud_daily_limit": int(env.get("CLOUD_DAILY_LIMIT", "200") or "200"),
                "cloud_is_free_glm_preset": free_glm_preset(env),
                "block_nonfree_cloud": is_true(env.get("BLOCK_NONFREE_CLOUD", "true")),
                "auto_policy": env.get("AUTO_POLICY", "smart_free"),
                "streaming_enabled": is_true(env.get("STREAMING_ENABLED","true")),
                "fast_commands_enabled": is_true(env.get("FAST_COMMANDS_ENABLED","true")),
                "last_ttft_ms": st.get("last_ttft_ms",0),
                "last_stream_total_ms": st.get("last_stream_total_ms",0),
                "last_stream_chunks": st.get("last_stream_chunks",0),
                "last_fast_command": st.get("last_fast_command",""),
                "deep_enabled": is_true(env.get("DEEP_ENABLED","true")),
                "deep_base_url": env.get("DEEP_BASE_URL",""),
                "deep_model_config": env.get("DEEP_MODEL",""),
                "deep_num_ctx": int(env.get("DEEP_NUM_CTX","4096") or "4096"),
                "deep_keep_alive": env.get("DEEP_KEEP_ALIVE","5m"),
                "deep_health": deep_health(env),
                "last_deep_model": st.get("last_deep_model",""),
                "last_deep_rtt_ms": st.get("last_deep_rtt_ms",0),
                "last_deep_health_reason": st.get("last_deep_health_reason",""),
                "last_deep_failover_ms": st.get("last_deep_failover_ms",0),
                "deep_failover_target_ms": int(float(env.get("DEEP_FAILOVER_TARGET_MS","1000") or "1000")),
                "live_enabled": is_true(env.get("LIVE_KNOWLEDGE_ENABLED","true")),
                "live_url": env.get("LIVE_KNOWLEDGE_URL",""),
                "last_live_used": st.get("last_live_used",False),
                "last_live_kind": st.get("last_live_kind",""),
                "last_live_status": st.get("last_live_status",""),
                "last_live_sources": st.get("last_live_sources",0),
                "last_live_elapsed_ms": st.get("last_live_elapsed_ms",0),
                "last_live_checked_at": st.get("last_live_checked_at",""),

            })
            return

        if self.path == "/mode":
            self.send_json({"mode": st["mode"]})
            return

        if self.path == "/v1/models":
            self.send_json({
                "object": "list",
                "data": [{"id": "dual-brain", "object": "model", "owned_by": "robot-ai-private"}],
            })
            return

        self.send_json({"error": "not_found"}, 404)

    def do_POST(self):
        if self.path == "/mode":
            try:
                obj = self.read_json()
                mode = str(obj.get("mode", "")).strip().lower()
                if mode not in VALID_MODES:
                    raise ValueError("mode phải là local/cloud/auto/council")
                with LOCK:
                    st = load_state()
                    st["mode"] = mode
                    save_state(st)
                self.send_json({"ok": True, "mode": mode})
            except Exception as e:
                self.send_json({"ok": False, "error": str(e)}, 400)
            return

        if self.path == "/v1/chat/completions":
            try:
                incoming = self.read_json()
                wants_stream = bool(incoming.get("stream", False))
                if wants_stream and is_true(load_env().get("STREAMING_ENABLED","true")):
                    stream_request(self, incoming)
                    return

                resp, selected = route(incoming)
                resp.setdefault("robot_brain", selected)
                self.send_json(resp)
                return

            except Exception as e:
                self.send_json({
                    "error": {
                        "message": str(e),
                        "type": "dual_brain_error",
                        "code": "dual_brain_error",
                    }
                }, 502)
            return

        self.send_json({"error": "not_found"}, 404)

    def log_message(self, fmt, *args):
        print(time.strftime("%H:%M:%S"), fmt % args)

if __name__ == "__main__":
    print("Robot AI V6.7 REAL-TIME KNOWLEDGE / FREE-FIRST :11435")
    print("True LLM SSE + fast direct tools + RAM-safe Qwen3.5")
    print("Modes: local | cloud | auto | council")
    ThreadingHTTPServer(("0.0.0.0", 11435), H).serve_forever()
