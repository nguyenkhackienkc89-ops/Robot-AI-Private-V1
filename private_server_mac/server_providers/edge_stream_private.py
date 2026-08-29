import os
import queue
import shutil
import asyncio
import traceback
import time
import json
import edge_tts

from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase
from core.providers.tts.dto.dto import SentenceType, ContentType, InterfaceType
from core.utils.tts import MarkdownCleaner
from core.utils import textUtils

TAG=__name__
logger=setup_logging()

class TTSProvider(TTSProviderBase):
    """
    EdgeTTS low-latency provider:
    Edge MP3 stream -> ffmpeg stdin -> PCM stdout -> Opus encoder -> robot.
    Không đợi tải xong cả câu mới gửi audio.
    """
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.interface_type=InterfaceType.SINGLE_STREAM
        self.voice=config.get("private_voice") or config.get("voice","vi-VN-NamMinhNeural")
        self.volume=int(config.get("volume","50") or 50)
        self.speech_rate=int(config.get("rate","0") or 0)
        self.pitch_rate=int(config.get("pitch","0") or 0)
        self.edge_rate=f"{self.speech_rate:+}%"
        self.edge_volume=f"{self.volume:+}%"
        self.edge_pitch=f"{self.pitch_rate:+}Hz"
        self.first_chunk_chars=max(16,int(config.get("first_chunk_chars","26") or 26))
        self.ffmpeg=shutil.which("ffmpeg")
        self.audio_file_type="mp3"
        # V6.6: đo chính xác latency TTS và ACK NamMinh local tùy chọn.
        self.instant_ack_enabled=str(config.get("instant_ack_enabled","false")).strip().lower() in {"1","true","yes","on"}
        self.instant_ack_file=config.get(
            "instant_ack_file",
            "/opt/xiaozhi-esp32-server/data/tts_cache/namminh_da_dai_ca.mp3"
        )
        self.metrics_file=config.get(
            "metrics_file",
            "/opt/xiaozhi-esp32-server/data/tts_latency_v66.jsonl"
        )
        self._v66_tts_first_at=0.0
        self._v66_edge_start_at=0.0
        self._v66_edge_audio_at=0.0
        self._v66_pcm_at=0.0
        self._v66_opus_at=0.0
        self._v66_ack_opus_at=0.0

    async def text_to_speak(self, text, output_file):
        # Fallback tương thích provider Edge chuẩn.
        communicate=edge_tts.Communicate(
            text,voice=self.voice,rate=self.edge_rate,
            volume=self.edge_volume,pitch=self.edge_pitch
        )
        if output_file:
            os.makedirs(os.path.dirname(output_file),exist_ok=True)
            with open(output_file,"wb") as f:
                async for chunk in communicate.stream():
                    if chunk.get("type")=="audio":
                        f.write(chunk["data"])
            return None
        data=bytearray()
        async for chunk in communicate.stream():
            if chunk.get("type")=="audio":
                data.extend(chunk["data"])
        return bytes(data)

    def _get_segment_text(self):
        # Giữ logic dấu câu upstream: câu đầu có thể chốt ngay ở dấu phẩy.
        seg=super()._get_segment_text()
        if seg:
            return seg

        # Nếu LLM chưa tạo dấu câu, không để robot chờ quá lâu ở câu đầu.
        full_text="".join(self.tts_text_buff)
        current=full_text[self.processed_chars:]
        if self.is_first_sentence and len(current)>=self.first_chunk_chars:
            limit=self.first_chunk_chars
            cut=current.rfind(" ",10,limit+1)
            if cut<10:
                cut=limit
            raw=current[:cut]
            cleaned=textUtils.get_string_no_punctuation_or_emoji(raw)
            if cleaned:
                self.processed_chars += len(raw)
                self.is_first_sentence=False
                return cleaned
        return None

    def _v66_reset_metrics(self):
        self._v66_tts_first_at=time.monotonic()
        self._v66_edge_start_at=0.0
        self._v66_edge_audio_at=0.0
        self._v66_pcm_at=0.0
        self._v66_opus_at=0.0
        self._v66_ack_opus_at=0.0

    def _v66_write_metric(self, kind, text=""):
        try:
            now=time.monotonic()
            base=self._v66_tts_first_at or now
            obj={
                "ts":time.time(),
                "kind":kind,
                "voice":self.voice,
                "text_chars":len(text or ""),
                "tts_first_to_ack_opus_ms":round((self._v66_ack_opus_at-base)*1000,1) if self._v66_ack_opus_at else None,
                "tts_first_to_edge_start_ms":round((self._v66_edge_start_at-base)*1000,1) if self._v66_edge_start_at else None,
                "tts_first_to_edge_audio_ms":round((self._v66_edge_audio_at-base)*1000,1) if self._v66_edge_audio_at else None,
                "tts_first_to_pcm_ms":round((self._v66_pcm_at-base)*1000,1) if self._v66_pcm_at else None,
                "tts_first_to_opus_ms":round((self._v66_opus_at-base)*1000,1) if self._v66_opus_at else None,
            }
            os.makedirs(os.path.dirname(self.metrics_file),exist_ok=True)
            with open(self.metrics_file,"a",encoding="utf-8") as f:
                f.write(json.dumps(obj,ensure_ascii=False)+"\n")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Không ghi được TTS metric V6.6: {e}")

    def _v66_play_cached_ack(self):
        if not self.instant_ack_enabled:
            return
        if not self.instant_ack_file or not os.path.exists(self.instant_ack_file):
            logger.bind(tag=TAG).warning(
                f"Instant ACK bật nhưng thiếu file: {self.instant_ack_file}"
            )
            return
        try:
            first=[False]
            def cb(packet):
                if not first[0]:
                    first[0]=True
                    self._v66_ack_opus_at=time.monotonic()
                self.handle_opus(packet)
            self._process_audio_file_stream(self.instant_ack_file,callback=cb)
            self._v66_write_metric("instant_ack")
        except Exception as e:
            logger.bind(tag=TAG).warning(f"Instant ACK lỗi, bỏ qua: {e}")

    def tts_text_priority_thread(self):
        while not self.conn.stop_event.is_set():
            try:
                msg=self.tts_text_queue.get(timeout=1)
                if self.conn.client_abort:
                    continue
                if msg.sentence_id != self.conn.sentence_id:
                    continue

                if msg.sentence_type==SentenceType.FIRST:
                    self.current_sentence_id=msg.sentence_id
                    self.tts_stop_request=False
                    self.processed_chars=0
                    self.tts_text_buff=[]
                    self.is_first_sentence=True
                    self.tts_audio_first_sentence=True
                    self.before_stop_play_files.clear()
                    self._v66_reset_metrics()
                    self._v66_play_cached_ack()

                elif msg.content_type==ContentType.TEXT:
                    self.tts_text_buff.append(msg.content_detail)
                    segment=self._get_segment_text()
                    if segment:
                        self.to_tts_single_stream(segment)

                elif msg.content_type==ContentType.FILE:
                    self._process_remaining_text_v63()
                    if msg.content_file and os.path.exists(msg.content_file):
                        self._process_audio_file_stream(
                            msg.content_file,callback=self.handle_opus
                        )

                if msg.sentence_type==SentenceType.LAST:
                    had=self._process_remaining_text_v63()
                    if not had:
                        self._process_before_stop_play_files()

            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"Edge stream TTS lỗi: {e}\n{traceback.format_exc()}"
                )

    def _process_remaining_text_v63(self):
        full_text="".join(self.tts_text_buff)
        remaining=full_text[self.processed_chars:]
        if not remaining:
            return False
        segment=textUtils.get_string_no_punctuation_or_emoji(remaining)
        if not segment:
            return False
        self.to_tts_single_stream(segment)
        self.processed_chars=len(full_text)
        return True

    def to_tts_single_stream(self,text):
        original=text
        text=MarkdownCleaner.clean_markdown(text)
        if self._correct_words_pattern:
            text=self._correct_words_pattern.sub(
                lambda m:self.correct_words[m.group(0)],text
            )

        if not self.ffmpeg:
            logger.bind(tag=TAG).warning(
                "Không có ffmpeg, fallback Edge TTS không-stream."
            )
            return super().to_tts_stream(original,opus_handler=self.handle_opus)

        try:
            asyncio.run(self._stream_edge_mp3_to_opus(text,original))
        except Exception as e:
            logger.bind(tag=TAG).error(f"Edge streaming thất bại: {e}")

    async def _stream_edge_mp3_to_opus(self,text,original):
        sentence_id=getattr(self,"current_sentence_id",None)
        self._v66_edge_start_at=time.monotonic()
        self.tts_audio_queue.put(
            (SentenceType.FIRST,[],original,sentence_id)
        )

        proc=await asyncio.create_subprocess_exec(
            self.ffmpeg,
            "-hide_banner","-loglevel","error",
            "-f","mp3","-i","pipe:0",
            "-f","s16le",
            "-ac","1",
            "-ar",str(self.conn.sample_rate),
            "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        sent_audio=[False]

        def opus_callback(packet):
            sent_audio[0]=True
            if not self._v66_opus_at:
                self._v66_opus_at=time.monotonic()
            self.handle_opus(packet)

        async def writer():
            communicate=edge_tts.Communicate(
                text,voice=self.voice,rate=self.edge_rate,
                volume=self.edge_volume,pitch=self.edge_pitch
            )
            try:
                async for chunk in communicate.stream():
                    if chunk.get("type")=="audio":
                        if not self._v66_edge_audio_at:
                            self._v66_edge_audio_at=time.monotonic()
                        proc.stdin.write(chunk["data"])
                        await proc.stdin.drain()
            finally:
                try:
                    proc.stdin.close()
                    if hasattr(proc.stdin,"wait_closed"):
                        await proc.stdin.wait_closed()
                except Exception:
                    pass

        writer_task=asyncio.create_task(writer())
        try:
            while True:
                pcm=await proc.stdout.read(4096)
                if not pcm:
                    break
                if not self._v66_pcm_at:
                    self._v66_pcm_at=time.monotonic()
                self.opus_encoder.encode_pcm_to_opus_stream(
                    pcm,end_of_stream=False,callback=opus_callback
                )
            await writer_task
            self.opus_encoder.encode_pcm_to_opus_stream(
                b"",end_of_stream=True,callback=opus_callback
            )
            rc=await proc.wait()
            if rc!=0 and not sent_audio[0]:
                err=(await proc.stderr.read()).decode("utf-8","ignore")
                raise RuntimeError(f"ffmpeg rc={rc}: {err[:300]}")
            self._v66_write_metric("edge_stream",original)
        except Exception:
            if not writer_task.done():
                writer_task.cancel()
            try:
                proc.kill()
            except Exception:
                pass
            raise
