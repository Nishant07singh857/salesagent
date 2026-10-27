import express from 'express';
import { WebSocketServer } from 'ws';
import http from 'http';
import path from 'path';
import { fileURLToPath } from 'url';
import { config } from './config/env.js';
import { getLLMStream } from './services/llm.service.js';
import { generateTTSBuffer } from './services/tts.service.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

// Serve static frontend
app.use(express.static(path.join(__dirname, '../public')));

wss.on('connection', (ws) => {
    console.log('[WebSocket] Client connected for real-time voice streaming');
    let conversationHistory = [];
    let currentAbortController = null;

    ws.on('message', async (message) => {
        try {
            const data = JSON.parse(message.toString());

            // Handle barge-in interrupt signal
            if (data.type === 'user_interrupt') {
                if (currentAbortController) {
                    console.log('[WebSocket] User interrupted agent - aborting ongoing generation');
                    currentAbortController.abort();
                    currentAbortController = null;
                }
                return;
            }

            // Client sends transcribed text (STT done on client with noise suppression)
            if (data.type === 'user_speech') {
                const text = (data.text || '').trim();
                if (!text || text.length < 2) return;

                console.log('[User Speech]:', text);

                // Cancel any previous in-flight generation
                if (currentAbortController) {
                    currentAbortController.abort();
                }
                currentAbortController = new AbortController();
                const signal = currentAbortController.signal;

                conversationHistory.push({ role: 'user', content: text });

                // Keep history compact for fast context and low token latency
                if (conversationHistory.length > 20) {
                    conversationHistory = conversationHistory.slice(conversationHistory.length - 20);
                }

                // Stream LLM response
                const llmStream = getLLMStream(conversationHistory, signal);
                let assistantResponse = "";

                for await (const sentence of llmStream) {
                    if (signal.aborted || ws.readyState !== ws.OPEN) {
                        break;
                    }

                    console.log('[Agent sentence]:', sentence);
                    assistantResponse += sentence + " ";

                    // Generate audio for this sentence with natural voice
                    const audioBuffer = await generateTTSBuffer(sentence, data.voice);
                    if (audioBuffer && ws.readyState === ws.OPEN && !signal.aborted) {
                        ws.send(audioBuffer);
                    }
                }

                if (!signal.aborted && ws.readyState === ws.OPEN) {
                    const fullReply = assistantResponse.trim();
                    if (fullReply) {
                        conversationHistory.push({ role: 'assistant', content: fullReply });
                    }
                    // Signal that agent response audio chunks are done
                    ws.send(JSON.stringify({ type: 'agent_response_end', text: fullReply }));
                }
            }
        } catch (error) {
            console.error('[WebSocket] Message handling error:', error?.message || error);
        }
    });

    ws.on('close', () => {
        if (currentAbortController) {
            currentAbortController.abort();
        }
        console.log('[WebSocket] Client disconnected');
    });

    ws.on('error', (err) => {
        console.error('[WebSocket] Socket error:', err?.message || err);
    });
});

server.listen(config.PORT, () => {
    console.log(`====================================================`);
    console.log(`Real-Time Voice Agent running at http://localhost:${config.PORT}`);
    console.log(`WebSocket server active on ws://localhost:${config.PORT}`);
    console.log(`====================================================`);
});
