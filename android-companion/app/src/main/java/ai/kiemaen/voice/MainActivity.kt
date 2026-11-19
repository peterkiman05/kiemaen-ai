package ai.kiemaen.voice

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.io.File

class MainActivity : Activity() {
    private lateinit var keyInput: EditText
    private lateinit var status: TextView
    private val prefs by lazy { getSharedPreferences("voice_settings", MODE_PRIVATE) }
    private var keywordFile: File? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        keywordFile = File(filesDir, "kiemaen.ppn").takeIf { it.exists() }
        buildScreen()
    }

    private fun buildScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 40, 32, 32)
        }
        root.addView(TextView(this).apply { text = "KIEMAEN VOICE"; textSize = 25f })
        root.addView(TextView(this).apply {
            text = "Local wake-word detection • Internet-powered conversations"
            textSize = 14f
            setPadding(0, 12, 0, 24)
        })
        keyInput = EditText(this).apply {
            hint = "Picovoice AccessKey"
            singleLine = true
            setText(prefs.getString("access_key", ""))
        }
        root.addView(keyInput)
        root.addView(TextView(this).apply {
            text = if (keywordFile != null) "Custom Kiemaen phrase imported" else "Test phrase: Computer"
            textSize = 14f
            setPadding(0, 8, 0, 12)
        })
        root.addView(Button(this).apply {
            text = "Import custom Hey Kiemaen .ppn file"
            setOnClickListener {
                val picker = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                    type = "*/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }
                startActivityForResult(picker, PICK_KEYWORD)
            }
        })
        status = TextView(this).apply {
            text = "Not listening. Save your AccessKey, then start listening."
            textSize = 14f
            setPadding(0, 20, 0, 20)
        }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "SAVE SETTINGS"
            setOnClickListener {
                val key = keyInput.text.toString().trim()
                if (key.isBlank()) toast("Enter your Picovoice AccessKey first.")
                else {
                    prefs.edit().putString("access_key", key).apply()
                    toast("Settings saved on this device.")
                }
            }
        })
        root.addView(Button(this).apply {
            text = "START WAKE-WORD LISTENING"
            setOnClickListener { startListening() }
        })
        root.addView(Button(this).apply {
            text = "STOP LISTENING"
            setOnClickListener {
                stopService(Intent(this, WakeWordService::class.java))
                status.text = "Listening stopped."
            }
        })
        root.addView(TextView(this).apply {
            text = "Privacy: wake-word matching runs locally. After activation, your phone's configured speech-recognition provider transcribes one request. Recognized text is sent to Kiemaen over HTTPS; continuous microphone audio is not uploaded."
            textSize = 12f
            setPadding(0, 24, 0, 0)
        })
        setContentView(root)
    }

    private fun startListening() {
        val key = keyInput.text.toString().trim()
        if (key.isBlank()) {
            toast("Enter and save your Picovoice AccessKey first.")
            return
        }
        prefs.edit().putString("access_key", key).apply()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_MIC)
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
            return
        }
        ContextCompat.startForegroundService(this, Intent(this, WakeWordService::class.java).setAction(WakeWordService.ACTION_START))
        status.text = "Starting wake-word engine. Keep its notification visible."
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            if (requestCode == REQUEST_MIC || requestCode == REQUEST_NOTIFICATIONS) startListening()
        } else toast("Permission is required for hands-free listening.")
    }

    @Deprecated("Document picker compatibility")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == PICK_KEYWORD && resultCode == RESULT_OK) {
            val uri: Uri = data?.data ?: return
            contentResolver.openInputStream(uri)?.use { input ->
                File(filesDir, "kiemaen.ppn").outputStream().use { output -> input.copyTo(output) }
            }
            keywordFile = File(filesDir, "kiemaen.ppn")
            toast("Custom wake-word imported. Restart listening to use it.")
            buildScreen()
        }
    }

    private fun toast(message: String) = Toast.makeText(this, message, Toast.LENGTH_LONG).show()

    companion object {
        private const val PICK_KEYWORD = 20
        private const val REQUEST_MIC = 21
        private const val REQUEST_NOTIFICATIONS = 22
    }
}
