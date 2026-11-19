package ai.kiemaen.voice

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import androidx.core.app.NotificationCompat
import ai.picovoice.porcupine.Porcupine
import ai.picovoice.porcupine.PorcupineException
import ai.picovoice.porcupine.PorcupineManager
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.Locale
import java.util.concurrent.Executors

class WakeWordService : Service(), TextToSpeech.OnInitListener {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val network = Executors.newSingleThreadExecutor()
    private var porcupine: PorcupineManager? = null
    private var speech: SpeechRecognizer? = null
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var busy = false
    private var restarting = false

    override fun onCreate() {
        super.onCreate()
        createChannel()
        tts = TextToSpeech(this, this)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopListening()
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, notification("Waiting for wake phrase"))
        startWakeEngine()
        return START_STICKY
    }

    private fun startWakeEngine() {
        if (porcupine != null || busy) return
        val key = getSharedPreferences("voice_settings", MODE_PRIVATE).getString("access_key", "").orEmpty()
        if (key.isBlank()) {
            updateNotification("Open Kiemaen Voice and add your AccessKey")
            stopSelf()
            return
        }
        try {
            val custom = java.io.File(filesDir, "kiemaen.ppn")
            val builder = PorcupineManager.Builder().setAccessKey(key).setSensitivity(0.58f)
            if (custom.exists() && custom.length() > 0) builder.setKeywordPath(custom.absolutePath)
            else builder.setKeyword(Porcupine.BuiltInKeyword.COMPUTER)
            porcupine = builder.build(this) { mainHandler.post { onWakeWordDetected() } }
            porcupine?.start()
            updateNotification(if (custom.exists()) "Listening for custom Kiemaen phrase" else "Listening for Computer; import your custom phrase")
        } catch (e: PorcupineException) {
            updateNotification("Wake-word setup error: " + (e.message ?: "check AccessKey"))
            stopSelf()
        } catch (e: Exception) {
            updateNotification("Could not start microphone: " + (e.message ?: "unknown error"))
            stopSelf()
        }
    }

    private fun onWakeWordDetected() {
        if (busy) return
        busy = true
        updateNotification("Kiemaen activated • speak now")
        try { porcupine?.stop() } catch (_: Exception) {}
        porcupine?.delete()
        porcupine = null
        beginSpeechRecognition()
    }

    private fun beginSpeechRecognition() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            speakAndResume("Speech recognition is unavailable. Check your phone's speech services.")
            return
        }
        mainHandler.post {
            try {
                speech?.destroy()
                speech = SpeechRecognizer.createSpeechRecognizer(applicationContext)
                speech?.setRecognitionListener(object : RecognitionListener {
                    override fun onReadyForSpeech(params: android.os.Bundle?) { updateNotification("Speak now • Kiemaen is listening") }
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() { updateNotification("Processing your request…") }
                    override fun onError(error: Int) { speakAndResume("I didn't catch that. Say the wake phrase again when ready.") }
                    override fun onResults(results: android.os.Bundle?) {
                        val spoken = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
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
    }

    private fun sendToKiemaen(spoken: String) {
        updateNotification("Sending request securely to Kiemaen…")
        network.execute {
            var reply = "I couldn't reach Kiemaen. Check your internet connection."
            try {
                val connection = URL("https://kiemaen-ai.onrender.com/chat").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 15000
                connection.readTimeout = 60000
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8")
                val body = "prompt=" + URLEncoder.encode(spoken, "UTF-8") + "&mode=auto"
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val response = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
                val json = JSONObject(response)
                reply = if (json.optString("status") == "ok") json.optString("response", "I received your request.") else "Kiemaen returned an error. Please try again."
                connection.disconnect()
            } catch (_: Exception) {}
            val clean = reply.replace(Regex("[*_#]"), " ").replace(Regex("\\s+"), " ").take(1800)
            mainHandler.post { speakAndResume(clean) }
        }
    }

    private fun speakAndResume(message: String) {
        updateNotification("Kiemaen is responding…")
        if (!ttsReady || tts == null) {
            updateNotification(message.take(120))
            busy = false
            scheduleRestart()
            return
        }
        tts?.speak(message, TextToSpeech.QUEUE_FLUSH, null, "kiemaen_reply")
        mainHandler.postDelayed({
            busy = false
            scheduleRestart()
        }, (message.length * 65L).coerceIn(1800L, 18000L))
    }

    private fun scheduleRestart() {
        if (restarting) return
        restarting = true
        mainHandler.postDelayed({
            restarting = false
            if (!busy && porcupine == null) startWakeEngine()
        }, 700L)
    }

    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS
        tts?.language = Locale.getDefault()
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 26) {
            val channel = NotificationChannel(CHANNEL_ID, "Kiemaen voice listening", NotificationManager.IMPORTANCE_LOW)
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun notification(message: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, WakeWordService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
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
        try { porcupine?.stop() } catch (_: Exception) {}
        porcupine?.delete()
        porcupine = null
        speech?.cancel()
        speech?.destroy()
        speech = null
        tts?.stop()
        busy = false
        stopForeground(STOP_FOREGROUND_REMOVE)
    }

    override fun onDestroy() {
        stopListening()
        tts?.shutdown()
        network.shutdownNow()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "ai.kiemaen.voice.START"
        const val ACTION_STOP = "ai.kiemaen.voice.STOP"
        private const val CHANNEL_ID = "kiemaen_voice"
        private const val NOTIFICATION_ID = 712
    }
}
