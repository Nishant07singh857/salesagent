"""
Terminal demos ke shared helpers (koi pip install zaroori nahi).

Har demo: caller type karta hai → agent jawab deta hai.
  - GROQ_API_KEY asli hai → asli LLM (tools ke saath)
  - nahi to → agent ka built-in demo flow (tools phir bhi ASLI chalte hain)
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents import AGENTS


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def groq_available() -> bool:
    key = os.getenv("GROQ_API_KEY", "")
    return bool(key) and "demo" not in key.lower() and "replace" not in key.lower()


def parse_phone(text):
    digits = re.sub(r"\D", "", text)
    return digits[-10:] if len(digits) >= 10 else None


def try_tts(text: str, n: int, prefix: str):
    """Piper Hindi voice files hain to jawab ka .wav banao, nahi to skip."""
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        model = os.path.join(base, os.getenv("PIPER_MODEL_PATH", "voices/hi_IN.onnx"))
        if not os.path.exists(model):
            return
        import audioop
        import wave
        from brain import synthesize

        pcm = audioop.ulaw2lin(synthesize(text), 2)
        path = os.path.join(base, f"{prefix}_reply_{n}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(8000)
            w.writeframes(pcm)
        print(f"  [audio] {os.path.basename(path)} me save hua")
    except Exception as e:  # noqa: BLE001 — demo me TTS optional hai
        print(f"  [audio] skip: {e}")


def run_demo(agent_key: str, flow_cls, title: str):
    """Ek demo chalao. flow_cls: .reply(user_text) -> (reply, done) wala class."""
    load_env()
    agent = AGENTS[agent_key]
    use_groq = groq_available()

    print("=" * 60)
    print(title)
    print("Tum caller ho: jo caller bolega wo TYPE karo.")
    print(f"Dimaag: {'ASLI Groq LLM' if use_groq else 'demo flow (GROQ_API_KEY demo hai)'}")
    print("Tools: ASLI (data/ files me sach me likhega)")
    print("Bahar nikalne ke liye: bye / exit")
    print("=" * 60)
    print(f"\nAgent: {agent['greeting']}\n")

    history = []
    flow = flow_cls()
    n = 0
    while True:
        try:
            user_text = input("Caller: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nDemo khatam.")
            break
        if not user_text:
            continue
        if user_text.lower() in ("bye", "exit", "quit"):
            print("Agent: Theek hai, dhanyavaad! Phir milenge.")
            break

        if use_groq:
            from brain import llm_reply

            reply = asyncio.run(llm_reply(agent, history, user_text))
            history += [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": reply},
            ]
            history = history[-10:]
            done = False
        else:
            reply, done = flow.reply(user_text)

        n += 1
        print(f"\nAgent: {reply}\n")
        try_tts(reply, n, prefix=agent_key)
        if done:
            break
