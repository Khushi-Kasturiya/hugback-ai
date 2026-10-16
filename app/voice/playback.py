"""Bounded TTS lookahead with one ordered emitter; never mix voices or turns."""

import asyncio
import base64
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field

from app.voice.service import REPLICATED_SPEECH_STYLE, stream_replicated_speech

logger = logging.getLogger("hugback.voice")
_FAILED = object()
PCM_CHUNK_BYTES = 24_000  # Half a second of mono PCM16 at 24 kHz.
BUFFERED_CHUNKS = 4      # At most two seconds buffered per producer.


@dataclass
class _Speech:
    text: str = field(repr=False)
    final: bool
    generation: int
    queued_at: float = field(default_factory=time.monotonic)
    audio: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=BUFFERED_CHUNKS), repr=False)
    producer: asyncio.Task | None = field(default=None, repr=False)
    started_at: float = 0
    first_audio_at: float = 0
    failed: bool = False


class ReplicatedPlayback:
    def __init__(self, client, websocket, *, voice_key, model, on_audio=None, lookahead=1,
                 style=REPLICATED_SPEECH_STYLE):
        if lookahead not in (0, 1):
            raise ValueError("TTS lookahead must be zero or one")
        self.client, self.websocket = client, websocket
        self.voice_key, self.model = voice_key, model
        self.style = style
        self.on_audio = on_audio
        self.lookahead = lookahead
        self.queue = deque()
        self.changed = asyncio.Event()
        self.generation = 0
        self.segment_task = None
        self.checkpoint_task = None
        self.producers = set()
        self.closed = False
        self.task = asyncio.create_task(self.run())

    def enqueue(self, text, *, final=False):
        if self.closed or self.task.done():
            raise RuntimeError("Replicated speech is unavailable; call stopped.")
        # Includes the currently emitted/prefetched phrases, not just waiting text.
        if len(self.queue) >= 32:
            raise asyncio.QueueFull()
        self.queue.append(_Speech(text=text, final=final, generation=self.generation))
        self.changed.set()
        self._fill_pipeline()

    def _fill_pipeline(self):
        if self.closed or self.task.done():
            return
        if any(speech.failed for speech in self.queue):
            # Deliver preceding audio/error in order, but do not spend on a new
            # phrase once a queued synthesis failure is already known.
            return
        # Only current + one already-generated phrase may synthesize. Count
        # cancelling workers too: a slow provider close must not create fan-out.
        for speech in list(self.queue)[:1 + self.lookahead]:
            if len(self.producers) >= 1 + self.lookahead:
                break
            if speech.text and speech.producer is None:
                speech.producer = asyncio.create_task(self._produce(speech))
                self.producers.add(speech.producer)
                speech.producer.add_done_callback(self._producer_finished)

    def _producer_finished(self, task):
        self.producers.discard(task)
        self._fill_pipeline()

    def interrupt(self):
        self.generation += 1
        self.queue.clear()
        for task in self.producers:
            task.cancel()
        if self.segment_task:
            self.segment_task.cancel()
        if self.checkpoint_task:
            self.checkpoint_task.cancel()

    async def _produce(self, speech):
        speech.started_at = time.monotonic()
        stream = None
        try:
            stream = stream_replicated_speech(
                self.client, voice_key=self.voice_key, text=speech.text, model=self.model,
                style=self.style,
            )
            async with asyncio.timeout(30):
                async for audio in stream:
                    if speech.generation != self.generation:
                        return
                    if audio.sample_rate != 24000 or len(audio.pcm) % 2:
                        raise RuntimeError("Invalid PCM16 TTS output")
                    if not audio.pcm:
                        continue
                    if not speech.first_audio_at:
                        speech.first_audio_at = time.monotonic()
                    # Backpressure bounds decoded audio even if Google emits
                    # several seconds at once. Only the emitter sends captions.
                    for offset in range(0, len(audio.pcm), PCM_CHUNK_BYTES):
                        await speech.audio.put(audio.pcm[offset:offset + PCM_CHUNK_BYTES])
                if not speech.first_audio_at:
                    raise RuntimeError("Google returned no replicated audio")
            await speech.audio.put(None)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Never save or expose provider bodies, text or voice keys.
            speech.failed = True
            await speech.audio.put(_FAILED)
        finally:
            if stream is not None:
                try:
                    await stream.aclose()
                except Exception:
                    logger.warning("Replicated speech stream cleanup unavailable")

    async def _checkpoint(self, generation):
        try:
            if generation == self.generation:
                async with asyncio.timeout(1):
                    await self.on_audio()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning("Replicated speech output checkpoint unavailable")

    async def segment(self, speech):
        chunks = 0
        while speech.generation == self.generation:
            audio = await speech.audio.get()
            if audio is _FAILED:
                raise RuntimeError("Replicated speech failed")
            if audio is None:
                return
            if speech.generation == self.generation:
                payload = {"content": {"parts": [{
                    "inlineData": {"mimeType": "audio/pcm;rate=24000",
                                   "data": base64.b64encode(audio).decode("ascii")}
                }]}}
                if chunks == 0:
                    # Phrase cue only, not word timestamps or proof of hearing.
                    # The browser reveals it when this PCM reaches playback.
                    payload["outputTranscription"] = {"text": speech.text, "playbackAligned": True}
                await self.websocket.send_text(json.dumps(payload))
                chunks += 1
                if chunks == 1:
                    # Content-free diagnostics, NOT mouth-to-ear measurements.
                    logger.info("Replicated TTS timing queue_ms=%d synthesis_first_pcm_ms=%d ordered_wait_ms=%d",
                                round((speech.started_at - speech.queued_at) * 1000),
                                round((speech.first_audio_at - speech.started_at) * 1000),
                                round((time.monotonic() - speech.first_audio_at) * 1000))
                    if self.on_audio and (not self.checkpoint_task or self.checkpoint_task.done()):
                        self.checkpoint_task = asyncio.create_task(self._checkpoint(speech.generation))

    async def run(self):
        try:
            while True:
                while not self.queue:
                    self.changed.clear()
                    await self.changed.wait()
                speech = self.queue[0]
                self._fill_pipeline()
                if speech.text:
                    self.segment_task = asyncio.create_task(self.segment(speech))
                    try:
                        # Include a stalled browser socket in the phrase deadline,
                        # not just time spent producing/buffering Google audio.
                        async with asyncio.timeout(30):
                            await self.segment_task
                    except asyncio.CancelledError:
                        if asyncio.current_task().cancelling() or speech.generation == self.generation:
                            raise
                        continue
                    finally:
                        self.segment_task = None
                if speech.generation != self.generation:
                    continue
                if speech.final:
                    await self.websocket.send_text(json.dumps({"turnComplete": True}))
                # A send can yield to interruption; do not pop the new turn.
                if self.queue and self.queue[0] is speech:
                    self.queue.popleft()
                self._fill_pipeline()
        except asyncio.CancelledError:
            raise
        except Exception:
            self.closed = True
            logger.warning("Replicated voice synthesis stopped; no preset fallback")
            await self.websocket.send_text(json.dumps({
                "type": "error", "code": "replicated_tts_failed",
                "message": "Custom voice synthesis failed. Call stopped without switching voices. Check Voice setup before retrying.",
            }))
        finally:
            self.closed = True
            pending = list(self.producers)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    async def close(self):
        self.closed = True
        self.task.cancel()
        if self.segment_task:
            self.segment_task.cancel()
        pending = [self.task, *self.producers]
        if self.segment_task:
            pending.append(self.segment_task)
        for task in self.producers:
            task.cancel()
        # The callback is separately capped at one second. Let an emitted-audio
        # checkpoint finish on normal disconnect; never block PCM delivery on it.
        if self.checkpoint_task:
            pending.append(self.checkpoint_task)
        await asyncio.gather(*pending, return_exceptions=True)
        self.queue.clear()
