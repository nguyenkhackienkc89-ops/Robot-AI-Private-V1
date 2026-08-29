#!/usr/bin/env python3
from pathlib import Path

HERE=Path(__file__).resolve().parent
cfg=HERE/"data/.config.yaml"
tpl=HERE/"data/.config.template.yaml"

if not cfg.exists():
    cfg.write_text(tpl.read_text(encoding="utf-8"),encoding="utf-8")
    print("Đã tạo data/.config.yaml từ template V6.3.")
    raise SystemExit(0)

text=cfg.read_text(encoding="utf-8")
text=text.replace("  TTS: EdgeTTS","  TTS: EdgeStreamPrivate")

def replace_top_block(text,key,new_block):
    lines=text.splitlines(True)
    start=None
    for i,line in enumerate(lines):
        if line.rstrip("\r\n")==key+":":
            start=i
            break
    if start is None:
        return text.rstrip()+"\n\n"+new_block.rstrip()+"\n"
    end=len(lines)
    for j in range(start+1,len(lines)):
        raw=lines[j].rstrip("\r\n")
        if raw and not raw[0].isspace() and raw.endswith(":"):
            end=j
            break
    return "".join(lines[:start])+new_block.rstrip()+"\n\n"+"".join(lines[end:]).lstrip("\n")

text=replace_top_block(text,"TTS","""TTS:
  EdgeStreamPrivate:
    type: edge_stream_private
    voice: vi-VN-NamMinhNeural
    output_dir: tmp/
    rate: 0
    pitch: 0
    volume: 50
    first_chunk_chars: 26""")

text=replace_top_block(text,"VAD","""VAD:
  SileroVAD:
    type: silero
    model_dir: models/snakers4_silero-vad
    threshold: 0.5
    threshold_low: 0.2
    min_silence_duration_ms: 550""")

cfg.write_text(text,encoding="utf-8")
print("Đã cập nhật TTS streaming + VAD 550ms.")
