"""Gate-controlled synthetic latency regressions. No Google, recordings or clocks to bill."""

import asyncio
import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import ValidationError

from app.config import Settings
from app.voice.playback import BUFFERED_CHUNKS, PCM_CHUNK_BYTES, ReplicatedPlayback
from app.voice.service import SynthesizedAudio, split_ready_speech


def pcm(text="ok"):
    return SynthesizedAudio(pcm=(text + " " * (len(text) % 2)).encode(), sample_rate=24000)


class FirstPhraseTests(unittest.TestCase):
    def test_initial_clause_can_start_before_sentence_completion(self):
        text = "It is really good to hear from you, and I am here to listen"
        self.assertEqual(split_ready_speech(text)[0], [])
        ready, pending = split_ready_speech(text, first_phrase_chars=96)
        self.assertEqual(ready, ["It is really good to hear from you,"])
        self.assertEqual(pending, "and I am here to listen")

    def test_initial_word_boundary_is_shorter_then_later_text_keeps_batching(self):
        text = "Here are some entirely fictional words for testing a streamed reply " * 3
        self.assertEqual(split_ready_speech(text)[0], [])
        ready, pending = split_ready_speech(text, first_phrase_chars=96)
        self.assertEqual(len(ready), 1)
        self.assertLessEqual(len(ready[0]), 96)
        self.assertEqual(" ".join(ready + [pending]).strip(), text.strip())
        self.assertEqual(split_ready_speech(pending)[0], [])

    def test_short_fragments_and_numbers_do_not_cause_micro_requests(self):
        for text in ("Yes, I", "I have 1,000", "I know", "नमस्ते पापा",
                     "The fictional number in this example is 1,"):
            with self.subTest(text=text):
                self.assertEqual(split_ready_speech(text, first_phrase_chars=96), ([], text))
                self.assertEqual(split_ready_speech(text, first_phrase_chars=96, final=True), ([text], ""))

    def test_hindi_and_partial_stream_preserve_words_without_duplication(self):
        text = "आपसे बात करके मुझे बहुत अच्छा लग रहा है, मैं आपकी बात ध्यान से सुन रहा हूँ।"
        pending = ""; all_ready = []; first = True
        for offset in range(0, len(text), 3):
            pending += text[offset:offset + 3]
            ready, pending = split_ready_speech(pending, first_phrase_chars=48 if first else None)
            all_ready.extend(ready)
            if ready:
                first = False
        tail, pending = split_ready_speech(pending, final=True)
        self.assertEqual(" ".join(all_ready + tail), text)
        self.assertEqual(pending, "")

    def test_initial_bound_does_not_chop_a_single_word(self):
        text = "क" * 120
        self.assertEqual(split_ready_speech(text, first_phrase_chars=96), ([], text))

    def test_latency_config_is_bounded(self):
        for kwargs in ({"HUGBACK_TTS_LOOKAHEAD": 2}, {"HUGBACK_TTS_LOOKAHEAD": -1},
                       {"HUGBACK_TTS_FIRST_PHRASE_CHARS": 0}, {"HUGBACK_TTS_FIRST_PHRASE_CHARS": 281}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                Settings(_env_file=None, **kwargs)


class LatencyPipelineTests(unittest.IsolatedAsyncioTestCase):
    def make(self, *, lookahead=1, checkpoint=None):
        self.events = []
        self.completed = asyncio.Queue()

        async def send(value):
            event = json.loads(value)
            self.events.append(event)
            if event.get("turnComplete") or event.get("type") == "error":
                await self.completed.put(event)

        return ReplicatedPlayback(
            None, SimpleNamespace(send_text=send), voice_key="voicekey_synthetic_private",
            model="synthetic-model", lookahead=lookahead, on_audio=checkpoint,
        )

    async def complete(self):
        return await asyncio.wait_for(self.completed.get(), 1)

    def subtitles(self):
        return [e["outputTranscription"]["text"] for e in self.events if "outputTranscription" in e]

    async def test_lookahead_starts_second_request_before_first_finishes_but_emits_in_order(self):
        requests = []
        release_first, second_started = asyncio.Event(), asyncio.Event()

        async def stream(*args, **kwargs):
            text = kwargs["text"]
            requests.append(text)
            if text == "first":
                await release_first.wait()
            elif text == "second":
                second_started.set()
            yield pcm(text)

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make()
            try:
                for text in ("first", "second", "third"):
                    playback.enqueue(text, final=True)
                await asyncio.wait_for(second_started.wait(), 1)
                await asyncio.sleep(0)
                self.assertEqual(requests, ["first", "second"])
                self.assertEqual(self.events, [])  # No early caption for prefetch.
                release_first.set()
                for _ in range(3):
                    self.assertEqual(await self.complete(), {"turnComplete": True})
                self.assertEqual(requests, ["first", "second", "third"])
                self.assertEqual(self.subtitles(), requests)
            finally:
                await playback.close()

    async def test_serial_switch_never_opens_a_second_request_early(self):
        requests = []
        started, release = asyncio.Event(), asyncio.Event()

        async def stream(*args, **kwargs):
            requests.append(kwargs["text"])
            if kwargs["text"] == "first":
                started.set()
                await release.wait()
            yield pcm()

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make(lookahead=0)
            try:
                playback.enqueue("first", final=True)
                playback.enqueue("second", final=True)
                await asyncio.wait_for(started.wait(), 1)
                await asyncio.sleep(0)
                self.assertEqual(requests, ["first"])
                release.set()
                await self.complete(); await self.complete()
                self.assertEqual(requests, ["first", "second"])
            finally:
                await playback.close()

    async def test_prefetched_pcm_is_bounded_and_both_streams_close_on_disconnect(self):
        next_started = asyncio.Event()
        closed = set()
        requests = []

        async def stream(*args, **kwargs):
            text = kwargs["text"]; requests.append(text)
            try:
                if text == "first":
                    await asyncio.Event().wait()
                next_started.set()
                yield SynthesizedAudio(pcm=b"\0" * PCM_CHUNK_BYTES * 12, sample_rate=24000)
                await asyncio.Event().wait()
            finally:
                closed.add(text)

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make()
            for text in ("first", "second", "third"):
                playback.enqueue(text)
            await asyncio.wait_for(next_started.wait(), 1)
            await asyncio.sleep(0)
            self.assertEqual(requests, ["first", "second"])
            future = list(playback.queue)[1]
            self.assertEqual(future.audio.qsize(), BUFFERED_CHUNKS)
            self.assertEqual(self.events, [])
            await asyncio.wait_for(playback.close(), 1)
            self.assertEqual(closed, {"first", "second"})
            self.assertFalse(playback.producers)
            self.assertFalse(playback.queue)

    async def test_interruption_closes_both_workers_before_starting_replacement(self):
        started = asyncio.Queue()
        closing = asyncio.Queue()
        cleanup = asyncio.Event()
        active = 0; maximum = 0

        async def stream(*args, **kwargs):
            nonlocal active, maximum
            text = kwargs["text"]
            active += 1; maximum = max(maximum, active)
            await started.put(text)
            try:
                if text.startswith("old"):
                    await asyncio.Event().wait()
                yield pcm()
            finally:
                if text.startswith("old"):
                    await closing.put(text)
                    await cleanup.wait()
                active -= 1

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make()
            try:
                playback.enqueue("old first", final=True)
                playback.enqueue("old second", final=True)
                await asyncio.wait_for(started.get(), 1); await asyncio.wait_for(started.get(), 1)
                playback.interrupt()
                playback.enqueue("new", final=True)
                await asyncio.wait_for(closing.get(), 1); await asyncio.wait_for(closing.get(), 1)
                self.assertTrue(started.empty())
                cleanup.set()
                self.assertEqual(await asyncio.wait_for(started.get(), 1), "new")
                await self.complete()
                self.assertEqual(self.subtitles(), ["new"])
                self.assertLessEqual(maximum, 2)
            finally:
                cleanup.set()
                await playback.close()

    async def test_slow_checkpoint_does_not_block_later_pcm_or_turn_completion(self):
        checkpoint_started, release = asyncio.Event(), asyncio.Event()

        async def checkpoint():
            checkpoint_started.set()
            await release.wait()

        async def stream(*args, **kwargs):
            yield pcm("one1")
            await checkpoint_started.wait()
            yield pcm("two2")

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make(checkpoint=checkpoint)
            try:
                playback.enqueue("Synthetic phrase", final=True)
                await self.complete()
                self.assertFalse(playback.checkpoint_task.done())
                audio = [base64.b64decode(e["content"]["parts"][0]["inlineData"]["data"])
                         for e in self.events if "content" in e]
                self.assertEqual(audio, [b"one1", b"two2"])
            finally:
                release.set()
                await playback.close()

    async def test_prefetch_failure_never_changes_voice_retries_or_sends_unspoken_caption(self):
        requests = []

        async def stream(*args, **kwargs):
            requests.append(kwargs["text"])
            if kwargs["text"] == "bad":
                raise RuntimeError("private-provider-body")
            yield pcm()

        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make()
            try:
                playback.enqueue("good", final=True)
                playback.enqueue("bad", final=True)
                playback.enqueue("must not start after known failure", final=True)
                await self.complete()
                self.assertEqual((await self.complete())["code"], "replicated_tts_failed")
                await asyncio.wait_for(playback.task, 1)
                self.assertEqual(requests, ["good", "bad"])
                self.assertEqual(self.subtitles(), ["good"])
                self.assertNotIn("private", json.dumps(self.events))
                with self.assertRaises(RuntimeError):
                    playback.enqueue("never fallback")
            finally:
                await playback.close()

    async def test_content_free_timings_and_failed_checkpoint_do_not_stop_audio(self):
        async def stream(*args, **kwargs):
            yield pcm()
        async def checkpoint():
            raise RuntimeError("private-storage-error")
        with patch("app.voice.playback.stream_replicated_speech", stream), self.assertLogs("hugback.voice", "INFO") as logs:
            playback = self.make(checkpoint=checkpoint)
            playback.enqueue("synthetic private text", final=True)
            await self.complete()
            await playback.close()
        log = "\n".join(logs.output)
        self.assertIn("synthesis_first_pcm_ms=", log)
        self.assertIn("queue_ms=", log)
        self.assertNotIn("private", log)
        self.assertEqual(self.events[-1], {"turnComplete": True})

    async def test_empty_final_marker_does_not_start_paid_work(self):
        with patch("app.voice.playback.stream_replicated_speech") as stream:
            playback = self.make()
            try:
                playback.enqueue("", final=True)
                await self.complete()
                stream.assert_not_called()
                self.assertEqual(self.subtitles(), [])
            finally:
                await playback.close()

    async def test_large_provider_chunk_is_split_without_duplicate_captions_or_pcm_loss(self):
        source = b"\1\0" * (PCM_CHUNK_BYTES * 3 + 1)
        async def stream(*args, **kwargs):
            yield SynthesizedAudio(pcm=source, sample_rate=24000)
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make()
            try:
                playback.enqueue("A synthetic phrase.", final=True)
                await self.complete()
                chunks = [base64.b64decode(e["content"]["parts"][0]["inlineData"]["data"])
                          for e in self.events if "content" in e]
                self.assertEqual(b"".join(chunks), source)
                self.assertTrue(all(len(chunk) <= PCM_CHUNK_BYTES and len(chunk) % 2 == 0 for chunk in chunks))
                self.assertEqual(self.subtitles(), ["A synthetic phrase."])
            finally:
                await playback.close()

    async def test_wrong_rate_and_malformed_pcm_fail_closed_before_subtitle(self):
        for audio in (SynthesizedAudio(pcm=b"\0\0", sample_rate=16000),
                      SynthesizedAudio(pcm=b"\0", sample_rate=24000)):
            with self.subTest(audio=audio):
                async def stream(*args, **kwargs):
                    yield audio
                with patch("app.voice.playback.stream_replicated_speech", stream):
                    playback = self.make()
                    try:
                        playback.enqueue("Must not appear.", final=True)
                        self.assertEqual((await self.complete())["code"], "replicated_tts_failed")
                        self.assertEqual(self.subtitles(), [])
                        self.assertFalse(any("content" in e for e in self.events))
                    finally:
                        await playback.close()

    async def test_blocked_checkpoint_times_out_on_normal_close(self):
        checkpoint_started, checkpoint_closed = asyncio.Event(), asyncio.Event()
        async def checkpoint():
            checkpoint_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                checkpoint_closed.set()
        async def stream(*args, **kwargs):
            yield pcm()
        with patch("app.voice.playback.stream_replicated_speech", stream):
            playback = self.make(checkpoint=checkpoint)
            playback.enqueue("Synthetic phrase.", final=True)
            await self.complete()
            await asyncio.wait_for(checkpoint_started.wait(), 1)
            await asyncio.wait_for(playback.close(), 2)
            self.assertTrue(checkpoint_closed.is_set())
            self.assertTrue(playback.checkpoint_task.done())
