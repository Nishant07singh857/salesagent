"""
FastAPI server: Twilio se call receive karta hai, har agent ke liye alag webhook.

Twilio number webhooks (POST):
  /voice/menu      → 1 number pe teenon agents (IVR: 1/2/3 dabao)
  /voice/booking   → booking agent (apna number)
  /voice/support   → support agent (apna number)
  /voice/lead      → lead agent (apna number)

  /media/<agent>   → real-time audio websocket (Twilio Media Streams)

Run:  ./start.sh        ya:  python server.py   (+ ngrok http 8000)
"""
import asyncio
import base64
import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from agents import AGENTS
from brain import CallBrain, mulaw_to_frames, synthesize

load_dotenv()
DOMAIN = os.getenv("PUBLIC_DOMAIN", "REPLACE-WITH-ngrok-domain")

app = FastAPI()


def twiml_stream(agent: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><Response><Connect>'
        f'<Stream url="wss://{DOMAIN}/media/{agent}"/></Connect></Response>'
    )


@app.post("/voice/menu")
async def voice_menu():
    return PlainTextResponse(
        '<?xml version="1.0" encoding="UTF-8"?><Response>'
        f'<Gather numDigits="1" action="https://{DOMAIN}/voice/route" method="POST">'
        "<Say language='hi-IN'>Namaste! Appointment ke liye 1 dabayein. "
        "Support ke liye 2 dabayein. Sales ke liye 3 dabayein.</Say>"
        "</Gather></Response>",
        media_type="text/xml",
    )


@app.post("/voice/route")
async def voice_route(request: Request):
    form = await request.form()
    digit = (form.get("Digits") or "").strip()
    target = {"1": "booking", "2": "support", "3": "lead"}.get(digit)
    if target:
        return PlainTextResponse(twiml_stream(target), media_type="text/xml")
    return await voice_menu()  # galat input → menu dobara


@app.post("/voice/{agent}")
async def voice_agent(agent: str):
    if agent not in AGENTS:
        return PlainTextResponse(
            "<Response><Say>Galat number.</Say></Response>",
            media_type="text/xml",
        )
    return PlainTextResponse(twiml_stream(agent), media_type="text/xml")


async def _speak(ws: WebSocket, stream_sid: str, brain: CallBrain, text: str):
    """Agent ka jawab audio me badalke Twilio ko bhejo. Barge-in pe beech me ruko."""
    brain.begin_speaking()
    try:
        mulaw = await asyncio.to_thread(synthesize, text)
        for payload in mulaw_to_frames(mulaw):
            if brain.interrupted():
                await ws.send_text(
                    json.dumps({"event": "clear", "streamSid": stream_sid})
                )
                break
            await ws.send_text(
                json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                })
            )
            await asyncio.sleep(0.02)  # real-time pace pe bhejo
    except Exception as e:
        print(f"[Speech Synthesis Warning] {e}", flush=True)
    finally:
        brain.end_speaking()


@app.websocket("/media/{agent_name}")
async def media_stream(ws: WebSocket, agent_name: str):
    if agent_name not in AGENTS:
        await ws.close()
        return
    await ws.accept()
    brain = CallBrain(AGENTS[agent_name])
    stream_sid = None

    async def process_turns():
        """Background loop: caller ruke → transcribe → socho → bolo."""
        while True:
            await asyncio.sleep(0.05)
            if brain.turn_ready():
                user_text, reply = await brain.handle_turn()
                if reply and stream_sid:
                    print(f"[caller] {user_text}\n[agent]  {reply}", flush=True)
                    await _speak(ws, stream_sid, brain, reply)

    processor = asyncio.create_task(process_turns())
    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            event = msg.get("event")
            if event == "start":
                stream_sid = msg["start"]["streamSid"]
                print(f"[call] {agent_name} agent, stream {stream_sid}", flush=True)
                await _speak(ws, stream_sid, brain, brain.agent["greeting"])
            elif event == "media":
                brain.feed_audio(base64.b64decode(msg["media"]["payload"]))
            elif event == "stop":
                print("[call] khatam", flush=True)
                break
    except WebSocketDisconnect:
        pass
    finally:
        processor.cancel()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
