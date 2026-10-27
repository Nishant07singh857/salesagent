import { MsEdgeTTS, OUTPUT_FORMAT } from 'msedge-tts';
import { config } from '../config/env.js';

/**
 * Clean text for natural speech output:
 * - Strip markdown formatting (**bold**, *italics*, # headers, backticks)
 * - Strip emojis and special characters that TTS might read aloud
 * - Normalize multiple spaces and punctuation
 */
export function cleanTextForSpeech(raw) {
    if (!raw) return '';
    return raw
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/#+\s*/g, '')
        .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Detect language script to select matching high-quality voice
 */
function selectVoice(text, requestedVoice) {
    if (requestedVoice) return requestedVoice;
    // If text contains Devanagari characters, use Swara (Hindi)
    if (/[\u0900-\u097F]/.test(text)) {
        return 'hi-IN-SwaraNeural';
    }
    return config.TTS_VOICE || 'en-US-JennyNeural';
}

/**
 * Generate audio buffer using Microsoft Edge TTS with automatic retry and error protection
 */
export async function generateTTSBuffer(text, targetVoice = null) {
    const cleaned = cleanTextForSpeech(text);
    if (!cleaned) return null;

    const voice = selectVoice(cleaned, targetVoice);

    try {
        const tts = new MsEdgeTTS();
        // Always pass empty object `{}` as 3rd param to prevent voiceLocale undefined error in msedge-tts
        await tts.setMetadata(voice, OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3, {});
        
        const result = await tts.toStream(cleaned);
        const stream = result.audioStream;

        return await new Promise((resolve, reject) => {
            const chunks = [];
            let finished = false;

            const onDone = () => {
                if (!finished) {
                    finished = true;
                    resolve(Buffer.concat(chunks));
                }
            };

            stream.on('data', (chunk) => chunks.push(chunk));
            stream.on('end', onDone);
            stream.on('close', onDone);
            stream.on('error', (err) => {
                if (!finished) {
                    finished = true;
                    reject(err);
                }
            });
        });
    } catch (error) {
        console.error(`[TTS Service] Error generating audio for "${cleaned.slice(0, 30)}...":`, error?.message || error);
        return null;
    }
}
