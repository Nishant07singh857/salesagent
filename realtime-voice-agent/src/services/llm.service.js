import { Groq } from 'groq-sdk';
import { config } from '../config/env.js';
import { cleanTextForSpeech } from './tts.service.js';

let groq = null;
try {
    if (config.GROQ_API_KEY && config.GROQ_API_KEY !== 'your_groq_api_key_here') {
        groq = new Groq({ apiKey: config.GROQ_API_KEY });
    }
} catch (e) {
    console.error('[LLM Service] Failed to initialize Groq SDK:', e.message);
}

/**
 * Clean chunk text to remove reasoning tokens or formatting
 */
function cleanChunk(text) {
    if (!text) return '';
    return text
        .replace(/<think>[\s\S]*?<\/think>/gi, '')
        .replace(/<thought>[\s\S]*?<\/thought>/gi, '')
        .replace(/\*\*/g, '')
        .replace(/[*#_~]/g, '');
}

/**
 * Stream LLM completions chunk by chunk, splitting on sentence boundaries.
 * Supports cancellation via abortSignal.
 */
export async function* getLLMStream(messages, abortSignal = null) {
    if (!groq) {
        yield "API key is missing. Please set GROQ_API_KEY in the environment variables.";
        return;
    }

    const candidateModels = [
        config.GROQ_MODEL || 'qwen/qwen3.8-27b',
        'qwen/qwen3.8-27b',
        'openai/gpt-oss-120b',
        'openai/gpt-oss-20b'
    ];

    let completion = null;
    let selectedModel = candidateModels[0];

    for (const model of candidateModels) {
        if (abortSignal?.aborted) return;
        try {
            const reqOptions = (abortSignal && abortSignal instanceof AbortSignal) ? { signal: abortSignal } : undefined;
            const maxTokens = model.includes('gpt-oss') ? 300 : 150;
            completion = await groq.chat.completions.create({
                messages: [
                    { role: "system", content: config.SYSTEM_PROMPT },
                    ...messages
                ],
                model: model,
                temperature: 0.6,
                max_tokens: maxTokens,
                stream: true,
            }, reqOptions);
            selectedModel = model;
            break;
        } catch (err) {
            if (abortSignal?.aborted) return;
            console.warn(`[LLM Service] Model ${model} failed, trying next candidate:`, err.message);
        }
    }

    if (!completion) {
        yield "I'm having trouble connecting to my brain right now.";
        return;
    }

    try {
        let currentSentence = "";
        for await (const chunk of completion) {
            if (abortSignal?.aborted) {
                console.log('[LLM Service] Stream aborted by client barge-in');
                return;
            }

            const delta = chunk.choices[0]?.delta?.content || "";
            if (!delta) continue;

            currentSentence += delta;

            // Stream chunk-by-chunk based on natural pauses (. ! ? । \n)
            if (/[.!?।\n]/.test(delta)) {
                const cleaned = cleanTextForSpeech(cleanChunk(currentSentence));
                if (cleaned.length > 0) {
                    yield cleaned;
                }
                currentSentence = "";
            }
        }

        // Yield remaining buffer if any
        if (currentSentence.trim()) {
            const cleaned = cleanTextForSpeech(cleanChunk(currentSentence));
            if (cleaned.length > 0) {
                yield cleaned;
            }
        }
    } catch (error) {
        if (abortSignal?.aborted) return;
        console.error("[LLM Service] Streaming Error:", error?.message || error);
        yield "I'm having a brief connection hitch, could you repeat that?";
    }
}
