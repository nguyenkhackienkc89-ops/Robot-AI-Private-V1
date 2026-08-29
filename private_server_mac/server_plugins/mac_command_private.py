import asyncio
import json
import os
import urllib.request

from plugins_func.register import register_function, ToolType, ActionResponse, Action

BRIDGE_URL = os.getenv("ROBOT_MAC_BRIDGE_URL", "http://host.docker.internal:8765/command")
TOKEN = os.getenv("ROBOT_MAC_BRIDGE_TOKEN", "").strip()

ALLOWED = {
    "open_chrome", "open_safari", "open_youtube", "youtube_search", "web_search",
    "open_word", "word_write", "open_finder", "open_app", "type_text",
    "volume_up", "volume_down", "play_pause", "play_music_youtube",
    "radio_vov1", "radio_vov2", "radio_vov_gt",
}

desc = {
    "type": "function",
    "function": {
        "name": "mac_command_private",
        "description": (
            "Dieu khien Mac mini an toan tu Robot AI, ke ca khi robot dang o Anywhere Mode. "
            "Chi dung action whitelist; khong shell, khong xoa file, khong mat khau, khong thanh toan."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": sorted(ALLOWED)},
                "value": {"type": "string"},
            },
            "required": ["action"],
        },
    },
}

def _call(action, value):
    if action not in ALLOWED:
        raise ValueError("Action khong duoc phep")
    if not TOKEN or len(TOKEN) < 40:
        raise RuntimeError("ROBOT_MAC_BRIDGE_TOKEN chua cau hinh")
    body = json.dumps({"action": action, "value": value or ""}, ensure_ascii=False).encode()
    req = urllib.request.Request(
        BRIDGE_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Robot-Token": TOKEN,
        },
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

@register_function("mac_command_private", desc, ToolType.SYSTEM_CTL)
async def mac_command_private(conn, action: str, value: str = ""):
    try:
        result = await asyncio.to_thread(_call, action, value)
        if not result.get("ok"):
            raise RuntimeError(result.get("error") or "Mac Bridge error")
        return ActionResponse(
            action=Action.RECORD,
            result=json.dumps(result, ensure_ascii=False),
            response="Da thuc hien tren Mac mini.",
        )
    except Exception as e:
        return ActionResponse(
            action=Action.RESPONSE,
            result=str(e),
            response="Khong dieu khien duoc Mac mini luc nay.",
        )
