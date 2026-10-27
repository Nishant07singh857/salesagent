package com.example.voiceagentbridge

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.telecom.Call
import android.telecom.InCallService
import android.util.Log

class VoiceAgentCallService : InCallService() {

    private lateinit var webSocketManager: WebSocketManager
    private lateinit var speechRecognizer: SpeechRecognizer
    private lateinit var audioManager: AudioManager

    override fun onCreate() {
        super.onCreate()
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        // Important: Change IP to your laptop's Local IP address (e.g., 192.168.1.5)
        webSocketManager = WebSocketManager("ws://192.168.1.X:3000") 
        webSocketManager.connect()
        setupSpeechRecognizer()
    }

    override fun onCallAdded(call: Call) {
        super.onCallAdded(call)
        Log.d("VoiceAgent", "Incoming Call Intercepted!")
        
        // Auto-answer the call
        call.answer(0)
        
        // Hack for Android Security: Injecting directly into uplink is blocked without root.
        // We route audio through the speakerphone so the mic picks it up naturally and sends it to the caller.
        audioManager.isSpeakerphoneOn = true
        
        // Start listening to the caller
        startListening()
    }

    override fun onCallRemoved(call: Call) {
        super.onCallRemoved(call)
        Log.d("VoiceAgent", "Call Ended.")
        webSocketManager.disconnect()
        speechRecognizer.destroy()
    }

    private fun setupSpeechRecognizer() {
        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this)
        speechRecognizer.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle) {
                val matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if (!matches.isNullOrEmpty()) {
                    val text = matches[0]
                    Log.d("VoiceAgent", "Caller Said: $text")
                    // Send text to Node.js backend
                    webSocketManager.sendSpeechText(text)
                }
                // Keep listening
                startListening()
            }
            override fun onError(error: Int) {
                startListening()
            }
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
    }

    private fun startListening() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-IN") // Change to hi-IN for Hindi
        }
        speechRecognizer.startListening(intent)
    }
}
