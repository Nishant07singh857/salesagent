package com.example.voiceagentbridge

import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.util.Log

class WebSocketManager(private val serverUrl: String) {
    private val client = OkHttpClient()
    private var webSocket: WebSocket? = null
    
    // AudioTrack for playing AI response audio
    private var audioTrack: AudioTrack? = null

    init {
        val bufferSize = AudioTrack.getMinBufferSize(
            24000, // EdgeTTS default sample rate
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        // Stream type VOICE_CALL helps play it into the active call on some devices
        audioTrack = AudioTrack(
            AudioManager.STREAM_VOICE_CALL,
            24000,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
            AudioTrack.MODE_STREAM
        )
        audioTrack?.play()
    }

    fun connect() {
        val request = Request.Builder().url(serverUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.d("VoiceAgent", "Connected to AI Server!")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d("VoiceAgent", "Message from Server: $text")
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Received binary audio chunk from Node.js (TTS)
                val pcmData = bytes.toByteArray()
                audioTrack?.write(pcmData, 0, pcmData.size)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e("VoiceAgent", "Connection Failed: ${t.message}")
            }
        })
    }

    fun sendSpeechText(text: String) {
        val json = JSONObject()
        json.put("type", "user_speech")
        json.put("text", text)
        webSocket?.send(json.toString())
    }

    fun disconnect() {
        webSocket?.close(1000, "Call Ended")
        audioTrack?.stop()
        audioTrack?.release()
    }
}
