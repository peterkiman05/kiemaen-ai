package ai.kiemaen.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.webkit.CookieManager
import androidx.core.app.NotificationCompat
import com.k2fsa.sherpa.onnx.FeatureConfig
import com.k2fsa.sherpa.onnx.KeywordSpotter
import com.k2fsa.sherpa.onnx.KeywordSpotterConfig
import com.k2fsa.sherpa.onnx.OnlineModelConfig
import com.k2fsa.sherpa.onnx.OnlineTransducerModelConfig
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.Executors

class WakeWordService : Service(), TextToSpeech.OnInitListener {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val engineExecutor = Executors.newSingleThreadExecutor()
    private val networkExecutor = Executors.newSingleThreadExecutor()

    @Volatile private var listening = false
    @Volatile private var busy = false
    @Volatile private var audioRecord: AudioRecord? = null

    private var spotter: KeywordSpotter? = null
    private var speech: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    @Volatile private var pendingSpeech: String? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        tts = TextToSpeech(this, this)
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {
                mainHandler.post { finishReplyAndResume() }
            }
            @Deprecated("Deprecated by Android")
            override fun onError(utteranceId: String?) {
                mainHandler.post { finishReplyAndResume() }
            }
            override fun onError(utteranceId: String?, errorCode: Int) {
                mainHandler.post { finishReplyAndResume() }
            }
        })
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopListening()
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, notification("Preparing local wake-word engine"))
        startWakeEngine()
        return START_STICKY
    }

    private fun startWakeEngine() {
        if (listening || busy) return
        listening = true
        updateNotification("Loading local Hey Kiemaen detector…")

        engineExecutor.execute {
            try {
                if (spotter == null) spotter = createSpotter()
                runKeywordLoop()
            } catch (e: Exception) {
                listening = false
                mainHandler.post {
                    updateNotification("Wake-word engine error: " + (e.message ?: "unknown error"))
                }
            }
        }
    }

    private fun createSpotter(): KeywordSpotter {
        val modelDir = "sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01-mobile"
        val model = OnlineModelConfig(
            transducer = OnlineTransducerModelConfig(
                encoder = "$modelDir/encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx",
                decoder = "$modelDir/decoder-epoch-12-avg-2-chunk-16-left-64.onnx",
                joiner = "$modelDir/joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx"
            ),
            tokens = "$modelDir/tokens.txt",
            numThreads = 2,
            provider = "cpu",
            modelType = "zipformer2",
            modelingUnit = "bpe",
            bpeVocab = "$modelDir/bpe.model"
        )
        val config = KeywordSpotterConfig(
            featConfig = FeatureConfig(sampleRate = SAMPLE_RATE, featureDim = 80),
            modelConfig = model,
            keywordsFile = "$modelDir/keywords.txt",
            keywordsScore = 3.0f,
            keywordsThreshold = 0.10f
        )
        return KeywordSpotter(assetManager = assets, config = config)
    }

    private fun runKeywordLoop() {
        val detector = spotter ?: throw IllegalStateException("Wake-word model is not loaded")
        val stream = detector.createStream()
        val minimum = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        if (minimum <= 0) {
            stream.release()
            throw IllegalStateException("This device does not support the required microphone format")
        }

        val recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minimum * 2, SAMPLE_RATE / 2)
        )
        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            recorder.release()
            stream.release()
            throw IllegalStateException("Could not initialise the microphone")
        }

        audioRecord = recorder
        var detected = false
        try {
            recorder.startRecording()
            mainHandler.post { updateNotification("Listening locally for Hey Kiemaen") }
            val buffer = ShortArray(1600)
            while (listening) {
                val count = recorder.read(buffer, 0, buffer.size)
                if (count <= 0) continue

                val samples = FloatArray(count) { buffer[it] / 32768.0f }
                stream.acceptWaveform(samples, sampleRate = SAMPLE_RATE)

                while (detector.isReady(stream)) {
                    detector.decode(stream)
                    val result = detector.getResult(stream)
                    if (result.keyword.isNotBlank()) {
                        detector.reset(stream)
                        detected = true
                        listening = false
                        break
                    }
                }
                if (detected) break
            }
        } finally {
            try {
                if (recorder.recordingState == AudioRecord.RECORDSTATE_RECORDING) recorder.stop()
            } catch (_: Exception) {}
            recorder.release()
            audioRecord = null
            stream.release()
        }

        if (detected) mainHandler.post { onWakeWordDetected() }
    }

    private fun onWakeWordDetected() {
        if (busy) return
        busy = true
        updateNotification("Kiemaen activated — speak your request")
        beginSpeechRecognition()
    }

    private fun beginSpeechRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            speakAndResume("Speech recognition is unavailable on this phone. Check its speech services.")
            return
        }
        try {
            speech?.destroy()
            speech = SpeechRecognizer.createSpeechRecognizer(applicationContext)
            speech?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: android.os.Bundle?) {
                    updateNotification("Speak now — Kiemaen is listening")
                }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { updateNotification("Processing your request…") }
                override fun onError(error: Int) {
                    speakAndResume("I didn't catch that. Say Hey Kiemaen again when ready.")
                }
                override fun onResults(results: android.os.Bundle?) {
                    val spoken = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                    if (spoken.isBlank()) speakAndResume("I didn't catch that. Please try again.")
                    else sendToKiemaen(spoken)
                }
                override fun onPartialResults(partialResults: android.os.Bundle?) {}
                override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
            })

            val request = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, false)
            }
            speech?.startListening(request)
        } catch (_: Exception) {
            speakAndResume("Voice recognition could not start. Check your phone's speech services.")
        }
    }

    private fun sendToKiemaen(spoken: String) {
        updateNotification("Sending your request securely to Kiemaen…")
        networkExecutor.execute {
            var reply = "I couldn't reach Kiemaen. Check your internet connection and try again."
            var connection: HttpURLConnection? = null
            try {
                connection = URL("$BASE_URL/chat").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 15000
                connection.readTimeout = 60000
                connection.doOutput = true
                val boundary = "----KiemaenVoice${System.currentTimeMillis()}"
                connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")

                val cookie = CookieManager.getInstance().getCookie(BASE_URL).orEmpty()
                if (cookie.contains("session_token=")) {
                    connection.setRequestProperty("Cookie", cookie)
                }

                val body = buildString {
                    append("--$boundary\r\n")
                    append("Content-Disposition: form-data; name=\"prompt\"\r\n\r\n")
                    append(spoken)
                    append("\r\n--$boundary\r\n")
                    append("Content-Disposition: form-data; name=\"mode\"\r\n\r\n")
                    append("auto")
                    append("\r\n--$boundary\r\n")
                    append("Content-Disposition: form-data; name=\"client\"\r\n\r\n")
                    append("android_voice")
                    append("\r\n--$boundary--\r\n")
                }
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }

                val code = connection.responseCode
                val responseStream = if (code in 200..299) connection.inputStream else connection.errorStream
                val response = responseStream?.bufferedReader()?.use { it.readText() }.orEmpty()
                val json = JSONObject(response)
                reply = if (json.optString("status") == "ok") {
                    json.optString("response").ifBlank { "I received your request." }
                } else {
                    json.optString("message").ifBlank { "Kiemaen returned an error. Please try again." }
                }
            } catch (e: Exception) {
                reply = "I couldn't complete that request: " + (e.message ?: "connection error")
            } finally {
                connection?.disconnect()
            }

            val alarm = Regex("\\[ALARM:(\\d{2}):(\\d{2})\\]", RegexOption.IGNORE_CASE).find(reply)
            val clean = reply
                .replace(Regex("\\[ALARM:\\d{2}:\\d{2}\\]", RegexOption.IGNORE_CASE), " ")
                .replace(Regex("[*_#>]"), " ")
                .replace(Regex("\\s+"), " ")
                .take(1800)
            mainHandler.post {
                if (alarm != null) {
                    val hour = alarm.groupValues[1].toIntOrNull()
                    val minute = alarm.groupValues[2].toIntOrNull()
                    if (hour != null && minute != null && hour in 0..23 && minute in 0..59) {
                        try {
                            val alarmIntent = Intent(android.provider.AlarmClock.ACTION_SET_ALARM).apply {
                                putExtra(android.provider.AlarmClock.EXTRA_HOUR, hour)
                                putExtra(android.provider.AlarmClock.EXTRA_MINUTES, minute)
                                putExtra(android.provider.AlarmClock.EXTRA_MESSAGE, "Kiemaen alarm")
                                putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, false)
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            }
                            startActivity(alarmIntent)
                            speakAndResume("$clean. I've opened your Clock app so you can confirm the alarm.")
                        } catch (_: Exception) {
                            speakAndResume("$clean. I couldn't open the Clock app to set the alarm.")
                        }
                    } else speakAndResume(clean)
                } else speakAndResume(clean)
            }
        }
    }

    private fun speakAndResume(message: String) {
        if (!ttsReady || tts == null) {
            pendingSpeech = message
            updateNotification("Preparing speech output…")
            return
        }
        updateNotification("Kiemaen is speaking…")
        val result = tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, UTTERANCE_ID)
        if (result == TextToSpeech.ERROR) {
            pendingSpeech = null
            updateNotification("Speech output failed. Check Android Text-to-speech settings.")
            finishReplyAndResume()
        }
    }

    private fun finishReplyAndResume() {
        if (!busy) return
        speech?.cancel()
        speech?.destroy()
        speech = null
        busy = false
        mainHandler.postDelayed({
            if (!busy && !listening) startWakeEngine()
        }, 700L)
    }

    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS
        if (ttsReady) {
            var result = tts?.setLanguage(Locale.getDefault()) ?: TextToSpeech.LANG_NOT_SUPPORTED
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                result = tts?.setLanguage(Locale.US) ?: TextToSpeech.LANG_NOT_SUPPORTED
            }
            if (result == TextToSpeech.LANG_MISSING_DATA || result == TextToSpeech.LANG_NOT_SUPPORTED) {
                updateNotification("No supported speech voice is installed on this phone.")
                return
            }
            val queued = pendingSpeech
            if (!queued.isNullOrBlank()) {
                pendingSpeech = null
                mainHandler.post { speakAndResume(queued) }
            }
        } else {
            updateNotification("Android Text-to-speech failed to initialise.")
            if (busy) finishReplyAndResume()
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(CHANNEL_ID, "Kiemaen voice listening", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(message: String): Notification {
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val stop = PendingIntent.getService(
            this, 1, Intent(this, WakeWordService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentTitle("Kiemaen Voice")
            .setContentText(message)
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(android.R.drawable.ic_media_pause, "Stop", stop)
            .build()
    }

    private fun updateNotification(message: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(message))
    }

    private fun stopListening() {
        listening = false
        try {
            audioRecord?.let {
                if (it.recordingState == AudioRecord.RECORDSTATE_RECORDING) it.stop()
            }
        } catch (_: Exception) {}
        speech?.cancel()
        speech?.destroy()
        speech = null
        tts?.stop()
        stopForeground(STOP_FOREGROUND_REMOVE)
    }

    override fun onDestroy() {
        stopListening()
        engineExecutor.shutdownNow()
        networkExecutor.shutdownNow()
        try { spotter?.release() } catch (_: Exception) {}
        spotter = null
        tts?.shutdown()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "ai.kiemaen.voice.START"
        const val ACTION_STOP = "ai.kiemaen.voice.STOP"
        private const val BASE_URL = "https://kiemaen-ai.onrender.com"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_ID = "kiemaen_voice"
        private const val NOTIFICATION_ID = 712
        private const val UTTERANCE_ID = "kiemaen_reply"
    }
}
