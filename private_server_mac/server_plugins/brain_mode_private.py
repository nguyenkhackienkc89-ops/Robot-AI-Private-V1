import asyncio
import json
import urllib.request

from plugins_func.register import register_function, ToolType, ActionResponse, Action

ROUTER="http://dual-brain-router:11435"

set_desc={
    "type":"function",
    "function":{
        "name":"set_brain_mode_private",
        "description":"Chuyển bộ não AI. local=não nhà, cloud=não mây, auto=tự động, council=hội ý hai não.",
        "parameters":{
            "type":"object",
            "properties":{"mode":{"type":"string","enum":["local","cloud","auto","council"]}},
            "required":["mode"]
        }
    }
}

status_desc={
    "type":"function",
    "function":{
        "name":"get_brain_status_private",
        "description":"Đọc trạng thái bộ não AI hiện tại, não mây có sẵn hay không và số lượt cloud hôm nay.",
        "parameters":{"type":"object","properties":{}}
    }
}

def _post_mode(mode):
    data=json.dumps({"mode":mode}).encode()
    req=urllib.request.Request(
        ROUTER+"/mode",data=data,
        headers={"Content-Type":"application/json"},method="POST"
    )
    with urllib.request.urlopen(req,timeout=3) as r:
        return json.loads(r.read().decode())

def _status():
    with urllib.request.urlopen(ROUTER+"/status",timeout=3) as r:
        return json.loads(r.read().decode())

@register_function("set_brain_mode_private",set_desc,ToolType.SYSTEM_CTL)
async def set_brain_mode_private(conn,mode:str):
    try:
        result=await asyncio.to_thread(_post_mode,mode)
        names={"local":"não nhà","cloud":"não mây","auto":"tự động","council":"hội ý hai não"}
        return ActionResponse(
            action=Action.RECORD,
            result=json.dumps(result,ensure_ascii=False),
            response=f"Đã chuyển sang chế độ {names.get(mode,mode)}."
        )
    except Exception as e:
        return ActionResponse(
            action=Action.RESPONSE,
            result=str(e),
            response="Không chuyển được bộ não. Hãy kiểm tra Dual Brain Router."
        )

@register_function("get_brain_status_private",status_desc,ToolType.SYSTEM_CTL)
async def get_brain_status_private(conn):
    try:
        st=await asyncio.to_thread(_status)
        return ActionResponse(
            action=Action.RECORD,
            result=json.dumps(st,ensure_ascii=False),
            response=(
                f"Chế độ {st.get('mode')}; lượt gần nhất {st.get('last_route') or 'chưa có'}; "
                f"não mây {'đã sẵn sàng' if st.get('cloud_ready') else 'chưa cấu hình'}."
            )
        )
    except Exception as e:
        return ActionResponse(action=Action.RESPONSE,result=str(e),response="Không đọc được trạng thái hai bộ não.")
