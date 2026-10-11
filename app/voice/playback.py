"""One bounded speech worker per call; only selected-voice audio is emitted."""

import asyncio
import base64
import json
import logging

from app.voice.service import stream_replicated_speech

logger = logging.getLogger("hugback.voice")


class ReplicatedPlayback:
    def __init__(self, client, websocket, *, voice_key, model, on_audio=None):
        self.client, self.websocket = client, websocket
        self.voice_key, self.model = voice_key, model
        self.on_audio = on_audio
        self.queue = asyncio.Queue(maxsize=32)
        self.generation = 0
        self.segment_task = None
        self.task = asyncio.create_task(self.run())

    def enqueue(self, text, *, final=False):
        if self.task.done():
            raise RuntimeError("Replicated speech is unavailable; call stopped.")
        # Never accumulate unbounded paid synthesis work.
        self.queue.put_nowait((text, final, self.generation))

    def interrupt(self):
        self.generation += 1
        while not self.queue.empty():
            self.queue.get_nowait()
        if self.segment_task:
            self.segment_task.cancel()

    async def segment(self, text, generation):
        chunks = 0
        async with asyncio.timeout(30):
            async for audio in stream_replicated_speech(
                self.client, voice_key=self.voice_key, text=text, model=self.model,
            ):
                if generation != self.generation:
                    return
                if audio.sample_rate != 24000:
                    raise RuntimeError("Unexpected TTS rate; refusing distorted playback")
                await self.websocket.send_text(json.dumps({"content": {"parts": [{
                    "inlineData": {"mimeType": "audio/pcm;rate=24000",
                                   "data": base64.b64encode(audio.pcm).decode("ascii")}
                }]}}))
                chunks += 1
                if chunks == 1 and self.on_audio:
                    await self.on_audio()
            if not chunks:
                raise RuntimeError("Google returned no replicated audio")

    async def run(self):
        try:
            while True:
                text, final, generation = await self.queue.get()
                if generation != self.generation:
                    continue
                if text:
                    self.segment_task = asyncio.create_task(self.segment(text, generation))
                    try:
                        await self.segment_task
                    except asyncio.CancelledError:
                        if asyncio.current_task().cancelling() or generation == self.generation:
                            raise
                        continue
                    finally:
                        self.segment_task = None
                if final and generation == self.generation:
                    await self.websocket.send_text(json.dumps({"turnComplete": True}))
                # Stay alive across turns. Returning here stranded the next turn
                # when Live produced it before the previous TTS finished.
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Replicated voice synthesis stopped; no preset fallback")
            await self.websocket.send_text(json.dumps({
                "type": "error", "code": "replicated_tts_failed",
                "message": "Custom voice synthesis failed. Call stopped without switching voices. Check Voice setup before retrying.",
            }))

    async def close(self):
        self.task.cancel()
        if self.segment_task:
            self.segment_task.cancel()
        await asyncio.gather(
            self.task, *([self.segment_task] if self.segment_task else []),
            return_exceptions=True,
        )
