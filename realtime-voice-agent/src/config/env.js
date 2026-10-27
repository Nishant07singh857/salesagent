import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '../../.env') });

export const config = {
  PORT: process.env.PORT || 3000,
  GROQ_API_KEY: process.env.GROQ_API_KEY || '',
  GROQ_MODEL: process.env.GROQ_MODEL || 'qwen/qwen3.8-27b',
  TTS_VOICE: process.env.TTS_VOICE || 'en-US-JennyNeural',
  SYSTEM_PROMPT: process.env.SYSTEM_PROMPT || 'You are a real human on a casual phone call. Never say you are an AI. Keep answers extremely short (1-2 sentences). Talk naturally like a normal person, use casual words like hmm, well, yeah, got it. Do not be overly polite, formal, or robotic.',
};
