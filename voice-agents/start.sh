#!/bin/bash
# Voice agents server start karo.
# Pehli baar: dependencies install hongi (faster-whisper ~2GB download ho sakta hai).
set -e
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ".env banaya hai (.env.example se) — apni keys bhardo, phir dobara chalao."
  exit 1
fi

if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
  echo "Dependencies install ho rahi hain..."
  pip install -r requirements.txt
fi

echo "Server start ho raha hai: http://localhost:8000"
echo "(Public URL ke liye doosre terminal me: ngrok http 8000)"
python3 server.py
