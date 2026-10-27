const talkBtn = document.getElementById('talkBtn');
const statusDiv = document.getElementById('status');
const chatLog = document.getElementById('chatLog');

let ws = null;
let isCallActive = false;
let recognition = null;
let audioQueue = [];
let isPlaying = false;
let currentSource = null;
let micMediaStream = null;
let audioContext = null;

// Ensure AudioContext is initialized
function getAudioContext() {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
    return audioContext;
}

// Connect WebSocket with auto-reconnect
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}`);

    ws.onopen = () => {
        console.log('[WebSocket] Connected');
        if (!isCallActive) {
            statusDiv.innerText = "Connected to Server. Ready to call.";
        }
    };

    ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
            // Received audio chunk (Edge TTS MP3)
            const arrayBuffer = await event.data.arrayBuffer();
            audioQueue.push(arrayBuffer);
            playNextAudio();
        } else {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'agent_response_end') {
                    if (isCallActive) {
                        statusDiv.innerText = "Agent finished. Listening to you...";
                    }
                    if (data.text) {
                        appendLog("Agent", data.text);
                    }
                }
            } catch (e) {
                console.error('[WebSocket] Failed to parse message:', e);
            }
        }
    };

    ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        statusDiv.innerText = "Disconnected. Reconnecting...";
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error('[WebSocket] Error:', err);
    };
}

// Stop currently playing audio immediately (barge-in support)
function stopCurrentAudio() {
    if (currentSource) {
        try {
            currentSource.onended = null;
            currentSource.stop(0);
            currentSource.disconnect();
        } catch (e) {}
        currentSource = null;
    }
    audioQueue = [];
    isPlaying = false;
}

// Play audio chunks sequentially
async function playNextAudio() {
    if (isPlaying || audioQueue.length === 0) return;
    isPlaying = true;

    const ctx = getAudioContext();
    const arrayBuffer = audioQueue.shift();

    try {
        const audioBuffer = await ctx.decodeAudioData(arrayBuffer.slice(0));
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);

        currentSource = source;

        source.onended = () => {
            currentSource = null;
            isPlaying = false;
            playNextAudio();
        };

        source.start(0);
    } catch (e) {
        console.error("[Audio] Playback decode error:", e);
        currentSource = null;
        isPlaying = false;
        playNextAudio();
    }
}

// Initialize Speech Recognition with Hardware DSP & Ambient Noise Filters
async function startAudioSession() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Your browser does not support Speech Recognition. Please use Google Chrome or Microsoft Edge.");
        return false;
    }

    try {
        // Activate WebRTC MediaStream with DSP: Hardware Echo Cancellation & Noise Suppression
        micMediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
            }
        });
        console.log('[Audio] Hardware Noise Suppression and Echo Cancellation active');
    } catch (err) {
        console.warn('[Audio] getUserMedia DSP activation notice:', err.message);
    }

    recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    // 'en-IN' handles Indian English, Hinglish, and English accents with high fidelity
    recognition.lang = 'en-IN';
    recognition.maxAlternatives = 1;

    let finalTranscript = '';

    recognition.onspeechstart = () => {
        // Instant barge-in: If user starts speaking while agent is talking, cut off agent audio immediately
        if (isPlaying || audioQueue.length > 0) {
            console.log('[Barge-In] User spoke while agent was talking - cutting agent audio');
            stopCurrentAudio();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'user_interrupt' }));
            }
        }
    };

    recognition.onresult = (event) => {
        let interim = '';

        for (let i = event.resultIndex; i < event.results.length; ++i) {
            const result = event.results[i];
            const transcript = result[0].transcript.trim();

            // Filter out low-confidence hallucinations and background whispers
            if (result[0].confidence !== undefined && result[0].confidence > 0 && result[0].confidence < 0.35) {
                continue;
            }

            if (result.isFinal) {
                finalTranscript = transcript;
            } else {
                interim += transcript;
            }
        }

        // Interrupt agent audio if intermediate speech detected
        if ((interim.length > 3 || finalTranscript.length > 2) && (isPlaying || audioQueue.length > 0)) {
            stopCurrentAudio();
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'user_interrupt' }));
            }
        }

        if (finalTranscript.length > 1) {
            const spokenText = finalTranscript;
            finalTranscript = '';

            // Filter out common ambient noise artifacts / breath sounds
            const cleaned = spokenText.replace(/^(ah|um|uh|hmm|shh|psst)\b/gi, '').trim();
            if (cleaned.length < 2) return;

            appendLog("You", cleaned);
            statusDiv.innerText = "Thinking...";

            // Send clean speech to backend
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'user_speech',
                    text: cleaned
                }));
            }
        }
    };

    recognition.onerror = (event) => {
        if (event.error === 'no-speech') {
            // Normal silence pause, keep listening
            return;
        }
        console.warn("[Speech] Recognition notice:", event.error);
        if (event.error === 'not-allowed') {
            statusDiv.innerText = "Microphone permission denied.";
            endCall();
        }
    };

    recognition.onend = () => {
        // Automatically keep alive if call is still active
        if (isCallActive) {
            try {
                recognition.start();
            } catch (e) {}
        }
    };

    try {
        recognition.start();
        return true;
    } catch (e) {
        console.error("[Speech] Start error:", e);
        return false;
    }
}

function startCall() {
    getAudioContext();
    isCallActive = true;
    talkBtn.innerText = "End Call";
    talkBtn.classList.add('listening');
    statusDiv.innerText = "Listening... Speak naturally.";

    startAudioSession();
}

function endCall() {
    isCallActive = false;
    talkBtn.innerText = "Start Call";
    talkBtn.classList.remove('listening');
    statusDiv.innerText = "Call ended.";

    stopCurrentAudio();

    if (recognition) {
        try {
            recognition.stop();
        } catch (e) {}
        recognition = null;
    }

    if (micMediaStream) {
        micMediaStream.getTracks().forEach(track => track.stop());
        micMediaStream = null;
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'user_interrupt' }));
    }
}

function appendLog(sender, text) {
    if (!text) return;
    chatLog.style.display = 'block';
    const div = document.createElement('div');
    div.innerHTML = `<span class="${sender === 'You' ? 'user-txt' : 'agent-txt'}">${sender}:</span> ${text}`;
    div.style.marginBottom = "8px";
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
}

talkBtn.addEventListener('click', () => {
    if (isCallActive) {
        endCall();
    } else {
        startCall();
    }
});

// Start connection on load
connectWebSocket();
