"""
Brain: Sunna (Whisper STT with Noise Suppression) -> Sochna (Groq LLM + tools) -> Bolna (Piper TTS)

Audio format: Twilio 8kHz mu-law frames.
  - STT ke liye: 8kHz mu-law -> 16kHz PCM (Whisper ko 16k chahiye)
  - TTS ke baad: Piper WAV -> 8kHz mu-law (Twilio ko wapas bhejne ke liye)

Features:
  - Ambient noise filtering via RMS energy gating
  - Hallucination rejection
  - Real-time barge-in cut-off
  - Groq Whisper Cloud (fast, zero DLL issues) + local faster-whisper fallback
"""
import asyncio
import audioop
import base64
import io
import json
import os
import re
import subprocess
import wave

import httpx
from dotenv import load_dotenv

load_dotenv()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "hi")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
PIPER_MODEL = os.getenv("PIPER_MODEL_PATH", "voices/hi_IN.onnx")
PIPER_CONFIG = os.getenv("PIPER_CONFIG_PATH", "voices/hi_IN.onnx.json")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Repetitive hallucination phrases emitted by Whisper on faint noise or silence
HALLUCINATION_BLACKLIST = {
    "thank you", "thank you.", "thanks for watching", "subtitles by",
    "you", "bye", "bye.", "...", "हां", "हाँ", "अच्छा", "हाँ।", "so", "the"
}

_model = None
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None and GROQ_API_KEY and "demo" not in GROQ_API_KEY.lower():
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            print(f"[Brain] Could not initialize Groq SDK: {e}")
    return _groq_client


def _whisper():
    """Local faster-whisper model lazy-load (fallback if available)."""
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel
            _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        except Exception as e:
            print(f"[Brain] Local faster-whisper unavailable ({e}), using cloud STT.")
    return _model


def _http_client() -> httpx.AsyncClient:
    proxy_url = os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
    return httpx.AsyncClient(timeout=30, trust_env=False, proxy=proxy_url)


def transcribe(pcm_8k: bytes) -> str:
    """
    8kHz 16-bit PCM bytes -> clean transcribed text.
    Filters out background noise, ambient room hiss, and whisper hallucinations.
    """
    if not pcm_8k or len(pcm_8k) < 8000:  # < 0.5s is too short
        return ""

    # 1. Noise Floor Gate: If overall RMS is below 480, it is ambient room noise/silence
    rms = audioop.rms(pcm_8k, 2)
    if rms < 480:
        return ""

    # 2. Resample 8kHz -> 16kHz
    pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm_16k)
    buf.seek(0)
    buf.name = "audio.wav"

    raw_text = ""

    # 3. Prefer Groq Whisper Cloud (fastest, most accurate, zero DLL dependencies)
    groq = _get_groq_client()
    if groq is not None:
        try:
            res = groq.audio.transcriptions.create(
                model="whisper-large-v3",
                file=buf,
                language=WHISPER_LANGUAGE,
                temperature=0.0
            )
            raw_text = (res.text or "").strip()
        except Exception as err:
            print(f"[Brain STT] Groq cloud transcription notice: {err}")

    # 4. Fallback to local faster-whisper if Groq cloud was unavailable
    if not raw_text:
        model = _whisper()
        if model is not None:
            try:
                buf.seek(0)
                segments, _ = model.transcribe(
                    buf,
                    language=WHISPER_LANGUAGE,
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500, threshold=0.5)
                )
                filtered = []
                for s in segments:
                    if getattr(s, 'no_speech_prob', 0) > 0.6:
                        continue
                    filtered.append(s.text)
                raw_text = "".join(filtered).strip()
            except Exception as e:
                print(f"[Brain STT] Local whisper transcription error: {e}")

    # 5. Hallucination & Low-Quality Filter
    cleaned = raw_text.strip().strip(".?! ")
    if not cleaned or len(cleaned) < 2:
        return ""

    if cleaned.lower() in HALLUCINATION_BLACKLIST:
        return ""

    return cleaned


async def llm_reply(agent: dict, history: list, user_text: str) -> str:
    """
    Groq LLM call + tool-calling loop.
    Returns: agent ka jawab (text).
    """
    from tools_impl import dispatch

    messages = [{"role": "system", "content": agent["system_prompt"]}]
    messages += history
    messages.append({"role": "user", "content": user_text})

    # Available models fallback list
    candidate_models = [GROQ_MODEL, "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

    async with _http_client() as client:
        for _ in range(3):  # tool -> result -> (tool) -> final jawab
            resp = None
            for model_name in candidate_models:
                try:
                    resp = await client.post(
                        GROQ_URL,
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                        json={
                            "model": model_name,
                            "messages": messages,
                            "tools": agent.get("tools", []),
                            "tool_choice": "auto" if agent.get("tools") else None,
                            "temperature": 0.6,
                            "max_tokens": 150,  # short response for phone pace
                        },
                    )
                    resp.raise_for_status()
                    break
                except Exception as ex:
                    print(f"[Brain LLM] Model {model_name} attempt: {ex}")

            if not resp or resp.status_code != 200:
                return "Haanji, ek second rukiye..."

            msg = resp.json()["choices"][0]["message"]
            messages.append(msg)

            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                content = (msg.get("content") or "").strip()
                # Clean out any thought tokens or markdown
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
                content = re.sub(r"[*#_~]", "", content).strip()
                return content or "Theek hai, samajh gaya."

            for tc in tool_calls:
                args = json.loads(tc["function"]["arguments"] or "{}")
                result = dispatch(tc["function"]["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": result}
                )

    return "Hmm, samajh gaya."


def synthesize(text: str) -> bytes:
    """
    Text -> 8kHz mu-law bytes (Twilio ready).
    Raises RuntimeError agar Piper model files nahi milein.
    """
    if not (os.path.exists(PIPER_MODEL) and os.path.exists(PIPER_CONFIG)):
        raise RuntimeError(
            f"Piper voice files nahi milein: {PIPER_MODEL}. "
            "piper-voices repo se Hindi voice download karke voices/ me rakho."
        )
    proc = subprocess.run(
        ["piper", "--model", PIPER_MODEL, "--config", PIPER_CONFIG,
         "--output_file", "-", "--quiet"],
        input=text.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Piper error: {proc.stderr.decode()[:200]}")
    with wave.open(io.BytesIO(proc.stdout), "rb") as w:
        pcm = w.readframes(w.getnframes())
        rate = w.getframerate()
    if rate != 8000:
        pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 8000, None)
    return audioop.lin2ulaw(pcm, 2)


def mulaw_to_frames(mulaw: bytes, ms: int = 20):
    """mu-law bytes -> base64 frames (20ms = 160 bytes @ 8kHz)."""
    chunk = int(8000 * ms / 1000)
    for i in range(0, len(mulaw), chunk):
        yield base64.b64encode(mulaw[i:i + chunk]).decode()


class CallBrain:
    """
    Ek call ka poora state: audio buffer, noise gating, barge-in, conversation history.

    Flow: feed_audio() har 20ms frame pe -> turn_ready() jab caller ruk jaye ->
          handle_turn() = transcribe -> llm_reply (+tools).
    """

    SILENCE_END_MS = 650   # itni khamoshi = caller ne baat khatam ki
    SPEECH_RMS = 480       # background noise floor filter
    BARGE_RMS = 1400       # bolte waqt isse zyada = caller ne beech me toka

    def __init__(self, agent: dict):
        self.agent = agent
        self.history: list = []
        self._buf = bytearray()
        self._silence_ms = 0
        self._speaking = False
        self._interrupt = asyncio.Event()

    # ---- speaking state (barge-in ke liye) ----
    def begin_speaking(self):
        self._speaking = True
        self._interrupt.clear()

    def end_speaking(self):
        self._speaking = False
        self._interrupt.clear()

    def interrupted(self) -> bool:
        return self._interrupt.is_set()

    # ---- incoming audio ----
    def feed_audio(self, mulaw_frame: bytes):
        """Twilio ka har 20ms audio frame yahan aata hai."""
        pcm = audioop.ulaw2lin(mulaw_frame, 2)
        rms = audioop.rms(pcm, 2)

        if self._speaking:
            if rms > self.BARGE_RMS:  # caller ne beech me bola -> ruko
                self._interrupt.set()
            return

        if rms > self.SPEECH_RMS:
            self._buf.extend(pcm)
            self._silence_ms = 0
        elif self._buf:
            self._silence_ms += 20
            self._buf.extend(pcm)  # chhota pause bhi buffer me

    def turn_ready(self) -> bool:
        return bool(self._buf) and self._silence_ms >= self.SILENCE_END_MS

    # ---- ek poora turn ----
    async def handle_turn(self):
        """
        Returns: (caller_text, agent_reply).
        (None, None) agar audio background noise tha ya kuch samajh nahi aaya.
        """
        pcm = bytes(self._buf)
        self._buf.clear()
        self._silence_ms = 0

        if len(pcm) < 8000:  # < 0.5 sec = noise, ignore
            return None, None

        # Check total buffer energy to eliminate low hum
        total_rms = audioop.rms(pcm, 2)
        if total_rms < self.SPEECH_RMS:
            return None, None

        user_text = await asyncio.to_thread(transcribe, pcm)
        if not user_text or len(user_text.strip()) < 2:
            return None, None

        reply = await llm_reply(self.agent, self.history, user_text)
        if not reply:
            return None, None

        self.history += [
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": reply},
        ]
        self.history = self.history[-10:]  # keep recent turns
        return user_text, reply
