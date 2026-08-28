import asyncio
import os
import tempfile
import shutil
from pathlib import Path

from plugins_func.register import register_function, ToolType, ActionResponse, Action
from core.providers.tts.dto.dto import TTSMessageDTO, SentenceType, ContentType

SESSIONS = {}

STATIONS = {
    "vov1": "https://audio-lss.vov.vn/han/live/vov1/audio/manifest.m3u8",
    "vov2": "https://audio-lss.vov.vn/han/live/vov2/audio/manifest.m3u8",
    "vov_giao_thong": "https://play.vovgiaothong.vn/live/gthn/playlist.m3u8",
}

play_desc = {
    "type":"function",
    "function":{
        "name":"play_radio_private",
        "description":"Phát radio VOV trực tiếp qua loa robot. station: vov1, vov2, vov_giao_thong.",
        "parameters":{
            "type":"object",
            "properties":{"station":{"type":"string","enum":["vov1","vov2","vov_giao_thong"]}},
            "required":["station"]
        }
    }
}

stop_desc = {
    "type":"function",
    "function":{
        "name":"stop_radio_private",
        "description":"Dừng radio đang phát.",
        "parameters":{"type":"object","properties":{}}
    }
}

async def _cleanup(key):
    state=SESSIONS.pop(key,None)
    if not state: return
    proc=state.get("proc")
    if proc and proc.returncode is None:
        proc.terminate()
        try: await asyncio.wait_for(proc.wait(),2)
        except Exception: proc.kill()
    shutil.rmtree(state.get("dir",""), ignore_errors=True)

async def _radio_loop(conn, station):
    key=id(conn)
    await _cleanup(key)
    d=tempfile.mkdtemp(prefix="tde-radio-")
    pattern=str(Path(d)/"seg-%05d.wav")
    url=STATIONS[station]

    proc=await asyncio.create_subprocess_exec(
        "ffmpeg","-hide_banner","-loglevel","error",
        "-i",url,"-vn","-ac","1","-ar","16000",
        "-f","segment","-segment_time","5","-reset_timestamps","1",
        pattern,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    SESSIONS[key]={"proc":proc,"dir":d,"station":station}
    idx=0
    try:
        # Segment N is treated as complete once N+1 exists.
        while key in SESSIONS and proc.returncode is None:
            current=Path(d)/f"seg-{idx:05d}.wav"
            nxt=Path(d)/f"seg-{idx+1:05d}.wav"
            for _ in range(80):
                if nxt.exists(): break
                if key not in SESSIONS: return
                await asyncio.sleep(.15)
            if not current.exists(): continue

            conn.tts.tts_text_queue.put(
                TTSMessageDTO(
                    sentence_id=conn.sentence_id,
                    sentence_type=SentenceType.MIDDLE,
                    content_type=ContentType.FILE,
                    content_file=str(current),
                )
            )
            idx += 1

            # Keep disk bounded.
            old=Path(d)/f"seg-{idx-3:05d}.wav"
            if old.exists():
                try: old.unlink()
                except Exception: pass
    finally:
        await _cleanup(key)

@register_function("play_radio_private", play_desc, ToolType.SYSTEM_CTL)
async def play_radio_private(conn, station: str):
    if station not in STATIONS:
        return ActionResponse(action=Action.RESPONSE,result="station_invalid",response="Kênh radio này chưa được cấu hình.")
    asyncio.create_task(_radio_loop(conn,station))
    names={"vov1":"VOV1","vov2":"VOV2","vov_giao_thong":"VOV Giao thông"}
    return ActionResponse(action=Action.RECORD,result="radio_started",response=f"Đang bật {names[station]}.")

@register_function("stop_radio_private", stop_desc, ToolType.SYSTEM_CTL)
async def stop_radio_private(conn):
    await _cleanup(id(conn))
    return ActionResponse(action=Action.RECORD,result="radio_stopped",response="Đã dừng radio.")
