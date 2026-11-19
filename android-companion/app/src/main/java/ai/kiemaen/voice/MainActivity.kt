package ai.kiemaen.voice

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.webkit.CookieManager
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : Activity() {
    private lateinit var status: TextView
    private lateinit var accountStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        buildScreen()
    }

    override fun onResume() {
        super.onResume()
        refreshAccountStatus()
    }

    private fun buildScreen() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 40, 32, 32)
        }
        root.addView(TextView(this).apply {
            text = "KIEMAEN VOICE"
            textSize = 26f
        })
        root.addView(TextView(this).apply {
            text = "Say “Hey Kiemaen” to wake your assistant."
            textSize = 15f
            setPadding(0, 12, 0, 24)
        })

        accountStatus = TextView(this).apply {
            textSize = 14f
            setPadding(0, 8, 0, 8)
        }
        root.addView(accountStatus)
        root.addView(Button(this).apply {
            text = "CONNECT KIEMAEN ACCOUNT"
            setOnClickListener {
                startActivity(Intent(this@MainActivity, AccountActivity::class.java))
            }
        })

        status = TextView(this).apply {
            text = "Not listening."
            textSize = 14f
            setPadding(0, 24, 0, 20)
        }
        root.addView(status)
        root.addView(Button(this).apply {
            text = "START HEY KIEMAEN LISTENING"
            setOnClickListener { startListening() }
        })
        root.addView(Button(this).apply {
            text = "STOP LISTENING"
            setOnClickListener {
                stopService(Intent(this@MainActivity, WakeWordService::class.java))
                status.text = "Listening stopped."
            }
        })
        root.addView(TextView(this).apply {
            text = "Wake-word detection runs locally on this phone. After activation, Android speech recognition transcribes your request. Only the recognised text is sent to Kiemaen over HTTPS. Connect your account above to use your signed-in Kiemaen session; otherwise requests use guest access."
            textSize = 12f
            setPadding(0, 28, 0, 0)
        })

        setContentView(root)
        refreshAccountStatus()
    }

    private fun refreshAccountStatus() {
        if (!::accountStatus.isInitialized) return
        val cookie = CookieManager.getInstance().getCookie(AccountActivity.BASE_URL).orEmpty()
        val linked = cookie.split(";").any { it.trim().startsWith("session_token=") }
        accountStatus.text = if (linked) {
            "Kiemaen account: linked (session may expire)"
        } else {
            "Kiemaen account: not linked — guest access is available"
        }
    }

    private fun startListening() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.RECORD_AUDIO), REQUEST_MIC)
            return
        }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQUEST_NOTIFICATIONS)
            return
        }

        ContextCompat.startForegroundService(
            this,
            Intent(this, WakeWordService::class.java).setAction(WakeWordService.ACTION_START)
        )
        status.text = "Starting local wake-word engine. Keep the Kiemaen Voice notification visible."
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            if (requestCode == REQUEST_MIC || requestCode == REQUEST_NOTIFICATIONS) startListening()
        } else {
            Toast.makeText(this, "Microphone and notification permissions are needed for hands-free listening.", Toast.LENGTH_LONG).show()
        }
    }

    companion object {
        private const val REQUEST_MIC = 21
        private const val REQUEST_NOTIFICATIONS = 22
    }
}
