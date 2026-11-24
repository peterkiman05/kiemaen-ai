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
    @Volatile private var conversationActive = false
    @Volatile private var expectingFollowUp = false
    @Volatile private var usingOnDeviceRecognition = false
    @Volatile private var recognitionFallbackAttempted = false
    @Volatile private var commandPollInFlight = false
    private val commandPollRunnable = object : Runnable {
        override fun run() {
            pollDeviceCommands()
            mainHandler.postDelayed(this, COMMAND_POLL_INTERVAL_MS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        createChannel()
        tts = TextToSpeech(this, this)
        tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {
                mainHandler.post { updateNotification("Kiemaen is speaking…") }
            }
            override fun onDone(utteranceId: String?) {
                mainHandler.post {
                    if (busy) finishReplyAndResume()
                    else updateNotification("Speech output test completed.")
                }
            }
            @Deprecated("Deprecated by Android")
            override fun onError(utteranceId: String?) {
                mainHandler.post {
                    updateNotification("Speech output failed. Check Android Text-to-speech settings.")
                    if (busy) finishReplyAndResume()
                }
            }
            override fun onError(utteranceId: String?, errorCode: Int) {
                mainHandler.post {
                    updateNotification("Speech output failed (error $errorCode). Check Android Text-to-speech settings.")
                    if (busy) finishReplyAndResume()
                }
            }
            override fun onStop(utteranceId: String?, interrupted: Boolean) {
                mainHandler.post { if (busy) finishReplyAndResume() }
            }
        })
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_TEST_TTS) {
            startForeground(NOTIFICATION_ID, notification("Testing speech output…"))
            speakAndResume("Kiemaen voice output is working.")
            return START_NOT_STICKY
        }
        if (intent?.action == ACTION_STOP) {
            stopListening()
            stopSelf()
            return START_NOT_STICKY
        }
        startForeground(NOTIFICATION_ID, notification("Preparing local wake-word engine"))
        startWakeEngine()
        mainHandler.removeCallbacks(commandPollRunnable)
        mainHandler.post(commandPollRunnable)
        return START_STICKY
    }

    private fun pollDeviceCommands() {
        val commandToken = DeviceTokenStore.commandToken(this) ?: return
        if (commandPollInFlight) return
        commandPollInFlight = true
        networkExecutor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("$BASE_URL/device/commands/next").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 8000
                connection.readTimeout = 10000
                connection.setRequestProperty("Authorization", "Bearer $commandToken")
                val code = connection.responseCode
                val stream = if (code in 200..299) connection.inputStream else connection.errorStream
                val json = JSONObject(stream?.bufferedReader()?.use { it.readText() }.orEmpty())
                if (code in 200..299 && json.optString("status") == "ok" && !json.isNull("command")) {
                    val command = json.optJSONObject("command")
                    if (command != null) mainHandler.post { executeDeviceCommand(command, commandToken) }
                } else if (code == 401) {
                    mainHandler.post { updateNotification("Kiemaen device access was revoked. Pair this phone again.") }
                }
            } catch (_: Exception) {
                // A temporary network failure is retried on the next polling interval.
            } finally {
                connection?.disconnect()
                commandPollInFlight = false
            }
        }
    }

    private fun executeDeviceCommand(command: JSONObject, commandToken: String) {
        val commandId = command.optString("command_id")
        val action = command.optString("action")
        val payload = command.optJSONObject("payload") ?: JSONObject()
        var success = false
        var detail = "Unsupported command."
        try {
            when (action) {
                "set_alarm" -> {
                    val hour = payload.getInt("hour")
                    val minute = payload.getInt("minute")
                    require(hour in 0..23 && minute in 0..59) { "Invalid alarm time." }
                    val alarmIntent = Intent(android.provider.AlarmClock.ACTION_SET_ALARM).apply {
                        putExtra(android.provider.AlarmClock.EXTRA_HOUR, hour)
                        putExtra(android.provider.AlarmClock.EXTRA_MINUTES, minute)
                        putExtra(android.provider.AlarmClock.EXTRA_MESSAGE, payload.optString("label", "Kiemaen alarm"))
                        putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, true)
                        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    }
                    startActivity(alarmIntent)
                    success = true
                    detail = "Alarm request handed to Android Clock for %02d:%02d.".format(hour, minute)
                }
                "open_app" -> {
                    val requested = payload.optString("app_name").trim()
                    require(requested.isNotBlank() && requested.length <= 60) { "Invalid app name." }
                    val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
                    val matches = packageManager.queryIntentActivities(launcher, 0)
                    val match = matches.firstOrNull {
                        it.loadLabel(packageManager).toString().equals(requested, ignoreCase = true)
                    } ?: matches.firstOrNull {
                        it.loadLabel(packageManager).toString().contains(requested, ignoreCase = true)
                    }
                    val resolved = match
                        ?: throw IllegalStateException("I couldn't find an installed app named " + requested + ".")
                    val packageName = resolved.activityInfo.packageName
                    val launch = packageManager.getLaunchIntentForPackage(packageName)
                        ?: throw IllegalStateException("Android does not provide a launcher for " + requested + ".")
                    launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(launch)
                    success = true
                    detail = "Opened " + resolved.loadLabel(packageManager) + "."
                }
            }
        } catch (e: Exception) {
            detail = e.message ?: "Android could not complete the command."
        }
        updateNotification(if (success) detail else "Phone command failed: $detail")
        reportDeviceCommand(commandToken, commandId, if (success) "completed" else "failed", detail)
    }

    private fun reportDeviceCommand(token: String, commandId: String, status: String, detail: String) {
        networkExecutor.execute {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("$BASE_URL/device/commands/result").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 8000
                connection.readTimeout = 10000
                connection.doOutput = true
                connection.setRequestProperty("Authorization", "Bearer $token")
                connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
                val body = "command_id=" + java.net.URLEncoder.encode(commandId, "UTF-8") +
                    "&result_status=" + java.net.URLEncoder.encode(status, "UTF-8") +
                    "&result=" + java.net.URLEncoder.encode(detail, "UTF-8")
                connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                connection.responseCode
            } catch (_: Exception) {
                // Result reporting is best-effort; commands are one-shot and are not replayed.
            } finally {
                connection?.disconnect()
            }
        }
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
        conversationActive = true
        expectingFollowUp = false
        recognitionFallbackAttempted = false
        busy = true
        updateNotification("Kiemaen activated — speak your request")
        beginSpeechRecognition()
    }

    private fun beginSpeechRecognition(forceSystemRecognizer: Boolean = false) {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            expectingFollowUp = false
            speakAndResume("Speech recognition is unavailable on this phone. Check its speech services.")
            return
        }
        try {
            speech?.destroy()
            usingOnDeviceRecognition = false
            speech = if (
                !forceSystemRecognizer &&
                Build.VERSION.SDK_INT >= 31 &&
                SpeechRecognizer.isOnDeviceRecognitionAvailable(this)
            ) {
                usingOnDeviceRecognition = true
                SpeechRecognizer.createOnDeviceSpeechRecognizer(applicationContext)
            } else {
                SpeechRecognizer.createSpeechRecognizer(applicationContext)
            }
            speech?.setRecognitionListener(object : RecognitionListener {
                override fun onReadyForSpeech(params: android.os.Bundle?) {
                    updateNotification("Speak now — Kiemaen is listening")
                }
                override fun onBeginningOfSpeech() {}
                override fun onRmsChanged(rmsdB: Float) {}
                override fun onBufferReceived(buffer: ByteArray?) {}
                override fun onEndOfSpeech() { updateNotification("Processing your request…") }
                override fun onError(error: Int) {
                    if (
                        usingOnDeviceRecognition &&
                        !recognitionFallbackAttempted &&
                        error != SpeechRecognizer.ERROR_NO_MATCH &&
                        error != SpeechRecognizer.ERROR_SPEECH_TIMEOUT
                    ) {
                        recognitionFallbackAttempted = true
                        speech?.destroy()
                        speech = null
                        updateNotification("Trying the phone's standard speech service…")
                        beginSpeechRecognition(forceSystemRecognizer = true)
                        return
                    }
                    if (expectingFollowUp) {
                        endConversationAndResumeWake()
                    } else {
                        conversationActive = false
                        expectingFollowUp = false
                        speakAndResume(recognitionErrorMessage(error))
                    }
                }
                override fun onResults(results: android.os.Bundle?) {
                    val spoken = results
                        ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                        ?.firstOrNull()
                        .orEmpty()
                    if (spoken.isBlank()) {
                        if (expectingFollowUp) endConversationAndResumeWake()
                        else {
                            conversationActive = false
                            speakAndResume("I didn't catch that. Please try again.")
                        }
                    } else {
                        recognitionFallbackAttempted = false
                        if (isEndConversationCommand(spoken)) {
                            conversationActive = false
                            expectingFollowUp = false
                            speakAndResume("Okay. I'll stop this conversation and wait for Hey Kiemaen.")
                        } else {
                            expectingFollowUp = true
                            sendToKiemaen(spoken)
                        }
                    }
                }
                override fun onPartialResults(partialResults: android.os.Bundle?) {}
                override fun onEvent(eventType: Int, params: android.os.Bundle?) {}
            })

            val request = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, usingOnDeviceRecognition)
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
            val clean = prepareSpokenReply(
                reply.replace(Regex("\\[ALARM:\\d{2}:\\d{2}\\]", RegexOption.IGNORE_CASE), " ")
            ).take(1800)
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
                                // The user explicitly requested this alarm in the conversation.
                                // Ask Android's Clock app to create it directly rather than
                                // presenting a second confirmation screen.
                                putExtra(android.provider.AlarmClock.EXTRA_SKIP_UI, true)
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            }
                            startActivity(alarmIntent)
                            speakAndResume("$clean. Your alarm for %02d:%02d has been sent to your Clock app.".format(hour, minute))
                        } catch (_: Exception) {
                            speakAndResume("$clean. Android could not create the alarm. Check that a Clock app is installed and supports direct alarm creation.")
                        }
                    } else speakAndResume(clean)
                } else speakAndResume(clean)
            }
        }
    }

    private fun prepareSpokenReply(source: String): String {
        return source
            .replace(Regex("(?s)```.*?```"), "I've included code in the chat.")
            .replace(Regex("!\\[([^\\]]*)\\]\\([^)]+\\)"), "$1")
            .replace(Regex("\\[([^\\]]+)\\]\\(https?://[^)]+\\)"), "$1")
            .replace(Regex("https?://\\S+"), "")
            .replace(Regex("(?m)^\\s{0,3}#{1,6}\\s*"), "")
            .replace(Regex("(?m)^\\s*[-*+]\\s+"), "")
            .replace(Regex("[*_~#>]"), " ")
            .replace(Regex("\\$\\$[\\s\\S]+?\\$\\$"), " mathematical expression ")
            .replace(Regex("\\$[^$]+\\$"), " mathematical expression ")
            .replace("\\", " ")
            .replace(Regex("\\s+"), " ")
            .trim()
    }

    private fun recognitionErrorMessage(error: Int): String = when (error) {
        SpeechRecognizer.ERROR_AUDIO -> "I couldn't access the microphone. Check microphone access and try again."
        SpeechRecognizer.ERROR_CLIENT -> "The speech service stopped unexpectedly. Please try again."
        SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS -> "Microphone permission is missing. Enable it in Android settings."
        SpeechRecognizer.ERROR_NETWORK, SpeechRecognizer.ERROR_NETWORK_TIMEOUT ->
            "The phone's speech service needs a network connection. Please check your connection."
        SpeechRecognizer.ERROR_RECOGNIZER_BUSY -> "The phone's speech service is busy. Please try again."
        SpeechRecognizer.ERROR_SERVER -> "The phone's speech service returned an error. Please try again."
        SpeechRecognizer.ERROR_NO_MATCH, SpeechRecognizer.ERROR_SPEECH_TIMEOUT ->
            "I didn't catch that. Say Hey Kiemaen when you're ready to try again."
        else -> "Speech recognition failed (error $error). Check the phone's speech services."
    }

    private fun isEndConversationCommand(spoken: String): Boolean {
        val command = spoken.trim().lowercase(Locale.ROOT)
            .replace(Regex("[^a-z0-9 ]"), " ")
            .replace(Regex("\\s+"), " ")
        return command in setOf(
            "stop listening", "stop listening kiemaen", "end conversation",
            "end this conversation", "goodbye kiemaen", "bye kiemaen",
            "that's all kiemaen", "thats all kiemaen"
        )
    }

    private fun endConversationAndResumeWake() {
        conversationActive = false
        expectingFollowUp = false
        busy = false
        speech?.cancel()
        speech?.destroy()
        speech = null
        updateNotification("Conversation ended. Listening locally for Hey Kiemaen.")
        mainHandler.postDelayed({
            if (!busy && !listening) startWakeEngine()
        }, 500L)
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
            if (conversationActive && expectingFollowUp && !busy && !listening) {
                busy = true
                updateNotification("Listening for your next request…")
                beginSpeechRecognition()
            } else if (!busy && !listening) {
                conversationActive = false
                expectingFollowUp = false
                startWakeEngine()
            }
        }, 600L)
    }

    override fun onInit(status: Int) {
        ttsReady = status == TextToSpeech.SUCCESS
        if (ttsReady) {
            val preferredLocales = listOf(
                Locale.getDefault(),
                Locale("en", "ZA"),
                Locale.UK,
                Locale.US
            ).distinct()
            val selectedLocale = preferredLocales.firstOrNull { locale ->
                val availability = tts?.isLanguageAvailable(locale) ?: TextToSpeech.LANG_NOT_SUPPORTED
                availability != TextToSpeech.LANG_MISSING_DATA &&
                    availability != TextToSpeech.LANG_NOT_SUPPORTED
            }
            val languageResult = selectedLocale?.let { tts?.setLanguage(it) }
                ?: TextToSpeech.LANG_NOT_SUPPORTED
            if (
                selectedLocale == null ||
                languageResult == TextToSpeech.LANG_NOT_SUPPORTED ||
                languageResult == TextToSpeech.LANG_MISSING_DATA
            ) {
                ttsReady = false
                pendingSpeech = null
                conversationActive = false
                expectingFollowUp = false
                updateNotification("No supported speech voice is installed. Install an English voice in Android Text-to-speech settings.")
                if (busy) finishReplyAndResume()
                return
            }
            val queued = pendingSpeech
            if (!queued.isNullOrBlank()) {
                pendingSpeech = null
                mainHandler.post { speakAndResume(queued) }
            }
        } else {
            pendingSpeech = null
            conversationActive = false
            expectingFollowUp = false
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
        mainHandler.removeCallbacks(commandPollRunnable)
        listening = false
        busy = false
        conversationActive = false
        expectingFollowUp = false
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
        const val ACTION_TEST_TTS = "ai.kiemaen.voice.TEST_TTS"
        private const val BASE_URL = "https://kiemaen-ai.onrender.com"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_ID = "kiemaen_voice"
        private const val NOTIFICATION_ID = 712
        private const val UTTERANCE_ID = "kiemaen_reply"
        private const val COMMAND_POLL_INTERVAL_MS = 10000L
    }
}
