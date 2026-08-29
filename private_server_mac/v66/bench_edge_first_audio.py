#!/usr/bin/env python3
import asyncio,time,statistics,argparse,edge_tts

ap=argparse.ArgumentParser()
ap.add_argument("--runs",type=int,default=5)
ap.add_argument("--text",default="Dạ Đại Ca.")
ap.add_argument("--voice",default="vi-VN-NamMinhNeural")
args=ap.parse_args()

async def one():
    c=edge_tts.Communicate(args.text,voice=args.voice)
    t0=time.perf_counter(); first=None; n=0
    async for chunk in c.stream():
        if chunk.get("type")=="audio":
            if first is None: first=time.perf_counter()
            n+=len(chunk.get("data") or b"")
    t1=time.perf_counter()
    return ((first or t1)-t0)*1000,(t1-t0)*1000,n

async def main():
    vals=[]
    for i in range(args.runs):
        a,b,n=await one()
        vals.append(a)
        print(f"run={i+1} first_audio_ms={a:.1f} total_ms={b:.1f} bytes={n}")
    print(f"p50_first_audio_ms={statistics.median(vals):.1f}")
    print(f"min_first_audio_ms={min(vals):.1f}")
    print(f"max_first_audio_ms={max(vals):.1f}")
asyncio.run(main())
