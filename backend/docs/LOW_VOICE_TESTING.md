# Test quiet and normal speaking in HugBack

This is a **fictional local simulator test** for a beginner. It checks two
different things: whether the microphone/Live session hears soft speech, and
whether HugBack responds gently when a voice *sounds* subdued. Soft volume by
itself does not mean sadness, illness, fatigue or low energy.

The John Keats local example mainly gives its Live agent instructions to
adjust pace and warmth. HugBack already has its own optional gentle tone
check-in path: Gemini Live may propose a bounded vocal-cue category, the server
requires high confidence and enough speech before storing one cue, and the next
call may use it tentatively. This is model interpretation, not a calibrated
acoustic measurement or voice identification. The **Microphone input** bar on
HugBack's fictional call screen shows local audio volume only; it does not
classify emotion and is not stored.

## Prepare the test

1. Start the backend and frontend using `docs/BEGINNER_E2E_AGENT_TESTING.md`.
   Use a fictional recipient such as Mumma, and keep **Gentle voice-tone
   check-ins** enabled in Family setup. Tick the separate simulated agreement
   and click **Enable gentle tone check-ins**; the checkbox alone does not save
   the setting. AI-estimated child call signals and automatic email can stay off.
2. In the same browser and origin, select Mumma and click **Test a call as
   Mumma**. Acknowledge the fictional call and begin. Keep the same headset,
   microphone position and room for the comparisons below. Do not use a real
   family voice or personal history.
3. Watch the **Microphone input** bar when you speak. It should move for normal
   and soft speech. Check the live **You:** words to see whether the model
   transcribed what you said. If the bar barely moves or words do not appear,
   fix microphone permissions, selected input device, distance or background
   noise before judging HugBack's tone response.

## Run the comparison

Use separate fresh calls as Mumma. Speak for at least two meaningful turns in
each call; a single “hi” is intentionally too little evidence for a retained
tone cue. End each call and wait for post-call processing before inspecting it.
After inspecting A and B, use Family setup to **Stop tone check-ins and erase
tone note**, then tick the simulated agreement and enable it again before the
next comparison. This prevents one call's note from influencing the next. Keep
C's note only when you intentionally test the later-call follow-up.

| Call | How to speak | Fictional words | What to look for |
| --- | --- | --- | --- |
| A: normal/medium | Natural volume and ordinary energy | “I had a quiet morning and watered my imaginary garden.” Then “I made tea and read a little.” | Bar moves; words are transcribed. HugBack should converse normally, without insisting you sound low. |
| B: soft but cheerful control | Lower volume, clearly cheerful delivery | “I am happy that my imaginary flowers bloomed today.” Then “It made me smile; I enjoyed the morning.” | Bar still moves and words appear. HugBack should not decide you are sad merely because volume is lower. |
| C: subdued delivery | Audible but slower, flatter and quieter than your normal delivery | Repeat A's **exact same two fictional sentences**. | This reduces the wording difference between A and C. After several utterances, HugBack **may** ask one tentative question such as “You sound a little quiet today; how are you feeling?” It must not diagnose or repeat the question. |
| D: low input or noise | Speak too far from the mic, or give only “hi” | No meaningful sustained speech | The bar/words may show poor capture. HugBack should not confidently infer a mood or save a cue. |

Call B is the key false-positive test. Call C is a *possible* true cue, not a
guaranteed model response. Exact results depend on audio, microphone gain,
Live transcription and model behavior. If you want to test the next-call flow,
start a new Mumma call **after** inspecting call C. HugBack may use a retained
cue only as uncertain context after hearing the new call; the note is consumed
on that next attempt. It must not say it recognized the person's voice.

## Check what the backend actually stored

The family UI intentionally does not show the private tone note. On the local
machine, the operator can inspect its **status only** immediately after ending
a call, before starting the next one:

```sh
cd /Users/pratham.gupta/elara.ai-backend
.venv/bin/python scripts/inspect_demo_tone.py \
  --owner YOUR_LOCAL_DEVELOPMENT_ID \
  --recipient SERVER_ISSUED_RECIPIENT_ID
```

Get the development ID from this browser's `localStorage` key
`hugback.development.user.v1` (Developer Tools → Application/Storage → Local
Storage). Get the recipient ID from the call's **Call details** or selected
family API response. `activeNote: true` with category `lower_energy` means the
model made a qualifying high-confidence vocal-cue proposal and the local store
accepted it. `activeNote: false` can mean no qualifying proposal, too-short
speech, uncertainty, a revoked setting, expiry, or a note consumed by the next
call. It does not by itself identify which reason occurred. The command shows
no transcript or audio. Firestore test mode additionally requires the existing
explicit `--allow-cloud-read` gate and its authorized test owner.

Stop check-ins in Family setup to erase the note. Saying “Please stop
analyzing my voice” during an enabled call should also revoke them. Tone alone
must not send the child an email or become a medical conclusion.

## Free repeatable checks

```sh
.venv/bin/python -m unittest tests.test_tone_continuity -q
.venv/bin/python -m evals.run --suite offline --output /tmp/hugback-offline-eval.json
```

These mock Google audio and tool output. They verify consent, recipient
isolation, short-call abstention, revocation, store inspection and broker
wiring. They **cannot** prove that a real quiet voice will be recognized or
that HugBack will phrase a check-in well. The manual A/B calls above are the
actual acoustic test and may use the configured paid Google Live model.
