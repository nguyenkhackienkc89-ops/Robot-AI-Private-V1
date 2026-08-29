#!/usr/bin/env python3
import json
import os
import re
import time
import html
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

PORT=int(os.getenv("LIVE_PORT","11437"))
SEARXNG_URL=os.getenv("LIVE_SEARXNG_URL","http://searxng:8080").rstrip("/")
MAX_SOURCES=int(os.getenv("LIVE_MAX_SOURCES","5"))
MIN_NEWS_SOURCES=int(os.getenv("LIVE_MIN_NEWS_SOURCES","2"))
SEARCH_TIMEOUT=float(os.getenv("LIVE_SEARCH_TIMEOUT_SECONDS","5.0"))
CACHE_TTL=float(os.getenv("LIVE_CACHE_TTL_SECONDS","60"))
DEFAULT_LOCATION=os.getenv("LIVE_DEFAULT_LOCATION","").strip()
FETCH_PAGES=os.getenv("LIVE_FETCH_PAGES","false").strip().lower() in {"1","true","yes","on"}
PAID_SEARCH_ENABLED=os.getenv("PAID_SEARCH_ENABLED","false").strip().lower() in {"1","true","yes","on"}
SEARXNG_ENABLED=os.getenv("LIVE_SEARXNG_ENABLED","true").strip().lower() in {"1","true","yes","on"}
OPEN_METEO_ENABLED=os.getenv("LIVE_OPEN_METEO_ENABLED","true").strip().lower() in {"1","true","yes","on"}
FRANKFURTER_ENABLED=os.getenv("LIVE_FRANKFURTER_ENABLED","true").strip().lower() in {"1","true","yes","on"}
COINGECKO_KEYLESS_ENABLED=os.getenv("LIVE_COINGECKO_KEYLESS_ENABLED","true").strip().lower() in {"1","true","yes","on"}

CACHE={}
CACHE_LOCK=Lock()

TRUSTED_DOMAINS={
    "reuters.com":100,
    "apnews.com":100,
    "bbc.com":95,
    "bbc.co.uk":95,
    "chinhphu.vn":100,
    "baochinhphu.vn":100,
    "sbv.gov.vn":100,
    "vietnamplus.vn":92,
    "nhandan.vn":92,
    "vov.vn":90,
    "vtv.vn":90,
    "vnexpress.net":88,
    "tuoitre.vn":88,
    "thanhnien.vn":86,
    "open-meteo.com":100,
    "frankfurter.dev":100,
    "coingecko.com":95,
}

CRYPTO_MAP={
    "bitcoin":"bitcoin","btc":"bitcoin",
    "ethereum":"ethereum","eth":"ethereum",
    "solana":"solana","sol":"solana",
    "bnb":"binancecoin","binance coin":"binancecoin",
    "xrp":"ripple","ripple":"ripple",
    "dogecoin":"dogecoin","doge":"dogecoin",
    "cardano":"cardano","ada":"cardano",
}

CURRENCY_ALIASES={
    "đô la mỹ":"USD","usd":"USD","dollar":"USD",
    "việt nam đồng":"VND","vnd":"VND","đồng việt nam":"VND",
    "euro":"EUR","eur":"EUR",
    "yên":"JPY","jpy":"JPY","yen":"JPY",
    "bảng anh":"GBP","gbp":"GBP",
    "won":"KRW","krw":"KRW",
    "nhân dân tệ":"CNY","cny":"CNY",
    "aud":"AUD","cad":"CAD","sgd":"SGD","thb":"THB",
}

LIVE_PATTERNS=[
    r"\bhôm nay\b",r"\bhôm qua\b",r"\bmới nhất\b",r"\bhiện tại\b",
    r"\bbây giờ\b",r"\bvừa xảy ra\b",r"\bvừa mới\b",r"\bsáng nay\b",
    r"\bchiều nay\b",r"\btối nay\b",r"\btrong ngày\b",r"\bthời tiết\b",
    r"\btỷ giá\b",r"\bgiá vàng\b",r"\bgiá bitcoin\b",r"\bgiá btc\b",
    r"\bgiá ethereum\b",r"\bgiá eth\b",r"\bkết quả mới\b",
    r"\btin mới\b",r"\btin tức\b",r"\btra cứu\b",r"\btìm trên mạng\b",
    r"\btìm trên web\b",r"\binternet\b",r"\bđang diễn ra\b",
]

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def jget(url, timeout=None, headers=None):
    h={"User-Agent":"RobotAIPrivate/6.7 (+local personal assistant)"}
    if headers: h.update(headers)
    req=urllib.request.Request(url,headers=h)
    with urllib.request.urlopen(req,timeout=timeout or SEARCH_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8","replace"))

def cache_get(key):
    now=time.monotonic()
    with CACHE_LOCK:
        item=CACHE.get(key)
        if not item: return None
        if now-item["at"]>CACHE_TTL:
            CACHE.pop(key,None); return None
        out=dict(item["value"])
        out["cache_hit"]=True
        return out

def cache_put(key,val):
    with CACHE_LOCK:
        CACHE[key]={"at":time.monotonic(),"value":val}

def hostname(url):
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""

def trust_score(url):
    h=hostname(url)
    best=50
    for dom,score in TRUSTED_DOMAINS.items():
        if h==dom or h.endswith("."+dom):
            best=max(best,score)
    if h.endswith(".gov.vn") or h.endswith(".gov"):
        best=max(best,100)
    if h.endswith(".edu") or h.endswith(".edu.vn"):
        best=max(best,90)
    return best

def clean_text(v,limit=700):
    if v is None: return ""
    s=html.unescape(str(v))
    s=re.sub(r"<[^>]+>"," ",s)
    s=re.sub(r"\s+"," ",s).strip()
    return s[:limit]

def is_live_query(text):
    t=(text or "").casefold()
    return any(re.search(p,t) for p in LIVE_PATTERNS)

def detect_kind(text):
    t=(text or "").casefold()
    if "thời tiết" in t or any(x in t for x in ["nhiệt độ","mưa không","bao nhiêu độ","dự báo thời tiết"]):
        return "weather"
    if "tỷ giá" in t or any(k in t for k in [" usd"," vnd"," eur"," jpy"," gbp"," krw"]):
        return "fx"
    if any(k in t for k in CRYPTO_MAP) and any(x in t for x in ["giá","hiện tại","bây giờ","hôm nay"]):
        return "crypto"
    if any(x in t for x in ["tin","mới nhất","vừa xảy ra","sáng nay","chiều nay","tối nay"]):
        return "news"
    return "web"

def extract_location(text):
    t=(text or "").strip()
    m=re.search(r"(?:ở|tại)\s+([^?.!,]+)",t,flags=re.I)
    if m:
        loc=m.group(1)
        loc=re.split(r"\b(?:hôm nay|bây giờ|hiện tại|ngày mai|thế nào|bao nhiêu)\b",loc,flags=re.I)[0]
        loc=loc.strip(" ,.")
        if 1<len(loc)<=80: return loc
    m=re.search(r"thời tiết\s+([^?.!,]+)",t,flags=re.I)
    if m:
        loc=m.group(1)
        loc=re.split(r"\b(?:hôm nay|bây giờ|hiện tại|ngày mai|thế nào|bao nhiêu|ra sao)\b",loc,flags=re.I)[0]
        loc=loc.strip(" ,.")
        if 1<len(loc)<=80: return loc
    return DEFAULT_LOCATION

def weather_query(text):
    if not OPEN_METEO_ENABLED:
        return {"status":"provider_disabled","kind":"weather","checked_at":now_iso(),"summary":"Open-Meteo adapter disabled.","sources":[]}
    loc=extract_location(text)
    if not loc:
        return {
            "status":"needs_location","kind":"weather","checked_at":now_iso(),
            "summary":"Chưa có địa điểm để tra thời tiết.","sources":[]
        }
    geo="https://geocoding-api.open-meteo.com/v1/search?"+urllib.parse.urlencode({
        "name":loc,"count":1,"language":"vi","format":"json"
    })
    g=jget(geo)
    results=g.get("results") or []
    if not results:
        return {"status":"no_results","kind":"weather","checked_at":now_iso(),
                "summary":f"Không tìm thấy địa điểm {loc}.","sources":[]}
    p=results[0]
    lat,lon=p["latitude"],p["longitude"]
    q="https://api.open-meteo.com/v1/forecast?"+urllib.parse.urlencode({
        "latitude":lat,"longitude":lon,
        "current":"temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m",
        "hourly":"precipitation_probability",
        "forecast_days":1,"timezone":"auto"
    })
    w=jget(q)
    cur=w.get("current") or {}
    hourly=w.get("hourly") or {}
    probs=hourly.get("precipitation_probability") or []
    max_rain=max([x for x in probs if isinstance(x,(int,float))],default=None)
    place=", ".join(x for x in [p.get("name"),p.get("admin1"),p.get("country")] if x)
    facts={
        "location":place,
        "temperature_c":cur.get("temperature_2m"),
        "feels_like_c":cur.get("apparent_temperature"),
        "precipitation_mm":cur.get("precipitation"),
        "rain_mm":cur.get("rain"),
        "wind_kmh":cur.get("wind_speed_10m"),
        "max_precip_probability_today":max_rain,
        "observation_time":cur.get("time"),
        "timezone":w.get("timezone"),
    }
    return {
        "status":"ok","kind":"weather","checked_at":now_iso(),
        "facts":facts,
        "summary":json.dumps(facts,ensure_ascii=False),
        "sources":[{
            "title":"Open-Meteo Weather API",
            "url":"https://open-meteo.com/",
            "domain":"open-meteo.com","trust":100,
            "published":cur.get("time") or "",
            "snippet":json.dumps(facts,ensure_ascii=False)
        }]
    }

def currency_codes(text):
    t=" "+(text or "").casefold()+" "
    found=[]
    for alias,code in CURRENCY_ALIASES.items():
        if alias in t and code not in found:
            found.append(code)
    # explicit XXX/YYY
    for a,b in re.findall(r"\b([A-Za-z]{3})\s*/\s*([A-Za-z]{3})\b",text or ""):
        for c in [a.upper(),b.upper()]:
            if c not in found: found.append(c)
    if len(found)==1:
        if found[0]=="VND": found.insert(0,"USD")
        else: found.append("VND")
    if len(found)<2:
        found=["USD","VND"]
    return found[0],found[1]

def fx_query(text):
    if not FRANKFURTER_ENABLED:
        return {"status":"provider_disabled","kind":"fx","checked_at":now_iso(),"summary":"Frankfurter adapter disabled.","sources":[]}
    base,quote=currency_codes(text)
    url="https://api.frankfurter.dev/v2/rates?"+urllib.parse.urlencode({
        "base":base,"quotes":quote
    })
    data=jget(url)
    rows=data if isinstance(data,list) else []
    row=rows[0] if rows else {}
    facts={
        "base":base,"quote":quote,
        "rate":row.get("rate"),
        "date":row.get("date"),
        "note":"Tỷ giá tham chiếu ngày từ nguồn ngân hàng trung ương; không phải báo giá giao dịch tức thời."
    }
    return {
        "status":"ok" if row else "no_results","kind":"fx","checked_at":now_iso(),
        "facts":facts,"summary":json.dumps(facts,ensure_ascii=False),
        "sources":[{
            "title":"Frankfurter exchange rates",
            "url":"https://frankfurter.dev/",
            "domain":"frankfurter.dev","trust":100,
            "published":row.get("date") or "",
            "snippet":json.dumps(facts,ensure_ascii=False)
        }] if row else []
    }

def crypto_id(text):
    t=(text or "").casefold()
    # longer aliases first
    for alias in sorted(CRYPTO_MAP,key=len,reverse=True):
        if re.search(r"(?<!\w)"+re.escape(alias)+r"(?!\w)",t):
            return CRYPTO_MAP[alias]
    return "bitcoin"

def crypto_query(text):
    if not COINGECKO_KEYLESS_ENABLED:
        return {"status":"provider_disabled","kind":"crypto","checked_at":now_iso(),"summary":"CoinGecko keyless adapter disabled.","sources":[]}
    cid=crypto_id(text)
    url="https://api.coingecko.com/api/v3/simple/price?"+urllib.parse.urlencode({
        "ids":cid,"vs_currencies":"usd,vnd",
        "include_last_updated_at":"true",
        "include_24hr_change":"true"
    })
    data=jget(url)
    row=data.get(cid) or {}
    facts={"asset":cid,**row}
    return {
        "status":"ok" if row else "no_results","kind":"crypto","checked_at":now_iso(),
        "facts":facts,"summary":json.dumps(facts,ensure_ascii=False),
        "sources":[{
            "title":"CoinGecko public market data",
            "url":"https://www.coingecko.com/",
            "domain":"coingecko.com","trust":95,
            "published":str(row.get("last_updated_at") or ""),
            "snippet":json.dumps(facts,ensure_ascii=False)
        }] if row else []
    }

def _searx_fetch(text, kind, category, time_range=None, language="vi-VN"):
    params={
        "q":text,
        "format":"json",
        "language":language,
        "safesearch":"0",
        "categories":category,
    }
    if time_range:
        params["time_range"]=time_range
    url=SEARXNG_URL+"/search?"+urllib.parse.urlencode(params)
    return jget(url)

def _searx_items(data):
    raw=data.get("results") or []
    items=[]
    seen_domains=set()
    for r in raw:
        u=r.get("url") or ""
        dom=hostname(u)
        if not u or not dom or dom in seen_domains:
            continue
        seen_domains.add(dom)
        published=clean_text(
            r.get("publishedDate") or r.get("published_date") or r.get("pubdate") or r.get("metadata"),
            80
        )
        item={
            "title":clean_text(r.get("title"),240),
            "url":u,
            "domain":dom,
            "trust":trust_score(u),
            "published":published,
            "snippet":clean_text(r.get("content"),700),
            "engine":clean_text(r.get("engine") or ",".join(r.get("engines") or []),80),
        }
        items.append(item)
        if len(items)>=MAX_SOURCES*2:
            break
    items=sorted(enumerate(items),key=lambda x:(-x[1]["trust"],x[0]))
    return [x[1] for x in items[:MAX_SOURCES]]

def _news_relevant_items(text, items):
    t=(text or "").casefold()
    if "ai" not in t and "trí tuệ nhân tạo" not in t and "artificial intelligence" not in t:
        return items
    needles=[
        " ai ", "trí tuệ nhân tạo", "artificial intelligence", "openai",
        "chatgpt", "anthropic", "google deepmind", "deepmind", "nvidia",
        "machine learning", "llm", "sora", "gemini", "claude",
    ]
    out=[]
    for item in items:
        hay=f" {item.get('title','')} {item.get('snippet','')} {item.get('domain','')} ".casefold()
        if any(n in hay for n in needles):
            out.append(item)
    return out

def searx_query(text, kind):
    if not SEARXNG_ENABLED:
        return {"status":"provider_disabled","kind":kind,"checked_at":now_iso(),"summary":"SearXNG adapter disabled.","sources":[]}
    attempts=[]
    if kind=="news":
        attempts=[
            (text,"news","day","vi-VN"),
            (text,"news",None,"vi-VN"),
            (text,"general","day","vi-VN"),
            ("latest AI news today" if "ai" in text.casefold() else text,"news","day","en-US"),
            ("latest AI news today" if "ai" in text.casefold() else text,"general",None,"en-US"),
        ]
    else:
        attempts=[(text,"general","day" if is_live_query(text) else None,"vi-VN")]
    items=[]
    used_query=text
    for q,category,time_range,language in attempts:
        data=_searx_fetch(q,kind,category,time_range,language)
        items=_searx_items(data)
        if kind=="news":
            items=_news_relevant_items(q if q != text else text, items)
        used_query=q
        if kind!="news" and items:
            break
        if kind=="news" and len(items)>=MIN_NEWS_SOURCES:
            break
    status="ok" if items else "no_results"
    if kind=="news" and 0<len(items)<MIN_NEWS_SOURCES:
        status="insufficient_sources"
    return {
        "status":status,
        "kind":kind,"checked_at":now_iso(),
        "summary":"\n".join(
            f"[{i+1}] {x['title']} | {x['domain']} | {x['published']} | {x['snippet']}"
            for i,x in enumerate(items)
        ),
        "sources":items,
        "searxng_query":used_query,
    }

def query(text):
    key=(text or "").strip()
    if not key:
        return {"status":"bad_request","kind":"none","checked_at":now_iso(),"sources":[]}
    cached=cache_get(key)
    if cached: return cached
    kind=detect_kind(key)
    started=time.monotonic()
    try:
        if kind=="weather": out=weather_query(key)
        elif kind=="fx": out=fx_query(key)
        elif kind=="crypto": out=crypto_query(key)
        else: out=searx_query(key,kind)
    except urllib.error.HTTPError as e:
        out={"status":"upstream_error","kind":kind,"checked_at":now_iso(),
             "summary":f"HTTP {e.code} khi tra dữ liệu.","sources":[]}
    except Exception as e:
        out={"status":"upstream_error","kind":kind,"checked_at":now_iso(),
             "summary":str(e)[:300],"sources":[]}
    out["elapsed_ms"]=round((time.monotonic()-started)*1000,1)
    out["cache_hit"]=False
    out["paid_search_enabled"]=PAID_SEARCH_ENABLED
    cache_put(key,out)
    return out

class H(BaseHTTPRequestHandler):
    server_version="RobotLiveKnowledge/6.7"
    def log_message(self,fmt,*args):
        print("[live]",fmt%args,flush=True)
    def sendj(self,obj,code=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if self.path.startswith("/health"):
            self.sendj({
                "ok":True,"version":"6.7",
                "searxng_url":SEARXNG_URL,
                "paid_search_enabled":PAID_SEARCH_ENABLED,
                "providers":{"searxng":SEARXNG_ENABLED,"open_meteo":OPEN_METEO_ENABLED,"frankfurter":FRANKFURTER_ENABLED,"coingecko_keyless":COINGECKO_KEYLESS_ENABLED},
                "checked_at":now_iso(),
            })
        else:
            self.sendj({"ok":False,"error":"not_found"},404)
    def do_POST(self):
        if not self.path.startswith("/query"):
            return self.sendj({"ok":False,"error":"not_found"},404)
        try:
            n=int(self.headers.get("Content-Length","0"))
            body=json.loads(self.rfile.read(n) or b"{}")
            text=str(body.get("query") or "")
            self.sendj(query(text))
        except Exception as e:
            self.sendj({"status":"error","error":str(e)},500)

if __name__=="__main__":
    print(f"Robot AI Live Knowledge V6.7 :{PORT}",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
